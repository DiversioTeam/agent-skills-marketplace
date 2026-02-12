---
description: Publish a GitHub release after a release PR has been merged.
---

Use your `release-manager` Skill in **publish** mode.

After a release PR is merged to master, this command:

1. Verifies the PR is actually merged
2. Gets the PR body (list of included PRs)
3. Creates a GitHub release with matching tag
4. Merges master back into release to keep branches in sync

**Arguments:**
- `[PR_NUMBER]` - The merged release PR number

**GitHub release title patterns:**
| Release Type | Tag | Title |
|--------------|-----|-------|
| First of day | `2026.01.21` | `January 21st 2026` |
| Second release | `2026.01.21-2` | `Release 2: January 21st 2026` |
| Third release | `2026.01.21-3` | `Release 3: January 21st 2026` |
| Hotfix | `2026.01.21` | `Hotfix Release: January 21st 2026` |

**Example:**
```bash
/backend-release:publish 2608
```

**Important:**
- Tag must match version in `pyproject.toml`
- Release notes contain the list of PR URLs from the release PR body
- Always verify with `gh release list --limit 3` after publishing
- **Always merge master back into release** after publishing — without this, `git diff --stat origin/master origin/release` shows the version bump as a pending difference and the next release merge will conflict on `pyproject.toml` / `uv.lock`. The publish step does this automatically:
  ```bash
  git fetch origin
  git checkout release
  git merge origin/master --no-edit
  git push origin release
  ```

See the SKILL.md for complete workflow.
