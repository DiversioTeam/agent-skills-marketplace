#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block creating or rewriting a DiversioTeam PR body without an agent session link.

Reads the hook payload on stdin. Exit 0 allows the call; exit 2 blocks it and shows stderr to the model. local-ci's
agent-session check (required `local/verify`) is the real gate; this gives the agent the feedback before the PR exists.

A chained command whose gh calls are only review replies, comments, reviewer requests or reads passes. Otherwise the
0.4.2 rule below judges the whole command, as before.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pr_body import DECLARATION, LINK, has_transcript  # noqa: E402

PR_COMMAND = re.compile(r"\bgh\s+pr\s+(?P<verb>create|edit)\b")
API_COMMAND = re.compile(r"\bgh\s+api\b[^\n]*\brepos/[^/\s]+/[^/\s]+/pulls\b")
BODY_FLAGS = ("--body", "-b", "--body-file", "-F")
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
    " A review reply or comment passes only as a single `gh api` command with a literal endpoint and no shell "
    "operators, `$` or backticks anywhere: put the text in a file and pass `-F body=@/path/reply.md`."
)
# Without `$`, backticks or operators, a word is only unquoted text, '...', "..." and backslash escapes. A regex
# scan keeps this linear: shlex takes seconds on a long reply body, and the hook runs before every Bash call.
WORD = re.compile(r"""(?:[^\s'"\\]|'[^']*'|"(?:[^"\\]|\\.)*"|\\.)+""", re.DOTALL)
PART = re.compile(r"""'([^']*)'|"((?:[^"\\]|\\.)*)"|\\(.)|([^\s'"\\]+)""", re.DOTALL)
SPACE = re.compile(r"[ \t]*")
GH_API_START = re.compile(r"[ \t]*gh[ \t]+api[ \t]")
# A literal `cd DIR` or `pushd DIR`, which moves where a relative --body-file is read from.
CD = re.compile(r"""(?:^|[;&|(\n])[ \t]*(?P<cd>cd|pushd)[ \t]+(?P<dir>(?:[^\s'"\\;&|()]|'[^']*'|"(?:[^"\\]|\\.)*"|\\.)+)"""
                r"""[ \t]*(?=$|[;&|)\n])""")
# A declaration that `printf` or `echo` writes to the body file earlier in the same command follows a quote or a `\n`.
WRITTEN_DECLARATION = re.compile(r"""(?:^|['"]|\\n)[ \t]*(?:[-*][ \t]*)?No agent session:[ \t]*[^\s'"\\][^\n'"]{2,}""",
                                 re.MULTILINE | re.IGNORECASE)
# The pieces that decide where one command in a chain ends: quoted spans, escapes, `$(`, parentheses, descriptor
# duplications such as `2>&1`, and the operators themselves.
SEGMENT_TOKEN = re.compile(r"""'[^']*'?|"(?:[^"\\]|\\.)*"?|\\.|\$\(|`[^`]*`?|[^'"\\$`;&|\n()]+|(?<=[<>])&[0-9-]*|&>>?|.""",
                           re.DOTALL)
# A `> FILE`, `>> FILE`, `tee FILE` or `tee -a FILE` that writes a file, and the file's word.
WRITE = re.compile(r"""(?:>>?|\btee(?:[ \t]+-a)?)[ \t]*(?P<target>(?:[^\s'"\\;&|()<>]|'[^']*'|"(?:[^"\\]|\\.)*")+)""")
# A heredoc operator and its delimiter (`<<<` is a here-string).
HEREDOC = re.compile(r"""<<(?!<)(?P<dash>-?)[ \t]*(?:'(?P<single>[^'\n]+)'|"(?P<double>[^"\n]+)"|\\?(?P<plain>[A-Za-z0-9_.-]+))""")
# A redirection of a call's own output, which does not change what the call sends.
OUTPUT_REDIRECT = re.compile(r"""[ \t]+(?:[0-9]*>>?|&>>?)[ \t]*(?:&[0-9-]+|[^\s;&|<>'"`$()]+)""")
UNREADABLE = (
    "The PR body file `{name}` could not be read at {path}. A relative path resolves from the last `cd` before the gh "
    "command, else from the session directory {cwd}. Pass an absolute path, or write the file before this command. "
    "The body needs an agent session transcript link or a line 'No agent session: <reason>'."
)
MESSAGE = (
    "This PR needs its agent session transcript. Run the agent-session skill "
    "(`agent-session share`, or `python3 {script} share`; on a first publish review the preview with the developer, then add `--yes`). "
    "It links the newest transcript in the body's "
    "'## Agent sessions' section. For a PR no agent worked on, add a line 'No agent session: <reason>'."
)


def _bodies(command: str, cwd: Path, argv: list[str] | None = None,
            unreadable: list[tuple[str, Path]] | None = None) -> list[str]:
    """The PR body texts a command passes: inline `--body`/`-b` values (and `body=` API fields) and `--body-file` contents.
    An argv list keeps its own argument boundaries. Body files that cannot be read are added to `unreadable`."""
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
            path = cwd / Path(file).expanduser()
            try:
                texts.append(path.read_text(encoding="utf-8"))
            except OSError:
                if unreadable is not None:
                    unreadable.append((file, path))
    return texts


def _writes_declaration(command: str, first: int, cwd: Path, directory: Path) -> bool:
    """Whether a `printf` or `echo` before the gh call writes a declaration into the body the call reads: the same
    command writes the declaration and redirects or tees it to the file the call passes as `--body-file`/`-F` (both
    paths resolved where their commands run), or pipes it into `--body-file -`."""
    prefix = command[:first]
    if not WRITTEN_DECLARATION.search(prefix):
        return False
    words = _words(command[first:]) or command[first:].split()
    files = [following for token, following in zip(words, words[1:]) if token in ("--body-file", "-F")]
    files += [token.split("=", 1)[1] for token in words if token.startswith("--body-file=")]
    spans = _segment_spans(prefix)
    for name in files:
        if name == "-":
            piped = re.search(r"(?<!\|)\|[ \t]*$", prefix)
            if piped and spans and WRITTEN_DECLARATION.search(prefix[spans[-1][0]:spans[-1][1]]):
                return True
            continue
        target = os.path.normpath(directory / Path(name).expanduser())
        for start, end in spans:
            text = prefix[start:end]
            if not WRITTEN_DECLARATION.search(text):
                continue
            for write in WRITE.finditer(text):
                written = _words(write.group("target"))
                if not written or len(written) != 1 or "$" in written[0]:
                    continue
                where = _directory(command, cwd, start)
                if os.path.normpath(where / Path(written[0]).expanduser()) == target:
                    return True
    return False


def _top_level(command: str, end: int) -> bytearray | None:
    """For each character before `end`, 1 when it is shell code outside every parenthesis, `$(...)`, quote, comment
    and heredoc body, else 0. None when the scan cannot tell (an unclosed quote). Deliberately conservative: a `cd`
    is trusted only where this marks it, so the hook never moves a call into a directory Bash does not use."""
    mask = bytearray(end)
    index, depth, double, pending = 0, 0, False, []
    while index < end:
        char = command[index]
        if char == "\\":
            index += 2
            continue
        if double:
            if char == '"':
                double = False
            elif command.startswith("$(", index):
                depth += 1
                index += 1
            elif char == ")" and depth:
                depth -= 1
            index += 1
            continue
        if char == "'":
            close = command.find("'", index + 1)
            if close < 0:
                return None
            index = close + 1
            continue
        if char == '"':
            double = True
        elif char == "#" and (index == 0 or command[index - 1] in " \t\n;&|("):
            newline = command.find("\n", index)
            index = end if newline < 0 else newline
            continue
        elif command.startswith("<<", index) and (heredoc := HEREDOC.match(command, index)):
            pending.append(heredoc)
            index = heredoc.end()
            continue
        elif char == "\n" and pending:
            # Skip each pending heredoc body, up to a line that is exactly its delimiter.
            position = index + 1
            for heredoc in pending:
                delimiter = heredoc.group("single") or heredoc.group("double") or heredoc.group("plain")
                tabs = r"\t*" if heredoc.group("dash") else ""
                last = re.compile(rf"^{tabs}{re.escape(delimiter)}$", re.MULTILINE).search(command, position)
                position = last.end() if last else len(command)
            pending = []
            index = position
            continue
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(depth - 1, 0)
        elif not depth:
            mask[index] = 1
        index += 1
    return None if double else mask


def _directory(command: str, cwd: Path, end: int | None = None) -> Path:
    """Where the command at `end` (default: the first gh call) runs: the session directory, changed by each literal
    `cd DIR` before it at the top level of the command. A `cd` inside parentheses, `$(...)`, quotes, a comment or a
    heredoc is ignored."""
    if end is None:
        end = min([match.start() for match in (PR_COMMAND.search(command), API_COMMAND.search(command)) if match] or [0])
    mask = _top_level(command, end)
    if mask is None:
        return cwd
    directory = cwd
    for match in CD.finditer(command, 0, end):
        if not mask[match.start("cd")]:
            continue
        words = _words(match.group("dir"))
        if not words or len(words) != 1 or "$" in words[0] or "`" in words[0] or words[0] == "-":
            continue
        directory = directory / Path(words[0]).expanduser()
    return directory


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


def _review_call(command: str) -> bool:
    """Whether the command is exactly one `gh api` call to a PR review sub-resource: replies, review comments,
    reviews and requested reviewers. Its only positional argument is that literal endpoint."""
    if not GH_API_START.match(command) or any(char in command for char in NOT_SIMPLE):
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
        if not token.startswith("-"):
            positional.append(token)
        index += 1
    return len(positional) == 1 and bool(REVIEW_ENDPOINT.match(positional[0]))


def _segment_spans(command: str) -> list[tuple[int, int]]:
    """Where each command of a chain starts and ends: split at unquoted `;`, `&`, `|` and newlines outside `$(...)`
    and parentheses."""
    spans, start, depth = [], 0, 0
    for match in SEGMENT_TOKEN.finditer(command):
        token = match.group()
        if token in ("$(", "("):
            depth += 1
        elif token == ")" and depth:
            depth -= 1
        elif token in (";", "&", "|", "\n") and not depth:
            spans.append((start, match.start()))
            start = match.end()
    return [(begin, stop) for begin, stop in spans + [(start, len(command))] if command[begin:stop].strip()]


def _segments(command: str) -> list[str]:
    """The commands of a chain, as text."""
    return [command[start:end] for start, end in _segment_spans(command)]


def _writes_description(segment: str, command: str) -> bool:
    """Whether one command of a chain gets the rule: a `gh pr create`, a `gh pr edit` with a body flag, or a `gh api`
    write to a pull request that sends a body. Review replies, review comments, reviewer requests, `gh pr comment`
    and reads do not."""
    text = segment.strip()
    if _review_call(OUTPUT_REDIRECT.sub("", text)):
        return False
    match = PR_COMMAND.search(text)
    api = API_COMMAND.search(text)
    if not match and not api:
        return False
    if match and match.group("verb") == "create":
        return True
    if match:
        return any(re.search(rf"(?:^|\s){re.escape(flag)}(?:[\s=]|$)", text) for flag in BODY_FLAGS)
    return bool(re.search(r"(?:-X|--method)\s*(?:POST|PATCH)|-f\s+body=|-F\s+body=|--field\s+body=|--raw-field\s+body=", text)
                and re.search(r"\bbody\b", command))  # as in the rule: a piped heredoc may hold the body


def decide(command: str, cwd: Path, argv: list[str] | None = None) -> str | None:
    """The reason to block, or None to allow. `argv` is the command as an argument list, when the tool sent one."""
    if _review_call(command):
        return None
    if argv is None and not any(_writes_description(segment, command) for segment in _segments(command)):
        return None  # only review traffic, comments and reads
    reason = _rule(command, cwd, argv)
    if reason and API_COMMAND.search(command) and re.search(r"/pulls/[^/\s]+/", command):
        reason += REPLY_HINT
    return reason


def _rule(command: str, cwd: Path, argv: list[str] | None = None) -> str | None:
    """The 0.4.2 rule, unchanged."""
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
    directory = _directory(command, cwd)
    if not _is_diversio(command, directory):
        return None
    # A heredoc body (`--body "$(cat <<'EOF' ...)"`, or `cat > body.md <<'EOF'` before the call) puts the body's lines in
    # the command text, so a link or a declaration line anywhere in it counts. So does a declaration that `printf` or
    # `echo` writes before the gh call.
    first = min([found.start() for found in (match, api) if found])
    if LINK.search(command) or DECLARATION.search(command) or _writes_declaration(command, first, cwd, directory):
        return None
    unreadable: list[tuple[str, Path]] = []
    if any(has_transcript(text) for text in _bodies(command, directory, argv, unreadable)):
        return None
    if unreadable:
        name, path = unreadable[0]
        return UNREADABLE.format(name=name, path=path, cwd=cwd)
    return MESSAGE.format(script=Path(__file__).resolve().parent / "agent_session.py")


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
