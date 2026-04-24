# E2E Debugging Guide

Use this guide only after the repo-local frontend digest has identified the
actual E2E framework, preview target, and commands.

## Root-Cause Workflow

Diagnose first, fix second.

1. Read the failing CI or preview logs.
2. Identify the failing package/app and E2E framework.
3. Reproduce with the repo’s real local command from the digest.
4. Use screenshots, traces, videos, or equivalent artifacts if the framework
   provides them.
5. Apply the smallest fix that addresses the root cause.
6. Re-run the same scoped test before pushing.

## Common Failure Categories

| Category | Symptoms | Usual Direction |
| --- | --- | --- |
| Selector | Cannot find element, strict locator failures | Use more stable selectors or wait for the correct state |
| Navigation | Target page never loads, connection refused | Check preview/base URL, app boot, routing, and environment |
| Auth | Redirect loops, 401/403, missing session | Check auth setup, cookies, tokens, seeded users, and environment |
| Flaky timing | Passes locally sometimes, fails in CI | Remove races, rely on framework waiting, stabilize async state |
| Config | Missing env vars, missing browser/test runner config | Align local/CI config and package scope |

## Artifact-Based Debugging

When the CI provider exposes artifacts:

1. download the failure artifacts
2. inspect screenshots or the HTML report
3. replay traces/videos if the framework supports them
4. compare the failing environment with the digest’s expected preview/local
   target

Examples of useful artifact tooling:
- Playwright HTML reports and traces
- Cypress screenshots/videos
- provider-specific preview logs

## Local Preview / Sandbox Validation

The digest should tell you whether the repo uses:
- local dev server only
- preview deploys
- internal sandbox tooling
- staging URLs

Use that detected target. Do not assume Crafting, Vercel previews, or localhost
without evidence.

If the preview target requires secrets, auth, or environment variables that are
not available, ask for the missing values explicitly.

## Verification

Before closing the debugging loop:

- rerun the failing scenario with the same framework and target
- confirm the failure category is gone
- note any remaining environment-specific uncertainty
