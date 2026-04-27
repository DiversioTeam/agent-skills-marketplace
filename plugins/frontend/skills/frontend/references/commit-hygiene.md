# Commit Hygiene Lane

Create clean frontend commits using the current repo's actual quality gates
and package layout.

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
