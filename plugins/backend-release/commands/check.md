---
description: Check what commits are pending release (on release branch but not on master).
---

Use your `release-manager` Skill in **check** mode.

Shows commits that are on the `release` branch but not yet on `master`:

```bash
git fetch origin master release
git log origin/master..origin/release --oneline
```

Also checks:
- Current version in `pyproject.toml`
- Recent releases for version numbering context
- Any pending release PRs

**Output:**
- List of commits pending release
- Current version
- Recommended next version (YYYY.MM.DD format)

Use this before creating a release to understand what will be included.
