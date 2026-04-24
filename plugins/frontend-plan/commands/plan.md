Start a frontend planning workflow using the repo-local digest and detected docs
conventions.

## Input

The user optionally provides: `$ARGUMENTS` (issue reference, e.g., `#1234`)

## Steps

1. Run the `frontend-plan` skill, passing the issue reference from
   `$ARGUMENTS` if provided.
2. Report the result produced by the skill.
