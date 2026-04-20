Run the full pre-commit checklist matching frontend pre-commit hooks.

## Steps

1. Run ESLint (must be 0 errors AND 0 warnings):

    ```bash
    yarn lint
    ```

2. Run TypeScript type-check (must be 0 errors):

    ```bash
    yarn type-check
    ```

3. Report results clearly:
    - If both pass: "Pre-commit checks passed. Ready to commit."
    - If either fails: Show the errors and suggest fixes.

## What This Matches

This runs the same checks as the husky pre-commit hook and the CI lint-typecheck job. Passing locally means CI will pass too.

## Additional Checks (Manual)

After the automated checks pass, remind the user to verify:

- No new `eslint-disable` comments in their changes
- No `console.log` statements left in code
- No hardcoded colors/fonts (use design system tokens)
- No AI co-author signatures in any commit messages
