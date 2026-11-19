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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pr_body import DECLARATION, LINK, has_transcript  # noqa: E402

# A call starts at `gh pr create`, `gh pr edit` or `gh api` anywhere in the text, heredocs and substitutions included,
# so a call inside a script fed to a shell still counts.
GH_CALL = re.compile(r"\bgh[ \t]+(?:pr[ \t]+(?:create|edit)|api)\b")
QUOTED_HEREDOC = re.compile(r"""<<(?P<dash>-?)[ \t]*(?:(['"])(?P<quoted>[^'"\s]+)\2|\\(?P<escaped>[A-Za-z0-9_]+))""")
# Commands whose heredoc is a script that runs, rather than data.
SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "fish", "ssh", "sudo", "su", "env", "exec", "eval", "source", ".",
                    "xargs", "nohup", "time", "timeout", "command"})
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
    for prefix, tokens, text in _gh_calls(command, argv):
        reason = _check_call(command, prefix, tokens, text, cwd)
        if reason:
            return reason
    return None


def _gh_calls(command: str, argv: list[str] | None) -> list[tuple[str, list[str], str]]:
    """Each gh call in the command as (the text before it, its words, its text), up to the operator that ends it."""
    if argv is not None and argv[:1] == ["gh"]:
        return [("", argv, command)]
    calls = []
    scanned = _without_data_heredocs(command)
    for match in GH_CALL.finditer(scanned):
        text = scanned[match.start():_segment_end(scanned, match.start())]
        tokens = _words(text)
        if tokens is None:
            try:
                tokens = shlex.split(text, posix=True)
            except ValueError:
                tokens = text.split()
        calls.append((scanned[:match.start()], tokens, text))
    return calls


def _without_data_heredocs(command: str) -> str:
    """The command with the bodies of quoted heredocs (`<<'EOF'`, `<<"EOF"`, `<<\\EOF`) blanked, unless they feed a
    shell. Bash expands nothing in such a body, so a script or notes file that mentions `gh pr create` runs nothing;
    `bash <<'EOF'` still runs its lines, so those stay."""
    pieces, position = [], 0
    for match in QUOTED_HEREDOC.finditer(command):
        if match.start() < position:
            continue  # inside a body already blanked
        line_start = command.rfind("\n", 0, match.start()) + 1
        words = re.split(r"[;&|(]", command[line_start:match.start()])[-1].split()
        body_start = command.find("\n", match.end())
        if not words or Path(words[0]).name in SHELLS or body_start < 0:
            continue
        delimiter = match.group("quoted") or match.group("escaped")
        tabs = r"\t*" if match.group("dash") else ""
        end = re.compile(rf"^{tabs}{re.escape(delimiter)}[ \t]*$", re.MULTILINE).search(command, body_start + 1)
        body_end = end.start() if end else len(command)
        pieces += [command[position:body_start + 1], "\n" * command.count("\n", body_start + 1, body_end)]
        position = body_end
    return "".join(pieces) + command[position:]


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


def _directory(prefix: str, cwd: Path) -> Path:
    """The directory a call runs in: the session's, changed by each literal `cd DIR` or `pushd DIR` before it."""
    directory = cwd
    for match in CD.finditer(prefix):
        words = _words(match.group("dir"))
        if not words or len(words) != 1 or "$" in words[0] or "`" in words[0] or words[0] == "-":
            continue
        directory = directory / Path(words[0]).expanduser()
    return directory


def _check_call(command: str, prefix: str, tokens: list[str], text: str, cwd: Path) -> str | None:
    """The reason to block one gh call, or None. Only PR description writes need the transcript."""
    if tokens[:3] in (["gh", "pr", "create"], ["gh", "pr", "edit"]):
        inline, files = _pr_bodies(tokens)
        if tokens[2] == "edit" and not inline and not files:
            return None  # labels, reviewers or the title, not the body
        api = False
    elif tokens[:2] == ["gh", "api"]:
        if not API_TARGET.search(text) or _review_call(text, strict=False):
            return None
        method, inline, files, sends_body = _api_request(tokens, command)
        if method == "GET" or not sends_body:
            return None
        api = True
    else:
        return None
    directory = _directory(prefix, cwd)
    if not _is_diversio(command, directory):
        return None
    # A heredoc body (`--body "$(cat <<'EOF' ...)"`, or `cat > f <<'EOF'` before the call) puts the body's lines in the
    # command text itself, so a link or a declaration line there counts.
    if LINK.search(command) or DECLARATION.search(command) or any(has_transcript(body) for body in inline):
        return None
    unreadable = []
    for name, is_json in files:
        if name == "-" or _writes(prefix, name):
            # Written or piped in by this same command, so the file on disk is not the body yet.
            if WRITTEN_DECLARATION.search(prefix):
                return None
            continue
        path = directory / Path(name).expanduser()
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            unreadable.append((name, path))
            continue
        if has_transcript(_json_body(content) if is_json else content):
            return None
    if unreadable:
        name, path = unreadable[0]
        return UNREADABLE.format(name=name, path=path, cwd=cwd)
    reason = MESSAGE.format(script=Path(__file__).resolve().parent / "agent_session.py")
    if api and re.search(r"/pulls/[^/\s]+/", text):
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


def _api_request(tokens: list[str], command: str) -> tuple[str, list[str], list[tuple[str, bool]], bool]:
    """A `gh api` call's method, inline `body` values, body files and whether it sends a body. gh sends GET unless
    told otherwise or given fields, then POST."""
    method, fields, sends_body = None, False, False
    inline: list[str] = []
    files: list[tuple[str, bool]] = []
    index = 2
    while index < len(tokens):
        token = tokens[index]
        value = tokens[index + 1] if index + 1 < len(tokens) else ""
        step = 2
        if token in ("-X", "--method"):
            method = value.upper()
        elif token.startswith("-X") or token.startswith("--method="):
            method, step = token.removeprefix("-X").removeprefix("--method=").upper(), 1
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
            # A request read from stdin is only known to hold a body when the command text says so.
            if value != "-" or re.search(r"\bbody\b", command):
                sends_body = True
                files.append((value, True))
        else:
            step = 1
        index += step
    return method or ("POST" if fields else "GET"), inline, files, sends_body


def _json_body(content: str) -> str:
    """The `body` of a JSON request file, or the whole text when it is not a JSON object."""
    try:
        data = json.loads(content)
    except ValueError:
        return content
    return str(data.get("body") or "") if isinstance(data, dict) else content


def _writes(prefix: str, name: str) -> bool:
    """Whether the command writes file `name` before the call: `> name`, `>> name` or `tee name`."""
    quoted = rf"""(?:{re.escape(name)}|'{re.escape(name)}'|"{re.escape(name)}")"""
    return bool(re.search(rf"(?:>>?|\btee(?:\s+-a)?)\s*{quoted}(?=$|[\s;&|)])", prefix))


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
