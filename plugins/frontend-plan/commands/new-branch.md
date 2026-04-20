Create a new feature branch from dev.

## Input

The user provides: `$ARGUMENTS`

Accepted formats:
- `1234 short description`
- `#1234 short description`
- `short description`

## Steps

1. Parse optional GitHub issue number and feature name from arguments.
2. Validate that a feature description exists.
3. Build branch name:
    - With issue: `feature/{issue-number}-{feature-slug}`
    - Without: `feature/{feature-slug}`
4. Run:

    ```bash
    git checkout dev
    git pull origin dev
    git checkout -b feature/{branch-name}
    ```

5. Report the created branch name.

## Examples

| Input                          | Branch Created                        |
| ------------------------------ | ------------------------------------- |
| `4757 slack pr notifications`  | `feature/4757-slack-pr-notifications` |
| `#4800 fix login redirect`    | `feature/4800-fix-login-redirect`     |
| `improve manager alerts`      | `feature/improve-manager-alerts`      |
