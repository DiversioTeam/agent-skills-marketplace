"""The local record of published transcripts, one JSON object per line.

local-ci's agent-session check reads this file when a branch has no PR yet, so the format is a contract:
{"repo": "Owner/name", "branch": "...", "head": "<sha>", "base": "<sha>", "commits": [...], "names": [...],
 "links": [...], "pr": 12 | null, "linked": true | false, "published_at": "<iso>"} or, for work with no agent,
{..., "none": "<reason>"}. A publish whose PR body update failed has "linked": false.
The newest publish line for a repo and branch wins. Lines with "cleanup": [names] are not publishes: the newest one lists
uploads that could not be deleted yet, retried by every later share until they are gone.
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


def history(repo: str, branch: str) -> list[dict[str, object]]:
    entries = []
    try:
        lines = path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict) and entry.get("repo") == repo and entry.get("branch") == branch:
            entries.append(entry)
    return entries


def unlinked_since_last_link(repo: str, branch: str) -> list[str]:
    """Upload names a successful link supersedes: the last linked publish's, and every publish since whose linking failed."""
    names: list[str] = []
    for entry in reversed(history(repo, branch)):
        if "cleanup" in entry:
            continue
        names.extend(str(name) for name in entry.get("names") or [])
        if entry.get("linked", True):
            break
    return names


def cleanup_debt(repo: str, branch: str) -> list[str]:
    """Uploads an earlier share could not delete."""
    for entry in reversed(history(repo, branch)):
        if "cleanup" in entry:
            return [str(name) for name in entry["cleanup"] or []]
    return []


def record_cleanup(repo: str, branch: str, names: list[str]) -> None:
    record({"repo": repo, "branch": branch, "cleanup": sorted(set(names))})


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
        if isinstance(entry, dict) and entry.get("repo") == repo and entry.get("branch") == branch and "cleanup" not in entry:
            found = entry
    return found
