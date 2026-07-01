---
description: Publish a GitHub release after a release PR has been merged.
---

Use your `release-manager` Skill in **publish** mode.

After a release PR is merged to master, this command:

1. Verifies the PR is actually merged
2. If the repo exposes `scripts/deploy/trigger_validated_backend_deploy.sh`,
   runs that helper from the exact clean `origin/master` head because it
   validates with local-ci and then triggers deploy; otherwise, if the repo
   supports local-ci, validates that head locally and follows the repo-local
   deploy path
3. Gets the PR body (list of included PRs)
4. Creates a GitHub release with matching tag
5. Merges master back into release to keep branches in sync

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
- Production deploy does **not** start on PR merge; if the validated deploy helper exists, prefer it from the exact clean `origin/master` checkout because it runs local-ci and then triggers deploy; otherwise validate that head and follow the repo-local deploy path
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
