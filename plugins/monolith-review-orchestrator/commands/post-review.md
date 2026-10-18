---
description: Draft a polished, teaching-oriented monolith final review for worker-owned GitHub publication, with inline comments only when the diff anchor is stable.
---

Use the `monolith-review-orchestrator` skill.

Operate in posting mode:
- load the latest local review artifacts and PR context
- load the latest compact review context before drafting the final review
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
- follow the conversation protocol: confirm fixes, withdraw what pushback
  disproved, answer the exact argument when a finding still applies, and
  verify other people's points before agreeing or kindly disagreeing
- write in a cheerful, teaching voice and pair findings with suggested
  directions, offered as something to explore
- when the review asks for changes, end the body with the re-review steps:
  push the fix, then reply in each of the reviewer's threads; no resolving or
  re-requesting is needed
- thread replies are published by the Temporal auto-reviewer only; in a manual
  post, answer the discussion in an "Earlier discussion" section of the body
