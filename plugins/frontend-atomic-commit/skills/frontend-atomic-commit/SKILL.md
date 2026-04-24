---
name: frontend-atomic-commit
description: "Digest-first frontend atomic-commit workflow. Uses detected repo commands, workspace scope, and commit conventions instead of fixed Yarn/tsc assumptions."
---

# Frontend Atomic Commit Skill

Create clean frontend commits using the current repo’s actual quality gates and
package layout.

## Digest-First Preflight

1. Load `docs/frontend-skill-digest/project-digest.md`.
2. Refresh it first if missing or stale.
3. If the digest is unavailable and cannot be created (the `frontend-bundle`
   plugin is not installed), detect the minimum required context inline before
   proceeding: package manager from lockfiles, framework from `package.json`
   dependencies, test/lint commands from `package.json` scripts, workspace
   layout from workspace config. Proceed with reduced confidence and note the
   missing digest in output.
4. Use the detected lint, type-check, test, and workspace commands.

Do not assume `yarn lint` or `yarn type-check`.

## Workflow

### 1. Analyze staged changes

Check staged vs unstaged work and decide whether the staged set is one logical
change.

### 2. Resolve scope

If the repo is a monorepo, identify the affected package(s) and use
package-scoped commands when appropriate.

### 3. Run quality gates

Use the digest-selected commands for:
- lint
- type-check
- tests required by repo convention

Also check staged diff for:
- debug logging
- new suppressions such as `eslint-disable` or similar bypasses
- accidental contract/doc drift in changed markdown when relevant

### 4. Commit hygiene

Enforce:
- one logical change per commit
- no AI co-author signatures
- no bypassing hooks
- commit-message format only if the repo actually expects a format

### 5. Create the commit

Craft a concise message matching repo conventions and create the commit only
after required gates pass.

## Output

Report:
- digest status
- affected package(s)
- gates run
- whether the commit is atomic
- final commit message and hash
