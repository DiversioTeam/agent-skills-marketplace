Use the install-once frontend bundle for repo-agnostic frontend work.

## Input

The user optionally provides: `$ARGUMENTS`

Interpret the request as one of these lanes:
- `review`
- `api`
- `testing`
- `mixpanel`
- `sentry`
- `cicd`
- `plan`
- `commit`

## Steps

1. Run the `frontend-project-digest` workflow first if
   `docs/frontend-skill-digest/project-digest.md` is missing, stale, or clearly
   inconsistent with the repo.
2. Load `docs/frontend-skill-digest/AGENTS.md` and
   `docs/frontend-skill-digest/project-digest.md`.
3. Route the task using the detected repo class, tooling, API contract sources,
   testing stack, analytics stack, observability stack, and workflow
   conventions.
4. If the requested lane is out of scope for the detected repo type, say so
   explicitly instead of forcing an app-shaped workflow.

## Quick Usage

```text
/frontend-bundle:frontend review 123
/frontend-bundle:frontend api feedback
/frontend-bundle:frontend testing e2e
```
