---
name: release-manager
description: "Prepare Django4Lyfe release candidates, stage them, validate deploy targets, or publish an authorized release."
allowed-tools: Bash Read Edit Grep Glob
argument-hint: "[action] [PR_NUMBER] [--hotfix] [--dry-run]"
---

# Release Manager

Prepare reviewed candidates, stage and validate exact commits, and publish the
matching release. Repository-local AGENTS.md and release/deploy docs take
precedence.

```text
feature PRs -> dev                                  (validation only, no deploy)
releases/YYYY.MM.DD[-N] = master + --no-ff merge of a chosen dev SHA + version bump
exact releases/* head -> trigger helper (candidate check + the ONE local-ci run) -> staging
release PR releases/* -> master   (merge commit, never squash; tree == staged tree)
exact master head -> trigger helper (staged-tree + recorded local-ci check, no run) -> production
release PR merge commit -> matching version tag -> GitHub release
```

There is no `release` branch and no promotion PR. The release branch is the
staging candidate: what staging ran is exactly what production gets.

**local-ci runs once per candidate**, inside the staging deploy helper, and is
reused for every commit with the same tree. Never run local-ci by hand on a
`releases/*` branch, its PR, or `master`: the PR head is the staged commit,
and production reuses the result by tree. A changed candidate (new `-N`) gets
its own single run. Only a `--hotfix` production deploy runs local-ci on
`master`.

## Modes and permissions

- `check`: inspect pending scope (`master` vs `dev`), version, recent releases,
  and open `releases/*` PRs. Report verified PR URLs, direct commits,
  ambiguities, and the recommended next version; create nothing.
- `create` / `release-prod`: cut `releases/*` from `master`, open the PR to
  `master`, and, only when authorized, stage its exact head.
- `publish PR_NUMBER`: after an authorized merge, deploy production (only when
  authorized) and publish the release at the PR's exact merge commit.
- `--hotfix`: the [hotfix lane](#hotfix-lane---hotfix) for when `dev` holds
  work that cannot ship. Scope is `master..hotfix/*`, never `dev`.
- `--dry-run`: read-only inspection only; disclose cached-ref freshness. Do not
  fetch, edit, push, publish, or deploy.

Ask for the intended mode if ambiguous. Require explicit authorization for
merges, deploys (staging or production), RLS policy writes, and branch sync.
Never treat `check`, PR creation, or GitHub publication as permission to deploy.

## Prerequisites and shared scope evidence

Read repo-local workflow docs and verify the target repository, clean working
state, remotes, branch policy, and installed tools before changes. Require Git,
`gh` authentication and `jq`. Scope capture needs Python 3.9+; the publication
TOML command needs Python 3.11+. Version/lock updates need `uv`. These helper
minimums do not replace the target repository's Python requirements.

- Detect local-ci with `command -v local-ci` and `.local-ci.toml`. A configured
  gate with a missing binary is a blocker, not permission to skip it.
- Detect `scripts/deploy/trigger_validated_backend_deploy.sh`. If absent, use
  only the documented repo-local validation/deploy path; otherwise stop.
- Set `SKILL_DIR` to the absolute directory containing this loaded SKILL.md.
  Require its `scripts/get_release_scope.py`; stop if installation is incomplete.

Read [captured release scope](references/release-scope.md) before `check` or
candidate preparation. It owns snapshot capture, PR attribution, legacy
cherry-pick reconciliation, and candidate verification. Do not substitute
timestamps or a capped PR search. Preserve full base/source/head SHAs in the
PR body.

## Prepare the release candidate

Capture `origin/master` as `BASE_SHA` and the chosen `origin/dev` commit as
`SOURCE_SHA` (normally the current `dev` head; any ancestor of `origin/dev` is
allowed when later work must wait). Review the diff and attributed PRs; an
empty content diff is not a new release.

```bash
git checkout -b releases/YYYY.MM.DD[-N] "$BASE_SHA"
git merge --no-ff "$SOURCE_SHA" --no-edit
# Edit only the project version in pyproject.toml; use today's date.
uv lock
git add pyproject.toml uv.lock
git commit -m "Version bump to YYYY.MM.DD[-N]"
# Review the final diff; record CANDIDATE_HEAD_SHA before pushing.
git push -u origin releases/YYYY.MM.DD[-N]
gh pr create --base master --title "Release: DDth Month YYYY" --body-file /path/to/reviewed-release-notes.md
```

The deploy helper refuses a candidate that is not this exact shape: cut from
the **current** `origin/master`, one `--no-ff` merge whose second parent is an
ancestor of `origin/dev`, then version-bump commits, with no difference from
that `dev` commit except the `version = ` lines of `pyproject.toml`/`uv.lock`.
So never commit fixes on a `releases/*` branch: land them on `dev` through a
reviewed PR, then cut `releases/YYYY.MM.DD-N+1` and stage it again. If `master`
moves (a hotfix), the candidate is stale: re-cut it.

Use merge commits, not cherry-picks or squash merges; squash destroys the
ancestry later scope checks need. Still inspect content and any conflict
resolution: ancestry alone does not prove patch novelty or preservation.

Release PR bodies need a `## Agent sessions` section like every DiversioTeam
PR: the transcript link from the `agent-session` skill, or
`No agent session: <reason>`. Read [detailed procedures](references/detailed-procedures.md)
for versions, titles, notes format, and conflict recovery.

## Stage the candidate (authorized only)

Run from a clean checkout **on the named release branch**, not a detached
HEAD: local-ci's agent-session step recognizes the release PR by branch name,
and a detached, not-yet-merged candidate fails it. Use the checkout that
created the branch if it is clean, or a fresh worktree tracking the remote
branch (if the local branch exists elsewhere, use that checkout instead):

```bash
BRANCH=releases/YYYY.MM.DD[-N]
git fetch origin "$BRANCH"
git worktree add --track -b "$BRANCH" /path/to/clean-backend-staging "origin/$BRANCH"
cd /path/to/clean-backend-staging
test "$(git rev-parse HEAD)" = "$CANDIDATE_HEAD_SHA"
test "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$BRANCH")"
test -z "$(git status --porcelain)"
scripts/deploy/trigger_validated_backend_deploy.sh
```

The helper checks the candidate shape, then runs local-ci only if this tree
has no recorded pass. It refuses the result if HEAD, the tree or the worktree
changed during the run, verifies the required statuses, and posts a
`release: local-ci tree` status (`local-ci passed on tree <tree sha>`) on the
head. Re-staging the same head reuses it. It then triggers CircleCI
`staging_deploy` on the branch. Production requires that status plus the
**whole** staging rollout on the head, cron services included: both
`ci/circleci: Staging: Deploy App` and `ci/circleci: Staging: Start Sleep Timer`
(the workflow's last job, after both cron rollouts) must be `success`. Watch
the pipeline to the end; test on staging. Any new candidate
commit invalidates that evidence. `python -m scripts.deploy.release_candidate
validated|record` reads and posts the status.

The checkout-unchanged guard covers local-ci-runner#11 (a run can report on a
checkout that changed under it) until that is fixed; never bypass it.

## Pre-release gates

Inspect the candidate's required checks; do not call a failed run ready. Do
not add local-ci runs beyond the helper's one per candidate.

1. Run `./.security/ruff_pr_diff.sh`; use `.bin/ruff format <file>` to fix
   formatting if the repo supplies these wrappers. Missing required wrappers
   need an explicit repo-documented fallback, not a guessed command.
2. **Type Gate Detection:** detect `ty`, then `pyright`, then `mypy`, respecting
   repo-local docs/CI order. Configured `ty` is mandatory and blocking. Touched
   paths must pass; final readiness also requires any repo-wide gates. Report
   blockers explicitly. The marketplace's authoring baseline is
   [Python typing and ty best practices](https://github.com/DiversioTeam/agent-skills-marketplace/blob/main/docs/python-typing-and-ty-best-practices.md).
   In the **target backend repository**, consult its own typing docs if present,
   such as `docs/python-typing-3.14-best-practices.md` or `TY_MIGRATION_GUIDE.md`;
   these example paths are not marketplace files or required filenames.
3. Inspect RLS policies for new models with the documented backend check,
   normally `.bin/django optimo_bootstrap_support_shell_rls`. The `--apply` form
   writes policies: run it only against the explicitly approved environment
   with authorization. Never label a production write safe merely because it
   is idempotent.

## After merge: production deploy and publication

Record the selected PR's `mergeCommit.oid` and verify its base is `master`.
This is `RELEASE_COMMIT_SHA` and the publication target. Follow
[publication checks](references/detailed-procedures.md#publishing-a-github-release)
to read the version at that commit and check existing tags/releases before
creating anything. Never use a moving `master` ref as the tag target.

Merges do **not** deploy. When explicitly authorized, run the helper from a
clean checkout of the exact **current** `origin/master` head. Fetch and compare
it to `RELEASE_COMMIT_SHA`; if they differ, stop for a new deployment decision.

```bash
git worktree add --detach /path/to/clean-backend-deploy "$RELEASE_COMMIT_SHA"
cd /path/to/clean-backend-deploy
scripts/deploy/trigger_validated_backend_deploy.sh            # release
scripts/deploy/trigger_validated_backend_deploy.sh --hotfix   # hotfix PR only
```

Without `--hotfix`, the helper runs no local-ci. It requires the head to be a
merge commit whose tree equals its second parent (the staged release head),
and that parent to carry `success` for both `ci/circleci: Staging: Deploy App`
and `ci/circleci: Staging: Start Sleep Timer` (the full staging rollout,
including cron) and a `release: local-ci tree` status for that same tree. With
`--hotfix` it runs local-ci on the exact `master` head. If it refuses,
do not work around it: the merge differs from what staging ran, so re-cut and
re-stage. Use `--hotfix` only for a merged `hotfix/*` PR, and say in the report
that it skipped staging.

Report validation, deployment, and GitHub publication as separate outcomes,
each with its SHA and evidence.

## Hotfix lane (`--hotfix`)

Only when `dev` holds work that cannot ship. The scope is the hotfix alone:

```bash
git fetch origin master
BASE_SHA=$(git rev-parse origin/master)
git checkout -b hotfix/<slug> "$BASE_SHA"
# Commit the fix, then bump the version (YYYY.MM.DD[-N]) and uv lock.
git push -u origin hotfix/<slug>
python3 "$SKILL_DIR/scripts/get_release_scope.py" "$BASE_SHA" "origin/hotfix/<slug>"
gh pr create --base master --title "Hotfix Release: DDth Month YYYY" --body-file /path/to/hotfix-notes.md
```

- Scope is `master..hotfix/<slug>`: only the fix and the version bump. Attribute
  it as in [release scope](references/release-scope.md); do not capture `dev`.
- Unlike a release PR, a hotfix PR adds new code: it needs normal review
  including little-person, and local-ci on its PR head (on the named branch).
- After an authorized merge (merge commit), deploy with
  `scripts/deploy/trigger_validated_backend_deploy.sh --hotfix` from the exact
  `master` head (it runs local-ci there; no staging), publish as below, then
  open the `master → dev` sync PR. Report that staging was skipped.

## Sync after a hotfix only

A normal release needs no back-merge: the next candidate is cut from `master`
anyway and `master`'s own commits are merge commits and version bumps. After a
**hotfix**, with authorization, open a sync PR so `dev` gets the fix:

```bash
git fetch origin master dev
git checkout -b sync/YYYY.MM.DD[-N]-master-to-dev origin/dev
git merge "$RELEASE_COMMIT_SHA" --no-edit
git push -u origin sync/YYYY.MM.DD[-N]-master-to-dev
gh pr create --base dev --title "Sync master (YYYY.MM.DD[-N]) into dev" --body-file /path/to/sync-notes.md
```

Never force-push or reset `dev`. Until the sync merges, new candidates fail the
helper's shape check (the `dev` commit lacks the hotfix); report it as outstanding.

## Completion report

Report the PR URL, type/target, version, captured base/source/head SHAs,
verified included PR URLs, direct commits, conflict adjustments, and unresolved
scope questions. For staging include the pipeline and staged head. For
post-merge work include the merge commit, tag target, exact-head gate results,
deployment result (or not authorized), publication result, and, after a
hotfix, the `dev` sync status. A created PR or GitHub release is not evidence
of a completed deployment.

## Quick references

- Pending scope: [capture and attribution](references/release-scope.md).
- Version/title formats, publication and tag verification, conflicts, retry
  behavior: [detailed procedures](references/detailed-procedures.md).
- Recent releases: `gh release list --limit 10` (format context, not inclusion).
- Selected PR: `gh pr view <NUMBER> --json state,baseRefName,headRefOid,mergeCommit,body`.
- Release details: `gh release view <TAG> --json body,tagName,name,url`.
