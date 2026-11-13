#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block creating or rewriting a DiversioTeam PR body without an agent session link.

Reads the hook payload on stdin. Exit 0 allows the call; exit 2 blocks it and shows stderr to the model. local-ci's
agent-session check (required `local/verify`) is the real gate; this gives the agent the feedback before the PR exists.

Only PR body writes are checked: `gh pr create`, `gh pr edit` with a body flag, `gh api` POST to `repos/O/R/pulls`
and `gh api` PATCH to `repos/O/R/pulls/N` with a body. Review comments, replies, reviews and issue comments are not
PR bodies. The command line is split the way Bash splits it: quoting is kept, so `$NAME` is expanded only where Bash
would expand it (unquoted or in double quotes), and a quoted `;` is an argument, not an operator. `NAME=value`
assignments and `cd` earlier in the same command line are applied, so `F=/tmp/body.md; gh pr create --body-file "$F"`
reads /tmp/body.md. Command substitutions (`$(...)`, backticks, including those in unquoted heredocs) are checked as
command lines of their own. A body the hook cannot read (an unknown variable, a missing file, stdin) is blocked with
that reason rather than allowed, and so is a PR command in a line the hook cannot split.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pr_body import LINK, has_transcript  # noqa: E402

# Fallback detection when the command line cannot be split (unbalanced quotes): the old, coarse rule.
PR_COMMAND = re.compile(r"\bgh\s+pr\s+(?P<verb>create|edit)\b")
API_COMMAND = re.compile(r"\bgh\s+api\b[^\n]*\brepos/[^/\s]+/[^/\s]+/pulls\b")
MESSAGE = (
    "This PR needs its agent session transcript. Run the agent-session skill "
    "(`agent-session share`, or `python3 {script} share`; on a first publish review the preview with the developer, then add `--yes`). "
    "It links the newest transcript in the body's "
    "'## Agent sessions' section. For a PR no agent worked on, add a line 'No agent session: <reason>'."
)
UNREADABLE = (
    "The agent-session hook could not read the PR body {what} ({why}), so it cannot see the agent session line. "
    "Write the body to a file in an earlier command, then pass that file's literal path (or a variable assigned earlier "
    "in the same command line). "
)
UNPARSED = "The agent-session hook could not split this command line into words, so it could not read the PR body. "

# Marks text Bash would only know at run time (an unset variable, a command substitution's output).
UNKNOWN = "\x00"
OPERATOR_CHARS = ";&|()<>\n"
SEPARATOR_CHARS = frozenset(";&|()\n")
EXPANSION = re.compile(r"\$(?:\{(?P<braced>[^}]*)\}|(?P<plain>[A-Za-z_]\w*)|(?P<special>[0-9@*#?$!-])|(?P<substitution>\())|`")
NAME = re.compile(r"^(?P<name>[A-Za-z_]\w*)=")
# `repos/{owner}/{repo}/pulls` creates a PR; `repos/{owner}/{repo}/pulls/N` updates one. Anything longer
# (`pulls/N/comments`, `pulls/N/reviews`, `pulls/comments/N/replies`, `pulls/N/requested_reviewers`) is not a PR body.
PR_ENDPOINT = re.compile(r"^/?repos/[^/\s]+/[^/\s]+/pulls(?:/(?P<number>\d+))?/?(?:\?.*)?$")
API_VALUE_FLAGS = frozenset({"-X", "--method", "-f", "-F", "--field", "--raw-field", "-H", "--header", "-q", "--jq",
                             "-t", "--template", "--input", "-p", "--preview", "--hostname", "--cache"})
FIELD_FLAGS = frozenset({"-f", "-F", "--field", "--raw-field"})

# A word is a list of (kind, text) parts: "plain" (unquoted), "double" (in double quotes), "literal" (single-quoted
# or backslash-escaped). Bash expands `$` only in plain and double parts.


class Unreadable(Exception):
    """A PR body the hook cannot read; the message says which and why."""


class Command:
    """One simple command: its words, and the bodies of unquoted heredocs fed to it (which Bash expands)."""

    def __init__(self) -> None:
        self.words: list[list[tuple[str, str]]] = []
        self.expanded_heredocs: list[str] = []


def _substitution_end(text: str, start: int) -> int:
    """Given `text[start] == "("` after a `$`, the index just past the matching `)`. Raises ValueError if unclosed."""
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char in "'\"":
            end = text.find(char, index + 1)
            if end == -1:
                raise ValueError("unclosed quote in a command substitution")
            index = end + 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    raise ValueError("unclosed command substitution")


def _substitutions(text: str) -> list[str]:
    """The command lines inside `$(...)` and backticks in text Bash expands."""
    found = []
    index = 0
    while index < len(text):
        if text.startswith("$(", index):
            try:
                end = _substitution_end(text, index + 1)
                found.append(text[index + 2:end - 1])
            except ValueError:
                # Quotes inside a substitution in double quotes (`"$(cat <<'EOF' ... it's ... )"`) defeat the scan;
                # take the rest of the text, as a whole command line.
                end = len(text)
                found.append(text[index + 2:].rstrip().removesuffix(")"))
            index = end
        elif text[index] == "`":
            end = text.find("`", index + 1)
            if end == -1:
                raise ValueError("unclosed backtick")
            found.append(text[index + 1:end])
            index = end + 1
        else:
            index += 1
    return found


def _lex(text: str) -> list[Command]:
    """The command line as Bash splits it into simple commands and words. Raises ValueError when it cannot."""
    commands = [Command()]
    parts: list[tuple[str, str]] = []
    started = False
    redirect_pending = False  # the next word is a redirection target (or heredoc delimiter), not an argument
    heredoc_next = None  # "<<" or "<<-" when the next word is a heredoc delimiter
    pending: list[tuple[bool, str, bool]] = []  # (strip tabs, delimiter, expanded) heredocs read at the next newline

    def add(kind: str, piece: str) -> None:
        nonlocal started
        started = True
        if parts and parts[-1][0] == kind:
            parts[-1] = (kind, parts[-1][1] + piece)
        else:
            parts.append((kind, piece))

    def flush() -> None:
        nonlocal parts, started, redirect_pending, heredoc_next
        if not started:
            return
        if heredoc_next:
            delimiter = "".join(piece for _, piece in parts)
            pending.append((heredoc_next == "<<-", delimiter, all(kind == "plain" for kind, _ in parts)))
            heredoc_next = None
        elif not redirect_pending:
            commands[-1].words.append(parts)
        redirect_pending = False
        parts, started = [], False

    index, size = 0, len(text)
    while index < size:
        char = text[index]
        if char in " \t\r":
            flush()
            index += 1
        elif char == "\\":
            if text.startswith("\\\n", index):
                index += 2
            else:
                add("literal", text[index + 1:index + 2] or "\\")
                index += 2
        elif char == "'":
            end = text.find("'", index + 1)
            if end == -1:
                raise ValueError("unclosed single quote")
            add("literal", text[index + 1:end])
            started = True
            index = end + 1
        elif char == '"':
            index += 1
            started = True
            while True:
                if index >= size:
                    raise ValueError("unclosed double quote")
                char = text[index]
                if char == '"':
                    index += 1
                    break
                if char == "\\" and index + 1 < size:
                    escaped = text[index + 1]
                    if escaped in '"\\$`':
                        add("literal", escaped)
                    elif escaped != "\n":
                        add("double", "\\" + escaped)
                    index += 2
                else:
                    add("double", char)
                    index += 1
        elif text.startswith("$(", index):
            end = _substitution_end(text, index + 1)
            add("plain", text[index:end])
            index = end
        elif char == "`":
            end = text.find("`", index + 1)
            if end == -1:
                raise ValueError("unclosed backtick")
            add("plain", text[index:end + 1])
            index = end + 1
        elif char == "#" and not started:
            end = text.find("\n", index)
            index = size if end == -1 else end
        elif char in OPERATOR_CHARS:
            flush()
            if char == "\n":
                operator = "\n"
            elif char in "()":
                operator = char
            else:
                end = index
                while end < size and text[end] in ";&|<>":
                    end += 1
                operator = text[index:end]
                if operator == "<<" and text.startswith("-", end):
                    operator = "<<-"
            index += len(operator)
            if set(operator) <= SEPARATOR_CHARS:
                commands.append(Command())
            elif operator in ("<<", "<<-"):
                heredoc_next = operator
            else:
                redirect_pending = True  # `> file`, `2>&1`, `< in`, `<<< text`: the next word is not an argument
            if operator == "\n" and pending:
                for strip_tabs, delimiter, expanded in pending:
                    lines = []
                    while index < size:
                        end = text.find("\n", index)
                        line = text[index:size if end == -1 else end]
                        index = size if end == -1 else end + 1
                        if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                            break
                        lines.append(line)
                    if expanded:
                        commands[-2].expanded_heredocs.append("\n".join(lines))
                pending = []
        else:
            add("plain", char)
            index += 1
    flush()
    return [command for command in commands if command.words or command.expanded_heredocs]


def _value(parts: list[tuple[str, str]], variables: dict[str, str]) -> str:
    """A word's value after Bash's expansion: known variables replaced; unknown ones and command substitutions
    marked UNKNOWN. Literal parts stay as written."""
    def expand(match: re.Match[str]) -> str:
        name = match.group("braced") if match.group("braced") is not None else match.group("plain")
        if name is not None and name in variables:
            return variables[name]
        return UNKNOWN + match.group(0)
    return "".join(piece if kind == "literal" else EXPANSION.sub(expand, piece) for kind, piece in parts)


def _shown(text: str) -> str:
    return text.replace(UNKNOWN, "")


def _read(path: str, cwd: Path, what: str) -> str:
    if path == "-" or path.startswith("/dev/"):
        raise Unreadable(UNREADABLE.format(what=what, why="it comes from standard input"))
    if UNKNOWN in path:
        raise Unreadable(UNREADABLE.format(what=what, why=f"`{_shown(path)}` uses a variable or command output not set earlier in the command"))
    try:
        return (cwd / Path(path).expanduser()).read_text(encoding="utf-8")
    except OSError as error:
        raise Unreadable(UNREADABLE.format(what=what, why=f"`{path}`: {error.strerror or error}")) from None


def _pr_bodies(verb: str, args: list[str], cwd: Path) -> list[str] | None:
    """The bodies a `gh pr create|edit` passes, or None when it writes no body (an edit without a body flag)."""
    texts: list[str] = []
    files: list[str] = []
    for index, token in enumerate(args):
        following = args[index + 1] if index + 1 < len(args) else None
        if token in ("--body", "-b") and following is not None:
            texts.append(following)
        elif token.startswith("--body="):
            texts.append(token.split("=", 1)[1])
        elif token in ("--body-file", "-F") and following is not None:
            files.append(following)
        elif token.startswith("--body-file="):
            files.append(token.split("=", 1)[1])
    if verb == "edit" and not texts and not files:
        return None
    if any(has_transcript(text) for text in texts):
        return texts
    # Read every file before deciding, so an unreadable one is reported only when nothing else carries the line.
    problem = None
    for file in files:
        try:
            texts.append(_read(file, cwd, "file"))
        except Unreadable as error:
            problem = problem or error
    if problem and not any(has_transcript(text) for text in texts):
        raise problem
    return texts


def _endpoint_path(endpoint: str) -> str:
    """`gh api` takes a path or a full URL; a URL's path (without a GitHub Enterprise `/api/v3` prefix) is the
    endpoint. The owner and repository stay in the path, so the DiversioTeam check still sees them."""
    if not re.match(r"^https?://", endpoint, re.IGNORECASE):
        return endpoint
    url = urlsplit(endpoint)
    path = url.path[len("/api/v3"):] if url.path.startswith("/api/v3/") else url.path
    return path + (f"?{url.query}" if url.query else "")


def _api_bodies(args: list[str], cwd: Path) -> list[str] | None:
    """The body a `gh api` call writes to a PR (create or update), or None when it does not write a PR body."""
    method = None
    endpoint = None
    fields: dict[str, str] = {}
    raw_fields: set[str] = set()
    input_file = None
    index = 0
    while index < len(args):
        token = args[index]
        flag, _, inline = token.partition("=") if token.startswith("--") else (token, "", "")
        if flag in API_VALUE_FLAGS:
            if inline:
                value = inline
            elif index + 1 < len(args):
                value = args[index + 1]
                index += 1
            else:
                break
            if flag in ("-X", "--method"):
                method = value.upper()
            elif flag in FIELD_FLAGS and "=" in value:
                key, field_value = value.split("=", 1)
                fields[key] = field_value
                if flag in ("-f", "--raw-field"):
                    raw_fields.add(key)
                else:
                    raw_fields.discard(key)
            elif flag == "--input":
                input_file = value
        elif token.startswith("-X") and len(token) > 2:
            method = token[2:].upper()
        elif not token.startswith("-") and endpoint is None:
            endpoint = token
        index += 1
    match = PR_ENDPOINT.match(_endpoint_path(endpoint or ""))
    if not match:
        return None
    method = method or ("POST" if fields or input_file else "GET")
    creates = match.group("number") is None
    if creates and method != "POST" or not creates and method not in ("PATCH", "POST", "PUT"):
        return None
    if input_file is not None:
        try:
            data = json.loads(_read(input_file, cwd, "input file"))
        except ValueError:
            raise Unreadable(UNREADABLE.format(what="input file", why=f"`{input_file}` is not JSON")) from None
        if isinstance(data, dict) and isinstance(data.get("body"), str):
            fields["body"] = data["body"]
            raw_fields.add("body")
    if "body" not in fields:
        # Creating a PR without a body leaves it empty; updating one without a body leaves the body alone.
        return [] if creates else None
    body = fields["body"]
    if "body" not in raw_fields and body.startswith("@"):
        body = _read(body[1:], cwd, "file")
    return [body]


def _is_diversio(text: str, cwd: Path) -> bool:
    if "diversioteam/" in text.lower():
        return True
    completed = subprocess.run(["git", "-C", str(cwd), "remote", "get-url", "origin"], capture_output=True, text=True, check=False, timeout=10)
    return "diversioteam/" in completed.stdout.lower()


def _fallback(command: str, cwd: Path) -> str | None:
    """A command line that cannot be split: block anything that looks like a PR body write, as before."""
    if not PR_COMMAND.search(command) and not API_COMMAND.search(command):
        return None
    if not _is_diversio(command, cwd):
        return None
    return UNPARSED + MESSAGE.format(script=Path(__file__).resolve().parent / "agent_session.py")


def _check(words: list[str], command: str, cwd: Path) -> str | None:
    """The reason to block one simple command's expanded words, or None."""
    # `gh` may follow a wrapper (`env`, `timeout 60`, `command`), so look for it among the words. A word that only
    # mentions gh (a `python3 -c` script, an echo'd string) is one word, not `gh` followed by `pr`.
    start = next((index for index, word in enumerate(words[:-1]) if Path(word).name == "gh" and words[index + 1] in ("pr", "api")), None)
    if start is None:
        return None
    words = words[start:]
    try:
        if words[1] == "pr" and len(words) > 2 and words[2] in ("create", "edit"):
            bodies = _pr_bodies(words[2], words[3:], cwd)
        elif words[1] == "api":
            bodies = _api_bodies(words[2:], cwd)
        else:
            return None
    except Unreadable as error:
        if _is_diversio(command + " " + " ".join(words), cwd):
            return str(error) + MESSAGE.format(script=Path(__file__).resolve().parent / "agent_session.py")
        return None
    if bodies is None or any(has_transcript(text) for text in bodies):
        return None
    if _is_diversio(command + " " + " ".join(words), cwd):
        return MESSAGE.format(script=Path(__file__).resolve().parent / "agent_session.py")
    return None


def decide(command: str, cwd: Path, argv: list[str] | None = None) -> str | None:
    """The reason to block, or None to allow. `argv` is the command as an argument list, when the tool sent one."""
    # A transcript link anywhere in the command (a heredoc writing the body file, say) is enough.
    if LINK.search(command):
        return None
    if argv is not None:
        return _check(argv, command, cwd)
    try:
        commands = _lex(command)
        nested = [[inner for kind, piece in parts if kind != "literal" for inner in _substitutions(piece)]
                  for simple in commands for parts in simple.words]
        nested += [_substitutions(body) for simple in commands for body in simple.expanded_heredocs]
    except ValueError:
        return _fallback(command, cwd)
    # Command substitutions (`URL="$(gh pr create ...)"`, `$(...)` in an unquoted heredoc) run as command lines.
    for inner in (inner for group in nested for inner in group):
        reason = decide(inner, cwd)
        if reason:
            return reason
    variables: dict[str, str] = {}
    for simple in commands:
        words = [_value(parts, variables) for parts in simple.words]
        if not words:
            continue
        names = [NAME.match(parts[0][1]) if parts and parts[0][0] == "plain" else None for parts in simple.words]
        if words[0] == "export" or all(names):
            # `NAME=value` alone sets a shell variable for the rest of the line.
            for word, name in zip(words, names):
                if name:
                    variables[name.group("name")] = word.split("=", 1)[1]
            continue
        while names and names[0]:
            words, names = words[1:], names[1:]  # `NAME=value gh ...` sets the variable for gh only.
        if not words:
            continue
        if words[0] == "cd" and len(words) == 2 and UNKNOWN not in words[1]:
            cwd = cwd / Path(words[1]).expanduser()
            continue
        if len(words) >= 3 and Path(words[0]).name in ("sh", "bash", "zsh") and words[1] in ("-c", "-lc"):
            reason = decide(words[2], cwd)
            if reason:
                return reason
            continue
        reason = _check(words, command, cwd)
        if reason:
            return reason
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input") or {}
    # Claude Code's Bash sends `command`; Codex's exec_command sends `cmd`, its shell tool an argv list.
    command = (tool_input.get("command") or tool_input.get("cmd")) if isinstance(tool_input, dict) else None
    argv = None
    if isinstance(command, list):
        argv = [str(part) for part in command]
        # A shell's -c payload is itself a command line; anything else keeps its argument boundaries.
        if len(argv) >= 3 and Path(argv[0]).name in ("sh", "bash", "zsh") and argv[1] in ("-c", "-lc"):
            command, argv = argv[2], None
        else:
            command = shlex.join(argv)
    if not isinstance(command, str):
        return 0
    reason = decide(command, Path(payload.get("cwd") or ".").expanduser(), argv)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
