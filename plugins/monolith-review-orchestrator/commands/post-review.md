---
description: Draft a polished, teaching-oriented monolith final review for worker-owned GitHub publication, with inline comments only when the diff anchor is stable.
---

Use the `monolith-review-orchestrator` skill.

Operate in posting mode:
- load the latest local review artifacts and PR context
- load the latest compact review context before drafting the final review
- validate that the live PR heads still match the latest recorded batch state
- require a prior substantive pass on the exact same heads before posting
- treat thread-resolution status as reliable when it came from the orchestrator's
  thread-aware `fetch_review_threads.py` helper
- keep one authoritative top-level review per PR
- remember the Phase 2a split: Codex drafts, worker revalidates, worker
  publishes
- dedupe against existing comments conservatively
- add inline comments only for distinct root-cause findings with genuinely
  stable diff anchors
- prefer simple single-line `RIGHT`-side anchors when possible
- use multi-line anchors only when the location is unambiguous
- if an inline anchor is uncertain or likely stale, fold that point into the
  top-level review body instead
- explain risk and concrete next step in every serious comment
- approve only when no legitimate blocking issues remain
- do not imply support for thread replies or partial inline publication
