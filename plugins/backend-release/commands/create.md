---
description: Create a release PR against master using the clean cherry-pick method.
---

Use your `release-manager` Skill in **create** mode.

Creates a release PR using the clean cherry-pick method:

1. Creates branch from `origin/master`
2. Cherry-picks new commits from release branch
3. Bumps version in `pyproject.toml` (YYYY.MM.DD format)
4. Runs `uv lock` to update lock file
5. Pushes and creates PR against `master`

**Version numbering:**
| Scenario | Format | Example |
|----------|--------|---------|
| First release of day | `YYYY.MM.DD` | `2026.01.21` |
| Second release | `YYYY.MM.DD-2` | `2026.01.21-2` |
| Third release | `YYYY.MM.DD-3` | `2026.01.21-3` |

**PR title patterns:**
- Regular: `Release: 21st January 2026`
- Multiple same-day: `Release 2: 21st January 2026`
- Hotfix: `Hotfix Release: 21st January 2026`

**Flags:**
- `--hotfix` - Mark as hotfix release
- `--dry-run` - Show what would be done without executing

**Pre-release checks:**
- Runs `./.security/ruff_pr_diff.sh`
- Checks RLS policies with `.bin/django optimo_bootstrap_support_shell_rls`

See the SKILL.md for full workflow details.
