---
name: frontend-pr-workflow
description: "Digest-first frontend PR creation workflow for app, design-system, and monorepo repos. Uses detected branch models, quality gates, and repo-local templates instead of fixed Yarn/dev/main assumptions."
---

# Frontend PR Workflow Skill

Create frontend PRs using the current repo’s actual branch model, quality gates,
and template conventions.

## When to Use This Skill

- Creating a feature PR, release PR, or equivalent frontend change review.
- Validating that the branch is ready before opening the PR.
- Running `/frontend-pr-workflow:create-pr`.

## Digest-First Preflight

Before creating the PR:

1. Load `docs/frontend-skill-digest/AGENTS.md` and
   `docs/frontend-skill-digest/project-digest.md`.
2. Refresh the digest first if it is missing, stale, or obviously wrong.
3. If the digest is unavailable and cannot be created (the `frontend-bundle`
   plugin is not installed), detect the minimum required context inline before
   proceeding: package manager from lockfiles, framework from `package.json`
   dependencies, test/lint commands from `package.json` scripts, workspace
   layout from workspace config. Proceed with reduced confidence and note the
   missing digest in output.
4. Prefer repo-local workflow docs and PR templates when present.

Do not assume:
- feature PRs always target `dev`
- release PRs always target `main`
- `yarn` is the package manager
- preview URLs or backend-branch metadata are always required

## Step 1: Determine PR Type

Infer the PR type from:
1. current branch
2. digest workflow conventions
3. repo-local docs/templates

If still ambiguous, ask the user a short question.

Common outcomes:
- feature/change PR
- release PR
- design-system release/dependency PR

## Step 2: Run Quality Gates

Use the commands recorded in the digest, scoped to the affected package(s) when
the repo is a monorepo.

Check:
- lint
- type-check
- tests required by repo convention
- no newly added `eslint-disable` or equivalent suppressions unless justified
- no leftover debug logging
- no AI co-author signatures

If any required gate fails, fix it before creating the PR.

## Step 3: Gather PR Inputs

Ask only for the fields the repo actually uses. Examples:
- linked issue/reference
- one-line summary
- preview URL
- backend branch dependency
- release notes context

For monorepos or design-system repos, also identify:
- affected package(s)
- consumer impact
- dependency publication expectations

## Step 4: Build The PR Body

Use this precedence:
1. repo-local PR template
2. digest workflow conventions
3. a minimal fallback structure

### Fallback feature/change PR body

```markdown
## Related issues
- Closes #XXXX

## What changed?
- bullet list

## Why?
- short rationale

## Scope / affected areas
- packages, components, modules, or consumers

## Validation
- commands run
- preview/sandbox link if applicable
```

### Fallback release PR body

When the repo uses a release PR model, follow the digest for:
- base/head branches
- title format
- whether the body is only PR links or needs extra release notes

Do not force the old `Release [Month] [Day] [Year]` format unless the repo
actually uses it.

## Step 5: Create The PR

Push the branch if needed, then create the PR with:
- the correct base branch from the digest/repo docs
- the correct template/body shape
- any required package, preview, or backend metadata

If the repo has unusual rules and the digest confidence is low, stop and ask one
short clarifying question rather than opening the wrong PR.

## Output Expectations

Report:
- digest status (reused/refreshed)
- PR type selected
- base/head branches used
- quality gates run
- any repo-specific fields included
