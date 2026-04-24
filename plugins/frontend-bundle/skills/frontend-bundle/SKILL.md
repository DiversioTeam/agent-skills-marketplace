---
name: frontend-bundle
description: "Repo-agnostic umbrella frontend skill. Refreshes a project digest, classifies the repo, and routes review, API, testing, analytics, observability, CI/CD, planning, and commit-hygiene work using detected local conventions."
---

# Frontend Bundle Skill

Use this as the install-once entrypoint for frontend repos.

## When to Use This Skill

- The user wants frontend help but the repo may be a plain app, a design-system
  repo, or a monorepo with multiple frontend packages.
- You want one stable frontend workflow that adapts to the repo instead of
  assuming Optimo-specific structure.
- You want later frontend tasks to reuse a persistent repo-local digest instead
  of rediscovering package managers, frameworks, testing tools, and API
  contract sources every session.

## Core Contract

Every frontend task starts the same way:

1. Load `docs/frontend-skill-digest/AGENTS.md` and
   `docs/frontend-skill-digest/project-digest.md`.
2. If the digest is missing, stale, or obviously wrong for the current repo,
   run the `frontend-project-digest` workflow first.
3. Use the digest as the starting point for commands, tooling, paths, and repo
   classification.
4. Re-check only the local details directly relevant to the requested task.

Do not assume:
- `yarn`
- `dev` / `main`
- React Query
- axios
- styled-components
- Playwright
- CloudFlare / Crafting
- Sentry or Mixpanel

Use what the digest detects.

## Task Routing

Route the work into one of these lanes after loading the digest.

### 1. PR review

Use when the user asks for PR review, diff review, code-review standards, or a
quality verdict.

Apply:
- repo workflow conventions from the digest
- detected styling / framework / testing / package-manager context
- the frontend review taste captured in
  `references/bumang-frontend-review-taste.md`

Focus on:
- shipped contract vs intended contract
- user-visible semantic regressions
- dependency readiness across app ↔ design-system boundaries
- consumer-level regression testing when the bug lives at the integration layer
- local repo consistency for imports, naming, query/mutation identifiers, and
  docs alignment

### 2. API integration

Use when the user needs a frontend endpoint integration, generated types, hooks,
SDK wiring, or API debugging.

Determine API contract sources in this order:
1. existing generated client / typed SDK in the repo
2. OpenAPI / Swagger files or generated types
3. Bruno / Postman / Insomnia collections
4. backend code within the same repo or monorepo
5. backend code in another repo provided by the user

If the repo lacks the necessary backend or spec context, ask for the missing
backend working directory or spec path. Do not invent a backend location.

### 3. Testing

Use the digest to choose the correct test stack and commands:
- Vitest or Jest for unit/component tests
- Playwright or Cypress for E2E
- workspace-aware commands when the repo is a monorepo

### 4. Analytics / observability

For Mixpanel, Sentry, or similar work:
- first verify the tool actually exists in the repo
- adapt to the local service layer and conventions
- if a different analytics or observability tool is used, say so and work with
  the detected stack instead of forcing Mixpanel/Sentry terminology

### 5. CI/CD

Use the digest to inspect actual CI and deploy systems. Prefer the existing
platforms and workflows instead of CloudFlare/Crafting defaults.

### 6. Planning

Use repo-local workflow conventions from the digest:
- default base branch
- docs / plan directory patterns
- monorepo package scope
- app vs design-system applicability

### 7. Commit hygiene

Use detected lint, type-check, and test commands plus repo-local commit
conventions. Do not hardcode `yarn lint` or `yarn type-check`.

## Applicability Rules

The digest must identify which lanes are safe:

- `design-system` repos:
  - review, testing, planning, CI/CD, and release-dependency review usually
    apply
  - API integration or app analytics work may be out of scope
- `frontend-app` repos:
  - all lanes may apply depending on local tooling
- `monorepo-frontend` repos:
  - lanes must identify the affected package(s) before choosing commands

If the user requests a lane that does not fit the repo type, explain why and
stop or narrow the task.

## Freshness Rules

Treat the digest as stale when any of these changed since the last run:
- lockfile or package-manager choice
- workspace layout
- primary frontend framework
- testing stack
- analytics/observability stack
- design-system package ownership
- API contract source or backend directory mapping

## Output Expectations

When this skill is active:
- mention whether you reused or refreshed the digest
- state the detected repo class and the lane you chose
- name any missing context you had to ask for, especially backend or API-spec
  paths
- keep guidance repo-aware and dynamic
