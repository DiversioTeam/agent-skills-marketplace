"""Pi session discovery and parsing.

Layout: ~/.pi/agent/sessions/--<cwd with '/' as '-'>--/<timestamp>_<id>.jsonl. The first line is the session header
(`type: session`, `cwd`); every other entry has `id` and `parentId`, forming a tree. The active conversation is the
path from the newest entry back to the root; entries on abandoned branches are counted, not shown. Messages are
`user`, `assistant` (blocks `text`, `thinking`, `toolCall`) and `toolResult` (by `toolCallId`). Pi does not record the
git branch, so a session belongs to a branch when it mentions it (or the PR) or ran in a worktree that has it checked
out.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from redaction import withheld_reason
from repo_context import RepoContext
from session_model import Item, Tokens, ToolCall, Turn, Unit

HARNESS = "Pi"
_SKILL = re.compile(r"^<skill name=\"(?P<name>[^\"]+)\"[\s\S]*?</skill>\s*", re.MULTILINE)


def sessions_root() -> Path:
    base = os.environ.get("PI_CODING_AGENT_DIR")
    return (Path(base) if base else Path.home() / ".pi" / "agent") / "sessions"


def _entries(path: Path) -> list[dict]:
    entries = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict):
                entries.append(entry)
    return entries


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content if isinstance(content, list) else []:
        if isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif block.get("type") == "image":
                parts.append("[image omitted]")
    return "\n".join(parts)


def _active_path(entries: list[dict]) -> tuple[list[dict], int]:
    """The entries from the root to the newest entry, and how many entries lie on other branches."""
    tree = [entry for entry in entries if entry.get("id") and entry.get("type") != "session"]
    if not tree:
        return [], 0
    by_id = {entry["id"]: entry for entry in tree}
    path, seen = [], set()
    node: dict | None = tree[-1]
    while node is not None and node["id"] not in seen:
        seen.add(node["id"])
        path.append(node)
        parent = node.get("parentId")
        node = by_id.get(parent) if parent else None
    path.reverse()
    return path, len(tree) - len(path)


def parse_session(path: Path, context: RepoContext) -> Unit:
    entries = _entries(path)
    header = next((entry for entry in entries if entry.get("type") == "session"), {})
    session_id = str(header.get("id") or path.stem)
    unit = Unit(id=path.stem, harness=HARNESS, kind="session", title=f"Pi session {session_id[:8]}", session_id=session_id,
                path=str(path), cwd=str(header.get("cwd", "")))
    active, abandoned = _active_path(entries)
    markers = context.evidence_pattern()
    on_branch = context.in_worktree_on_branch(unit.cwd)
    pending: dict[str, ToolCall] = {}
    turn: Turn | None = None

    def current(timestamp: str) -> Turn:
        nonlocal turn
        if turn is None:
            turn = Turn(kind="agent", sender="session start", text="", timestamp=timestamp)
            unit.turns.append(turn)
        return turn

    for entry in active:
        timestamp = str(entry.get("timestamp", ""))
        unit.started = unit.started or timestamp
        unit.ended = timestamp or unit.ended
        kind = entry.get("type")
        if kind == "compaction":
            turn = Turn(kind="compaction", text=str(entry.get("summary", "")), timestamp=timestamp)
            unit.turns.append(turn)
        elif kind == "branch_summary":
            current(timestamp).items.append(Item(kind="note", text="The developer switched branches in the session tree here.", timestamp=timestamp))
        elif kind == "message":
            message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
            role = message.get("role")
            if role == "user":
                text = _text(message.get("content"))
                skill = _SKILL.match(text)
                if skill:
                    text = f"/skill:{skill.group('name')} {text[skill.end():]}".strip()
                if text.strip():
                    turn = Turn(kind="developer", text=text, timestamp=timestamp, branch=context.branch if on_branch else "")
                    unit.turns.append(turn)
            elif role == "assistant":
                model = str(message.get("model", ""))
                if model and model not in unit.models:
                    unit.models.append(model)
                usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
                unit.tokens.add(Tokens(input=int(usage.get("input") or 0), output=int(usage.get("output") or 0),
                                       cache_read=int(usage.get("cacheRead") or 0), cache_write=int(usage.get("cacheWrite") or 0)))
                for block in message.get("content") if isinstance(message.get("content"), list) else []:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text" and str(block.get("text", "")).strip():
                        current(timestamp).items.append(Item(kind="assistant", text=str(block["text"]), timestamp=timestamp))
                    elif block.get("type") == "toolCall":
                        arguments = block.get("arguments") if isinstance(block.get("arguments"), dict) else {}
                        call = ToolCall(id=str(block.get("id", "")), name=str(block.get("name", "")), input=arguments, timestamp=timestamp)
                        call.withheld = withheld_reason(call.name, call.input)
                        pending[call.id] = call
                        current(timestamp).items.append(Item(kind="tool", tool=call, timestamp=timestamp))
            elif role == "toolResult":
                call = pending.get(str(message.get("toolCallId", "")))
                if call:
                    call.output = _text(message.get("content"))
                    call.is_error = bool(message.get("isError"))
        if markers and turn is not None and markers.search(json.dumps(entry)):
            turn.evidence = True
    if abandoned:
        unit.notes.append(f"{abandoned} {'entry' if abandoned == 1 else 'entries'} on abandoned branches of the session tree "
                          f"{'is' if abandoned == 1 else 'are'} not shown.")
    if on_branch:
        unit.evidence.append(f"ran in a worktree on {context.branch}")
    if any(turn.evidence for turn in unit.turns):
        unit.evidence.append("mentions the branch or PR")
    return unit


def find_sessions(context: RepoContext, root: Path | None = None) -> list[Path]:
    """Session files modified since the branch started that ran in a worktree on the branch or mention it or the PR."""
    root = root or sessions_root()
    if not root.is_dir():
        return []
    pattern = context.evidence_pattern()
    found = []
    for path in root.glob("*/*.jsonl"):
        try:
            if path.stat().st_mtime < context.since:
                continue
            with path.open(encoding="utf-8", errors="replace") as handle:
                first = handle.readline()
                header = json.loads(first) if first.strip() else {}
                if isinstance(header, dict) and context.in_worktree_on_branch(str(header.get("cwd") or "")):
                    found.append(path)
                    continue
                if pattern and (pattern.search(first) or any(pattern.search(line) for line in handle)):
                    found.append(path)
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(found, key=lambda candidate: candidate.stat().st_mtime)
