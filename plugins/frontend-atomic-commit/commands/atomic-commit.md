Create an atomic frontend commit using the repo-local digest and quality gates.

## Input

The user optionally provides: `$ARGUMENTS`

If provided, use as the commit message. Otherwise, suggest a message based on staged changes.

## Steps

1. Check `git status` and `git diff --cached --stat` for staged changes.

2. Verify staged changes represent ONE logical change. If not, advise splitting.

3. Load or refresh `docs/frontend-skill-digest/project-digest.md`.
4. Run the digest-selected quality gates for the affected package(s).

5. Check staged diff for forbidden patterns:
    - No `eslint-disable` or similar suppressions added without justification
    - No `console.log` statements
    - No AI co-author signatures in commit history

6. Craft or validate the commit message:
    - Format: `type(scope): concise description`
    - Use repo-specific commit conventions when present
    - Imperative mood, under 72 chars, no trailing period
    - **NEVER include `Co-Authored-By: Claude`**

7. Create the commit (do NOT use `--no-verify`).

8. Report: hash, message, file count, gates run, and confirm no forbidden patterns.

## Validation

- Reject if required digest-selected gates fail
- Reject if `eslint-disable` found in staged diff
- Warn if staged changes aren't atomic (multiple unrelated concerns)
- NEVER add AI co-author signatures to any commit
- NEVER bypass hooks with `--no-verify`
