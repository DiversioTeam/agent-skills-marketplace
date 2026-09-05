---
name: release-manager
description: "Create and manage promotion and release PRs for Django4Lyfe. Use this when preparing dev→release promotion PRs, release→master release PRs, validating exact branch heads with local-ci, triggering validated backend deploys, bumping versions, resolving merge conflicts, and publishing GitHub releases."
allowed-tools: Bash Read Edit Grep Glob
argument-hint: "[action] [PR_NUMBER] [--hotfix] [--dry-run]"
---

# Release Manager

Prepare reviewed candidates, validate exact commits, and publish the matching
release. Repository-local AGENTS.md and release/deploy docs take precedence.

```text
feature PRs -> dev       (validation only)
promotion PRs -> release (staging candidate)
exact release head -> local-ci -> authorized deploy helper -> staging
release PRs -> master   (production candidate; merge commit, never squash)
exact master head -> local-ci -> authorized deploy helper -> production
merged release PR SHA -> matching version tag -> GitHub release
```

## Modes and permissions

- `check`: inspect pending release scope, version, recent releases, and open
  release PRs. Report verified PR URLs, direct commits, ambiguities, and the
  recommended next version; do not create PRs, tags, or deployments.
- `create` / `release-prod`: prepare `release → master`.
- `promote-staging`: prepare `dev → release`.
- `publish PR_NUMBER`: publish the already-merged production release at its
  exact merge commit. Publication does not imply deployment permission.
- `--hotfix`: use the hotfix title convention without bypassing scope or gates.
- `--dry-run`: show the intended actions using read-only inspection only;
  disclose cached-ref freshness. Do not fetch, edit, push, publish, or deploy.

Ask for the intended mode if ambiguous. Require explicit authorization for
merges, deploys, RLS policy writes, and branch synchronization. Never interpret
`check`, PR creation, or GitHub publication as permission to deploy.

## Prerequisites and shared scope evidence

Read repo-local workflow docs and verify the target repository, clean working
state, remotes, branch policy, and installed tools before changes. Require Git,
`gh` authentication, `jq`, Python 3.11+, and `uv` for version/lock updates.

- Detect local-ci with `command -v local-ci` and `.local-ci.toml`. A configured
  gate with a missing binary is a blocker, not permission to skip it.
- Detect `scripts/deploy/trigger_validated_backend_deploy.sh`. If absent, use
  only the documented repo-local validation/deploy path; otherwise stop.
- Set `SKILL_DIR` to the absolute directory containing this loaded SKILL.md.
  Require its `scripts/get_release_scope.py`; stop if installation is incomplete.

Read [captured release scope](references/release-scope.md) before `check` or
candidate preparation. It owns snapshot capture, PR attribution, legacy
cherry-pick reconciliation, and candidate verification. Use its helper for
both promotion and production scopes; do not substitute timestamps or a
capped PR search. Preserve full source/base/head SHAs in the PR body.

## Prepare a staging candidate

Capture `origin/release` as `BASE_SHA` and `origin/dev` as `SOURCE_SHA` with the
shared scope procedure. Review the diff and attributed PRs; an empty content
diff is not a new release. Create the branch from those captured commits:

```bash
git checkout -b promote/YYYY.MM.DD[-N] "$BASE_SHA"
git merge "$SOURCE_SHA" --no-edit
# Review resolutions and record/check the final candidate head before pushing.
git push -u origin promote/YYYY.MM.DD[-N]
gh pr create --base release --title "Promotion: DDth Month YYYY" --body-file /path/to/reviewed-promotion-notes.md
```

Feature PRs merge to `dev`; promotion is the intentional move onto `release`.
The open promotion branch's local-ci run is a preflight only. In Django4Lyfe it
can run the full parity lanes; failures block readiness. It does not replace
validation of the exact merged `release` head. Validate staging before preparing
production. Fix staging issues on `dev` and promote again, not by patching
`release` directly.

## Prepare a production candidate

Capture `origin/master` as `BASE_SHA` and `origin/release` as `SOURCE_SHA` with
the shared scope procedure. Reconcile legacy patch duplicates and unresolved
PR attribution before claiming a complete release list.

```bash
git checkout -b releases/YYYY.MM.DD[-N] "$BASE_SHA"
git merge "$SOURCE_SHA" --no-edit
# Edit only the project version in pyproject.toml; use today's date.
uv lock
git add pyproject.toml uv.lock
git commit -m "Version bump to YYYY.MM.DD[-N]"
# Review the final diff; record/check CANDIDATE_HEAD_SHA before pushing.
git push -u origin releases/YYYY.MM.DD[-N]
gh pr create --base master --title "Release: DDth Month YYYY" --body-file /path/to/reviewed-release-notes.md
```

Use merge commits, not cherry-picks or squash merges. Cherry-picks create new
SHAs for old patches; squash merging the release PR destroys the ancestry
needed for subsequent scope checks. Preserve original source commits through
the promotion and release PRs. Still inspect actual content and conflict
resolutions: ancestry alone does not prove patch novelty or preservation.

Read [detailed procedures](references/detailed-procedures.md) for date-based
versions, Promotion/Release/Hotfix titles, notes format, and conflict recovery.

## Pre-release gates

Run repository-required checks and inspect CI for the exact candidate head.
Do not call a failed preflight ready. In repositories with local-ci parity,
run the configured preflight lanes; after merge, validate the exact target head
again rather than reusing candidate-branch results.

1. Run `./.security/ruff_pr_diff.sh`; use `.bin/ruff format <file>` to fix
   formatting if the repo supplies these wrappers. Missing required wrappers
   need an explicit repo-documented fallback, not a guessed command.
2. **Type Gate Detection:** detect `ty`, then `pyright`, then `mypy`, respecting
   repo-local docs/CI order. Configured `ty` is mandatory and blocking. Touched
   paths must pass; final readiness also requires any repo-wide gates. Report
   blockers explicitly. Consult local typing docs, including
   `docs/python-typing-3.14-best-practices.md` or `TY_MIGRATION_GUIDE.md` if present.
3. Inspect RLS policies for new models with the documented backend check,
   normally `.bin/django optimo_bootstrap_support_shell_rls`. The `--apply` form
   writes policies: run it only against the explicitly approved environment
   with authorization. Never label a production write safe merely because it
   is idempotent.

## After merge: validation, deployment, publication

Record the selected PR's `mergeCommit.oid` and verify its target branch. For
production, this is `RELEASE_COMMIT_SHA`; it is also the publication target.
Follow [publication checks](references/detailed-procedures.md#publishing-a-github-release)
to read the version at that commit and check existing tags/releases before
creating anything. Never use a moving `master` ref as the tag target.

Merges do **not** deploy automatically. When explicitly authorized, prefer the
backend validated deploy helper: it runs local-ci before triggering deploy.
It must run from the exact clean **current** target head. Fetch and compare it
to the selected PR's merged commit; if they differ, stop for a new deployment
decision and fresh validation. Do not silently deploy intervening commits or
reuse an older release's proof. The same rule applies to staging promotions.

For an unchanged, verified target head, prepare a clean checkout at its full
SHA, using a fresh path or inspecting an existing worktree before reuse. Check
how the installed helper selects its target: Django4Lyfe's current helper
prefers `release` when a detached SHA matches both remote heads. In that case,
use the actual intended `master`/`release` branch checkout after verifying it
is clean and at the expected SHA; never force a branch out of another worktree.
Use the detached example only when its SHA uniquely identifies the target:

```bash
# DEPLOY_COMMIT_SHA is the verified current target head, not a moving ref.
git worktree add --detach /path/to/clean-backend-deploy "$DEPLOY_COMMIT_SHA"
cd /path/to/clean-backend-deploy
# Only after explicit authorization; obtain credentials through the approved setup.
scripts/deploy/trigger_validated_backend_deploy.sh
```

If no helper exists but local-ci is supported, validate the exact head and
follow repo-local deployment instructions. Report validation, deployment, and
GitHub publication as separate outcomes, each with its SHA and evidence.

## Synchronize after production publication

Production changes and the version bump need to flow back into **both**
`release` and `dev`. Require authorization and follow protected-branch policy
(use sync PRs if required). Do not force-push or reset either branch. On a clean
checkout, where direct merge-back pushes are allowed:

```bash
git fetch origin master release dev
# Check any local branch against its fetched counterpart before reuse.
git checkout release
git merge --ff-only origin/release
git merge "$RELEASE_COMMIT_SHA" --no-edit
git push origin release
SYNC_RELEASE_SHA=$(git rev-parse release)
git checkout dev
git merge --ff-only origin/dev
git merge "$SYNC_RELEASE_SHA" --no-edit
git push origin dev
```

Sync the selected published commit; including later `master` changes needs
separate review and authorization. Inspect what will enter `dev` as well:
`release` may contain newer staging work alongside the production commit. New work on `release`
or `dev` can legitimately leave nonempty diffs afterwards. Verify that the
production commit/version reached both branches rather than demanding all
three trees be identical. If sync is blocked, report it as outstanding.

## Completion report

Report the PR URL, type/target, version, captured base/source/head SHAs,
verified included PR URLs, direct commits, conflict adjustments, and unresolved
scope questions. For post-merge work also include the merge commit, tag target,
exact-head gate results, deployment result (or not authorized), publication
result, and `release`/`dev` sync status. A created PR or GitHub release is not
evidence of a completed deployment.

## Quick references

- Pending scope: [capture and attribution](references/release-scope.md).
- Version/title formats, publication and tag verification, conflicts, retry
  behavior: [detailed procedures](references/detailed-procedures.md).
- Recent releases: `gh release list --limit 10` (format context, not inclusion).
- Selected PR: `gh pr view <NUMBER> --json state,baseRefName,headRefOid,mergeCommit,body`.
- Release details: `gh release view <TAG> --json body,tagName,name,url`.
