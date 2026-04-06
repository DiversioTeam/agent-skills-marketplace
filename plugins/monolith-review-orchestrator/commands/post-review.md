---
description: Post a polished monolith review to GitHub, including inline comments when justified and an approval only when the final verdict is clean.
---

Use the `monolith-review-orchestrator` skill.

Operate in posting mode:
- load the latest local review artifacts and PR context
- treat thread-resolution status as reliable only when a dedicated helper exists
- dedupe against existing comments conservatively
- keep one authoritative top-level review per PR
- add inline comments only for distinct root-cause findings
- approve only when no legitimate blocking issues remain
- in v1, prefer backend posting paths that can reuse Monty posting/memory
  machinery
