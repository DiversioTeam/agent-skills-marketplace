---
name: workflow-pipeline
description: "Full workflow pipeline: scout codebase → self-review → standards pass → documentation → ship. Run with /run-chain workflow-pipeline -- <task>"
---

## scout
output: context.md
progress: true

Scout the codebase for {task}. Identify:
- Relevant files and entry points
- Data flow and dependencies
- Existing patterns and conventions
- Risks and gotchas
- Where implementation or review should start

Write findings to context.md for the next steps.

## reviewer
reads: context.md
progress: true

Review the current changes for {task} with fresh eyes. Use the scout context from {previous} as background.

Check for:
- **Correctness**: does the code do what it's supposed to?
- **Edge cases**: nulls, empties, race conditions, error paths
- **Bugs**: logic errors, off-by-one, incorrect assumptions
- **Confusion**: unclear naming, missing comments, ambiguous behavior

Fix any issues you find. Output a summary of what you found and what you fixed.

## worker
reads: context.md
progress: true

Run the coding standards pass on the modified files from the previous step.
Follow repository rules first; these backend defaults apply only to Python/Django:

- Follow import rules and fix circular dependencies
- No unnecessary getattr() calls — use hasattr() only if needed
- No overly large try/except blocks
- Structured logging in optimo_ apps
- No hardcoded strings/numbers where typed payloads should be used
- Use TypedDict instead of loose dict with Any
- Ruff must be happy with all files
- No string-based type hints
- Prefer types that prove the contract; do not hide type errors with casts
- No repeated fixtures in tests
- Use Django ORM reverse relations to avoid unnecessary model imports
- Be pedantic about type hints, avoid Any
- Use ast-grep where helpful

Fix scope-related issues and required gate errors. Preserve unrelated work;
reuse valid checks for unchanged inputs and rerun affected checks after edits.

## reviewer
reads: context.md
progress: true

Update existing docs for changed contracts, commands, and non-obvious decisions.
Explain why in plain language; use visuals only when useful. Do not restate code
or require a doc per file. For agent instructions, use repo-docs-generator when
available; keep reading task-specific and safe-action permissions verified.

## delegate
reads: context.md
progress: true

Prepare the authorized commit/PR handoff. First identify the repository,
branch, intended diff, existing PR, related issues, and target. Ask only about
consequential uncertainty. API failure is not evidence that no PR exists.
Existing CI is diagnostic context, not proof for unpushed changes.

If the repo supports local-ci (repo root `.local-ci.toml` + `local-ci` on PATH),
use `local-ci run --no-github` for authorized local validation. Investigate
failures before claiming readiness. Preserve explicit no-commit/no-push limits;
this chain never authorizes merges, status publication, or deployments.

For separately authorized backend deployments, PR-head validation is only a
preflight. Follow the release skill and exact clean target-head deploy contract;
do not invoke a deploy helper merely because it exists.

After required gates pass, commit atomically and push normally only when
authorized. If prohibited, deliver the corresponding local handoff and report
publication as pending. Then use the PR description writer to create/update the
identified PR from the actual pushed diff, preserving repo-local base/draft
conventions and linking issues.

Finally inspect required CI for the exact remote PR head, after push and PR
creation/update. An earlier green head is not proof. Investigate failures and
repeat authorized fixes/checks/commit/push steps as needed, then check the new
head. Pending/missing checks or failed discovery mean readiness is pending or
unknown. Report the PR URL, head SHA, observed checks, and remaining blockers.
