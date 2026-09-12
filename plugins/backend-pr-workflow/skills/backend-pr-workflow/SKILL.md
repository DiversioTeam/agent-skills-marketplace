---
name: backend-pr-workflow
description: "Prepare or review Django backend PR workflow, issue linkage, and migration rollout safety."
allowed-tools: Read Bash Glob Grep
---

# Backend PR Workflow Skill

## When to Use This Skill

Use this Skill whenever you are:

- Creating or reviewing a backend PR that touches Django models, migrations, or
  production data.
- Preparing a PR for Django4Lyfe / Workforce backend or a similar repo that
  uses GitHub as the active workflow system.
- Planning a release or hotfix and want to ensure the workflow (branches, tags,
  and migrations) is correct and downtime-safe.

If the target repo has its own harness docs, treat `AGENTS.md` as the
canonical entrypoint and follow any linked workflow/release/migration docs or
directory-scoped `AGENTS.md` files for per-topic truth. `CLAUDE.md` should be
treated as a pointer, not as a unique rule source. This Skill is the default
baseline when repo-local docs are absent or thin.

## Example Prompts

- “Use the `backend-pr-workflow` skill to review this Django4Lyfe PR’s branch name, linked issues, migrations, and downtime-safety. Here are the branch name, base branch, and PR title: …”
- “Before I open this backend PR, run `backend-pr-workflow` on my planned title, description, and migration summary and tell me all `[BLOCKING]` and `[SHOULD_FIX]` issues.”
- “For this hotfix PR on Django4Lyfe, use `backend-pr-workflow` to check that my base branch, title, and release plan follow our backend workflow.”
- “I’ve added a new nullable field and a backfill migration. Use `backend-pr-workflow` to verify that my migrations and rollout plan are downtime-safe.”

## Severity Tags & Output Shape

When this Skill reviews a PR or workflow plan, the response **must** be
structured and tagged:

- Start with a 1–3 sentence summary of what was checked.
- Then use sections:
  - `What’s aligned` – bullets of things that follow the workflow.
  - `Needs changes` – bullets with severity tags:
    - `[BLOCKING]` – must fix before merge or deploy.
    - `[SHOULD_FIX]` – important but not strictly blocking for merge.
    - `[NIT]` – minor consistency or documentation suggestions.

Each bullet in `Needs changes` should:

- Point to the specific item (branch name, PR title, description, migration
  file, release plan).
- State the problem **and** the concrete correction the author should make.

Example bullet:

- `[SHOULD_FIX] Branch name 'misc/work' does not match the repo's documented feature-branch convention. Rename it to something clearer like 'feature/1234-user-auth' or 'feature/user-auth'.`

## Inputs This Skill Expects

Before giving a full review, this Skill should gather:

- The **repository** and context (e.g. Django4Lyfe backend / monolith).
- The **branch name**.
- The **PR title** and **PR description** (or the planned ones).
- The **base branch** (what the PR targets: `dev`, `release`, `master`, etc.).
- Whether the PR:
  - Includes Django model changes.
  - Adds, modifies, or deletes migrations.
  - Is a normal feature/bugfix, a hotfix, or a release PR.

Discover these from the checkout, PR, and diff. Ask only when missing or
conflicting evidence changes the target, scope, or rollout decision.

Before applying the checklist, inspect the repo harness:

- Read `AGENTS.md` first.
- Load linked workflow/release/runbook docs or relevant directory-scoped
  `AGENTS.md` files when they exist.
- Detect local-ci support only when `local-ci` is on PATH **and** repo root
  contains `.local-ci.toml`.
- Detect the validated deploy helper when
  `scripts/deploy/trigger_validated_backend_deploy.sh` exists.
- If workflow rules are tribal knowledge or only implied by stale docs, emit a
  `[SHOULD_FIX]` harness finding recommending a `repo-docs` update.

## Checklist 1 – Repo-Local Branch / PR Conventions

This Skill treats the target repo's current `AGENTS.md`, runbooks, and PR
template as the source of truth.

### 1.1 Branch name

Check the branch name:

- First, inspect the target repo's documented convention.
- For Django4Lyfe today, the backend docs now prefer neutral repo-local names
  such as:
  - `feature/employee-import`
  - `bugfix/1234-employee-import`
  - `chore/ci-cleanup`
- If the repo includes an issue number in branch names, treat it as helpful
  traceability, not a universal requirement unless the repo docs explicitly say
  otherwise.

If the branch does not follow this pattern, emit:

- `[SHOULD_FIX]` – with a suggested corrected branch name that matches the repo
  docs.
- Upgrade to `[BLOCKING]` only if current CI or automation still explicitly
  depends on a pattern and would fail without it.

### 1.2 Multi-repo work and sub-tickets

When a feature spans multiple repositories, prefer:

- one planning issue in `DiversioTeam/monolith` when the work is cross-repo
- repo-local execution issues when ownership or tooling lives in one code repo
- clear links between the planning issue and the execution PR

Explain the risk of collapsing unrelated repo work into one opaque thread:

- ownership becomes unclear
- review history is harder to follow
- repo-local execution tooling cannot attach cleanly

If the user appears to be shoving cross-repo work into one PR or one unclear
issue reference, emit:

- `[SHOULD_FIX]` – recommending a `monolith` planning issue and separate
  repo-local execution work where appropriate.

### 1.3 Commit messages

Check or remind the user that:

- Commit messages should follow the repo-local harness.
- For Django4Lyfe today, the backend docs prefer a clear summary and allow an
  issue reference when it improves traceability.
- If commit-msg hooks or repo docs enforce something stricter, follow that
  repository-local rule instead of inventing a global one.

If commit messages are vague, misleading, or clearly violate a documented
repo-local rule, emit:

- `[SHOULD_FIX]` – asking the author to fix future commits and, where
  practical, to rewrite recent history before merge.

### 1.4 PR title

The PR title must:

- Follow the repo-local PR guidance.
- For Django4Lyfe today, that means a clear summary title; issue linkage should
  live in the PR body using GitHub-native references such as:
  - `Closes #1234`
  - `Refs DiversioTeam/monolith#1234`

If not, emit:

- `[SHOULD_FIX]` – and propose a corrected title or PR-body linkage that
  matches the repo docs.

## Checklist 2 – WIP Signalling & Base Branch

### 2.1 WIP / draft status

Check whether the work is still in progress:

- If the author indicates the PR is not ready for review yet:
  - The PR should be in **draft** mode, or
  - The title or label should clearly include `WIP` / `[WIP]`.

If not, emit:

- `[SHOULD_FIX]` – asking the author to convert to draft or annotate the PR as
  WIP to avoid premature review.

### 2.2 Base branch selection

Confirm the base branch matches the project’s release workflow:

- **Normal feature / bugfix work**:
  - Base branch should be `dev` (the integration branch).
  - Merging into `dev` runs validation only — no staging deploy.
  - On an open PR to `dev`, local-ci on the exact PR head is the real backend
    validation path; GitHub Actions may still show only safety or advisory jobs.
- **Staging promotion**:
  - Base branch should be `release`.
  - A PR from `dev` → `release` is a **promotion PR** — merging moves the
    candidate to `release`; staging deploy then happens from the exact
    `origin/release` head via repo-local local-ci / deploy helper steps.
- **Hotfix** that must bypass the current `release` contents:
  - Base branch should be `master`.
- **Production release**:
  - `release` → `master` after staging validation; production deploy then runs
    from the exact `origin/master` head, not from PR merge itself.

If a PR targets the wrong base branch:

- Emit `[BLOCKING]` and recommend the correct base, explaining whether the
  change belongs in `dev`, `release`, or should be a `master` hotfix.

If the repo’s harness docs specify a different default (e.g. custom long-lived
branches in `AGENTS.md` or a linked workflow doc), follow that instead.

## Checklist 3 – PR Description & Self-Review

This Skill expects PR authors to be their own first reviewer.

### 3.1 PR description quality

Check that the description (or planned description):

- Follows any existing PR template for the repo, if one exists.
- Clearly explains:
  - What changed.
  - Why it changed (the problem or goal).
  - Whether there are any **breaking changes** and what reviewers should
    inspect carefully.
  - Any required secrets, DB dumps, or setup information, with guidance to
    share secrets via 1Password / Slack and to clean up messages.
  - Any manual steps needed for deploy:
    - Env vars to add/update.
    - Buckets or external resources to create.
    - Management commands or scripts to run.
    - Whether a DB snapshot is recommended before deploy (for heavy data
      changes).

If key context is missing, emit:

- `[SHOULD_FIX]` – listing the missing items and suggesting how to include
  them.

### 3.2 Self-review checklist

Prompt the author to confirm they have checked:

- Branch is up to date with the base branch; diff is not polluted by unrelated
  files.
- All debugging code is removed:
  - No `print()` / `ipdb` / `pdb` left behind.
- Tests have been added or updated for new functionality.
- Remote CI is green when applicable.
- If the repo supports local-ci (`command -v local-ci` + `.local-ci.toml`),
  repo-owned local validation has been run on the intended commit/worktree.
  If that local-ci run fails, treat it as blocking and dig into the failure
  before calling the PR ready.
- Active Python type gate is passing for touched files:
  - Detect in this order unless repo docs/CI differ: `ty`, then `pyright`,
    then `mypy`.
  - If `ty` is configured, it is mandatory and blocking.
- Pre-commit hooks and coding conventions have been applied.
- Code coverage has not regressed significantly.
- For Django changes: migrations have been cleaned up and regenerated if there
  were multiple schema iterations.

If any of these fail obviously based on the PR description or user input, emit
appropriate `[SHOULD_FIX]` or `[BLOCKING]` bullets. Type-gate failures should
generally be `[BLOCKING]` for merge readiness.

## Release And Hotfix Checks

For release or hotfix PRs, read [release checks](references/release-checks.md).
Ordinary feature PRs do not need that workflow. Release preparation, exact-head
validation, deployment, publication, and synchronization remain separate actions.

## Migration And Schema Checks

When model or migration changes are present, read
[migration checks](references/migration-checks.md) before a readiness verdict.
Preserve downtime-safe rollout, backfill, and deployed-history constraints.
Review does not authorize database mutation or destructive rollback.

## How This Skill Should Behave in Practice

When invoked, this Skill should:

1. Gather the inputs listed above (branch, PR title/description, base branch,
   migration/schema summary).
2. Use the checklists relevant to the PR: conventions, base, and description;
   release/hotfix checks only for those workflows; migration and schema checks
   only when those contracts change. Preserve ordering constraints within a
   rollout; do not run deployment commands during review.
3. Emit:
   - A short summary paragraph.
   - `What’s aligned` bullets.
   - `Needs changes` bullets with `[BLOCKING]`, `[SHOULD_FIX]`, `[NIT]`.
4. Be direct and pedantic but constructive:
   - Treat automation, traceability, and downtime-safety as **hard**
     requirements, not nice-to-haves.
   - Always provide specific, actionable corrections rather than vague
     guidance.
   - When rules are missing from the repo harness, call that out explicitly as
     a documentation/tooling problem, not just a one-off nit.

## Compatibility Notes

This Skill is designed to work with both Claude Code and OpenAI Codex.

- Claude Code: install the corresponding plugin and use its slash commands (see `plugins/backend-pr-workflow/commands/`).
- Codex: install the Skill directory and invoke `name: backend-pr-workflow`.

For installation, see this repo's `README.md`.
