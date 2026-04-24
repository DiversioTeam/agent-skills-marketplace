Implement Mixpanel tracking using the repo-local digest and local tracking
architecture.

## Input

The user optionally provides: `$ARGUMENTS` (event description)

## Steps

1. Run the `frontend-mixpanel` skill's implementation lane, passing
   `$ARGUMENTS` as the event description if provided.
2. Report the result produced by the skill.
