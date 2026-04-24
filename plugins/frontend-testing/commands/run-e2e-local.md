Run frontend E2E tests locally using the repo-local digest and detected preview
or sandbox setup.

## Steps

1. Load or refresh `docs/frontend-skill-digest/project-digest.md`.
2. Confirm the repo actually has an E2E framework and identify the correct
   preview/sandbox/local target.
3. Use the repo’s real environment variables and local E2E command.
4. Ask for missing secrets or preview URLs only when the repo requires them.
5. Run the detected E2E command and inspect the report/artifacts.

## Quick Commands

Use package- or repo-specific E2E commands from the digest. Do not assume
Crafting or Playwright unless the repo actually uses them.
