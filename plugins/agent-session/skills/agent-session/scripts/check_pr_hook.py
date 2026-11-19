#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block creating or rewriting a DiversioTeam PR body without an agent session link.

Reads the hook payload on stdin. Exit 0 allows the call; exit 2 blocks it and shows stderr to the model. local-ci's
agent-session check (required `local/verify`) is the real gate; this gives the agent the feedback before the PR exists.

Each `gh pr create`, `gh pr edit` and `gh api` call in the command is judged by its own words, so a review reply, a
reviewer request or a read chained next to it is never mistaken for a PR description write.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pr_body import DECLARATION, LINK, has_transcript  # noqa: E402

# A call starts at `gh pr create`, `gh pr edit` or `gh api` where the shell runs it: substitutions, scripts fed to a
# shell and quoted `bash -c` arguments count; a quoted argument such as a PR title or a data heredoc does not.
GH_CALL = re.compile(r"\bgh[ \t]+(?:pr[ \t]+(?:create|edit)|api)\b")
# A heredoc operator and its delimiter; `<<<` is a here-string, not a heredoc.
HEREDOC = re.compile(r"""(?<!<)<<(?!<)(?P<dash>-?)[ \t]*(?:(['"])(?P<quoted>[^'"\s]+)\2|\\(?P<escaped>[A-Za-z0-9_.-]+)"""
                     r"""|(?P<plain>[A-Za-z0-9_.-]+))""")
# Commands whose heredoc is a script that runs, rather than data.
SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "fish", "ssh", "sudo", "su", "env", "exec", "eval", "source", ".",
                    "xargs", "nohup", "time", "timeout", "command"})
# Commands that run a quoted argument as shell code, and wrappers that run the command named after them.
SCRIPT_RUNNERS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "fish", "ssh", "su", "eval"})
WRAPPERS = frozenset({"sudo", "env", "exec", "nohup", "nice", "time", "timeout", "command", "xargs"})
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
# Runs of characters with no meaning to the quote scan, skipped in one step to keep it linear on long arguments.
CODE_TEXT = re.compile(r"""[^\\'"$()`;&|\n]+""")
EXPANDED_TEXT = re.compile(r"""[^\\"$`]+""")
API_TARGET = re.compile(r"\brepos/[^/\s]+/[^/\s]+/pulls\b")
# The shell pieces that decide where one simple command ends: quoted spans, escapes, `$(`, parentheses and operators.
SEGMENT_TOKEN = re.compile(r"""'[^']*'?|"(?:[^"\\]|\\.)*"?|\\.|\$\(|`[^`]*`?|[^'"\\$`;&|\n()]+|.""", re.DOTALL)
CD = re.compile(r"""(?:^|[;&|(\n])[ \t]*(?:cd|pushd)[ \t]+(?P<dir>(?:[^\s'"\\;&|()]|'[^']*'|"(?:[^"\\]|\\.)*"|\\.)+)"""
                r"""[ \t]*(?=$|[;&|)\n])""")
# A declaration that `printf` or `echo` writes to the body file earlier in the same command follows a quote or a `\n`.
WRITTEN_DECLARATION = re.compile(r"""(?:^|['"]|\\n)[ \t]*(?:[-*][ \t]*)?No agent session:[ \t]*[^\s'"\\][^\n'"]{2,}""",
                                 re.MULTILINE | re.IGNORECASE)
# The one shape the hook allows before its rule: a single `gh api` call to a review sub-resource of a PR, whose
# `body` is review text, not the PR description. A command with any shell operator, redirection, substitution or
# variable is not this shape, so it always gets the rule below.
REVIEW_ENDPOINT = re.compile(
    # Literal owner and repository names only: gh expands `{owner}`, `{repo}` and `{branch}` placeholders, and a branch
    # name can hold `/`, `?` or `#`, so a placeholder could turn a review path into the PR itself.
    r"^(?:https://api\.github\.com/|/)?repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pulls/(?:"
    r"[0-9]+/(?:comments(?:/[0-9]+/replies)?|reviews(?:/[0-9]+(?:/events|/comments)?)?|requested_reviewers)"
    r"|comments/[0-9]+)$"
)
NOT_SIMPLE = (";", "&", "|", "\n", "\r", "$", "`", "<", ">")
API_VALUE_FLAGS = frozenset({"-X", "--method", "-f", "-F", "--field", "--raw-field", "-H", "--header", "-q", "--jq",
                             "-t", "--template", "--input", "-p", "--preview", "--hostname", "--cache"})
REPLY_HINT = (
    " A review reply or comment passes only as a `gh api` call with a literal endpoint and no `$` or backticks: put "
    "the text in a file and pass `-F body=@/path/reply.md`."
)
# Without `$`, backticks or operators, a word is only unquoted text, '...', "..." and backslash escapes. A regex
# scan keeps this linear: shlex takes seconds on a long reply body, and the hook runs before every Bash call.
WORD = re.compile(r"""(?:[^\s'"\\]|'[^']*'|"(?:[^"\\]|\\.)*"|\\.)+""", re.DOTALL)
PART = re.compile(r"""'([^']*)'|"((?:[^"\\]|\\.)*)"|\\(.)|([^\s'"\\]+)""", re.DOTALL)
SPACE = re.compile(r"[ \t]*")
GH_API_START = re.compile(r"[ \t]*gh[ \t]+api[ \t]")
MESSAGE = (
    "This PR needs its agent session transcript. Run the agent-session skill "
    "(`agent-session share`, or `python3 {script} share`; on a first publish review the preview with the developer, then add `--yes`). "
    "It links the newest transcript in the body's "
    "'## Agent sessions' section. For a PR no agent worked on, add a line 'No agent session: <reason>'."
)
UNREADABLE = (
    "The PR body file `{name}` could not be read at {path}. A relative path resolves from the last `cd` before the gh "
    "command, else from the session directory {cwd}. Pass an absolute path, or write the file before this command. "
    "The body needs an agent session transcript link or a line 'No agent session: <reason>'."
)


def _is_diversio(command: str, cwd: Path) -> bool:
    if "DiversioTeam/" in command or "diversioteam/" in command.lower():
        return True
    completed = subprocess.run(["git", "-C", str(cwd), "remote", "get-url", "origin"], capture_output=True, text=True, check=False, timeout=10)
    return "diversioteam/" in completed.stdout.lower()


def _words(command: str) -> list[str] | None:
    """The command's words as Bash passes them, or None if a quote is unbalanced."""
    words = []
    index = SPACE.match(command).end()
    while index < len(command):
        match = WORD.match(command, index)
        if not match:
            return None
        pieces = []
        for single, double, escaped, plain in PART.findall(match.group()):
            if double:
                pieces.append(re.sub(r'\\([\\"])', r"\1", double))
            else:
                pieces.append(single or escaped or plain)
        words.append("".join(pieces))
        index = SPACE.match(command, match.end()).end()
    return words


def _review_call(command: str, strict: bool = True) -> bool:
    """Whether the command is exactly one `gh api` call to a PR review sub-resource: replies, review comments,
    reviews and requested reviewers. Its only positional argument is that literal endpoint. With `strict` off, the
    text is one call already cut from a longer command at its shell operator, so only `$` or a backtick disqualifies it."""
    if not GH_API_START.match(command) or any(char in command for char in (NOT_SIMPLE if strict else ("$", "`"))):
        return False
    tokens = _words(command)
    if tokens is None or tokens[:2] != ["gh", "api"]:
        return False
    positional = []
    index = 2
    while index < len(tokens):
        token = tokens[index]
        if token in API_VALUE_FLAGS:
            index += 2  # the flag's value
            continue
        if not strict and (token[:1] in ("<", ">") or token[:2] in ("1>", "2>")):
            break  # a redirection of this call's own output or input
        if not token.startswith("-"):
            positional.append(token)
        index += 1
    return len(positional) == 1 and bool(REVIEW_ENDPOINT.match(positional[0]))


def decide(command: str, cwd: Path, argv: list[str] | None = None) -> str | None:
    """The reason to block, or None to allow. `argv` is the command as an argument list, when the tool sent one."""
    if _review_call(command):
        return None
    if argv is not None and argv[:1] == ["gh"]:
        return _check_call(Call(command, command, [], 0, len(command), argv, command), cwd)
    for call in _gh_calls(command):
        reason = _check_call(call, cwd)
        if reason:
            return reason
    return None


class Heredoc(NamedTuple):
    operator: int  # where `<<` stands
    newline: int  # the end of the line holding it
    start: int  # the first character of the body
    end: int  # the start of the delimiter line
    after: int  # the end of the delimiter line
    data: bool  # whether the body is text rather than a script that runs
    quoted: bool  # whether Bash leaves the body unexpanded


class Call(NamedTuple):
    """One gh call: the whole command, that command with heredoc data blanked, its heredocs, where the call starts and
    ends, its words, and its text."""

    command: str
    scanned: str
    heredocs: list[Heredoc]
    start: int
    end: int
    tokens: list[str]
    text: str


def _gh_calls(command: str) -> list[Call]:
    """Each gh call that runs in the command, up to the operator that ends it."""
    heredocs = _heredocs(command)
    scanned = _without_heredoc_data(command, heredocs)
    quoted = _quoted_data(scanned)
    calls = []
    for match in GH_CALL.finditer(scanned):
        if any(start <= match.start() < end for start, end in quoted):
            continue  # text in a quoted argument, such as a PR title, runs nothing
        end = _segment_end(scanned, match.start())
        text = scanned[match.start():end]
        tokens = _words(text)
        if tokens is None:
            try:
                tokens = shlex.split(text, posix=True)
            except ValueError:
                tokens = text.split()
        calls.append(Call(command, scanned, heredocs, match.start(), end, tokens, text))
    return calls


def _heredocs(command: str) -> list[Heredoc]:
    """Every heredoc in the command. A body ends only at a line that is exactly its delimiter (after leading tabs for
    `<<-`), as in Bash: `EOF ` with a trailing blank is still body text."""
    found: list[Heredoc] = []
    for match in HEREDOC.finditer(command):
        if any(heredoc.data and heredoc.start <= match.start() < heredoc.after for heredoc in found):
            continue  # text inside a body that is not a script
        newline = command.find("\n", match.end())
        if newline < 0:
            continue
        # A second heredoc on the same line starts after the first one's delimiter.
        start = max([newline + 1] + [heredoc.after + 1 for heredoc in found if heredoc.newline == newline])
        delimiter = match.group("quoted") or match.group("escaped") or match.group("plain")
        tabs = r"\t*" if match.group("dash") else ""
        last = re.compile(rf"^{tabs}{re.escape(delimiter)}$", re.MULTILINE).search(command, min(start, len(command)))
        if not last and match.group("plain"):
            continue  # likely a shift such as `$((1<<2))`; an unterminated heredoc would warn anyway
        end, after = (last.start(), last.end()) if last else (len(command), len(command))
        line_start = command.rfind("\n", 0, match.start()) + 1
        words = re.split(r"[;&|(]", command[line_start:match.start()])[-1].split()
        data = bool(words) and Path(words[0]).name not in SHELLS
        found.append(Heredoc(match.start(), newline, start, end, after, data, match.group("plain") is None))
    return found


def _without_heredoc_data(command: str, heredocs: list[Heredoc]) -> str:
    """The command with heredoc text blanked, keeping every offset. Bash runs nothing in a quoted heredoc (`<<'EOF'`,
    `<<"EOF"`, `<<\\EOF`), and only the substitutions of an unquoted one, unless the heredoc feeds a shell, whose
    lines all run."""
    blank = list(command)
    for heredoc in heredocs:
        if not heredoc.data:
            continue
        if heredoc.quoted:
            spans = [(heredoc.start, heredoc.end)]
        else:
            spans = []
            _expanded(command[heredoc.start:heredoc.end], 0, None, spans)
            spans = [(heredoc.start + start, heredoc.start + end) for start, end in spans]
        for start, end in spans:
            for index in range(start, end):
                if blank[index] != "\n":
                    blank[index] = " "
    return "".join(blank)


def _quoted_data(text: str) -> list[tuple[int, int]]:
    """The quoted spans of `text` that are plain arguments: single-quoted text, and double-quoted text outside `$(...)`
    and backticks. A quoted argument to a shell, `eval` or `ssh` is a script, so it is scanned as commands."""
    spans: list[tuple[int, int]] = []
    _code(text, 0, None, spans)
    return spans


def _code(text: str, index: int, close: str | None, spans: list[tuple[int, int]]) -> int:
    """Scan shell code from `index` to `close` (`)`, a backtick or `"`, or the end), recording quoted data spans.
    Returns the index after the closing character."""
    segment = index
    while index < len(text):
        char = text[index]
        if char == close:
            return index + 1
        if char == "\\":
            index += 2
        elif char == "'":
            end = text.find("'", index + 1)
            end = len(text) if end < 0 else end
            if _runs_script(text, segment, index):
                spans += [(index + 1 + start, index + 1 + stop) for start, stop in _quoted_data(text[index + 1:end])]
            else:
                spans.append((index, end + 1))
            index = end + 1
        elif char == '"':
            script = _runs_script(text, segment, index)
            index = (_code if script else _expanded)(text, index + 1, '"', spans)
        elif text.startswith("$(", index):
            index = _code(text, index + 2, ")", spans)
        elif char in "(`":
            index = _code(text, index + 1, ")" if char == "(" else "`", spans)
        elif char in ";&|\n":
            segment = index + 1
            index += 1
        else:
            plain = CODE_TEXT.match(text, index)
            index = plain.end() if plain else index + 1
    return len(text)


def _expanded(text: str, index: int, close: str | None, spans: list[tuple[int, int]]) -> int:
    """Scan double-quoted or unquoted-heredoc text from `index` to `close`: data, except its substitutions."""
    start = index
    while index < len(text):
        char = text[index]
        if char == close:
            spans.append((start, index + 1))
            return index + 1
        if char == "\\":
            index += 2
        elif text.startswith("$(", index) or char == "`":
            spans.append((start, index))
            index = _code(text, index + 2, ")", spans) if char == "$" else _code(text, index + 1, "`", spans)
            start = index
        else:
            plain = EXPANDED_TEXT.match(text, index)
            index = plain.end() if plain else index + 1
    spans.append((start, len(text)))
    return len(text)


def _runs_script(text: str, segment: int, index: int) -> bool:
    """Whether the simple command between `segment` and `index` runs its quoted argument as shell code."""
    words = [Path(word).name for word in text[segment:index].split() if not ASSIGNMENT.match(word)]
    if not words:
        return False
    # `sudo -u someone bash -c '...'`: a wrapper runs the command named after it.
    return words[0] in SCRIPT_RUNNERS or (words[0] in WRAPPERS and any(word in SCRIPT_RUNNERS for word in words))


def _segment_end(command: str, start: int) -> int:
    """Where the simple command at `start` ends: the first unquoted `;`, `&`, `|`, newline or unmatched `)`."""
    depth = 0
    for match in SEGMENT_TOKEN.finditer(command, start):
        token = match.group()
        if token in ("$(", "("):
            depth += 1
        elif token == ")":
            if not depth:
                return match.start()
            depth -= 1
        elif token in (";", "&", "|", "\n") and not depth:
            return match.start()
    return len(command)


def _segment_start(command: str, position: int) -> int:
    """Where the simple command holding `position` starts: after the last `;`, `&`, `|`, newline or `(` before it
    that is not inside a finished subshell or substitution."""
    starts = [0]
    for match in SEGMENT_TOKEN.finditer(command, 0, position):
        token = match.group()
        if token in ("$(", "("):
            starts.append(match.end())
        elif token == ")" and len(starts) > 1:
            starts.pop()
            starts[-1] = match.end()
        elif token in (";", "&", "|", "\n"):
            starts[-1] = match.end()
    return starts[-1]


def _directory(prefix: str, cwd: Path) -> Path:
    """The directory a call runs in: the session's, changed by each literal `cd DIR` or `pushd DIR` before it, except
    one inside a subshell or substitution that has already closed."""
    changes = sorted((match.start("dir"), match.group("dir")) for match in CD.finditer(prefix))
    levels: list[list[str]] = [[]]
    for match in SEGMENT_TOKEN.finditer(prefix):
        while changes and changes[0][0] < match.end():
            levels[-1].append(changes.pop(0)[1])
        token = match.group()
        if token in ("$(", "("):
            levels.append([])
        elif token == ")" and len(levels) > 1:
            levels.pop()
    levels[-1] += [change for _, change in changes]
    directory = cwd
    for change in (change for level in levels for change in level):
        words = _words(change)
        if not words or len(words) != 1 or "$" in words[0] or "`" in words[0] or words[0] == "-":
            continue
        directory = directory / Path(words[0]).expanduser()
    return directory


def _source(call: Call, start: int, end: int, text: bool = True) -> str:
    """The original text from `start` to `end` (unless `text` is off), followed by the bodies of the heredocs opened
    there."""
    bodies = [call.command[heredoc.start:heredoc.end] for heredoc in call.heredocs if start <= heredoc.operator < end]
    return "\n".join([call.command[start:end]] * text + bodies)


def _stdin(call: Call) -> str:
    """What feeds the call's standard input: its own heredocs, and the command piped into it."""
    own = _source(call, call.start, call.end, text=False)
    before = call.scanned[:call.start].rstrip()
    if before.endswith("|") and not before.endswith("||"):
        pipe = len(before) - 1
        own += "\n" + _source(call, _segment_start(call.scanned, pipe), pipe)
    return own


def _written(call: Call, name: str) -> str | None:
    """The command that writes file `name` before the call (`> name`, `>> name` or `tee name`), with its heredocs, or
    None if nothing does."""
    quoted = rf"""(?:{re.escape(name)}|'{re.escape(name)}'|"{re.escape(name)}")"""
    writes = list(re.finditer(rf"(?:>>?|\btee(?:\s+-a)?)\s*{quoted}(?=$|[\s;&|)])", call.scanned[:call.start]))
    if not writes:
        return None
    start = _segment_start(call.scanned, writes[-1].start())
    return _source(call, start, _segment_end(call.scanned, start))


def _check_call(call: Call, cwd: Path) -> str | None:
    """The reason to block one gh call, or None. Only PR description writes need the transcript."""
    tokens, method = call.tokens, None
    if tokens[:3] in (["gh", "pr", "create"], ["gh", "pr", "edit"]):
        inline, files = _pr_bodies(tokens)
        if tokens[2] == "edit" and not inline and not files:
            return None  # labels, reviewers or the title, not the body
    elif tokens[:2] == ["gh", "api"]:
        if not API_TARGET.search(call.text) or _review_call(call.text, strict=False):
            return None
        method, inline, files, sends_body = _api_request(tokens, _stdin(call))
        if method == "GET" or not sends_body:
            return None
    else:
        return None
    directory = _directory(call.scanned[:call.start], cwd)
    if not _is_diversio(call.command, directory):
        return None
    # The call's own text holds an inline body, including a heredoc in `--body "$(cat <<'EOF' ...)"`.
    own = _source(call, call.start, call.end)
    if LINK.search(own) or DECLARATION.search(own) or any(has_transcript(body) for body in inline):
        return None
    unreadable, metadata = [], 0
    for name, is_json in files:
        written = _stdin(call) if name == "-" else _written(call, name)
        if written is not None:
            # Written or piped in by this same command, so the file on disk is not the body yet.
            if has_transcript(written) or WRITTEN_DECLARATION.search(written):
                return None
            continue
        path = directory / Path(name).expanduser()
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            unreadable.append((name, path))
            continue
        if not is_json:
            body = content
        else:
            body = _json_body(content)
            if body is None and method == "PATCH":
                metadata += 1  # a title, state or base change leaves the description alone
                continue
        if has_transcript(body or ""):
            return None
    if unreadable:
        name, path = unreadable[0]
        return UNREADABLE.format(name=name, path=path, cwd=cwd)
    if files and metadata == len(files) and not inline:
        return None
    reason = MESSAGE.format(script=Path(__file__).resolve().parent / "agent_session.py")
    if method and re.search(r"/pulls/[^/\s]+/", call.text):
        reason += REPLY_HINT
    return reason


def _pr_bodies(tokens: list[str]) -> tuple[list[str], list[tuple[str, bool]]]:
    """The inline body texts and body files a `gh pr create|edit` call passes."""
    inline, files = [], []
    for index, token in enumerate(tokens):
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        if token in ("--body", "-b") and following is not None:
            inline.append(following)
        elif token.startswith("--body="):
            inline.append(token.split("=", 1)[1])
        elif token in ("--body-file", "-F") and following is not None:
            files.append((following, False))
        elif token.startswith("--body-file="):
            files.append((token.split("=", 1)[1], False))
    return inline, files


def _api_flags(tokens: list[str]) -> list[str]:
    """The words of a `gh api` call with every attached flag value split off: `--raw-field=body=x` and `-fbody=x`
    become `--raw-field body=x` and `-f body=x`, as gh reads them."""
    words = []
    for token in tokens:
        long = re.match(r"(--[a-z-]+)=(.*)", token, re.DOTALL)
        short = re.match(r"(-[A-Za-z])(.+)", token, re.DOTALL)
        if long and long.group(1) in API_VALUE_FLAGS:
            words += [long.group(1), long.group(2)]
        elif short and short.group(1) in API_VALUE_FLAGS:
            words += [short.group(1), short.group(2)]
        else:
            words.append(token)
    return words


def _api_request(tokens: list[str], stdin: str) -> tuple[str, list[str], list[tuple[str, bool]], bool]:
    """A `gh api` call's method, inline `body` values, body files and whether it may send a body. gh sends GET unless
    told otherwise or given fields, then POST."""
    method, fields, sends_body = None, False, False
    inline: list[str] = []
    files: list[tuple[str, bool]] = []
    tokens = _api_flags(tokens)
    index = 2
    while index < len(tokens):
        token = tokens[index]
        value = tokens[index + 1] if index + 1 < len(tokens) else ""
        step = 2
        if token in ("-X", "--method"):
            method = value.upper()
        elif token in ("-f", "-F", "--field", "--raw-field"):
            fields = True
            if value.startswith("body="):
                sends_body = True
                body = value.split("=", 1)[1]
                if token in ("-F", "--field") and body.startswith("@"):
                    files.append((body[1:], False))
                else:
                    inline.append(body)
        elif token == "--input":
            fields = True
            # A request read from stdin is only known to hold a body when what feeds it says so.
            if value != "-" or re.search(r"\bbody\b", stdin):
                sends_body = True
                files.append((value, True))
        else:
            step = 1
        index += step
    return method or ("POST" if fields else "GET"), inline, files, sends_body


def _json_body(content: str) -> str | None:
    """The `body` of a JSON request file, None when the object has no `body` field, or the whole text when it is not a
    JSON object."""
    try:
        data = json.loads(content)
    except ValueError:
        return content
    if not isinstance(data, dict):
        return content
    return str(data["body"] or "") if "body" in data else None


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
