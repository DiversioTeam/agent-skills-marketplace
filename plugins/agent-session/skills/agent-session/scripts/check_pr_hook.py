#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block creating or rewriting a DiversioTeam PR body without an agent session link.

Reads the hook payload on stdin. Exit 0 allows the call; exit 2 blocks it and shows stderr to the model. local-ci's
agent-session check (required `local/verify`) is the real gate; this gives the agent the feedback before the PR exists.

The hook fails closed. Its baseline is the original rule (`_main_rule`): any `gh pr create|edit` or `gh api ...
repos/O/R/pulls` with a body in the command text is checked. It is more precise only for command lines inside a strict
whitelist (`_modeled`), where every word and command is one of:
- simple commands joined by `;`, `&&`, `||`, `|` or newlines, with redirections and heredocs (a newline right
  after `&&`, `||` or `|` is not modeled);
- an assignment `NAME=<literal>` as a command of its own (no `$`, backtick, glob or brace characters);
- a word that is a literal, or exactly `$NAME`, `${NAME}` or `"$NAME"` with a known value without whitespace
  (and, unquoted, without glob characters);
  unquoted text has no `{ } * ? [ ~ $` or backticks, and nothing is joined to a variable;
- `cd` to a literal absolute path without `..` and without redirections, which holds only for the rest of its `&&`
  chain (a relative body path is resolved against it only there);
- `gh` first, or behind `env`, `timeout`, `command`, `nice`, `nohup` or `time`, with a literal `gh api` method.
There, quoted heredocs and prose that only mentions `gh pr create` are not commands, and only real PR body writes are
checked: `gh pr create`, `gh pr edit` with a body flag, a `gh api` POST to `repos/O/R/pulls` and a PATCH to
`repos/O/R/pulls/N` with a body. Review comments, replies, reviews and issue comments pass, and a body the hook cannot
read (a missing file, stdin) is blocked with that reason. So is a body file another command on the line may rewrite
first (anything before gh but an assignment, `cd`, `true`, `false`, `:`, `echo` or `pwd`; a pipeline peer other than a
read-only filter; gh's own redirection to it), because the file on disk may not be what gh reads. With `--input`, the
input file alone is the API request body.

Anything else falls back to the original rule, and a block says why so the agent can simplify the command.
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
    "a literal path, or `F=/abs/path; ... \"$F\"` with nothing joined to the variable; `cd /abs/dir && ...`; no "
    "`$(...)`, globs, braces, `bash -c`, `eval` or `export`. "
)
BODY_FLAGS = ("--body", "-b", "--body-file", "-F")
WRAPPERS = frozenset({"env", "timeout", "command", "nice", "nohup", "time"})
# Commands that change shell state in ways the hook does not follow, or run text as commands.
UNMODELED_COMMANDS = frozenset({
    "eval", "declare", "typeset", "local", "readonly", "export", "wait", "unset", "read", "readarray", "mapfile", "source", ".", "exec",
    "set", "shift", "let", "getopts", "pushd", "popd", "alias", "xargs", "parallel", "trap", "builtin", "coproc",
    "select", "for", "while", "until", "if", "case", "function", "then", "do", "else", "elif", "fi", "done", "esac",
    "[[", "((", "!", "{", "}", "sudo", "doas", "watch", "script",
})
SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh", "fish"})
METHODS = frozenset({"GET", "POST", "PATCH", "PUT", "DELETE", "HEAD"})
# Operators a modeled line may use: list and pipeline separators, redirections and heredocs.
MODELED_OPERATORS = frozenset({";", "\n", "&&", "||", "|", "|&", ">", ">>", ">|", "<", ">&", "&>", "&>>", "<<", "<<-",
                               "<<<"})

# Marks text Bash would only know at run time (an unset variable, a command substitution's output).
UNKNOWN = "\x00"
OPERATOR_CHARS = ";&|()<>\n"
SEPARATOR_CHARS = frozenset(";&|()\n")
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

    region = 0  # each quoted region (and each run of unquoted text) is its own part, so `"$F""ILE"` stays two parts
    part_region = -1

    def add(kind: str, piece: str) -> None:
        nonlocal started, part_region
        started = True
        if parts and parts[-1][0] == kind and part_region == region:
            parts[-1] = (kind, parts[-1][1] + piece)
        else:
            parts.append((kind, piece))
            part_region = region

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
                region += 1
                add("literal", text[index + 1:index + 2] or "\\")
                region += 1
                index += 2
        elif char == "'":
            end = text.find("'", index + 1)
            if end == -1:
                raise ValueError("unclosed single quote")
            region += 1
            add("literal", text[index + 1:end])
            region += 1
            started = True
            index = end + 1
        elif char == '"':
            index += 1
            started = True
            region += 1
            while True:
                if index >= size:
                    raise ValueError("unclosed double quote")
                char = text[index]
                if char == '"':
                    index += 1
                    region += 1
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
            if char in "<>" and len(parts) == 1 and parts[0][0] == "plain":
                # An unquoted number right before `<`/`>` (`2>/dev/null`) is the redirection's descriptor, not an
                # argument; Bash removes it. A `{name}>` descriptor variable is not modeled.
                if parts[0][1].isdigit():
                    parts, started = [], False
                elif re.fullmatch(r"\{\w+\}", parts[0][1]):
                    raise ValueError("a {name} redirection descriptor")
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
                last = commands[-1]
                if operator == "\n" and not last.words and not last.redirects and last.before in ("&&", "||", "|", "|&"):
                    # `false &&` then a newline: the next line still belongs to the `&&`. Not modeled.
                    raise ValueError(f"a newline continues the `{last.before}` before it")
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


PLAIN_EXPANDING = frozenset("{}*?[~$`")
GLOB_CHARS = frozenset("*?[")
VARIABLE_WORD = re.compile(r"\$(?:\{(?P<braced>[A-Za-z_]\w*)\}|(?P<plain>[A-Za-z_]\w*))")


def _literal(parts: list[tuple[str, str]]) -> str:
    """The value of a word Bash does not expand at all, or Unmodeled: unquoted text without `{ } * ? [ ~ $` or
    backticks, single-quoted or escaped text, and double-quoted text without `$` or backticks."""
    for kind, piece in parts:
        if kind == "plain" and PLAIN_EXPANDING & set(piece):
            raise Unmodeled(f"the unquoted `{piece}` may be expanded by the shell")
        if kind == "double" and ("$" in piece or "`" in piece):
            raise Unmodeled(f"the double-quoted `{piece}` is not exactly one variable")
    return "".join(piece for _, piece in parts)


def _word(parts: list[tuple[str, str]], variables: dict[str, str]) -> str:
    """A word's value, when it is a literal or exactly `$NAME`, `${NAME}` or `"$NAME"` with a known value without
    whitespace. Raises Unmodeled for anything else."""
    if len(parts) == 1 and parts[0][0] in ("plain", "double"):
        match = VARIABLE_WORD.fullmatch(parts[0][1])
        if match:
            name = match.group("braced") or match.group("plain")
            value = variables.get(name)
            if value is None:
                raise Unmodeled(f"`${name}` is not set to a literal earlier in the line (or may not have been)")
            if not value or any(char in value for char in " \t\n"):
                raise Unmodeled(f"`${name}` is empty or holds whitespace")
            # Unquoted, Bash also expands a value's glob characters against the filesystem (`F='[b].md'; $F` may
            # name b.md); quoted, the value is literal.
            if parts[0][0] == "plain" and GLOB_CHARS & set(value):
                raise Unmodeled(f"the unquoted `${name}` holds a glob character the shell may expand")
            return value
    return _literal(parts)


class Files:
    """What else on the command line could change a body file before gh reads it."""

    def __init__(self, writer: str | None = None, targets: frozenset[Path] = frozenset()) -> None:
        self.writer = writer  # an earlier (or same-pipeline) command that may write files
        self.targets = targets  # paths the gh command's own redirections write


TRUSTED = Files()


def _read(path: str, cwd: Path, what: str, guard: Files = TRUSTED) -> str:
    if path == "-" or path.startswith("/dev/"):
        raise Unreadable(UNREADABLE.format(what=what, why="it comes from standard input"))
    # The path is already what Bash passes: an unquoted `~` falls back earlier, and a quoted one is a literal name.
    target = cwd / path
    if UNKNOWN in str(target):
        raise Unmodeled(f"the relative body path `{path}` follows a `cd` the hook does not follow")
    # The file on disk now may not be what gh reads, and the 0.4.2 rule would read the same stale file, so block.
    if guard.writer:
        raise Unreadable(UNREADABLE.format(what=what, why=f"`{guard.writer}` runs before or beside gh and may rewrite `{path}`"))
    if target in guard.targets:
        raise Unreadable(UNREADABLE.format(what=what, why=f"a redirection on the gh command rewrites `{path}`"))
    try:
        return target.read_text(encoding="utf-8")
    except OSError as error:
        raise Unreadable(UNREADABLE.format(what=what, why=f"`{path}`: {error.strerror or error}")) from None


# Short options gh takes with a value, and those that take none, per lane. gh (pflag) also accepts the value attached:
# `-bTEXT`, `-b=TEXT`, `-XPATCH`, `-f=body=x`.
PR_SHORT_VALUES, PR_SHORT_FLAGS = frozenset("aBbFHlmprRTt"), frozenset("dfw")
API_SHORT_VALUES, API_SHORT_FLAGS = frozenset("XfFHpqt"), frozenset("i")
LONG_VALUES = frozenset({"--body", "--body-file", "--title", "--base", "--head", "--repo", "--label", "--assignee",
                         "--milestone", "--project", "--reviewer", "--template", "--method", "--field", "--raw-field",
                         "--header", "--jq", "--input", "--preview", "--hostname", "--cache"})


def _short_options(args: list[str], values: frozenset[str], flags: frozenset[str]) -> list[str]:
    """The arguments with attached short-option values split off (`-b=TEXT` -> `-b`, `TEXT`). Raises Unmodeled for
    short-option forms the hook does not follow, such as several options combined with one that takes a value."""
    normalized: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token in LONG_VALUES or (len(token) == 2 and token[0] == "-" and token[1] in values):
            normalized += args[index:index + 2]  # the next word is this option's value, even if it starts with `-`
            index += 2
            continue
        if token.startswith("-") and not token.startswith("--") and len(token) > 2:
            if token[1] in values:
                value = token[2:]
                normalized += [token[:2], value[1:] if value.startswith("=") else value]
            elif all(letter in flags for letter in token[1:]):
                normalized += [f"-{letter}" for letter in token[1:]]
            else:
                raise Unmodeled(f"the short-option form `{token}` is not one the hook follows")
        else:
            normalized.append(token)
        index += 1
    return normalized


def _pr_bodies(verb: str, args: list[str], cwd: Path, guard: Files = TRUSTED) -> list[str] | None:
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
            texts.append(_read(file, cwd, "file", guard))
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


def _api_bodies(args: list[str], cwd: Path, guard: Files = TRUSTED) -> list[str] | None:
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
        raise Unmodeled(f"the gh api method `{method}` is not a literal HTTP method")
    match = PR_ENDPOINT.match(_endpoint_path(endpoint or ""))
    if not match:
        return None
    method = method or ("POST" if fields or input_file else "GET")
    creates = match.group("number") is None
    if creates and method != "POST" or not creates and method not in ("PATCH", "POST", "PUT"):
        return None
    if input_file is not None:
        try:
            data = json.loads(_read(input_file, cwd, "input file", guard))
        except ValueError:
            raise Unreadable(UNREADABLE.format(what="input file", why=f"`{input_file}` is not JSON")) from None
        # With `--input`, the file is the whole request body; gh sends `-f/-F` fields as URL query parameters.
        fields = {}
        if isinstance(data, dict) and isinstance(data.get("body"), str):
            fields["body"] = data["body"]
            raw_fields.add("body")
    if "body" not in fields:
        # Creating a PR without a body leaves it empty; updating one without a body leaves the body alone.
        return [] if creates else None
    body = fields["body"]
    if "body" not in raw_fields and body.startswith("@"):
        body = _read(body[1:], cwd, "file", guard)
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
        if name not in WRAPPERS:
            return False
        index += 1
        while index < len(words) and Path(words[index]).name not in WRAPPERS:
            word = words[index]
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


def _check(words: list[str], command: str, cwd: Path, guard: Files = TRUSTED) -> str | None:
    """The reason to block one simple command's expanded words, or None. Raises Unmodeled when `gh pr|api` appears
    somewhere other than first or behind a supported wrapper."""
    if Path(words[0]).name in UNMODELED_COMMANDS or (words[0] == "printf" and "-v" in words):
        raise Unmodeled(f"it uses `{words[0]}`")
    if any(Path(word).name in SHELLS for word in words):
        raise Unmodeled("it runs a shell (`bash -c` and the like)")
    # A word that only mentions gh (a `python3 -c` script, an echo'd string) is one word, not `gh` followed by `pr`.
    start = next((index for index, word in enumerate(words[:-1]) if Path(word).name == "gh" and words[index + 1] in ("pr", "api")), None)
    if start is None:
        return None
    if not _wrapper_prefix(words[:start]):
        raise Unmodeled(f"gh runs behind `{' '.join(words[:start])}`")
    words = words[start:]
    try:
        if words[1] == "pr" and len(words) > 2 and words[2] in ("create", "edit"):
            bodies = _pr_bodies(words[2], _short_options(words[3:], PR_SHORT_VALUES, PR_SHORT_FLAGS), cwd, guard)
        elif words[1] == "api":
            bodies = _api_bodies(_short_options(words[2:], API_SHORT_VALUES, API_SHORT_FLAGS), cwd, guard)
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


ASSIGNMENT_LIKE = re.compile(r"^[A-Za-z_]\w*(?:\[[^\]]*\])?\+?=")


def _modeled(command: str, cwd: Path) -> str | None:
    """The decision for a command line inside the hook's whitelist (see the module docstring). Raises Unmodeled
    for anything outside it."""
    try:
        commands, operators = _lex(command)
    except ValueError as error:
        raise Unmodeled(f"it could not split the line: {error}") from None
    unsupported = sorted(operators - MODELED_OPERATORS)
    if unsupported:
        raise Unmodeled("it uses " + ", ".join(f"`{operator}`" for operator in unsupported).replace("\n", "a newline"))
    if any("$(" in body or "`" in body for simple in commands for body in simple.expanded_heredocs):
        raise Unmodeled("an unquoted heredoc runs a command substitution")

    # Variables hold only literal values. `certain` ones hold for the rest of the line; `chained` ones, set after
    # `cmd &&`, only for the rest of that `&&` chain. Any other change makes the variable unknown, and using an
    # unknown variable is outside the whitelist. A `cd` can fail, so it only ever holds for the rest of its `&&` chain.
    certain: dict[str, str] = {}
    chained: dict[str, str] = {}
    unknown_cwd = Path(UNKNOWN + "cd")
    certain_cwd, chained_cwd = cwd, None
    # The first earlier command other than an assignment or `cd`: it may rewrite a body file before gh reads it,
    # so after it a body file is not read (the 0.4.2 rule applies).
    writer: str | None = None

    for position, simple in enumerate(commands):
        if simple.before != "&&":
            for name in chained:
                certain.pop(name, None)
            chained.clear()
            if chained_cwd is not None:
                certain_cwd, chained_cwd = unknown_cwd, None
        variables = {**certain, **chained}
        cwd = chained_cwd or certain_cwd
        for parts in simple.redirects:
            _literal(parts)
        if not simple.words:
            if simple.redirects:
                writer = writer or "a redirection"  # `> body.md` on its own truncates the file
            continue
        in_pipeline = simple.before in ("|", "|&") or simple.after in ("|", "|&")
        first = simple.words[0]
        if first and first[0][0] == "plain" and ASSIGNMENT_LIKE.match(first[0][1]):
            match = NAME.match(first[0][1])
            if not match or len(simple.words) > 1 or in_pipeline:
                raise Unmodeled("an assignment is not a single `NAME=literal` command of its own")
            name = match.group("name")
            value = _literal([("plain", first[0][1][match.end():]), *first[1:]])
            if simple.before in ("", ";", "\n"):
                certain[name] = value
            elif simple.before == "&&":
                chained[name] = value
            else:  # after `||` it runs only when the command before failed
                certain.pop(name, None)
            continue
        words = [_word(parts, variables) for parts in simple.words]
        if words[0] == "cd":
            target = words[1] if len(words) == 2 else ""
            whitelisted = (target.startswith("/") and ".." not in Path(target).parts and not simple.redirects
                           and not simple.expanded_heredocs and not in_pipeline and simple.before in ("", ";", "\n", "&&"))
            if whitelisted and simple.before != "&&":
                certain_cwd, chained_cwd = cwd, Path(target)
            elif whitelisted:
                chained_cwd = Path(target)
            else:
                certain_cwd, chained_cwd = unknown_cwd, None
            continue
        reason = _check(words, command, cwd, Files(writer or _pipeline_writer(commands, position, variables),
                                                   frozenset(cwd / _literal(parts) for parts in simple.redirects)))
        if reason:
            return reason
        if words[0] not in NO_WRITES or simple.redirects or simple.expanded_heredocs:
            writer = writer or words[0]
    return None


# Commands that write no files (without a redirection), so a body file read after them is current.
NO_WRITES = frozenset({"true", "false", ":", "echo", "pwd"})
# Pipeline consumers that only read their input and write nothing but their output.
READ_ONLY_FILTERS = frozenset({"tail", "head", "grep", "jq", "wc", "cat", "sort", "uniq", "cut"})


def _pipeline_writer(commands: list[Command], position: int, variables: dict[str, str]) -> str | None:
    """A command later in the same pipeline that runs beside gh and may write files, or None."""
    index = position
    while commands[index].after in ("|", "|&") and index + 1 < len(commands):
        index += 1
        peer = commands[index]
        name = Path(_word(peer.words[0], variables)).name if peer.words else ""
        if name not in READ_ONLY_FILTERS or peer.redirects:
            return name or "a redirection"
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
