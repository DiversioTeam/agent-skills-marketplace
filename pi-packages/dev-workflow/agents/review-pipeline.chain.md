---
name: review-pipeline
description: Full review pipeline: scout codebase → self-review → standards pass → documentation → ship. Run with /run-chain review-pipeline -- <task>
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

Run the coding standards pass on the modified files from the previous step. Check:

- No local imports (check circular imports)
- No unnecessary getattr() calls — use hasattr() only if needed
- No overly large try/except blocks
- Structured logging in optimo_ apps
- No hardcoded strings/numbers where typed payloads should be used
- Use TypedDict instead of loose dict with Any
- Ruff must be happy with all files
- No string-based type hints
- Never use typing.cast() — it's a code smell
- No repeated fixtures in tests
- Use Django ORM reverse relations to avoid unnecessary model imports
- Be pedantic about type hints, avoid Any
- Use ast-grep where helpful

Apply fixes for everything you find.

## reviewer
reads: context.md
progress: true

Update the documentation for all code changed in this pipeline. Explain changes in simple, visual, first-principles-driven language. Focus on **why** each change was made. Use docstrings, comments, and any other documentation mechanisms.

## delegate
reads: context.md
progress: true

Ship the work. First discover context:
1. Check the current branch and look for existing GitHub PRs or issues
2. If an existing PR is open for this branch, update it
3. If no PR exists, create one, linking any related issues
4. Ask me if you're unsure about anything

Then: atomic commit (ensure everything passes), generate a PR description, and open the PR on GitHub.
