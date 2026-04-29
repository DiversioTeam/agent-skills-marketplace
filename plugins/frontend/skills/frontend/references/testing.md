# Testing Lane

Use the current repo's detected test stack rather than a fixed
Vitest/Playwright playbook.

## Routing

Choose the lane from the digest:
- unit/component tests
- integration tests
- E2E tests
- coverage/debugging

### Repo-shape notes

- `frontend-app`: all test lanes may apply
- `design-system`: emphasize component, accessibility, visual, and consumer
  contract tests; E2E may be partial or absent
- `monorepo-frontend`: select the affected package(s) before running commands

## Workflow

### 1. Resolve scope

Identify:
- affected package or app
- relevant framework (`vitest`, `jest`, etc.)
- E2E tool (`playwright`, `cypress`, or none)

### 2. Match the local test pattern

Inspect the existing repo pattern for:
- colocated tests vs separate test directories
- component harnesses
- API mocking approach
- accessibility or visual-test helpers

Do not force a new layout if the repo already has a pattern.

### 3. Run or write the right tests

Use the digest-selected commands. If no E2E stack exists, say so clearly
instead of pretending the repo supports Playwright.

### 4. Validate all relevant states

For frontend work, cover:
- success state
- empty state
- error state
- accessibility behavior where applicable

For design-system work, cover:
- consumer-facing contract behavior
- token or theming impact
- visual semantics, not only snapshots

## E2E Debugging

Use this guidance only after the digest has identified the actual E2E
framework, preview target, and commands.

### Root-cause workflow

Diagnose first, fix second.

1. Read the failing CI or preview logs.
2. Identify the failing package/app and E2E framework.
3. Reproduce with the repo's real local command from the digest.
4. Use screenshots, traces, videos, or equivalent artifacts if the framework
   provides them.
5. Apply the smallest fix that addresses the root cause.
6. Re-run the same scoped test before pushing.

### Common failure categories

| Category | Symptoms | Usual Direction |
| --- | --- | --- |
| Selector | Cannot find element, strict locator failures | Use more stable selectors or wait for the correct state |
| Navigation | Target page never loads, connection refused | Check preview/base URL, app boot, routing, and environment |
| Auth | Redirect loops, 401/403, missing session | Check auth setup, cookies, tokens, seeded users, and environment |
| Flaky timing | Passes locally sometimes, fails in CI | Remove races, rely on framework waiting, stabilize async state |
| Config | Missing env vars, missing browser/test runner config | Align local/CI config and package scope |

### Artifact-based debugging

When the CI provider exposes artifacts:
1. download the failure artifacts
2. inspect screenshots or the HTML report
3. replay traces/videos if the framework supports them
4. compare the failing environment with the digest's expected preview/local
   target

### Local preview / sandbox validation

Use the detected target from the digest. Do not assume Crafting, Vercel
previews, or localhost without evidence.

If the preview target requires secrets, auth, or environment variables that
are not available, ask for the missing values explicitly.

### Verification

Before closing the debugging loop:
- rerun the failing scenario with the same framework and target
- confirm the failure category is gone
- note any remaining environment-specific uncertainty

## Output

Report:
- digest status
- affected package(s)
- detected test stack
- commands run
- coverage or missing-state gaps
