Sentry guidance for the frontend using the repo-local digest and local
observability setup.

## Input

The user optionally provides: `$ARGUMENTS` (`debug`, `context`, or `verify`)

## Steps

1. Run the `frontend-sentry` skill, passing the lane from `$ARGUMENTS`:
   - `debug` - Investigate a Sentry error
   - `context` - Add breadcrumbs or tags
   - `verify` - Check Sentry setup
   - (none) - Architecture overview
2. Report the result produced by the skill.
