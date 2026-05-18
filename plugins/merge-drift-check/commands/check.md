---
description: "Detect merge resolution drift: version metadata, unrelated file regression, and PR description accuracy."
---

Use your `merge-drift-check` Skill to detect silent regressions from merge
resolution, following the workflow in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:
1. Check pyproject.toml version against origin/release.
2. Audit uv.lock for unintended lock churn.
3. Check WhiteLabel assets for dynamic URL vs hardcoded S3 regression.
4. Audit fixture type cleanup regression (ty will fail CI).
5. Check config constants for unintended changes.
6. Verify PR description matches actual branch state.
