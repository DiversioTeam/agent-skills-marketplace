---
name: release-manager
description: "Create and manage release PRs against master branch. Use this when preparing releases, bumping versions, resolving merge conflicts, and publishing GitHub releases. Handles the full release workflow including merging release into master, version bumping in pyproject.toml, running uv lock, and creating GitHub releases."
allowed-tools: Bash Read Edit Grep Glob
argument-hint: "[action] (e.g., create, publish, check)"
---

# Release Manager Skill

Manages the full release workflow for Django4Lyfe backend releases to production.

## When to Use This Skill

- Creating release PRs against master branch
- Preparing hotfix releases
- Bumping versions in pyproject.toml
- Resolving merge conflicts between release and master
- Publishing GitHub releases after PRs are merged
- Checking what commits are on release but not on master

## Core Workflow

### 1. Check What Needs Releasing

```bash
git fetch origin master release

# PRIMARY CHECK — are there actual code differences between the branches?
git diff --stat origin/master origin/release
```

`git diff --stat` compares the actual tree state (file contents), not commit
history. It is the only reliable way to determine whether there is something to
release. If the output is empty, there is nothing to release — stop here.

If there ARE differences, identify which PRs they belong to. Use GitHub's PR
metadata (merge timestamps), not git commit ancestry:

```bash
# Get the merge date of the last release PR (the definitive cutoff).
# The release PR's merge to master is the exact moment `git merge origin/release`
# captured the release branch state. Anything merged to release BEFORE that
# moment was included; anything AFTER is genuinely new.
LAST_RELEASE_DATE=$(gh pr list --base master --state merged --limit 100 \
  --json number,title,mergedAt \
  --jq '[.[] | select(.title | test("^(Release|Hotfix)"))] | sort_by(.mergedAt) | last | .mergedAt // empty' \
  2>/dev/null || echo "")

# List PRs merged to release since that date
if [ -n "${LAST_RELEASE_DATE}" ]; then
  gh pr list --base release --state merged --limit 100 --json number,title,mergedAt \
    --jq "[.[] | select(.mergedAt > \"${LAST_RELEASE_DATE}\")] | sort_by(.mergedAt) | .[] | \"#\\(.number): \\(.title)\""
else
  # No previous release — list recent merged PRs as candidates
  gh pr list --base release --state merged --limit 20 --json number,title \
    --jq '.[] | "#\(.number): \(.title)"'
fi
```

**Why the release PR's `mergedAt` instead of `publishedAt`?** GitHub release
`publishedAt` is when a human clicks "Publish" — which can be minutes or hours
after the release PR actually merges. PRs merged to release in that gap would
be missed on the next check. The release PR's `mergedAt` is the definitive
cutoff because `git merge origin/release` captures the exact state of the
release branch at that moment.

**Why GitHub metadata instead of `git log`?** All `git log`-based approaches
(`master..release`, `--cherry-pick`, `--first-parent` with tags) can return
stale results due to historical cherry-pick artifacts and because release tags
live on master's ancestry, not release's first-parent chain. PR merge
timestamps from GitHub are immune to git ancestry issues.

### 2. Create Release PR (Merge Method)

Merge the release branch into a branch from master. This preserves commit
ancestry so that `git log master..release` works correctly after the PR merges.

```bash
# 1. Create branch from master
git checkout -b releases/YYYY.MM.DD[-N] origin/master

# 2. Merge release into it
git merge origin/release --no-edit

# 3. Bump version in pyproject.toml
# Format: YYYY.MM.DD for first release, YYYY.MM.DD-N for subsequent releases

# 4. Update lock file
uv lock

# 5. Commit version bump
git add pyproject.toml uv.lock
git commit -m "Version bump to YYYY.MM.DD[-N]"

# 6. Push and create PR
git push -u origin releases/YYYY.MM.DD[-N]
gh pr create --base master --title "Release: DDth Month YYYY" --body "..."
```

**Why merge instead of cherry-pick?** Cherry-picking creates new commits with
different SHAs. Even with merge-back, `git log master..release` permanently
shows the original commits as "pending" because git compares SHAs, not patches.
Merging preserves the original commit objects so master and release share the
same ancestry. After the release PR merges to master, `git log master..release`
correctly shows only genuinely new commits.

### 3. Version Numbering Convention

| Scenario | Version Format | Example |
|----------|---------------|---------|
| First release of day | `YYYY.MM.DD` | `2026.01.21` |
| Second release | `YYYY.MM.DD-2` | `2026.01.21-2` |
| Third release | `YYYY.MM.DD-3` | `2026.01.21-3` |
| Hotfix release | `YYYY.MM.DD` or `YYYY.MM.DD-N` | `2026.01.21` |

### 4. PR Title and Body Format

**Title patterns:**
- Regular release: `Release: 21st January 2026`
- Multiple same-day: `Release 2: 21st January 2026`
- Hotfix: `Hotfix Release: 21st January 2026`

**Body format:**
```markdown
- https://github.com/DiversioTeam/Django4Lyfe/pull/XXXX
- https://github.com/DiversioTeam/Django4Lyfe/pull/YYYY
```

### 5. Resolve Conflicts (If Any)

If the merge has conflicts:

```bash
# 1. Edit conflicted files to keep correct changes
# 2. For uv.lock conflicts, regenerate:
git checkout --theirs uv.lock
uv lock

# 3. Stage resolved files
git add <resolved-files>

# 4. Complete merge
git commit -m "Merge origin/release into releases/YYYY.MM.DD"
```

### 6. Publish GitHub Release

After PR is merged to master, create a GitHub release.

**IMPORTANT: Merge Strategy** — Release PRs to master MUST be merged using
**"Create a merge commit"** (not squash). Squash merging breaks commit ancestry
and causes `master..release` to grow unboundedly. If GitHub is configured to
allow multiple merge strategies, always select "Create a merge commit" for
release PRs.

#### Step 1: Verify PR is merged

```bash
gh pr view <PR_NUMBER> --json state,mergeCommit,mergedAt
# Should show: "state": "MERGED"
```

#### Step 2: Check recent releases for format consistency

```bash
gh release list --limit 5
```

#### Step 3: Get PR details for release notes

```bash
# Get the PR body which contains the list of included PRs
gh pr view <PR_NUMBER> --json body,title
```

#### Step 4: Create the GitHub release

```bash
gh release create YYYY.MM.DD[-N] \
  --title "Release Title" \
  --notes "$(cat <<'EOF'
- https://github.com/DiversioTeam/Django4Lyfe/pull/XXXX
- https://github.com/DiversioTeam/Django4Lyfe/pull/YYYY
EOF
)" \
  --target master
```

#### GitHub Release Title Patterns

| Release Type | Tag | Title |
|--------------|-----|-------|
| First of day | `2026.01.21` | `January 21st 2026` |
| Second release | `2026.01.21-2` | `Release 2: January 21st 2026` |
| Third release | `2026.01.21-3` | `Release 3: January 21st 2026` |
| Hotfix | `2026.01.21` | `Hotfix Release: January 21st 2026` |

#### Step 5: Verify release was created

```bash
gh release list --limit 3
# Or view specific release:
gh release view YYYY.MM.DD[-N]
```

#### Complete Example

```bash
# 1. Check PR is merged
gh pr view 2608 --json state,mergeCommit,mergedAt

# 2. Create release (using heredoc for multi-line notes)
gh release create 2026.01.21 \
  --title "January 21st 2026" \
  --notes "$(cat <<'EOF'
- https://github.com/DiversioTeam/Django4Lyfe/pull/2607
EOF
)" \
  --target master

# 3. Verify
gh release list --limit 3
```

### 7. Merge Master Back Into Release

**This step is mandatory after every release PR merge.** It keeps the branches
in sync so that `git diff --stat origin/master origin/release` is clean and
future releases start from a consistent baseline.

```bash
git fetch origin
git checkout release
git merge origin/master --no-edit
git push origin release
```

**Why this matters**: After a release PR merges into master, master has a merge
commit and a version-bump commit that release doesn't. Without merge-back,
`git diff --stat origin/master origin/release` shows the version bump as a
pending difference, and the next `git merge origin/release` will conflict on
`pyproject.toml` / `uv.lock`. The merge-back keeps both branches aligned.

## Pre-Release Checks

Before creating a release PR, verify:

1. **Ruff formatting passes:**
   ```bash
   ./.security/ruff_pr_diff.sh
   ```
   If it fails, fix with:
   ```bash
   .bin/ruff format <file>
   ```

2. **Active Python type gate passes (strict):**
   - Detect in this order unless repo docs/CI differ:
     - `ty` (mandatory if configured)
     - `pyright`
     - `mypy`
   - Run on touched paths at minimum, and run any repo-required broad gate
     before final release readiness.

3. **RLS policies for new models:**
   ```bash
   # Check status
   .bin/django optimo_bootstrap_support_shell_rls

   # Apply if needed (safe for production)
   .bin/django optimo_bootstrap_support_shell_rls --apply
   ```

## Output Shape

When reporting release status:

```
Created: https://github.com/DiversioTeam/Django4Lyfe/pull/XXXX

**Summary:**
- Version: `YYYY.MM.DD[-N]`
- Title: "Release: DDth Month YYYY"
- Target: `master`
- Conflicts: None / Resolved

**Included PRs:**
- #XXXX - Description
- #YYYY - Description
```

When listing releases:

```
| Release | Tag | PRs Included |
|---------|-----|--------------|
| Release Name | `tag` | #PR1, #PR2 |
```

## Important Rules

1. **Always merge release into the release PR branch** — Do not cherry-pick. Merging preserves commit ancestry so `git log master..release` works correctly. Cherry-picking creates duplicate commits with different SHAs, causing stale "pending" commits that were already shipped.
2. **Never force push** — Release branches should have clean history
3. **Check date before versioning** — Use current date, not yesterday's
4. **Run uv lock after version bump** — Lock file must match pyproject.toml
5. **List all PRs in release body** — Use full GitHub URLs
6. **Verify PR is merged before publishing release** — Check with `gh pr view`
7. **Always publish GitHub release after merge** — Every merged release PR needs a corresponding GitHub release
8. **Tag must match version in pyproject.toml** — e.g., version `2026.01.21-2` = tag `2026.01.21-2`
9. **Always merge master back into release after publish** — Run `git merge origin/master --no-edit` on release after every release PR merge. Without this, the version bump stays only on master, causing `git diff --stat` to show false differences and the next release merge to conflict.
10. **Never squash-merge release PRs** — Release PRs to master MUST use "Create a merge commit". Squash merging breaks commit ancestry tracking.

## Full End-to-End Example

Here's a complete example of releasing PR #2607:

```bash
# 1. Check what needs releasing (diff is the source of truth)
git fetch origin master release
git diff --stat origin/master origin/release
# Output shows files changed — confirms there IS something to release

# 2. Identify which PRs are included (uses release PR merge date as cutoff)
LAST_RELEASE_DATE=$(gh pr list --base master --state merged --limit 100 \
  --json number,title,mergedAt \
  --jq '[.[] | select(.title | test("^(Release|Hotfix)"))] | sort_by(.mergedAt) | last | .mergedAt // empty' \
  2>/dev/null || echo "")
gh pr list --base release --state merged --limit 100 --json number,title,mergedAt \
  --jq "[.[] | select(.mergedAt > \"${LAST_RELEASE_DATE}\")] | sort_by(.mergedAt) | .[] | \"#\\(.number): \\(.title)\""
# Output: #2607: #GH-4420: Include alert notifications in Slack App Home

# 3. Check today's date
date  # Wed Jan 21 2026

# 4. Create branch from master and merge release
git checkout -b releases/2026.01.21 origin/master
git merge origin/release --no-edit

# 5. Bump version
sed -i '' 's/version = ".*"/version = "2026.01.21"/' pyproject.toml

# 6. Update lock file
uv lock

# 7. Commit version bump
git add pyproject.toml uv.lock
git commit -m "Version bump to 2026.01.21"

# 8. Push and create PR
git push -u origin releases/2026.01.21
gh pr create --base master \
  --title "Release: 21st January 2026" \
  --body "- https://github.com/DiversioTeam/Django4Lyfe/pull/2607"

# 9. After PR is merged, publish GitHub release
gh pr view 2608 --json state  # Verify merged
gh release create 2026.01.21 \
  --title "January 21st 2026" \
  --notes "- https://github.com/DiversioTeam/Django4Lyfe/pull/2607" \
  --target master

# 10. Merge master back into release (MANDATORY)
git fetch origin
git checkout release
git merge origin/master --no-edit
git push origin release

# 11. Verify release and branch sync
gh release list --limit 3
git diff --stat origin/master origin/release  # Should be empty
```

## Quick Reference Commands

```bash
# Check what's pending release (source of truth — compares actual file contents)
git fetch origin master release && git diff --stat origin/master origin/release

# Identify new PRs (uses last release PR's merge date as cutoff)
LAST_RELEASE_DATE=$(gh pr list --base master --state merged --limit 100 \
  --json number,title,mergedAt \
  --jq '[.[] | select(.title | test("^(Release|Hotfix)"))] | sort_by(.mergedAt) | last | .mergedAt // empty' \
  2>/dev/null || echo "") && \
  gh pr list --base release --state merged --limit 100 --json number,title,mergedAt \
    --jq "[.[] | select(.mergedAt > \"${LAST_RELEASE_DATE}\")] | sort_by(.mergedAt) | .[] | \"#\\(.number): \\(.title)\""

# Check current version
grep '^version' pyproject.toml

# List recent releases
gh release list --limit 10

# Check PR status
gh pr view <NUMBER> --json state,mergeable,mergeCommit

# View release details
gh release view <TAG> --json body,tagName,name
```

## Error Recovery

### Merge conflict during release branch creation
```bash
# For uv.lock conflicts:
git checkout --theirs uv.lock
uv lock
git add uv.lock

# For code conflicts: resolve manually, then:
git add <resolved-files>
git commit  # Completes the merge
```

### Wrong version bumped
```bash
# Edit pyproject.toml to correct version
uv lock
git add pyproject.toml uv.lock
git commit --amend -m "Version bump to correct-version"
git push --force-with-lease  # Only if not yet reviewed
```

### PR created against wrong base
```bash
gh pr close <NUMBER>
# Create new PR with correct base
gh pr create --base master ...
```
