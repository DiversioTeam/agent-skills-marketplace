#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block creating or rewriting a DiversioTeam PR body without an agent session link.

Reads the hook payload on stdin. Exit 0 allows the call; exit 2 blocks it and shows stderr to the model. local-ci's
agent-session check (required `local/verify`) is the real gate; this gives the agent the feedback before the PR exists.

Only PR body writes are checked: `gh pr create`, `gh pr edit` with a body flag, `gh api` POST to `repos/O/R/pulls`
and `gh api` PATCH to `repos/O/R/pulls/N` with a body. Review comments, replies, reviews and issue comments are not
PR bodies. A command line is split into its simple commands; `NAME=value` assignments and `cd` earlier in the same
command line are applied, so `F=/tmp/body.md; gh pr create --body-file "$F"` reads /tmp/body.md. A body the hook
cannot read (an unknown variable, a missing file, stdin) is blocked with that reason rather than allowed.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

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

SEPARATORS = frozenset(";&|()\n")
VARIABLE = re.compile(r"\$(?:\{(?P<braced>[A-Za-z_]\w*)\}|(?P<plain>[A-Za-z_]\w*))")
ASSIGNMENT = re.compile(r"^(?P<name>[A-Za-z_]\w*)=(?P<value>.*)$", re.DOTALL)
HEREDOC = re.compile(r"<<(?P<dash>-?)[ \t]*(?P<quote>['\"]?)(?P<word>[A-Za-z_][\w.-]*)(?P=quote)")
# `repos/{owner}/{repo}/pulls` creates a PR; `repos/{owner}/{repo}/pulls/N` updates one. Anything longer
# (`pulls/N/comments`, `pulls/N/reviews`, `pulls/comments/N/replies`, `pulls/N/requested_reviewers`) is not a PR body.
PR_ENDPOINT = re.compile(r"^/?repos/[^/\s]+/[^/\s]+/pulls(?:/(?P<number>\d+))?/?(?:\?.*)?$")
API_VALUE_FLAGS = frozenset({"-X", "--method", "-f", "-F", "--field", "--raw-field", "-H", "--header", "-q", "--jq",
                             "-t", "--template", "--input", "-p", "--preview", "--hostname", "--cache"})
FIELD_FLAGS = frozenset({"-f", "-F", "--field", "--raw-field"})


class Unreadable(Exception):
    """A PR body the hook cannot read; the message says which and why."""


def _strip_heredocs(command: str) -> str:
    """The command line without top-level heredoc bodies and `#` comments, which are not arguments and often hold
    unbalanced quotes (`it's`). A heredoc inside a quoted argument (`--body "$(cat <<'EOF' ...)"`) is kept: it is the
    argument's text."""
    out: list[str] = []
    pending: list[tuple[bool, str]] = []
    quote = None
    index, size = 0, len(command)
    while index < size:
        char = command[index]
        if quote == "'":
            quote = None if char == "'" else quote
            out.append(char)
            index += 1
        elif char == "\\" and index + 1 < size:
            out.append(command[index:index + 2])
            index += 2
        elif quote == '"':
            quote = None if char == '"' else quote
            out.append(char)
            index += 1
        elif char in "'\"":
            quote = char
            out.append(char)
            index += 1
        elif char == "#" and (index == 0 or command[index - 1] in " \t\n;&|("):
            end = command.find("\n", index)
            index = size if end == -1 else end
        elif command.startswith("<<", index) and not command.startswith("<<<", index) and HEREDOC.match(command, index):
            match = HEREDOC.match(command, index)
            pending.append((bool(match.group("dash")), match.group("word")))
            out.append(match.group(0))
            index = match.end()
        elif char == "\n" and pending:
            out.append(char)
            index += 1
            for dash, word in pending:
                while index < size:
                    end = command.find("\n", index)
                    line = command[index:size if end == -1 else end]
                    index = size if end == -1 else end + 1
                    if (line.lstrip("\t") if dash else line) == word:
                        break
            pending = []
        else:
            out.append(char)
            index += 1
    return "".join(out)


def _simple_commands(command: str) -> list[list[str]] | None:
    """The command line's simple commands as word lists, split at `;`, `&&`, `||`, `|`, parentheses and newlines.
    None when the line cannot be split (unbalanced quotes)."""
    text = _strip_heredocs(command.replace("\\\n", " "))
    lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    commands: list[list[str]] = [[]]
    for token in tokens:
        if token and set(token) <= SEPARATORS:
            commands.append([])
        else:
            commands[-1].append(token)
    return [words for words in commands if words]


def _expand(word: str, variables: dict[str, str]) -> str:
    """`$NAME` and `${NAME}` replaced from assignments seen so far; unknown names stay as written."""
    def value(match: re.Match[str]) -> str:
        name = match.group("braced") or match.group("plain")
        return variables.get(name, match.group(0))
    return VARIABLE.sub(value, word)


def _nested(words: list[str]) -> list[str]:
    """Command lines nested in these words: `$(...)` command substitutions and `bash -c '...'` payloads."""
    nested = [word[word.index("$(") + 2:].rstrip().removesuffix(")") for word in words if "$(" in word]
    if len(words) >= 3 and Path(words[0]).name in ("sh", "bash", "zsh") and words[1] in ("-c", "-lc"):
        nested.append(words[2])
    return nested


def _read(path: str, cwd: Path, what: str) -> str:
    if path == "-" or path.startswith("/dev/"):
        raise Unreadable(UNREADABLE.format(what=what, why="it comes from standard input"))
    if "$" in path or "`" in path:
        raise Unreadable(UNREADABLE.format(what=what, why=f"`{path}` uses a variable not set earlier in the command"))
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
    match = PR_ENDPOINT.match(endpoint or "")
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


def decide(command: str, cwd: Path, argv: list[str] | None = None) -> str | None:
    """The reason to block, or None to allow. `argv` is the command as an argument list, when the tool sent one."""
    # A transcript link anywhere in the command (a heredoc writing the body file, say) is enough.
    if LINK.search(command):
        return None
    commands = [argv] if argv is not None else _simple_commands(command)
    if commands is None:
        return _fallback(command, cwd)
    variables: dict[str, str] = {}
    for words in commands:
        if argv is None:
            words = [_expand(word, variables) for word in words]
            # A command substitution (`URL="$(gh pr create ...)"`) or `sh -c` holds a command line of its own.
            for inner in _nested(words):
                reason = decide(inner, cwd)
                if reason:
                    return reason
            assignments = [ASSIGNMENT.match(word) for word in words]
            if words[0] == "export" or all(assignments):
                # `NAME=value` alone sets a shell variable; a value still holding `$` (command substitution, an
                # unknown variable) is unknown, so later uses of it stay unresolved.
                for match in (ASSIGNMENT.match(word) for word in words):
                    if match:
                        variables.pop(match.group("name"), None)
                        if "$" not in match.group("value") and "`" not in match.group("value"):
                            variables[match.group("name")] = match.group("value")
                continue
            while words and ASSIGNMENT.match(words[0]):
                words = words[1:]  # `NAME=value gh ...` sets the variable for gh only.
            if words and words[0] == "cd" and len(words) == 2 and "$" not in words[1]:
                cwd = cwd / Path(words[1]).expanduser()
                continue
        # `gh` may follow a wrapper (`env`, `timeout 60`, `command`), so look for it among the words. A word that only
        # mentions gh (a `python3 -c` script, an echo'd string) is one word, not `gh` followed by `pr`.
        start = next((index for index, word in enumerate(words[:-1]) if Path(word).name == "gh" and words[index + 1] in ("pr", "api")), None)
        if start is None:
            continue
        words = words[start:]
        try:
            if words[1] == "pr" and len(words) > 2 and words[2] in ("create", "edit"):
                bodies = _pr_bodies(words[2], words[3:], cwd)
            elif words[1] == "api":
                bodies = _api_bodies(words[2:], cwd)
            else:
                continue
        except Unreadable as error:
            if _is_diversio(command + " " + " ".join(words), cwd):
                return str(error) + MESSAGE.format(script=Path(__file__).resolve().parent / "agent_session.py")
            continue
        if bodies is None or any(has_transcript(text) for text in bodies):
            continue
        if _is_diversio(command + " " + " ".join(words), cwd):
            return MESSAGE.format(script=Path(__file__).resolve().parent / "agent_session.py")
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
