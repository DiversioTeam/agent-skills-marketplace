Create an atomic frontend commit using the repo-local digest and quality gates.

## Input

The user optionally provides: `$ARGUMENTS`

If provided, use as the commit message. Otherwise, suggest a message based on
staged changes.

## Steps

1. Run the `frontend-atomic-commit` skill, passing `$ARGUMENTS` as the
   suggested commit message if provided.
2. Report the result produced by the skill.
