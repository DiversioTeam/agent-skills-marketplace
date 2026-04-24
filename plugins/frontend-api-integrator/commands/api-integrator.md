Implement a frontend API integration using the repo-local digest and detected
contract source.

## Input

The user optionally provides: `$ARGUMENTS` (feature name)

If provided, use as the feature area. Otherwise, ask for endpoint details.

## Steps

1. Run the `frontend-api-integrator` skill, passing the feature area from
   `$ARGUMENTS` if provided.
2. Report the result produced by the skill.
