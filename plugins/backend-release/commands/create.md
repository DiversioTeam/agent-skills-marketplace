---
description: Create a release PR against master by merging the release branch.
---

Use your `release-manager` Skill in **create** mode.

Creates a release PR by merging release into a branch from master:

1. Creates branch from `origin/master`
2. Merges `origin/release` into it
3. Bumps version in `pyproject.toml` (YYYY.MM.DD format)
4. Runs `uv lock` to update lock file
5. Pushes and creates PR against `master`

**Why merge (not cherry-pick)?** Cherry-picking creates duplicate commits with
different SHAs on master vs release. This causes `git log master..release` to
permanently show already-shipped commits as "pending". Merging preserves the
original commit objects so ancestry tracking works correctly.

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

**Merge strategy:**
- Release PRs to master MUST be merged using **"Create a merge commit"** (not squash)
- Squash merging breaks commit ancestry and causes `master..release` divergence

See the SKILL.md for full workflow details.
