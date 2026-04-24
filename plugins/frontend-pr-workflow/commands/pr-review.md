Review a frontend pull request using the repo-local digest and workflow rules.

## Input

The user optionally provides: `$ARGUMENTS` (PR number)

If no PR number is provided, ask for it.

## Steps

1. Load or refresh `docs/frontend-skill-digest/project-digest.md`
2. Load the PR context using `gh pr view` and `gh pr diff`
3. Follow the digest-first review workflow defined in the
   `frontend-pr-review` skill
4. Output a structured review report with verdict

## Quick Usage

```
/frontend-pr-workflow:pr-review 309
```
