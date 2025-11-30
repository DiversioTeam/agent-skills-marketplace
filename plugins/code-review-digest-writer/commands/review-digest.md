---
description: Generate a code review digest using the code-review-digest-writer Skill.
---

Use your `code-review-digest-writer` Skill to generate a code review digest for
this repository over a user-specified date range.

Before running, ask the user for:
- Start date (`YYYY-MM-DD`).
- End date (`YYYY-MM-DD`).

Then:
- Collect and synthesize PR review comments (human and AI) for that window.
- Follow any project-specific `docs/review-digests/AGENTS.md` rules if present.
- Write a markdown digest file under `docs/review-digests/END_DATE.md` with
  themes, examples, and `[NEW]` / `[REPEAT]` tags as described in the Skill.

