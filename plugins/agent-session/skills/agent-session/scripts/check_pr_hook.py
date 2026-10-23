#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block creating or rewriting a DiversioTeam PR body without an agent session link.

Reads the hook payload on stdin. Exit 0 allows the call; exit 2 blocks it and shows stderr to the model. local-ci's
agent-session check (required `local/verify`) is the real gate; this gives the agent the feedback before the PR exists.
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

PR_COMMAND = re.compile(r"\bgh\s+pr\s+(?P<verb>create|edit)\b")
API_COMMAND = re.compile(r"\bgh\s+api\b[^\n]*\brepos/[^/\s]+/[^/\s]+/pulls\b")
BODY_FLAGS = ("--body", "-b", "--body-file", "-F")
MESSAGE = (
    "This PR needs its agent session transcript. Run the agent-session skill "
    "(`python3 {script} share`; on a first publish review the preview with the developer, then add `--yes`). It links the newest transcript in the body's "
    "'## Agent sessions' section. For a PR no agent worked on, add a line 'No agent session: <reason>'."
)


def _bodies(command: str, cwd: Path) -> list[str]:
    """The PR body texts a command passes: inline `--body`/`-b` values (and `body=` API fields) and `--body-file` contents."""
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


def _is_diversio(command: str, cwd: Path) -> bool:
    if "DiversioTeam/" in command or "diversioteam/" in command.lower():
        return True
    completed = subprocess.run(["git", "-C", str(cwd), "remote", "get-url", "origin"], capture_output=True, text=True, check=False, timeout=10)
    return "diversioteam/" in completed.stdout.lower()


def decide(command: str, cwd: Path) -> str | None:
    """The reason to block, or None to allow."""
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
    if LINK.search(command) or any(has_transcript(text) for text in _bodies(command, cwd)):
        return None
    return MESSAGE.format(script=Path(__file__).resolve().parent / "agent_session.py")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return 0
    reason = decide(command, Path(payload.get("cwd") or ".").expanduser())
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
