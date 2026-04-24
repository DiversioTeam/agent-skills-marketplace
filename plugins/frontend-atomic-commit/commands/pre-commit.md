Run the frontend pre-commit checklist using the repo-local digest.

## Steps

1. Load or refresh `docs/frontend-skill-digest/project-digest.md`.
2. Run the digest-selected lint, type-check, and any required test commands.
3. Report results clearly:
    - If both pass: "Pre-commit checks passed. Ready to commit."
    - If either fails: Show the errors and suggest fixes.

## What This Matches

This should match the repo’s actual pre-commit / CI expectations rather than a
fixed Yarn-only workflow.

## Additional Checks (Manual)

After the automated checks pass, remind the user to verify:

- No new `eslint-disable` or similar suppressions in their changes
- No `console.log` statements left in code
- No avoidable hardcoded design values when the repo uses shared tokens
- No AI co-author signatures in any commit messages
