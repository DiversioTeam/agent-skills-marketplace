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

**First principles — why two phases?**

The old model deployed staging on every merge to `release`:

```
old:  feature PR → release → staging deploy (every merge!)
```

This was noisy and expensive.  The new model separates concerns:

```
new:  feature PR → dev           (validation only, cheap)
      promotion PR → release     (staging deploy, intentional)
```

Routine feature PRs merge into `dev` where CI validates but never deploys.
Only a human opening a `dev → release` promotion PR triggers staging deploy.
This means:

- **Fewer staging deploys** — only when someone intentionally promotes
- **Clearer intent** — the promotion PR says "I've reviewed these changes
  and believe they're ready for staging"
- **Lower CI cost** — dev merges run `run_tests` (classifier-derived flags),
  not full `run_staging_deploy`

**After merge**: Validate staging.  If issues are found, fix them on `dev` and
create a new promotion PR.  Do not fix directly on `release` — `release`
should only receive changes through promotion PRs.

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

### 3. Version Numbering, PR Formats, Conflict Resolution, and GitHub Releases

See [detailed-procedures.md](references/detailed-procedures.md) for:

- Version numbering conventions (`YYYY.MM.DD[-N]`)
- PR title patterns (Promotion, Release, Hotfix)
- Resolving merge conflicts
- Publishing GitHub releases (merge strategy, verification, creation)

### 4. Merge Master Back Into Release AND Dev

**This step is mandatory after every release PR merge.** It keeps all three
branches in sync so future work starts from a consistent baseline.

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

**First principles — why sync all three?**

After a production release, the branches look like this:

```
master   ── has: release content + version bump + merge commit
release  ── has: release content (stale — missing version bump)
dev      ── has: release content (stale — missing version bump)
```

The sync cascade fixes this:

```
master ─────────────────────────────┐
  │ merge master → release          │
  ▼                                 │
release  (now has version bump) ────┤
  │ merge release → dev             │
  ▼                                 │
dev      (now has version bump) ────┘
```

Without syncing to release: the next release PR sees a stale diff
(`git diff --stat origin/master origin/release` shows the version bump as
"pending") and the release merge conflicts on `pyproject.toml`/`uv.lock`.

Without syncing to dev: the integration branch drifts from production, and
subsequent feature branches are developed against code that doesn't match
what's actually running in production.

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

When reporting promotion PR status:

```
Created: https://github.com/DiversioTeam/Django4Lyfe/pull/XXXX

**Summary:**
- Type: Promotion (dev → release, triggers staging deploy)
- Title: "Promotion: DDth Month YYYY"
- Target: `release`
- Conflicts: None / Resolved
```

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

See [detailed-procedures.md](references/detailed-procedures.md#full-end-to-end-example) for a
complete walkthrough of both phases (promotion + release) with copy-paste commands.

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

See [detailed-procedures.md](references/detailed-procedures.md#error-recovery) for merge conflict
resolution, wrong-version fixes, and wrong-base PR recovery.
