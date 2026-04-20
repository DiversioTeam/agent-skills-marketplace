Create atomic commits with strict quality enforcement.

## Input

The user optionally provides: `$ARGUMENTS`

If provided, use as the commit message. Otherwise, suggest a message based on staged changes.

## Steps

1. Check `git status` and `git diff --cached --stat` for staged changes.

2. Verify staged changes represent ONE logical change. If not, advise splitting.

3. Run quality gates (both must pass with 0 errors, 0 warnings):

    ```bash
    yarn lint
    yarn type-check
    ```

4. Check staged diff for forbidden patterns:
    - No `eslint-disable` comments added
    - No `console.log` statements
    - No AI co-author signatures in commit history

5. Craft or validate the commit message:
    - Format: `type(scope): concise description`
    - Types: `feat`, `fix`, `refactor`, `style`, `chore`, `docs`, `test`, `perf`
    - Imperative mood, under 72 chars, no trailing period
    - **NEVER include `Co-Authored-By: Claude`**

6. Create the commit (do NOT use `--no-verify`).

7. Report: hash, message, file count, lint/type-check status, and confirm no forbidden patterns.

## Validation

- Reject if lint or type-check has errors or warnings
- Reject if `eslint-disable` found in staged diff
- Warn if staged changes aren't atomic (multiple unrelated concerns)
- NEVER add AI co-author signatures to any commit
- NEVER bypass hooks with `--no-verify`
