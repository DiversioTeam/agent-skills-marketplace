#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block creating or rewriting a DiversioTeam PR body without an agent session link.

Reads the hook payload on stdin. Exit 0 allows the call; exit 2 blocks it and shows stderr to the model. local-ci's
agent-session check (required `local/verify`) is the real gate; this gives the agent the feedback before the PR exists.

The hook fails closed. Its baseline is the original rule (`_main_rule`): any `gh pr create|edit` or `gh api ...
repos/O/R/pulls` with a body in the command text is checked. It is more precise only for command lines it fully
models (`_modeled`):
- simple commands joined by `;`, `&&`, `||`, `|` or newlines, with redirections to literal targets and heredocs;
- plain `NAME=value` (also after `export`) and `cd`, outside pipelines;
- `gh` first in its simple command, or behind `env`, `timeout`, `command`, `nice`, `nohup` or `time`;
- for `gh api`, a literal method (`-X`/`--method`) and an endpoint the hook can resolve.
Quoting is kept, so `$NAME` expands only where Bash expands it, and quoted heredocs and prose that only mentions
`gh pr create` are not commands. In a modeled line only real PR body writes are checked: `gh pr create`, `gh pr edit`
with a body flag, a `gh api` POST to `repos/O/R/pulls` and a PATCH to `repos/O/R/pulls/N` with a body, so review
comments, replies, reviews and issue comments pass. Variables and `cd` are applied only where they surely ran, and a
body the hook cannot read (an unknown variable, a missing file, stdin) is blocked with that reason.

Anything else (command substitution outside a quoted heredoc or single quotes, `bash -c`, `eval`, `declare`, `unset`,
`read`, `local`, `{ }` groups, subshells, background jobs, an unknown method, anything the lexer is unsure of) falls
back to the original rule, and a block says why so the agent can simplify the command.
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
    "Write the body to a file in an earlier command, then pass that file's literal path (or a variable assigned at the "
    "start of the command line, as in `F=/path/body.md; ...`). "
)
UNMODELED = (
    "The agent-session hook cannot follow this command line exactly ({why}), so it applied its basic rule, which "
    "treats any PR command in the text as a PR body write. To let it read the body, run the gh command on its own: "
    "literal paths or `NAME=value` set at the start of the line, no `$(...)`, `bash -c`, `eval` or `{{ }}`. "
)
BODY_FLAGS = ("--body", "-b", "--body-file", "-F")
WRAPPERS = frozenset({"env", "timeout", "command", "nice", "nohup", "time"})
# Commands that change shell state in ways the hook does not follow, or run text as commands.
UNMODELED_COMMANDS = frozenset({
    "eval", "declare", "typeset", "local", "readonly", "unset", "read", "readarray", "mapfile", "source", ".", "exec",
    "set", "shift", "let", "getopts", "pushd", "popd", "alias", "xargs", "parallel", "trap", "builtin", "coproc",
    "select", "for", "while", "until", "if", "case", "function", "then", "do", "else", "elif", "fi", "done", "esac",
    "[[", "((", "!", "{", "}", "sudo", "doas", "watch", "script",
})
SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh", "fish"})
METHODS = frozenset({"GET", "POST", "PATCH", "PUT", "DELETE", "HEAD"})
# Operators a modeled line may use: list and pipeline separators, redirections and heredocs.
MODELED_OPERATORS = frozenset({";", "\n", "&&", "||", "|", "|&", ">", ">>", ">|", "<", ">&", "&>", "&>>", "<<", "<<-",
                               "<<<"})
STATE_WORD = re.compile(r"^[A-Za-z_]\w*(?:\[[^\]]*\])?\+?=")

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


class Unmodeled(Exception):
    """A command line outside the subset the hook models exactly; the message says what is outside it."""


class Command:
    """One simple command: its words, the bodies of unquoted heredocs fed to it (which Bash expands), the control
    operators before and after it, and how many parentheses (subshells) it sits in."""

    def __init__(self, before: str = "", depth: int = 0) -> None:
        self.words: list[list[tuple[str, str]]] = []
        self.redirects: list[list[tuple[str, str]]] = []  # redirection targets, which Bash expands too
        self.expanded_heredocs: list[str] = []
        self.before = before
        self.after = ""
        self.depth = depth


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


def _lex(text: str) -> tuple[list[Command], set[str]]:
    """The command line as Bash splits it into simple commands and words, and the operators it uses. Raises
    ValueError when it cannot."""
    commands = [Command()]
    operators: set[str] = set()
    depth = 0
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
        elif redirect_pending:
            commands[-1].redirects.append(parts)
        else:
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
            operators.add(operator)
            if set(operator) <= SEPARATOR_CHARS:
                depth += {"(": 1, ")": -1}.get(operator, 0)
                if commands[-1].words or commands[-1].expanded_heredocs:
                    commands[-1].after = operator
                # An empty command between operators (`a; (b)`) passes on the earlier operator.
                before = operator if commands[-1].words or operator not in "()" else commands[-1].before
                commands.append(Command(before, depth))
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
    if heredoc_next or redirect_pending:
        raise ValueError("a redirection without a target")
    return [command for command in commands if command.words or command.redirects or command.expanded_heredocs], operators


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
        raise Unreadable(UNREADABLE.format(what=what, why=f"`{_shown(path)}` uses a variable or command output not set earlier in the command, or set only "
                                                       "where it may not run: after `cmd &&` or `||`, in a pipeline, subshell, `{ }` group or the background"))
    if UNKNOWN in str(cwd / Path(path).expanduser()):
        raise Unreadable(UNREADABLE.format(what=what, why=f"`{path}` is relative to a directory the hook cannot follow"))
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
    if method is not None and method not in METHODS:
        raise Unmodeled(f"the gh api method `{_shown(method)}` is not a literal HTTP method")
    if endpoint is not None and UNKNOWN in endpoint:
        raise Unmodeled(f"the gh api endpoint `{_shown(endpoint)}` uses a value the hook cannot resolve")
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
    if "diversioteam/" in text.lower() or UNKNOWN in str(cwd):
        return True  # a directory the hook cannot follow might be a DiversioTeam checkout
    completed = subprocess.run(["git", "-C", str(cwd), "remote", "get-url", "origin"], capture_output=True, text=True, check=False, timeout=10)
    return "diversioteam/" in completed.stdout.lower()


def _wrapper_prefix(words: list[str]) -> bool:
    """Whether these words before `gh` are only supported wrappers with their options: `env [-i] [NAME=value]...`,
    `timeout [-s SIG] 60`, `command`, `nice [-n 10]`, `nohup`, `time`."""
    index = 0
    while index < len(words):
        name = Path(words[index]).name
        if name not in WRAPPERS or UNKNOWN in words[index]:
            return False
        index += 1
        while index < len(words) and Path(words[index]).name not in WRAPPERS:
            word = words[index]
            if UNKNOWN in word:
                return False
            if name == "env" and (NAME.match(word) or word in ("-i", "-")):
                index += 1
            elif name == "timeout" and word in ("-s", "--signal", "-k", "--kill-after") and index + 1 < len(words):
                index += 2
            elif name == "timeout" and (re.fullmatch(r"\d+(?:\.\d+)?[smhd]?", word) or word in ("--foreground", "--preserve-status")):
                index += 1
            elif name == "nice" and word == "-n" and index + 1 < len(words):
                index += 2
            elif name in ("command", "time") and word in ("-p",):
                index += 1
            else:
                return False
    return True


def _check(words: list[str], command: str, cwd: Path) -> str | None:
    """The reason to block one simple command's expanded words, or None. Raises Unmodeled when `gh pr|api` appears
    somewhere other than first or behind a supported wrapper."""
    if Path(words[0]).name in UNMODELED_COMMANDS or (words[0] == "printf" and "-v" in words):
        raise Unmodeled(f"it uses `{_shown(words[0])}`")
    if any(Path(word).name in SHELLS for word in words):
        raise Unmodeled("it runs a shell (`bash -c` and the like)")
    # A word that only mentions gh (a `python3 -c` script, an echo'd string) is one word, not `gh` followed by `pr`.
    start = next((index for index, word in enumerate(words[:-1]) if Path(word).name == "gh" and words[index + 1] in ("pr", "api")), None)
    if start is None:
        return None
    if not _wrapper_prefix(words[:start]):
        raise Unmodeled(f"gh runs behind `{_shown(' '.join(words[:start]))}`")
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


def _main_bodies(command: str, cwd: Path, argv: list[str] | None = None) -> list[str]:
    """The original rule's body texts: inline `--body`/`-b` values, `body=` API fields and `--body-file` contents."""
    if argv is not None:
        tokens = argv
    else:
        try:
            tokens = shlex.split(command, posix=True)
        except ValueError:
            return []
    texts = []
    for index, token in enumerate(tokens):
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        if token in ("--body", "-b") and following is not None:
            texts.append(following)
        elif token.startswith("--body="):
            texts.append(token.split("=", 1)[1])
        elif token.startswith("body=") and index and tokens[index - 1] in ("-f", "-F", "--field", "--raw-field"):
            texts.append(token.split("=", 1)[1])
        file = following if token in ("--body-file", "-F") and following and not following.startswith("body=") else (
            token.split("=", 1)[1] if token.startswith("--body-file=") else None)
        if file and file != "-":
            try:
                texts.append((cwd / file).expanduser().read_text(encoding="utf-8"))
            except OSError:
                pass
    return texts


def _main_rule(command: str, cwd: Path, argv: list[str] | None = None) -> str | None:
    """The original (0.4.2) rule, unchanged: the baseline for any command line the hook does not model exactly."""
    match = PR_COMMAND.search(command)
    api = API_COMMAND.search(command)
    if not match and not api:
        return None
    if api and not re.search(r"(?:-X|--method)\s*(?:POST|PATCH)|-f\s+body=|-F\s+body=|--field\s+body=|--raw-field\s+body=", command):
        return None
    if match and match.group("verb") == "edit" and not any(re.search(rf"(?:^|\s){re.escape(flag)}(?:[\s=]|$)", command) for flag in BODY_FLAGS):
        return None
    if api and not re.search(r"\bbody\b", command):
        return None
    if not _is_diversio(command, cwd):
        return None
    # A heredoc body (`--body "$(cat <<'EOF' ...)"`) arrives as one token holding the text, so its lines are checked too.
    if LINK.search(command) or any(has_transcript(text) for text in _main_bodies(command, cwd, argv)):
        return None
    return MESSAGE.format(script=Path(__file__).resolve().parent / "agent_session.py")


def _substituted(parts: list[tuple[str, str]]) -> bool:
    """Whether Bash would run a command substitution while expanding this word."""
    return any(kind != "literal" and ("$(" in piece or "`" in piece) for kind, piece in parts)


def _modeled(command: str, cwd: Path) -> str | None:
    """The decision for a command line the hook models exactly. Raises Unmodeled when the line is outside that subset
    (see the module docstring)."""
    try:
        commands, operators = _lex(command)
    except ValueError as error:
        raise Unmodeled(f"it could not split the line: {error}") from None
    unsupported = sorted(operators - MODELED_OPERATORS)
    if unsupported:
        raise Unmodeled("it uses " + ", ".join(f"`{operator}`" for operator in unsupported).replace("\n", "a newline"))
    for simple in commands:
        if any(_substituted(parts) for parts in simple.words + simple.redirects):
            raise Unmodeled("it uses a command substitution, `$(...)` or backticks")
        if any("$(" in body or "`" in body for body in simple.expanded_heredocs):
            raise Unmodeled("an unquoted heredoc runs a command substitution")

    # Shell state (variables, the working directory) a later command can rely on. `certain` holds changes that ran
    # whenever a later command runs; `chained` holds changes made after the start of an `a && b && ...` list, which
    # are certain only for the rest of that `&&` chain. A change after `||` becomes UNKNOWN, so reads that depend on
    # it block.
    certain: dict[str, str] = {}
    chained: dict[str, str] = {}
    unknown_cwd = Path(UNKNOWN + "cd")
    certain_cwd, chained_cwd = cwd, None

    def forget_chain() -> None:
        nonlocal chained_cwd, certain_cwd
        for name in chained:
            certain[name] = UNKNOWN + "$" + name
        chained.clear()
        if chained_cwd is not None:
            certain_cwd, chained_cwd = unknown_cwd, None

    for simple in commands:
        if simple.before != "&&":
            forget_chain()
        if not simple.words:
            continue
        starts_list = simple.before in ("", ";", "\n")
        in_pipeline = simple.before in ("|", "|&") or simple.after in ("|", "|&")
        variables = {**certain, **chained}
        cwd = chained_cwd or certain_cwd
        words = [_value(parts, variables) for parts in simple.words]
        names = [NAME.match(parts[0][1]) if parts and parts[0][0] == "plain" else None for parts in simple.words]
        prefix = 0
        while prefix < len(words) and names[prefix]:
            prefix += 1
        # `NAME+=value` or `NAME[i]=value` where an assignment would go.
        if prefix < len(words) and simple.words[prefix] and simple.words[prefix][0][0] == "plain" \
                and STATE_WORD.match(simple.words[prefix][0][1]):
            raise Unmodeled("it uses an assignment form other than `NAME=value`")
        rest = words[prefix:]
        changes: dict[str, str] = {}
        if not rest or rest[0] == "export":
            exported = simple.words[prefix + 1:] if rest else []
            if any(not (parts and parts[0][0] == "plain" and NAME.match(parts[0][1])) for parts in exported):
                raise Unmodeled("`export` is used with something other than `NAME=value`")
            changes = {match.group("name"): word.split("=", 1)[1]
                       for word, match in zip(words, (NAME.match(parts[0][1]) if parts and parts[0][0] == "plain" else None
                                                       for parts in simple.words)) if match}
        elif rest[0] == "cd":
            changes = {"": rest[1] if len(rest) == 2 and rest[1] != "-" else UNKNOWN}
        if changes:
            if in_pipeline:
                raise Unmodeled("it changes a variable or the directory inside a pipeline")
            for name, value in changes.items():
                if name == "":
                    value = unknown_cwd if UNKNOWN in value else cwd / Path(value).expanduser()
                elif simple.before == "||":
                    value = UNKNOWN + "$" + name  # skipped whenever the command before `||` succeeds
                if name == "" and simple.before == "||":
                    value = unknown_cwd
                if starts_list or simple.before == "||":
                    if name == "":
                        certain_cwd = value
                    else:
                        certain[name] = value
                elif name == "":
                    chained_cwd = value
                else:
                    chained[name] = value
            continue
        reason = _check(rest, command, cwd)
        if reason:
            return reason
    return None


def decide(command: str, cwd: Path, argv: list[str] | None = None) -> str | None:
    """The reason to block, or None to allow. `argv` is the command as an argument list, when the tool sent one."""
    # A transcript link anywhere in the command (a heredoc writing the body file, say) is enough.
    if LINK.search(command):
        return None
    try:
        return _check(argv, command, cwd) if argv is not None else _modeled(command, cwd)
    except Unmodeled as error:
        reason = _main_rule(command, cwd, argv)
        return UNMODELED.format(why=str(error)) + reason if reason else None


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
