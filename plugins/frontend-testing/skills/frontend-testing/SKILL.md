---
name: frontend-testing
description: "Digest-first frontend testing workflow for app, design-system, and monorepo repos. Chooses the real unit/component/E2E stack and commands instead of assuming Vitest and Playwright."
---

# Frontend Testing Skill

Use the current repo’s detected test stack rather than a fixed Vitest/Playwright
playbook.

## Digest-First Preflight

1. Load `docs/frontend-skill-digest/project-digest.md`.
2. Refresh it first if missing or stale.
3. Use the detected unit/component/E2E frameworks, commands, and package scope.

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

Use the digest-selected commands. If no E2E stack exists, say so clearly instead
of pretending the repo supports Playwright.

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

## Output

Report:
- digest status
- affected package(s)
- detected test stack
- commands run
- coverage or missing-state gaps
