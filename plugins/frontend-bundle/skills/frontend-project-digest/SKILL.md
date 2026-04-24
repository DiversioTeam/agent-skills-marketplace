---
name: frontend-project-digest
description: "Fingerprint the current repo for frontend work, classify it as app/design-system/monorepo, detect tooling and API contract sources, and write a durable repo-local digest for later frontend skills."
---

# Frontend Project Digest Skill

This skill writes the durable repo-local frontend digest that other frontend
skills must load before acting.

## When to Use This Skill

- `docs/frontend-skill-digest/project-digest.md` does not exist.
- The existing digest is stale or clearly inconsistent with the repo.
- A later frontend skill needs to know package manager, framework, testing
  stack, analytics/observability stack, workflow conventions, or API contract
  sources before it can proceed safely.

## Output Location

Write only to these repo-local files:

- `docs/frontend-skill-digest/AGENTS.md`
- `docs/frontend-skill-digest/project-digest.md`

Do not change application code while this skill is active.

## Detection Workflow

Follow this order.

### 1. Classify the repo

Determine whether the repo is primarily:
- `frontend-app`
- `design-system`
- `monorepo-frontend`
- `unknown`

Use multiple signals:
- workspace manifests
- package layout
- Storybook/design-token packages
- app entrypoints
- frontend framework markers
- internal package relationships

### 2. Detect package and workspace tooling

Record:
- package manager (`pnpm`, `yarn`, `npm`, `bun`, unknown)
- workspace system (`pnpm-workspace.yaml`, npm workspaces, Yarn workspaces,
  Turborepo, Nx, none)
- install command
- likely lint / type-check / unit / E2E commands

Use the repo’s scripts and lockfiles, not assumptions.

### 3. Detect framework and rendering model

Look for:
- React
- Next.js
- Vite
- Remix
- Storybook
- library-only/design-system setup
- SSR / SPA / component-library hints

### 4. Detect styling and design-system stack

Look for:
- styled-components
- Emotion
- Tailwind
- CSS Modules
- Sass
- MUI / Chakra / Radix / shadcn or similar
- token packages
- internal design-system packages

Record whether:
- the repo consumes a design system
- the repo publishes a design system
- both happen in the same monorepo

### 5. Detect data, state, and API patterns

Look for:
- React Query / TanStack Query
- RTK Query
- Redux Toolkit
- Zustand
- Apollo / Relay
- axios / fetch wrappers / generated clients
- endpoint registries
- hooks folders

Also determine API contract sources in this order:
1. generated SDK/client already in use
2. OpenAPI / Swagger files or generated schema artifacts
3. Bruno / Postman / Insomnia collections
4. backend code in the same repo
5. backend code in a sibling repo path provided later by the user

If the repo does not contain enough backend or spec context, record that later
API-integration work must ask the user for:
- a backend working directory
- or an API spec path / URL
- or a docs collection location

### 6. Detect testing stack

Look for:
- Vitest
- Jest
- React Testing Library
- Playwright
- Cypress
- Storybook visual tests

Record the likely commands and any workspace/package scoping needed.

### 7. Detect analytics and observability

Look for:
- Mixpanel
- PostHog
- Segment
- RudderStack
- Sentry
- LogRocket
- Datadog RUM

Do not force Mixpanel or Sentry if the repo uses something else or nothing.

### 8. Detect CI/CD and workflow conventions

Look for:
- GitHub Actions
- Vercel
- Netlify
- CloudFlare
- internal sandbox tooling
- release workflows
- default branches
- docs / planning folder conventions

### 9. Write applicability guidance

State which frontend lanes apply cleanly in this repo:
- PR review
- API integration
- testing
- analytics
- observability
- CI/CD
- planning
- commit hygiene

State which lanes are partial or out of scope.

## Digest Files

### `docs/frontend-skill-digest/AGENTS.md`

Write a short operating contract that explains:
- what the frontend digest folder is for
- which file is authoritative for the current fingerprint
- when later skills must refresh it
- which fields can be trusted vs re-checked

### `docs/frontend-skill-digest/project-digest.md`

Use the schema in `references/digest-schema.md`.

Required sections:
- repo classification
- package manager and workspace model
- framework/runtime
- styling and design-system map
- data/state/API map
- testing stack
- analytics/observability stack
- CI/CD and deploy signals
- workflow conventions
- skill applicability map
- freshness and confidence
- open questions / missing context

## Missing Context Rules

Do not guess when important context is absent.

Examples:
- If a frontend repo consumes an API but the contract lives only in a separate
  backend repo, record that and tell later API work to ask for a backend
  directory.
- If the repo has Bruno collections but no backend code, prefer Bruno as the
  contract source.
- If the repo has Swagger/OpenAPI, prefer that over reverse-engineering endpoint
  behavior from component code.
- If the repo is a monolith and frontend/backend coexist, record the relevant
  package or service paths instead of asking unnecessarily.

## Freshness Rules

Refresh the digest when any of these changed:
- lockfile or package manager
- workspace layout
- major framework
- testing stack
- analytics/observability stack
- design-system ownership
- API contract source
- backend directory mapping

## Review-Taste Reference

When the digest will be used by PR-review workflows, also load:

- `references/bumang-frontend-review-taste.md`

Use that reference to shape review priorities, not as a repo classifier.
