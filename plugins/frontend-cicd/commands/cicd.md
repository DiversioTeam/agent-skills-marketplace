CI/CD guidance for the frontend using the repo-local digest and real delivery
stack.

## Input

The user optionally provides: `$ARGUMENTS` (`workflows`, `deploy`, `sandbox`, `debug`, or `release`)

## Steps

1. Run the `frontend-cicd` skill, passing the lane from `$ARGUMENTS`:
   - `workflows` - Explain CI/CD workflows
   - `deploy` - Deployment process
   - `sandbox` - Preview/sandbox management
   - `debug` - Debug failing CI runs
   - `release` - Production release process
   - (none) - Pipeline overview
2. Report the result produced by the skill.
