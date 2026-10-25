"""Codex session discovery and parsing.

Layout: ~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<thread id>.jsonl (or $CODEX_HOME/sessions). The first record
is `session_meta`: `cwd`, `git.branch`, `git.repository_url`, and for subagents `parent_thread_id` (or
`source.subagent.thread_spawn.parent_thread_id`), `agent_nickname`, `agent_role`, and `subagent_history_start_ordinal`
(a subagent's file starts with a copy of its parent's history; its own work starts at that ordinal). Conversation items
are `response_item` records: `message` (roles user, assistant, developer), `function_call`/`custom_tool_call`/
`local_shell_call` with `call_id`, and their `*_output`. Reasoning is encrypted and never shown. `token_count` events carry
cumulative usage.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from redaction import is_credential_path, withheld_reason
from repo_context import RepoContext, is_recent, parse_repo_slug
from slicing import DELEGATED, _trim_to_workers
from session_model import Item, Tokens, ToolCall, Turn, Unit

HARNESS = "Codex"
# Harness context Codex injects as user messages: not the developer's prompt. Only these known wrappers are dropped, so
# a prompt the developer wrapped in a tag of their own (<task>…</task>) stays.
_CONTEXT_TAGS = ("environment_context", "user_instructions", "recommended_plugins", "app-context", "app_context",
                 "permissions_instructions", "collaboration_mode", "skills_instructions", "apps_instructions", "plugins_instructions",
                 "turn_aborted", "subagent_notification", "model_switch", "realtime_context", "personality")
_CONTEXT_BLOCK = re.compile(r"^\s*<(?P<tag>" + "|".join(re.escape(tag) for tag in _CONTEXT_TAGS) + r")\b[^>]*>[\s\S]*</(?P=tag)>\s*$")
# Code-mode `exec` wraps shell calls in JavaScript: tools.exec_command({cmd: "..."}).
_NESTED_COMMAND = re.compile(r"""\b(?:cmd|command)\s*["']?\s*:\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)""")
# Code mode calls other tools too: tools.mcp__postgres__query({...}), tools["apply_patch"]("...").
_NESTED_TOOL = re.compile(r"""\btools(?:\.([A-Za-z_]\w*)|\[\s*["']([^"']+)["']\s*\])\s*\(""")
_PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (\S+)", re.MULTILINE)
_TERMINAL = re.compile(r"session ID:?\s*(\d+)", re.IGNORECASE)
# A terminal session id however the call spells it: {"session_id": 1}, {session_id: 1}, "session_id" : "1".
_TERMINAL_REF = re.compile(r"""session_id["']?\s*:\s*["']?(\d+)""")
# A code-mode script that yields leaves a cell that `wait({cell_id})` resumes; its output inherits the same way.
_CELL = re.compile(r"cell ID:?\s*([\w-]+)", re.IGNORECASE)
_CELL_REF = re.compile(r"""cell_id["']?\s*:\s*["']?([\w-]+)""")


def _terminal_refs(arguments: dict) -> list[str]:
    texts = [json.dumps(arguments, default=str), *(value for value in arguments.values() if isinstance(value, str))]
    return [handle for text in texts for handle in _TERMINAL_REF.findall(text)] + \
        [f"cell:{cell}" for text in texts for cell in _CELL_REF.findall(text)]
_CALLS = {"function_call", "custom_tool_call", "local_shell_call", "tool_search_call"}
_OUTPUTS = {"function_call_output", "custom_tool_call_output", "local_shell_call_output", "tool_search_output"}


def sessions_root() -> Path:
    base = os.environ.get("CODEX_HOME")
    return (Path(base).expanduser() if base else Path.home() / ".codex") / "sessions"


def _records(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def _meta(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            record = json.loads(handle.readline())
    except (OSError, json.JSONDecodeError):
        return {}
    payload = record.get("payload") if isinstance(record, dict) and record.get("type") == "session_meta" else None
    return payload if isinstance(payload, dict) else {}


def _parent(meta: dict) -> str:
    if meta.get("parent_thread_id"):
        return str(meta["parent_thread_id"])
    source = meta.get("source")
    spawn = source.get("subagent", {}).get("thread_spawn", {}) if isinstance(source, dict) and isinstance(source.get("subagent"), dict) else {}
    return str(spawn.get("parent_thread_id") or "")


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content if isinstance(content, list) else []:
        if isinstance(block, dict):
            if block.get("type") in ("input_text", "output_text", "text"):
                parts.append(str(block.get("text", "")))
            elif block.get("type") in ("input_image", "image"):
                parts.append("[image omitted]")
    return "\n".join(parts)


def _prompt(content: object) -> str:
    """A user message's own words, without the context blocks Codex injects."""
    blocks = content if isinstance(content, list) else [{"type": "input_text", "text": str(content or "")}]
    texts = [str(block.get("text", "")) for block in blocks if isinstance(block, dict) and block.get("type") in ("input_text", "text")]
    return "\n".join(text for text in texts if text.strip() and not _CONTEXT_BLOCK.match(text)).strip()


def _output(value: object) -> str:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        return str(parsed.get("output", value)) if isinstance(parsed, dict) else value
    return _text(value)


def _unescape(code: str) -> str:
    """JavaScript or JSON string escapes undone, so a patch inside a string literal reads as lines."""
    return code.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"').replace("\\'", "'")


_STRING_LITERAL = re.compile(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'|`((?:[^`\\]|\\.)*)`')
_JS_LITERAL_OR_KEY = re.compile(_STRING_LITERAL.pattern + r'|(?P<prefix>[{,]\s*)(?P<key>[A-Za-z_$][\w$]*)\s*:')


def _object_literal(text: str) -> object:
    """A complete JSON or simple JavaScript literal argument, not a computed expression."""
    def json_token(match: re.Match) -> str:
        if match.group("key") is not None:
            return f'{match.group("prefix")}"{match.group("key")}":'
        literal = match.group(0)
        if literal.startswith('"') or literal.startswith("`") and "${" in literal:
            return literal
        body = literal[1:-1].replace("\\'", "'").replace("\\`", "`").replace('\\"', '"')
        return '"' + body.replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t") + '"'

    for normalize in (False, True):
        try:
            candidate = _JS_LITERAL_OR_KEY.sub(json_token, text) if normalize else text
            value, end = json.JSONDecoder().raw_decode(candidate)
            if candidate[end:].lstrip().startswith(")"):
                return value
        except json.JSONDecodeError:
            continue
    return None


def _nested_tools(code: str) -> list[tuple[str, dict]]:
    """Each tool a code-mode script calls, with its arguments when they are a JSON or simple JavaScript object literal,
    else the raw text."""
    # shortcut: literal tool-call text can over-withhold; exclude it only with a proven JavaScript lexical parser.
    found = []
    for match in _NESTED_TOOL.finditer(code):
        rest = code[match.end():].lstrip()
        arguments = _object_literal(rest)
        found.append((match.group(1) or match.group(2), arguments if isinstance(arguments, dict) else {"input": rest[:2000]}))
    return found


def _call(payload: dict, timestamp: str) -> ToolCall:
    kind = payload.get("type")
    name = str(payload.get("name") or ("shell" if kind == "local_shell_call" else kind or "tool"))
    if payload.get("namespace"):
        name = f"{payload['namespace']}__{name}"
    if kind == "custom_tool_call":
        arguments: object = {"input": payload.get("input", "")}
    elif kind == "local_shell_call":
        action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
        arguments = {"command": action.get("command", "")}
    else:
        raw = payload.get("arguments", {})
        try:
            arguments = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            arguments = {"arguments": raw}
    if not isinstance(arguments, dict):
        arguments = {"arguments": arguments}
    call = ToolCall(id=str(payload.get("call_id") or payload.get("id") or ""), name=name, input=arguments, timestamp=timestamp)
    reasons = [withheld_reason(name, arguments)]
    code = arguments.get("input")
    if isinstance(code, str):
        # Classify each shell command a code-mode wrapper runs, then the whole script as a fallback for computed commands.
        nested = [literal[1:-1].replace('\\"', '"').replace("\\'", "'").replace("\\n", "\n") for literal in _NESTED_COMMAND.findall(code)]
        reasons += [withheld_reason("exec_command", {"cmd": command}) for command in [*nested, code]]
        # Non-shell tools keep their own meaning: a database tool is classified by its name, as when called directly.
        for tool, tool_input in _nested_tools(code):
            reasons.append(withheld_reason(tool, tool_input))
            command = tool_input.get("command") or tool_input.get("cmd")
            # Only literal shell arguments are inspectable; do not evaluate JavaScript to guess what ran.
            if tool in {"exec_command", "run"} and not (isinstance(command, str) or
                    isinstance(command, list) and command and all(isinstance(part, str) for part in command)):
                reasons.append("unresolved shell command")
        # Any string the script passes that names a credential file, however the call around it is spelled.
        literals = [_unescape(next(group for group in match.groups() if group is not None)) for match in _STRING_LITERAL.finditer(code)]
        patched = _PATCH_FILE.findall(code) + _PATCH_FILE.findall(_unescape(code))
        if any(is_credential_path(path) for path in [*patched, *(literal.strip() for literal in literals if "\n" not in literal)]):
            reasons.append("credential file")
    # A credential file outranks every other reason: only it also hides the call's input.
    call.withheld = "credential file" if "credential file" in reasons else next((reason for reason in reasons if reason), None)
    return call


def parse_session(path: Path, context: RepoContext, kind: str = "session") -> Unit:
    records = _records(path)
    meta = _meta(path)
    thread = str(meta.get("id") or meta.get("session_id") or path.stem)
    title = (f"Codex subagent: {meta.get('agent_nickname') or thread[:8]}" + (f" ({meta['agent_role']})" if meta.get("agent_role") else "")
             if kind == "subagent" else f"Codex session {thread[:8]}")
    unit = Unit(id=path.stem, harness=HARNESS, kind=kind, title=title, session_id=thread, path=str(path), cwd=str(meta.get("cwd", "")))  # type: ignore[arg-type]
    git = meta.get("git") if isinstance(meta.get("git"), dict) else {}
    on_branch = (git.get("branch") == context.branch and parse_repo_slug(str(git.get("repository_url", ""))) == context.repo_slug) \
        or context.in_worktree_on_branch(unit.cwd)
    start = int(meta.get("subagent_history_start_ordinal") or 0) if kind == "subagent" else 0
    markers = context.evidence_pattern()
    pending: dict[str, ToolCall] = {}
    # A long-running exec_command leaves a terminal session that write_stdin polls; the polls inherit its withholding.
    terminals: dict[str, str | None] = {}
    turn: Turn | None = None
    usage: dict = {}
    # Calls that started or messaged a subagent thread (SubAgentActivity items), by call id.
    spawned: dict[str, str] = {}

    def current(timestamp: str) -> Turn:
        nonlocal turn
        if turn is None:
            turn = Turn(kind="agent", sender="session start", text="", timestamp=timestamp)
            unit.turns.append(turn)
        return turn

    for index, record in enumerate(records):
        if int(record.get("ordinal", index) or 0) < start:
            continue
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        timestamp = str(record.get("timestamp", ""))
        kind_ = record.get("type")
        item = payload.get("item") if isinstance(payload.get("item"), dict) else {}
        if kind_ == "event_msg" and item.get("type") == "SubAgentActivity" and item.get("id") and item.get("agent_thread_id"):
            spawned[str(item["id"])] = str(item["agent_thread_id"])
        if kind_ == "turn_context" and payload.get("model") and payload["model"] not in unit.models:
            unit.models.append(str(payload["model"]))
        elif kind_ == "event_msg" and payload.get("type") == "token_count" and isinstance(payload.get("info"), dict):
            usage = payload["info"].get("total_token_usage") or usage
        elif kind_ == "response_item":
            unit.started = unit.started or timestamp
            unit.ended = timestamp or unit.ended
            item_type = payload.get("type")
            if item_type == "message" and payload.get("role") == "user":
                text = _prompt(payload.get("content"))
                if text:
                    turn = Turn(kind="agent" if kind == "subagent" and not unit.turns else "developer", sender="parent agent" if kind == "subagent" else "",
                                text=text, timestamp=timestamp, branch=context.branch if on_branch else "")
                    unit.turns.append(turn)
            elif item_type == "message" and payload.get("role") == "assistant":
                text = _text(payload.get("content"))
                if text.strip():
                    current(timestamp).items.append(Item(kind="assistant", text=text, timestamp=timestamp))
            elif item_type == "agent_message":
                text = f"To {payload.get('recipient', 'an agent')}: {_text(payload.get('content'))}"
                current(timestamp).items.append(Item(kind="assistant", text=text, timestamp=timestamp))
            elif item_type in _CALLS:
                call = _call(payload, timestamp)
                polled = [terminals[handle] for handle in _terminal_refs(call.input) if handle in terminals]
                call.withheld = call.withheld or next((reason for reason in polled if reason), None)
                pending[call.id] = call
                current(timestamp).items.append(Item(kind="tool", tool=call, timestamp=timestamp))
            elif item_type in _OUTPUTS:
                call = pending.get(str(payload.get("call_id", "")))
                if call:
                    raw = payload.get("output", payload.get("tools", ""))
                    call.output = _output(raw)
                    # The terminal a call leaves open, from the raw result ({"session_id": 1, ...}) as well as its text.
                    raw_text = raw if isinstance(raw, str) else json.dumps(raw, default=str)
                    cells = {f"cell:{cell}" for cell in [*_CELL.findall(call.output), *_CELL_REF.findall(raw_text)]}
                    for handle in {*_TERMINAL.findall(call.output), *_TERMINAL_REF.findall(raw_text), *cells}:
                        terminals[handle] = call.withheld
        if markers and turn is not None and markers.search(json.dumps(record)):
            turn.evidence = True
    for call in pending.values():
        call.links_to = spawned.get(call.id, "")
    if usage:
        cached = int(usage.get("cached_input_tokens") or 0)
        unit.tokens = Tokens(input=max(int(usage.get("input_tokens") or 0) - cached, 0), output=int(usage.get("output_tokens") or 0),
                             cache_read=cached, cache_write=int(usage.get("cache_write_input_tokens") or 0))
    if on_branch:
        unit.evidence.append(f"ran on branch {context.branch}")
        for each in unit.turns:
            each.branch = context.branch
    if any(each.evidence for each in unit.turns):
        unit.evidence.append("mentions the branch or PR")
    return unit


def find_sessions(context: RepoContext, root: Path | None = None) -> list[Path]:
    """Top-level rollouts since the branch started that ran on the branch (git metadata or worktree) or mention it."""
    root = root or sessions_root()
    if not root.is_dir():
        return []
    pattern = context.evidence_pattern()
    found = []
    for path in root.glob("*/*/*/*.jsonl"):
        if not is_recent(path, context.since):
            continue
        meta = _meta(path)
        git = meta.get("git") if isinstance(meta.get("git"), dict) else {}
        matched = (git.get("branch") == context.branch and parse_repo_slug(str(git.get("repository_url", ""))) == context.repo_slug) \
            or context.in_worktree_on_branch(str(meta.get("cwd") or ""))
        if not matched and pattern:
            try:
                with path.open(encoding="utf-8", errors="replace") as handle:
                    matched = any(pattern.search(line) for line in handle)
            except OSError:
                continue
        if not matched:
            continue
        # A subagent's work brings in its parent rollout, where the slicer keeps the turns that spawned it.
        # Walk up to the top-level rollout (a grandchild's work belongs to its lead too).
        target, parent, hops = path, _parent(meta), 0
        while parent and hops < 8:
            parents = sorted(root.glob(f"*/*/*/*-{parent}.jsonl"))
            if not parents:
                break
            target, parent, hops = parents[0], _parent(_meta(parents[0])), hops + 1
        if not parent and target not in found:
            found.append(target)
    return sorted(found, key=lambda candidate: candidate.stat().st_mtime)


def load_session(path: Path, context: RepoContext, root: Path | None = None) -> Unit:
    """A top-level rollout with every descendant subagent rollout attached (children, grandchildren, …), each from its
    own history start. A subagent whose descendants worked on the branch counts as working on it too, so the chain
    from the lead to the work stays connected."""
    unit = parse_session(path, context)
    root = root or sessions_root()
    # Index old rollouts too: a recent worker can sit behind an ancestor older than the cutoff.
    paths: dict[str, Path] = {}
    parents: dict[str, str] = {}
    recent: set[str] = set()
    for candidate in sorted(root.glob("*/*/*/*.jsonl")):
        if candidate == path:
            continue
        meta = _meta(candidate)
        thread = str(meta.get("id") or meta.get("session_id") or candidate.stem)
        paths[thread], parents[thread] = candidate, _parent(meta)
        if is_recent(candidate, context.since):
            recent.add(thread)
    needed = set(recent)
    ancestors = list(recent)
    while ancestors:
        parent = parents.get(ancestors.pop())
        if parent and parent not in needed:
            needed.add(parent)
            ancestors.append(parent)
    children: dict[str, list[Path]] = {}
    for thread, candidate in paths.items():
        if thread in needed and parents[thread]:
            children.setdefault(parents[thread], []).append(candidate)
    queue = [(unit.session_id, None)]
    attached: list[tuple[Unit, Unit | None]] = []
    while queue:
        thread, owner = queue.pop(0)
        for candidate in children.get(thread, []):
            child = parse_session(candidate, context, "subagent")
            if child.session_id not in recent:
                # An expired ancestor is only a bridge to current work, not fresh evidence of its own.
                child.evidence.clear()
                for turn in child.turns:
                    turn.evidence, turn.branch = False, ""
            child.worker_key = child.session_id
            unit.teammates.append(child)
            attached.append((child, owner))
            queue.append((child.session_id, child))
    below: dict[int, list[Unit]] = {}
    for child, owner in attached:
        if owner is not None:
            below.setdefault(id(owner), []).append(child)

    def works(child: Unit) -> bool:
        return bool(child.evidence) or any(works(grandchild) for grandchild in below.get(id(child), []))

    for child, _owner in attached:
        if not child.evidence and works(child):
            child.evidence.append(DELEGATED)
    keys = {child.worker_key for child, _owner in attached if child.evidence}
    for child, _owner in attached:
        if child.session_id not in recent:
            # Prune before shared slicing can rediscover historical branch mentions as independent evidence.
            _trim_to_workers(child, keys, pattern=None)
    return unit
