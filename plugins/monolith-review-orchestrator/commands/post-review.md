---
description: Post a polished, teaching-oriented monolith review to GitHub, including inline comments when justified and an approval only when the final verdict is clean.
---

Use the `monolith-review-orchestrator` skill.

Operate in posting mode:
- load the latest local review artifacts and PR context
- load the latest compact review context before drafting the final review
- validate that the live PR heads still match the latest recorded batch state
- require a prior substantive pass on the exact same heads before posting
- treat thread-resolution status as reliable when it came from the orchestrator's
  thread-aware `fetch_review_threads.py` helper
- dedupe against existing comments conservatively
- keep one authoritative top-level review per PR
- add inline comments only for distinct root-cause findings
- explain risk and concrete next step in every serious comment
- approve only when no legitimate blocking issues remain
- in v1, prefer backend posting paths that can reuse Monty posting/memory
  machinery
