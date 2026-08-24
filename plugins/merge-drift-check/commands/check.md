---
description: "Detect merge resolution drift: version metadata, unrelated file regression, lockfile/build-artifact drift, and PR description accuracy."
---

Use your `merge-drift-check` Skill to detect silent regressions from merge
resolution, following the workflow in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:
1. Check pyproject.toml version against the PR base branch.
2. Audit uv.lock or yarn.lock for unintended churn/internal inconsistency.
3. Check WhiteLabel assets for dynamic URL vs hardcoded S3 regression.
4. Audit fixture/conftest/build-artifact regression (ty/build can fail CI).
5. Check config constants and package metadata for unintended changes.
6. Verify PR description matches actual branch state.
