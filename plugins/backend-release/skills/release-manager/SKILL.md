---
name: release-manager
description: "Create and manage promotion and release PRs for Django4Lyfe. Use this when preparing dev→release promotion PRs, release→master release PRs, validating exact branch heads with local-ci, triggering validated backend deploys, bumping versions, resolving merge conflicts, and publishing GitHub releases."
allowed-tools: Bash Read Edit Grep Glob
argument-hint: "[action] (e.g., promote-staging, release-prod, publish, check)"
---

# Release Manager Skill

Manages the full release workflow for Django4Lyfe backend releases.

## Branch Model

```text
feature PRs -> dev        (validation only)
promotion PRs -> release  (move staging candidate)
origin/release head -> local-ci -> validated deploy helper -> staging deploy
release PRs -> master     (move production candidate)
origin/master head -> local-ci -> validated deploy helper -> production deploy
```

## Repo Feature Detection

- local-ci support: `command -v local-ci` succeeds and repo root contains `.local-ci.toml`
- validated deploy helper: `scripts/deploy/trigger_validated_backend_deploy.sh` exists

## When to Use This Skill

- Creating **promotion PRs** from `dev` → `release` to move a staging candidate onto `release`
- Creating **release PRs** from `release` → `master` to move a production candidate onto `master`
- Preparing hotfix releases
- Bumping versions in pyproject.toml
- Resolving merge conflicts between branches
- Publishing GitHub releases after PRs are merged
- Checking what commits are pending promotion or release

## Core Workflow

### 0. Promotion PR: dev → release (prepare staging candidate)

Before a production release, promote reviewed changes from `dev` to `release`.
Merging the promotion PR does **not** deploy staging automatically.

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

Routine feature PRs still merge into `dev` where CI validates but never
deploys. The promotion PR is the intentional step that moves the candidate onto
`release`.

A `local-ci` run on the open `promote/*` branch is still only a preflight. In
Django4Lyfe today that preflight can run the full parity lanes, but it still
does not replace exact target-head validation after merge. If the preflight
fails, stop and dig into the harness/code before calling the promotion ready.
Exact `release` parity still happens on the clean merged `origin/release` head.

**After merge**: use the exact `origin/release` head from a clean checkout.
If the validated deploy helper exists, prefer it — it runs local-ci and then
triggers staging deploy. Otherwise, if the repo supports local-ci, run
`local-ci` manually and follow the repo-local deploy steps.

```bash
git fetch origin
git worktree add ../backend-release origin/release
cd ../backend-release
CIRCLECI_TOKEN=... scripts/deploy/trigger_validated_backend_deploy.sh
```

Validate staging before proceeding. If issues are found, fix them on `dev` and
create a new promotion PR instead of patching `release` directly.

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

Merging the release PR does **not** deploy production automatically. A
`local-ci` run on the open `release -> master` PR head is only a preflight. In
Django4Lyfe today that preflight can run the full parity lanes, but exact
`origin/master` validation still happens after merge. If it fails, stop and dig
into it before calling the release ready. After the PR lands, use the exact
`origin/master` head from a clean checkout. If the validated deploy helper
exists, prefer it — it runs local-ci and then triggers production deploy.
Otherwise, if the repo supports local-ci, run `local-ci` manually and follow
the repo-local deploy steps.

```bash
git fetch origin
git worktree add ../backend-master origin/master
cd ../backend-master
CIRCLECI_TOKEN=... scripts/deploy/trigger_validated_backend_deploy.sh
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
- Type: Promotion (dev → release, staging candidate only)
- Title: "Promotion: DDth Month YYYY"
- Target: `release`
- Conflicts: None / Resolved
- Deploy: run the validated deploy helper from the clean `origin/release` head
```

When reporting release status:

```
Created: https://github.com/DiversioTeam/Django4Lyfe/pull/XXXX

**Summary:**
- Version: `YYYY.MM.DD[-N]`
- Title: "Release: DDth Month YYYY"
- Target: `master`
- Conflicts: None / Resolved
- Deploy: run the validated deploy helper from the clean `origin/master` head

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
11. **Promotion/release PR merges do not deploy automatically** — After `dev → release` or `release → master` merges, use `scripts/deploy/trigger_validated_backend_deploy.sh` from the exact clean branch head when the repo exposes it; otherwise validate that head with `local-ci` and follow the repo-local deploy path.

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

# Create promotion PR (dev → release, prepare staging candidate)
git checkout -b promote/YYYY.MM.DD[-N] origin/release
git merge origin/dev --no-edit
git push -u origin promote/YYYY.MM.DD[-N]
gh pr create --base release --title "Promotion: DDth Month YYYY"

# Create release PR (release → master, prepare production candidate)
git checkout -b releases/YYYY.MM.DD[-N] origin/master
git merge origin/release --no-edit
# (bump version, uv lock, commit, then:)
gh pr create --base master --title "Release: DDth Month YYYY"

# Validate + deploy exact release head after promotion PR merge
git fetch origin && git worktree add ../backend-release origin/release && cd ../backend-release
CIRCLECI_TOKEN=... scripts/deploy/trigger_validated_backend_deploy.sh

# Validate + deploy exact master head after release PR merge
git fetch origin && git worktree add ../backend-master origin/master && cd ../backend-master
CIRCLECI_TOKEN=... scripts/deploy/trigger_validated_backend_deploy.sh

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
