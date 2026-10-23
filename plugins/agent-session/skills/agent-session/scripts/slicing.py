"""Scope a session to the work behind one PR.

A lead session often runs several features through subagents and teammates. A PR's transcript shows the worker that did
its work (a subagent or teammate whose own transcript ties it to the branch or PR) and, from the lead, only what concerns
that worker: the turn that spawned it (the Agent call's description, prompt, type and name), the messages sent to it and
received from it, and the lead's prompts and narration around those calls. When the lead itself ran on the branch, its
turns on the branch are the work and stay whole. Everything else is counted as omitted.
"""

from __future__ import annotations

from repo_context import RepoContext
from session_model import Item, Turn, Unit


def nested_subagents(unit: Unit) -> list[Unit]:
    return [item.tool.subagent for turn in unit.turns for item in turn.items if item.tool and item.tool.subagent]


def _related_items(turn: Turn, keys: set[str], pattern) -> list[Item]:
    """The calls that spawn or message a worker, the lead's text just before them, and text that names the work."""
    kept: list[Item] = []
    pending_text: list[Item] = []
    for item in turn.items:
        if item.kind == "assistant":
            if pattern and pattern.search(item.text):
                kept.extend(pending_text)
                pending_text = []
                kept.append(item)
            else:
                pending_text.append(item)
            continue
        if item.tool and item.tool.links_to and item.tool.links_to in keys:
            kept.extend(pending_text)
            kept.append(item)
        pending_text = []
    return kept


def slice_to_work(unit: Unit, context: RepoContext, whole: bool) -> None:
    """Keep the parts of `unit` (a top-level session) that belong to this PR's work; mutate it in place."""
    if whole:
        return
    workers = [worker for worker in [*nested_subagents(unit), *unit.teammates] if worker.evidence]
    keys = {worker.worker_key for worker in workers if worker.worker_key}
    pattern = context.evidence_pattern()
    kept: list[Turn] = []
    sliced = False
    for turn in unit.turns:
        if context.branch and turn.branch == context.branch:
            kept.append(turn)
            continue
        # A turn that names the branch or PR itself is part of the work: it stays whole.
        if turn.evidence:
            kept.append(turn)
            continue
        inbound = turn.kind == "teammate" and turn.sender in keys
        items = _related_items(turn, keys, pattern)
        if items or inbound:
            sliced = sliced or len(items) < len(turn.items)
            turn.items = items
            kept.append(turn)
    # A session tied to the PR only by its pr-link record (it opened the PR from another branch) is kept whole.
    if not kept and any(evidence.startswith("linked to PR") for evidence in unit.evidence):
        return
    unit.omitted_turns = len(unit.turns) - len(kept)
    unit.turns = kept
    unit.teammates = [teammate for teammate in unit.teammates if teammate in workers]
    if keys and (sliced or unit.omitted_turns) and not any(turn.branch == context.branch for turn in kept):
        unit.title = f"{unit.title}: only the parts about this work"
    if kept and unit.omitted_turns:
        unit.started = kept[0].timestamp
        last = kept[-1]
        unit.ended = max([last.timestamp, *(item.timestamp for item in last.items if item.timestamp)])
