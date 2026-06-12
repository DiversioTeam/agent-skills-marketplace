---
name: release-manager
description: "Create and manage promotion and release PRs for Django4Lyfe. Use this when preparing staging promotion PRs (dev→release), production release PRs (release→master), bumping versions, resolving merge conflicts, and publishing GitHub releases. Handles the full three-branch workflow."
allowed-tools: Bash Read Edit Grep Glob
argument-hint: "[action] (e.g., promote-staging, release-prod, publish, check)"
---

# Release Manager Skill

Manages the full release workflow for Django4Lyfe backend releases.

## Branch Model

```
feature PRs
    │  merge to dev (validation only, no deploy)
    ▼
   dev    ── integration branch
    │  promotion PR (dev → release) → staging deploy
    ▼
release   ── staging promotion branch
    │  release PR (release → master) → production deploy
    ▼
master    ── production branch
```

## When to Use This Skill

- Creating **promotion PRs** from `dev` → `release` to deploy staging
- Creating **release PRs** from `release` → `master` to deploy production
- Preparing hotfix releases
- Bumping versions in pyproject.toml
- Resolving merge conflicts between branches
- Publishing GitHub releases after PRs are merged
- Checking what commits are pending promotion or release

## Core Workflow

### 0. Promotion PR: dev → release (Staging Deploy)

Before a production release, promote changes from the integration branch to
the staging branch. This is the ONLY path that triggers staging deploy.

```bash
# 1. Check what's on dev but not yet on release
git fetch origin dev release
git diff --stat origin/release origin/dev

# 2. Create promotion branch from release
git checkout -b promote/YYYY.MM.DD[-N] origin/release

# 3. Merge dev into it
git merge origin/dev --no-edit

# 4. Push and create promotion PR
git push -u origin promote/YYYY.MM.DD[-N]
gh pr create --base release --title "Promotion: DDth Month YYYY" --body "..."
```

**Why this exists**: Routine feature PRs merge into `dev` with validation only
— no staging deploy.  The promotion PR is the intentional gate that says
"these changes are ready for staging."  Merging the promotion PR into
`release` triggers `run_staging_deploy=true` in CI.

**After merge**: Validate staging.  If issues are found, fix them on `dev` and
create a new promotion PR.  Do not fix directly on `release`.

### 1. Check What Needs Releasing (release → master)

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

### 7. Merge Master Back Into Release AND Dev

**This step is mandatory after every release PR merge.** It keeps the branches
in sync so future releases start from a consistent baseline.

```bash
git fetch origin
git checkout release
git merge origin/master --no-edit
git push origin release

# ALSO sync dev so the integration branch stays current with production
git checkout dev
git merge origin/release --no-edit
git push origin dev
```

**Why this matters**: After a release PR merges into master, master has a merge
commit and a version-bump commit that release and dev don't. Without merge-back,
`git diff --stat origin/master origin/release` shows the version bump as a
pending difference.  Without the dev sync, the integration branch drifts from
production, and subsequent feature branches are developed against a stale base.

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
9. **Always merge master back into release AND dev after publish** — Run `git merge origin/master --no-edit` on release, then merge release into dev. Without this, the version bump stays only on master, causing stale diffs and future merge conflicts.
10. **Never squash-merge release PRs** — Release PRs to master MUST use "Create a merge commit". Squash merging breaks commit ancestry tracking.
11. **Staging deploy only on promotion PRs** — Only a `dev → release` promotion PR triggers staging deploy. Routine feature merges to `dev` run validation only.

## Full End-to-End Example

Here's a complete example of promoting and releasing PR #2607:

```bash
# ============================================
# PHASE 1: Promote dev → release (staging)
# ============================================

# 1. Check what's on dev but not release
git fetch origin dev release
git diff --stat origin/release origin/dev

# 2. Create promotion branch and merge dev
git checkout -b promote/2026.01.21 origin/release
git merge origin/dev --no-edit
git push -u origin promote/2026.01.21
gh pr create --base release \
  --title "Promotion: 21st January 2026" \
  --body "- https://github.com/DiversioTeam/Django4Lyfe/pull/2607"

# 3. After promotion PR is merged, staging deploy triggers automatically.
#    Validate staging before proceeding.

# ============================================
# PHASE 2: Release release → master (production)
# ============================================

# 4. Check what needs releasing
git fetch origin master release
git diff --stat origin/master origin/release
# Output shows files changed — confirms there IS something to release

# 5. Identify which PRs are included
LAST_RELEASE_DATE=$(gh pr list --base master --state merged --limit 100 \
  --json number,title,mergedAt \
  --jq '[.[] | select(.title | test("^(Release|Hotfix)"))] | sort_by(.mergedAt) | last | .mergedAt // empty' \
  2>/dev/null || echo "")
gh pr list --base release --state merged --limit 100 --json number,title,mergedAt \
  --jq "[.[] | select(.mergedAt > \"${LAST_RELEASE_DATE}\")] | sort_by(.mergedAt) | .[] | \"#\\(.number): \\(.title)\""
# Output: #2607: #GH-4420: Include alert notifications in Slack App Home

# 6. Create branch from master and merge release
git checkout -b releases/2026.01.21 origin/master
git merge origin/release --no-edit

# 7. Bump version
sed -i '' 's/version = ".*"/version = "2026.01.21"/' pyproject.toml
uv lock
git add pyproject.toml uv.lock
git commit -m "Version bump to 2026.01.21"

# 8. Push and create release PR
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

# 10. Merge master back into release AND dev (MANDATORY)
git fetch origin
git checkout release
git merge origin/master --no-edit
git push origin release
git checkout dev
git merge origin/release --no-edit
git push origin dev

# 11. Verify
gh release list --limit 3
git diff --stat origin/master origin/release  # Should be empty
git diff --stat origin/release origin/dev      # Should be empty
```

## Quick Reference Commands

```bash
# Check what's pending promotion (dev → release)
git fetch origin dev release && git diff --stat origin/release origin/dev

# Check what's pending release (release → master)
git fetch origin master release && git diff --stat origin/master origin/release

# Check all three branches are in sync (should all be empty after release)
git fetch origin dev release master && \
  git diff --stat origin/release origin/dev && \
  git diff --stat origin/master origin/release

# Identify new PRs since last release
LAST_RELEASE_DATE=$(gh pr list --base master --state merged --limit 100 \
  --json number,title,mergedAt \
  --jq '[.[] | select(.title | test("^(Release|Hotfix)"))] | sort_by(.mergedAt) | last | .mergedAt // empty' \
  2>/dev/null || echo "") && \
  gh pr list --base release --state merged --limit 100 --json number,title,mergedAt \
    --jq "[.[] | select(.mergedAt > \"${LAST_RELEASE_DATE}\")] | sort_by(.mergedAt) | .[] | \"#\\(.number): \\(.title)\""

# Create promotion PR (dev → release, triggers staging deploy)
git checkout -b promote/YYYY.MM.DD[-N] origin/release
git merge origin/dev --no-edit
git push -u origin promote/YYYY.MM.DD[-N]
gh pr create --base release --title "Promotion: DDth Month YYYY"

# Create release PR (release → master, triggers production deploy)
git checkout -b releases/YYYY.MM.DD[-N] origin/master
git merge origin/release --no-edit
# (bump version, uv lock, commit, then:)
gh pr create --base master --title "Release: DDth Month YYYY"

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
