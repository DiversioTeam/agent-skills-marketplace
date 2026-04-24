CI/CD guidance for the frontend using the repo-local digest and real delivery
stack.

## Input

The user optionally provides: `$ARGUMENTS` (`workflows`, `deploy`, `sandbox`, `debug`, or `release`)

## Routing

- `workflows` - Explain the repo’s actual CI/CD workflows
- `deploy` - Deployment process for the detected platform(s)
- `sandbox` - Preview/sandbox management if the repo actually has it
- `debug` - Debug failing CI runs
- `release` - Production release process
- (none) - Pipeline overview

## Quick Commands

```bash
First load or refresh `docs/frontend-skill-digest/project-digest.md`, then use
the detected CI, preview, and local build/test commands. Do not assume Crafting
or Yarn unless the digest says they are present.
```
