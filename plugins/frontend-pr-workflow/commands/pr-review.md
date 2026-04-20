Review a pull request for code quality, template compliance, and design system standards.

## Input

The user optionally provides: `$ARGUMENTS` (PR number)

If no PR number is provided, ask for it.

## Steps

1. Load the PR context using `gh pr view` and `gh pr diff`
2. Follow the 6-step review workflow defined in the frontend-pr-review skill
3. Output a structured review report with verdict

## Quick Usage

```
/frontend-pr-workflow:pr-review 309
```
