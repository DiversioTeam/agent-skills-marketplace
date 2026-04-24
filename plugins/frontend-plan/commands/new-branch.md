Create a new frontend branch using the repo-local digest and branch model.

## Input

The user provides: `$ARGUMENTS`

Accepted formats:
- `1234 short description`
- `#1234 short description`
- `short description`

## Steps

1. Parse optional GitHub issue number and feature name from arguments.
2. Validate that a feature description exists.
3. Load or refresh `docs/frontend-skill-digest/project-digest.md`.
4. Build branch name using the repo's detected naming conventions:
    - With issue: `feature/{issue-number}-{feature-slug}` (fallback)
    - Without: `feature/{feature-slug}` (fallback)
    - Override with repo-specific conventions from the digest when present.
5. Use the repo's detected base branch instead of assuming `dev`.

6. Report the created branch name and base branch used.

## Examples

| Input                          | Branch Created                        |
| ------------------------------ | ------------------------------------- |
| `4757 slack pr notifications`  | `feature/4757-slack-pr-notifications` |
| `#4800 fix login redirect`    | `feature/4800-fix-login-redirect`     |
| `improve manager alerts`      | `feature/improve-manager-alerts`      |

These are examples only; the repo’s actual naming convention wins.
