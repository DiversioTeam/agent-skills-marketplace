"""Scope a session to the work behind one PR.

A lead session often runs several features through subagents and teammates. A PR's transcript shows the worker that did
its work (a subagent or teammate whose own transcript ties it to the branch or PR) and, from the lead, only what concerns
that worker: the turn that spawned it (the Agent call's description, prompt, type and name), the messages sent to it and
received from it, and the lead's prompts and narration around those calls. When the lead itself ran on the branch, its
turns on the branch are the work and stay whole. Everything else is counted as omitted.
"""

from __future__ import annotations

from repo_context import RepoContext
from session_model import Item, ToolCall, Turn, Unit


def nested_subagents(unit: Unit) -> list[Unit]:
    return [subagent for turn in unit.turns for item in turn.items if item.tool for subagent in item.tool.subagents]


def _prune_children(tool: ToolCall, keys: set[str], other_work: bool = False) -> None:
    """One call can start several children (parallel runs). When some do this work, only they stay, and the call keeps
    only their part of a multi-task payload: other tasks become placeholders, or the whole list (and any chain) is withheld
    when the children cannot be mapped to tasks. The call's own output, which carries every child's result, is withheld. With
    `other_work` (the turn delegated this work elsewhere), a call whose children all do other work loses them, its
    payload, and its result."""
    children = tool.subagents
    if not other_work and not any(child.worker_key in keys for child in children):
        return
    kept = [child for child in children if child.worker_key in keys or not child.worker_key]
    if len(kept) == len(children):
        return
    tool.subagent, tool.more_subagents = (kept[0] if kept else None), kept[1:]
    if not kept:
        # A spawn only for other work (`other_work`): its whole payload and result are that work's.
        tool.input = {"task": "[a spawn for other work, not shown]"}
        tool.withheld = tool.withheld or "results of other work"
        return
    tasks = tool.input.get("tasks")
    if isinstance(tasks, list):
        if all(child.task_index is not None for child in children):
            mine = {child.task_index for child in kept}
            tasks = [task if index in mine else "[a task for other work, not shown]" for index, task in enumerate(tasks)]
        else:
            tasks = "[withheld: tasks shared with other work]"
        tool.input = {**tool.input, "tasks": tasks}
    # pi-subagents' `chain` steps (some of them parallel groups) do not map to children safely: the whole chain is held.
    if "chain" in tool.input:
        tool.input = {**tool.input, "chain": "[withheld: chain steps shared with other work]"}
    tool.withheld = tool.withheld or "results of other work"


def _relevant(worker: Unit) -> bool:
    """A worker that did this work itself, or started one that did (at any depth)."""
    return bool(worker.evidence) or any(_relevant(child) for child in nested_subagents(worker))


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
        tool = item.tool
        if tool and ((tool.links_to and tool.links_to in keys) or any(child.worker_key in keys for child in tool.subagents)):
            _prune_children(tool, keys)
            kept.extend(pending_text)
            kept.append(item)
        pending_text = []
    return kept


# Evidence of an intermediate agent: it did not work on the branch itself, but a subagent it started did.
DELEGATED = "its subagent worked on the branch"


def _trim_to_workers(unit: Unit, keys: set[str], pattern) -> None:
    kept: list[Turn] = []
    for turn in unit.turns:
        if turn.evidence:
            kept.append(turn)
            continue
        items = _related_items(turn, keys, pattern)
        if items:
            turn.items = items
            kept.append(turn)
    unit.omitted_turns += len(unit.turns) - len(kept)
    unit.turns = kept


def slice_to_work(unit: Unit, context: RepoContext, whole: bool) -> None:
    """Keep the parts of `unit` (a top-level session) that belong to this PR's work; mutate it in place."""
    if whole:
        return
    workers = [worker for worker in [*nested_subagents(unit), *unit.teammates] if _relevant(worker)]
    keys = {worker.worker_key for worker in workers if worker.worker_key}
    # A worker that only started the one doing the work keeps just that path: its call to the worker and what led there.
    for worker in workers:
        if not worker.evidence:
            slice_to_work(worker, context, whole=False)
    pattern = context.evidence_pattern(branch=unit.branch_counts)
    kept: list[Turn] = []
    sliced = False
    for turn in unit.turns:
        if context.branch and turn.branch == context.branch:
            kept.append(turn)
            continue
        # A turn that names the branch or PR itself is part of the work: it stays whole, less parallel children doing
        # other work.
        if turn.evidence:
            spawns = [item.tool for item in turn.items if item.tool and item.tool.subagents]
            # When the turn hands this work to particular workers, its other spawns are other work.
            delegated = any(child.worker_key in keys for tool in spawns for child in tool.subagents)
            for tool in spawns:
                _prune_children(tool, keys, other_work=delegated)
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
    # An intermediate agent kept only because something it started did the work is trimmed like a lead: its turns
    # that spawned or messaged those workers stay, its unrelated work goes.
    for teammate in unit.teammates:
        if teammate.evidence and all(evidence == DELEGATED for evidence in teammate.evidence):
            _trim_to_workers(teammate, keys, context.evidence_pattern(branch=teammate.branch_counts))
    if keys and (sliced or unit.omitted_turns) and not any(turn.branch == context.branch for turn in kept):
        unit.title = f"{unit.title}: only the parts about this work"
    if kept and unit.omitted_turns:
        unit.started = kept[0].timestamp
        last = kept[-1]
        unit.ended = max([last.timestamp, *(item.timestamp for item in last.items if item.timestamp)])
