CI/CD pipeline guidance for the frontend.

## Input

The user optionally provides: `$ARGUMENTS` (`workflows`, `deploy`, `sandbox`, `debug`, or `release`)

## Routing

- `workflows` - Explain all CI/CD workflows
- `deploy` - Deployment process (staging/production)
- `sandbox` - Crafting Sandbox management
- `debug` - Debug failing CI runs
- `release` - Production release process
- (none) - Pipeline overview

## Quick Commands

```bash
# Debug CI failures
gh run list --limit 10
gh run view {run-id} --log-failed

# Sandbox management
cs sandbox list
cs sandbox show test-my-feature
cs sandbox resume test-my-feature

# Reproduce CI locally
yarn lint && yarn type-check && yarn build
```
