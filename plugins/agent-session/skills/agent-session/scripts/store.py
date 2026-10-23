"""The local record of published transcripts, one JSON object per line.

local-ci's agent-session check reads this file when a branch has no PR yet, so the format is a contract:
{"repo": "Owner/name", "branch": "...", "head": "<sha>", "base": "<sha>", "commits": [...], "names": [...],
 "links": [...], "pr": 12 | null, "published_at": "<iso>"} or, for work with no agent, {..., "none": "<reason>"}.
The newest line for a repo and branch wins.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def path() -> Path:
    base = os.environ.get("AGENT_SESSION_HOME")
    return (Path(base).expanduser() if base else Path.home() / ".agent" / "sessions") / "published.jsonl"


def record(entry: dict[str, object]) -> None:
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def latest(repo: str, branch: str) -> dict[str, object] | None:
    found = None
    try:
        lines = path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict) and entry.get("repo") == repo and entry.get("branch") == branch:
            found = entry
    return found
