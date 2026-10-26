"""Pi session discovery and parsing.

Layout: ~/.pi/agent/sessions/--<cwd with '/' as '-'>--/<timestamp>_<id>.jsonl. The first line is the session header
(`type: session`, `cwd`); every other entry has `id` and `parentId`, forming a tree. The active conversation is the
path from the newest entry back to the root; entries on abandoned branches are counted, not shown. Messages are
`user`, `assistant` (blocks `text`, `thinking`, `toolCall`) and `toolResult` (by `toolCallId`). Pi does not record the
git branch, so a session belongs to a branch when it ran in a worktree that has it checked out, mentions the branch while
running in this repository, or mentions the PR from anywhere (a branch name alone is shared by every repository with a
branch of that name).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from provenance import Provenance
from redaction import withheld_reason
from repo_context import RepoContext, is_recent
from session_model import Item, Tokens, ToolCall, Turn, Unit

HARNESS = "Pi"
# Pi's bash writes overflow to <tmp>/pi-bash-<id>.log. pi-subagents keeps only the first 32 KiB of a child's tool output
# and drops `details`, so a long result can lose its "Full output:" notice: an overflow file whose origin is unknown is
# withheld rather than trusted.
_OVERFLOW_FILE = re.compile(r"pi-bash[^\s/'\"]*\.log")
_OVERFLOW_NOTICE = re.compile(r"Full output:?\s*(/\S+?)[\].,;)]*(?:\s|$)")
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


def _unknown_overflow(call: ToolCall, overflow: Provenance) -> str | None:
    """Withhold a call that names any overflow file no recorded notice explains, even beside files whose origin is known."""
    flat = json.dumps(call.input, default=str)
    known = {Path(handle).name for handle in overflow.handles if handle in flat}
    if any(name not in known for name in _OVERFLOW_FILE.findall(flat)):
        return "overflow output of unknown origin"
    return None


def _starts_children(call: ToolCall) -> bool:
    """pi-subagents' `subagent` tool run for execution; with `action` it only manages runs (status, list, guide), and
    other tools (an `ls` of the artifacts) can name a run without having started it."""
    return call.name == "subagent" and not call.input.get("action")


def _evidence(context: RepoContext, cwd: str) -> re.Pattern[str] | None:
    """What ties a session or child to this work, judged by its own directory: in this repository the branch counts;
    elsewhere only what names this repository, the PR."""
    return context.evidence_pattern(branch=context.in_repo(cwd))


def _run_ids(details: object) -> list[str]:
    """Run ids in a result's structured details (pi-subagents puts `runId` there; its text need not name the run)."""
    if isinstance(details, dict):
        found = [str(details["runId"])] if isinstance(details.get("runId"), str) else []
        return found + [run for value in details.values() for run in _run_ids(value)]
    if isinstance(details, list):
        return [run for value in details for run in _run_ids(value)]
    return []


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


def parse_session(path: Path, context: RepoContext, entries: list[dict] | None = None, kind: str = "session", title: str = "",
                  harness: str = HARNESS) -> Unit:
    """A Pi-format session file (Pi's own, or a Courage export with its own harness label), or (with `entries`) a
    pi-subagents child transcript already converted to entries."""
    entries = _entries(path) if entries is None else entries
    header = next((entry for entry in entries if entry.get("type") == "session"), {})
    session_id = str(header.get("id") or path.stem)
    unit = Unit(id=path.stem, harness=harness, kind=kind, title=title or f"{harness} session {session_id[:8]}", session_id=session_id,  # type: ignore[arg-type]
                path=str(path), cwd=str(header.get("cwd", "")))
    active, abandoned = _active_path(entries)
    unit.branch_counts = context.in_repo(unit.cwd)
    markers = _evidence(context, unit.cwd)
    on_branch = context.in_worktree_on_branch(unit.cwd)
    pending: dict[str, ToolCall] = {}
    # Pi's bash saves truncated output to a file (details.fullOutputPath); reading it inherits the bash call's withholding.
    overflow = Provenance()
    # The pi-subagents runs each call started, from its result's structured details.
    runs: dict[str, list[str]] = {}
    unit.runs = runs
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
                        call.withheld = withheld_reason(call.name, call.input) or overflow.inherited(call) or _unknown_overflow(call, overflow)
                        pending[call.id] = call
                        current(timestamp).items.append(Item(kind="tool", tool=call, timestamp=timestamp))
            elif role == "toolResult":
                call = pending.get(str(message.get("toolCallId", "")))
                if call:
                    call.output = _text(message.get("content"))
                    call.is_error = bool(message.get("isError"))
                    details = message.get("details") if isinstance(message.get("details"), dict) else {}
                    # Child artifacts drop `details`; the "Full output: <path>" notice in the text names the same file.
                    overflow.record([str(details.get("fullOutputPath") or ""), *_OVERFLOW_NOTICE.findall(call.output)], call.withheld)
                    runs[call.id] = _run_ids(details)
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


def _child_entries(transcript: Path) -> list[dict]:
    """A pi-subagents transcript (recordType "message" lines with a pi-ai message) as Pi session entries, with a session
    header carrying the child's working directory (each record has `cwd`)."""
    records = _entries(transcript)
    cwd = next((str(record["cwd"]) for record in records if record.get("cwd")), "")
    entries: list[dict] = [{"type": "session", "id": transcript.stem, "cwd": cwd}]
    for record in records:
        message = record.get("message")
        if record.get("recordType") != "message" or not isinstance(message, dict):
            continue
        entry_id = f"child-{len(entries)}"
        entries.append({"type": "message", "id": entry_id, "parentId": entries[-1]["id"] if len(entries) > 1 else None,
                        "timestamp": str(record.get("timestamp", "")), "message": message})
    return entries


def _abandoned_runs(entries: list[dict]) -> set[str]:
    """Run ids that spawning calls on abandoned branches of the session tree started, by their results' structured
    details."""
    spawning: set[str] = set()
    runs: set[str] = set()
    for entry in entries:
        message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
        if message.get("role") == "assistant":
            for block in message.get("content") if isinstance(message.get("content"), list) else []:
                if isinstance(block, dict) and block.get("type") == "toolCall" and _starts_children(
                        ToolCall(id="", name=str(block.get("name", "")), input=block.get("arguments") if isinstance(block.get("arguments"), dict) else {})):
                    spawning.add(str(block.get("id", "")))
        elif message.get("role") == "toolResult" and str(message.get("toolCallId", "")) in spawning:
            runs.update(_run_ids(message.get("details")))
    return runs


def load_session(path: Path, context: RepoContext) -> Unit:
    """A Pi session with its pi-subagents children (subagent-artifacts/<run>_<agent>_meta.json naming this session as
    the parent), nested at the call whose result names their run id, or listed after the session."""
    unit = parse_session(path, context)
    # Entries on abandoned branches of the session tree are not shown, and neither are the children they started.
    entries = _entries(path)
    active, _ = _active_path(entries)
    kept = {id(entry) for entry in active}
    off_path = [entry for entry in entries if entry.get("type") != "session" and id(entry) not in kept]
    abandoned = "\n".join(json.dumps(entry) for entry in off_path)
    abandoned_runs = _abandoned_runs(off_path)
    calls = [item.tool for turn in unit.turns for item in turn.items if item.tool]
    spawns = [call for call in calls if _starts_children(call)]
    for meta_path in sorted((path.parent / "subagent-artifacts").glob("*_meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(meta, dict) or str(meta.get("parentSessionId", "")) != unit.session_id:
            continue
        run_id = str(meta.get("runId", ""))
        transcript = Path(str(meta.get("transcriptPath") or meta_path.with_name(meta_path.name.replace("_meta.json", "_transcript.jsonl"))))
        if not run_id or not transcript.exists():
            continue
        label = f"{meta.get('agent') or run_id[:8]}" + (f" #{meta['index']}" if meta.get("index") is not None else "")
        child = parse_session(transcript, context, _child_entries(transcript), "subagent", f"Pi subagent: {label}")
        child.id = meta_path.name.removesuffix("_meta.json")
        # Each child is its own worker, even when a parallel run gives siblings one run id; the spawning call is
        # related to the run through its children.
        child.worker_key = child.id
        child.task_index = meta["index"] if isinstance(meta.get("index"), int) else None
        # The result's structured run id names the spawning call. A run an abandoned call started stays out, even when an
        # active call mentions it; otherwise the run id in the input or text of a call whose result names no run of its
        # own is the fallback.
        spawn = next((call for call in spawns if run_id in unit.runs.get(call.id, [])), None)
        if spawn is None and run_id not in abandoned_runs:
            spawn = next((call for call in spawns if not unit.runs.get(call.id)
                          and (run_id in json.dumps(call.input) or run_id in (call.output or ""))), None)
        if spawn is None and run_id in abandoned:
            continue
        tasks = spawn.input.get("tasks") if spawn else None
        pattern = _evidence(context, child.cwd)
        if pattern and isinstance(tasks, list) and child.task_index is not None and child.task_index < len(tasks) \
                and pattern.search(json.dumps(tasks[child.task_index], default=str)):
            child.evidence.append("its task names the branch or PR")
        if spawn:
            spawn.links_to = run_id
            if spawn.subagent is None:
                spawn.subagent = child
            else:
                spawn.more_subagents.append(child)
        else:
            unit.teammates.append(child)
    return unit


def find_sessions(context: RepoContext, root: Path | None = None) -> list[Path]:
    """Session files modified since the branch started that ran in a worktree on the branch, mention the branch while in
    this repository, or mention the PR."""
    root = root or sessions_root()
    if not root.is_dir():
        return []
    found = []
    for path in root.glob("*/*.jsonl"):
        if not is_recent(path, context.since):
            continue
        try:
            with path.open(encoding="utf-8", errors="replace") as handle:
                first = handle.readline()
                header = json.loads(first) if first.strip() else {}
                cwd = str(header.get("cwd") or "") if isinstance(header, dict) else ""
                if context.in_worktree_on_branch(cwd):
                    found.append(path)
                    continue
                pattern = _evidence(context, cwd)
                if pattern and (pattern.search(first) or any(pattern.search(line) for line in handle)):
                    found.append(path)
        except (OSError, json.JSONDecodeError):
            continue
    # A lead whose only tie to the branch is a pi-subagents child: the child ran in a worktree on the branch, or its
    # transcript names the work.
    for meta_path in root.glob("*/subagent-artifacts/*_meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            transcript = Path(str(meta.get("transcriptPath") or meta_path.with_name(meta_path.name.replace("_meta.json", "_transcript.jsonl"))))
            if transcript.stat().st_mtime < context.since:
                continue
            parent = str(meta.get("parentSessionId", ""))
            child_entries = _child_entries(transcript)
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
        child_cwd = str(child_entries[0].get("cwd") or "")
        pattern = _evidence(context, child_cwd)
        matched = context.in_worktree_on_branch(child_cwd) or bool(
            pattern and any(pattern.search(json.dumps(entry)) for entry in child_entries))
        if matched and parent:
            found.extend(path for path in meta_path.parent.parent.glob(f"*_{parent}.jsonl") if path not in found)
    return sorted(found, key=lambda candidate: candidate.stat().st_mtime)
