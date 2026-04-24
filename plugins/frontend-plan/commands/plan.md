Start a frontend planning workflow using the repo-local digest and detected docs
conventions.

## Input

The user optionally provides: `$ARGUMENTS` (issue reference, e.g., `#1234`)

## Steps

1. Load or refresh `docs/frontend-skill-digest/project-digest.md`.
2. Resolve issue reference, feature name, and affected package/app if needed.
3. Use the repo’s docs/planning convention instead of assuming `docs/feature/`.
4. Understand scope, ask scoping questions, and write the right planning
   artifacts for this repo.
5. Use the repo’s branch model instead of assuming `dev`.

## Philosophy

Spend most of the time clarifying scope before implementation, but adapt the
artifact set to the repo’s actual workflow.
