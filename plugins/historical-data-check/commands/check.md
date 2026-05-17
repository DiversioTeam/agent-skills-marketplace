---
description: "Audit historical data: existing rows, legacy config reuse, rollback safety, and inverse state-clearing."
---

Use your `historical-data-check` Skill to verify fixes don't just prevent new
bad data but also handle existing stale/broken data, following the workflow
in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:
1. Identify every constrained/changed model field.
2. Assess existing DB rows for violations.
3. Trace config import path for legacy config injection (P23 — #2 most-missed).
4. Audit state writes for inverse/rollback safety.
5. Check reprocess/rollback paths for old data safety.
