---
name: frontend-pr-review
description: "Digest-first frontend PR review for app, design-system, and monorepo repos. Uses detected repo conventions, dynamic quality gates, and Bumang-style review priorities instead of fixed stack assumptions."
---

# Frontend PR Review Skill

Review frontend PRs against the current repo’s actual workflow, stack, and
quality gates.

## When to Use This Skill

- Reviewing a frontend PR or branch diff for correctness, review readiness, and
  repo-local conventions.
- Checking whether a feature, design-system, or monorepo PR is ready to merge.
- Running `/frontend-pr-workflow:pr-review` with a PR number.

## Digest-First Preflight

Before reviewing:

1. Load `docs/frontend-skill-digest/AGENTS.md` and
   `docs/frontend-skill-digest/project-digest.md`.
2. If the digest is missing, stale, or obviously inconsistent with the repo,
   run the `frontend-project-digest` workflow first.
3. Read the review heuristics in
   `references/bumang-frontend-review-taste.md`.

Do not assume:
- `dev` / `main`
- `yarn`
- styled-components
- React Query
- one-package repos

Use the digest’s detected workflow conventions, commands, and repo class.

## Step 1: Load PR Context

If the user provides a PR number, inspect it with GitHub metadata and diff.
Otherwise review the current branch diff or ask for the PR number when that
matters.

Collect:
- title and body
- head and base branches
- changed files
- commits
- repo class from the digest
- affected package(s) when this is a monorepo

## Step 2: Determine The Right Review Shape

Use the digest to decide which standards apply.

### `frontend-app`

Focus on:
- user-visible behavior
- API/use-case contracts
- app-level testing and release readiness

### `design-system`

Focus on:
- consumer-facing contract changes
- unpublished dependency expectations
- release/versioning implications
- visual semantics and accessibility

### `monorepo-frontend`

Focus on:
- affected packages and boundaries
- workspace-aware commands
- app ↔ design-system compatibility

If the digest says the repo is only partially applicable for this task, say so
explicitly instead of forcing a generic app checklist.

## Step 3: Template & Workflow Compliance

Check PR process using this precedence:

1. repo-local PR template or workflow docs
2. workflow conventions recorded in the digest
3. current branch/PR metadata

Review:
- base/head branch pairing
- issue linkage when the repo expects it
- required PR body sections or release-body shape
- preview/sandbox/backend-branch fields only when this repo uses them
- placeholder text or stale plan text

If the repo’s PR process differs from the old `feature -> dev` / `dev -> main`
model, the repo wins.

## Step 4: Review The Code Using Bumang-Style Lenses

Prioritize in this order:

1. shipped contract vs stated intent
2. dependency readiness and publish/consume compatibility
3. user-visible semantics and accessibility
4. regression test quality at the consumer layer
5. local consistency for naming, imports, identifiers, and docs

Concrete things to check:
- hidden UI or design-token contract regressions
- app code depending on a design-system capability that is not actually shipped
- docs or PR text that contradict the final implementation
- missing consumer-level regression tests for bugs observed in the UI contract
- unstable or duplicate query/mutation keys
- naming and import patterns that fight the repo norm

## Step 5: Commit Hygiene

Check commit quality relative to repo standards:
- conventional-commit format when the repo uses it
- no WIP/fixup noise in a final PR
- no AI co-author signatures
- commits are reasonably atomic

Do not treat a non-conventional message as a failure unless the repo uses that
rule.

## Step 6: Run The Right Quality Gates

Use the digest’s commands. Examples:
- lint
- type-check
- unit/component tests
- package-scoped checks in a monorepo

If the digest confidence is low, inspect local package scripts before running
commands.

Never hardcode `yarn lint` or `yarn type-check` unless the digest says that is
correct for this repo.

## Step 7: Output The Review

Produce a structured report with:

```markdown
# PR Review: #<number-or-branch>

## Repo Context
- Repo class:
- Digest status: reused | refreshed
- Affected package(s):

## Workflow Compliance
- Pass/fail items tied to repo-local expectations

## Review Findings
1. **[Critical/Warning/Nit]** issue summary — file:line

## Quality Gates
- Lint:
- Type-check:
- Tests:

## Verdict
- APPROVED
- REQUEST CHANGES
- COMMENT
```

Keep the findings grounded in the repo’s actual stack and review taste instead
of generic React advice.
