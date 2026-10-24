"""Claude Code session discovery and parsing.

Layout: ~/.claude/projects/<cwd with non-alphanumerics as '-'>/<session>.jsonl holds the main thread. Beside it,
<session>/subagents/agent-<id>.jsonl holds each subagent or agent-team teammate, with agent-<id>.meta.json naming it
(`toolUseId` links a subagent to the Agent call that started it; teammates have `taskKind: in_process_teammate`).
Assistant records hold one content block each, so usage is counted once per message id.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from pathlib import Path

from provenance import Provenance
from redaction import withheld_reason
from repo_context import RepoContext
from session_model import Item, Tokens, ToolCall, Turn, Unit

HARNESS = "Claude Code"
_REMINDER = re.compile(r"<system-reminder>[\s\S]*?</system-reminder>")
_TEAMMATE = re.compile(r"<teammate-message\s+teammate_id=\"(?P<sender>[^\"]*)\"[^>]*>(?P<body>[\s\S]*?)(?:</teammate-message>|$)")
_TAG = re.compile(r"<(?P<tag>[a-z-]+)>(?P<body>[\s\S]*?)</(?P=tag)>")


def projects_root() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(base) if base else Path.home() / ".claude") / "projects"


def _records(path: Path) -> Iterator[tuple[str, dict[str, object]]]:
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                yield line, record


def _tool_output(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif block.get("type") == "image":
                    parts.append("[image omitted]")
        return "\n".join(parts)
    return ""


_BACKGROUND_ID = re.compile(r"\bwith ID:?\s*([A-Za-z0-9_-]{4,})")
_BACKGROUND_FILE = re.compile(r"Output is being written to:?\s*(\S+?)\.?(?:\s|$)")
def _worker_link(call: ToolCall) -> str:
    """Which worker a call spawns or messages: a teammate by name (Agent's `name`, SendMessage's `to`), else a
    subagent by the Agent call's own id."""
    if call.name in ("Agent", "Task"):
        return str(call.input.get("name") or call.id)
    if call.name == "SendMessage":
        return str(call.input.get("to") or call.input.get("recipient") or "")
    return ""


def _background_handles(output: str) -> list[str]:
    return [*_BACKGROUND_ID.findall(output), *_BACKGROUND_FILE.findall(output)]


def _classify(text: str, record: dict[str, object], in_subagent: bool) -> tuple[str, str, str] | None:
    """(kind, sender, text) for a prompt-like user message, or None when it is harness noise."""
    text = _REMINDER.sub("", text).strip()
    if not text:
        return None
    if record.get("isCompactSummary"):
        return "compaction", "", text
    teammate = _TEAMMATE.search(text)
    if teammate:
        return "teammate", teammate.group("sender"), teammate.group("body").strip()
    tags = {match.group("tag"): match.group("body").strip() for match in _TAG.finditer(text)}
    if "local-command-stdout" in tags or "local-command-caveat" in tags or "local-command-stderr" in tags:
        return None
    if "command-name" in tags:
        return "developer", "", f"{tags['command-name']} {tags.get('command-args', '')}".strip()
    if "task-notification" in tags:
        return "agent", "background task", tags["task-notification"]
    origin = record.get("origin")
    if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
        return "agent", str(origin.get("name") or origin.get("kind")), text
    if in_subagent:
        return "agent", "lead", text
    return "developer", "", text


def parse_unit(path: Path, kind: str, title: str, context: RepoContext, parent_tool_use_id: str = "") -> Unit:
    session_id = path.stem if kind == "session" else path.parent.parent.name
    unit = Unit(id=path.stem, harness=HARNESS, kind=kind, title=title, session_id=session_id, path=str(path),  # type: ignore[arg-type]
                parent_tool_use_id=parent_tool_use_id)
    pending: dict[str, ToolCall] = {}
    # Background work (a task id, its output file) carries the withholding of the call that started it.
    background = Provenance()
    counted: set[str] = set()
    turn: Turn | None = None
    evidence = context.evidence_pattern()

    def current(timestamp: str, branch: str) -> Turn:
        nonlocal turn
        if turn is None:
            turn = Turn(kind="agent", sender="session start", text="", timestamp=timestamp, branch=branch)
            unit.turns.append(turn)
        return turn

    for line, record in _records(path):
        kind_ = record.get("type")
        if kind_ == "pr-link":
            # Claude Code repeats this record while the PR stays linked, so it marks the session, not a turn.
            label = f"linked to PR #{context.pr}"
            if context.pr and str(record.get("prNumber")) == str(context.pr) and record.get("prRepository") == context.repo_slug \
                    and label not in unit.evidence:
                unit.evidence.append(label)
            continue
        if kind_ not in ("user", "assistant") or record.get("isMeta"):
            continue
        timestamp = str(record.get("timestamp", ""))
        branch = str(record.get("gitBranch", ""))
        unit.started = unit.started or timestamp
        unit.ended = timestamp or unit.ended
        unit.cwd = unit.cwd or str(record.get("cwd", ""))
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if kind_ == "assistant":
            model = str(message.get("model", ""))
            if model and not model.startswith("<") and model not in unit.models:
                unit.models.append(model)
            usage = message.get("usage")
            message_id = str(message.get("id", ""))
            if isinstance(usage, dict) and message_id not in counted:
                counted.add(message_id)
                unit.tokens.add(Tokens(input=int(usage.get("input_tokens") or 0), output=int(usage.get("output_tokens") or 0),
                                       cache_read=int(usage.get("cache_read_input_tokens") or 0),
                                       cache_write=int(usage.get("cache_creation_input_tokens") or 0)))
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and str(block.get("text", "")).strip():
                    current(timestamp, branch).items.append(Item(kind="assistant", text=str(block["text"]), timestamp=timestamp))
                elif block.get("type") == "tool_use":
                    tool_input = block.get("input") if isinstance(block.get("input"), dict) else {}
                    call = ToolCall(id=str(block.get("id", "")), name=str(block.get("name", "")), input=tool_input,  # type: ignore[arg-type]
                                    timestamp=timestamp)
                    call.withheld = withheld_reason(call.name, call.input) or background.inherited(call)
                    call.links_to = _worker_link(call)
                    pending[call.id] = call
                    current(timestamp, branch).items.append(Item(kind="tool", tool=call, timestamp=timestamp))
        else:
            texts: list[str] = []
            if isinstance(content, str):
                texts.append(content)
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_result":
                    call = pending.get(str(block.get("tool_use_id", "")))
                    if call:
                        call.output = _tool_output(block.get("content"))
                        call.is_error = bool(block.get("is_error"))
                        background.record(_background_handles(call.output), call.withheld)
                elif block.get("type") == "text":
                    texts.append(str(block.get("text", "")))
                elif block.get("type") == "image":
                    texts.append("[image omitted]")
            classified = _classify("\n".join(texts), record, kind != "session") if texts else None
            if classified:
                turn_kind, sender, text = classified
                turn = Turn(kind=turn_kind, sender=sender, text=text, timestamp=timestamp, branch=branch)  # type: ignore[arg-type]
                unit.turns.append(turn)
        if evidence and kind_ != "pr-link" and evidence.search(line):
            current(timestamp, branch).evidence = True
        if context.branch and branch == context.branch:
            current(timestamp, branch).branch = branch
    if any(turn.evidence for turn in unit.turns) and not unit.evidence:
        unit.evidence.append("mentions the branch or PR")
    if any(turn.branch == context.branch for turn in unit.turns) and context.branch:
        unit.evidence.append(f"ran on branch {context.branch}")
    return unit


def _meta(path: Path) -> dict[str, object]:
    meta_path = path.with_suffix(".meta.json")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return meta if isinstance(meta, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_session(main_path: Path, context: RepoContext) -> Unit:
    """A session's main thread with its subagents nested at their call sites and its teammates attached."""
    unit = parse_unit(main_path, "session", f"Session {main_path.stem[:8]}", context)
    subagent_dir = main_path.with_suffix("") / "subagents"
    subagents: list[Unit] = []
    for path in sorted(subagent_dir.glob("agent-*.jsonl")) if subagent_dir.is_dir() else []:
        meta = _meta(path)
        tool_use_id = str(meta.get("toolUseId", ""))
        if meta.get("taskKind") == "in_process_teammate" or not tool_use_id:
            name = str(meta.get("name") or meta.get("description") or path.stem)
            teammate = parse_unit(path, "teammate", f"Teammate: {name}", context)
            teammate.worker_key = str(meta.get("name") or "")
            unit.teammates.append(teammate)
            continue
        title = f"Subagent: {meta.get('description') or meta.get('agentType') or path.stem}"
        subagent = parse_unit(path, "subagent", title, context, tool_use_id)
        subagent.worker_key = tool_use_id
        subagents.append(subagent)
    # Every Agent call in the session, its teammates and its subagents (a subagent's own Agent calls start nested
    # subagents in the same folder), so each subagent attaches to its caller wherever that is.
    calls = {item.tool.id: item.tool for owner in [unit, *unit.teammates, *subagents] for turn in owner.turns
             for item in turn.items if item.tool}
    for subagent in subagents:
        caller = calls.get(subagent.parent_tool_use_id)
        if caller is not None and caller.subagent is None:
            caller.subagent = subagent
        else:
            unit.teammates.append(subagent)
    return unit


def find_sessions(context: RepoContext, root: Path | None = None) -> list[Path]:
    """Main-thread files modified since the branch started that mention the branch or PR, or ran in its worktrees."""
    root = root or projects_root()
    if not root.is_dir():
        return []
    evidence = context.evidence_pattern()
    pattern = re.compile(evidence.pattern.encode()) if evidence else None
    worktree_dirs = {re.sub(r"[^A-Za-z0-9]", "-", str(path)) for path in context.worktrees}
    found: list[Path] = []
    for project in root.iterdir():
        if not project.is_dir():
            continue
        for path in project.glob("*.jsonl"):
            try:
                if path.stat().st_mtime < context.since:
                    continue
            except OSError:
                continue
            files = [path, *sorted((path.with_suffix("") / "subagents").glob("agent-*.jsonl"))]
            if any(_mentions(candidate, pattern, context.branch if project.name in worktree_dirs else "") for candidate in files):
                found.append(path)
    return sorted(found, key=lambda candidate: candidate.stat().st_mtime)


def _mentions(path: Path, pattern: re.Pattern[bytes] | None, branch: str) -> bool:
    branch_record = f'"gitBranch":"{branch}"'.encode() if branch else b""
    try:
        with path.open("rb") as handle:
            for line in handle:
                if branch_record and branch_record in line:
                    return True
                if pattern and pattern.search(line):
                    return True
    except OSError:
        return False
    return False
