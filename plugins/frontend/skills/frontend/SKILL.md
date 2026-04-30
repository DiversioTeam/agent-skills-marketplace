---
name: frontend
description: "Digest-first frontend skill with repo classification, dynamic detection, and internal lane routing for review, API, testing, analytics, observability, CI/CD, planning, and commit workflows."
---

# Frontend Skill

Use this as the single entrypoint for all frontend work in any repo shape.

## When to Use This Skill

- The user wants frontend help in a plain app, design-system, or monorepo.
- You need a stable frontend workflow that adapts to the repo instead of
  assuming a specific stack.
- You want later tasks to reuse a persistent repo-local digest instead of
  rediscovering tooling every session.

## Example Prompts

- `/frontend:work review 123` - Review PR #123 with thread-aware context.
- `/frontend:work api feedback` - Implement or debug frontend API integration
  for the "feedback" flow.
- `/frontend:work testing` - Run, add, or repair tests using the detected
  frontend test stack.
- `/frontend:refresh-digest` - Recompute and persist
  `docs/frontend-skill-digest/AGENTS.md` and
  `docs/frontend-skill-digest/project-digest.md`.
- `/frontend:work new-branch 45 digest-contract-fix` - Create a branch using
  the repo's detected branch model.
- `/frontend:work commit "align frontend digest contract"` - Create an atomic
  commit using detected repo conventions.

## Digest-First Preflight

Every frontend task starts here.

### 1. Load the digest

Read both files from the target repo:

- `docs/frontend-skill-digest/AGENTS.md`
- `docs/frontend-skill-digest/project-digest.md`

### 2. Evaluate freshness

Treat the digest as stale when any of these changed since the last run:
lockfile, workspace layout, primary framework, testing stack,
analytics/observability stack, design-system ownership, API contract source,
or backend directory mapping.

Freshness evidence in the digest (when present): generated commit SHA,
inspected file list, key file hashes or mtimes.

### 3. Decide persist vs ephemeral

- **User ran `/frontend:refresh-digest`**: run full detection (see Detection
  Workflow below) and **persist** the result to `docs/frontend-skill-digest/`.
- **User ran any other command**: if the digest is missing or stale, run
  **ephemeral inline detection** (no file writes). Detect package manager,
  framework, workspace layout, AND lane-specific facts relevant to the
  requested lane (API contract sources, analytics stack, observability stack,
  CI provider, test stack, branch model). Proceed with reduced confidence and
  note the missing digest in output.

Do not silently write digest files outside of `/frontend:refresh-digest`.

### 4. Anti-assumptions

Do not assume: `yarn`, `dev` / `main`, React Query, axios, styled-components,
Playwright, CloudFlare / Crafting, Sentry, or Mixpanel. Use what the digest or
inline detection finds.

## Detection Workflow

Follow this order when persisting a full digest.

1. **Classify the repo** — `frontend-app`, `design-system`,
   `monorepo-frontend`, or `unknown`. Use workspace manifests, package layout,
   Storybook/token packages, app entrypoints, framework markers, internal
   package relationships.
2. **Detect package and workspace tooling** — package manager, workspace
   system, install command, likely lint/type-check/unit/E2E commands.
3. **Detect framework and rendering model** — React, Next.js, Vite, Remix,
   Storybook, library-only, SSR/SPA/component-library hints.
4. **Detect styling and design-system stack** — styled-components, Emotion,
   Tailwind, CSS Modules, Sass, component libraries, token packages, whether
   the repo publishes/consumes a design system.
5. **Detect data, state, and API patterns** — React Query, RTK Query, Redux,
   Zustand, Apollo, fetch wrappers, generated clients, endpoint registries.
   Determine API contract sources in ranked order (generated SDK, OpenAPI,
   Bruno/Postman, local backend, external backend).
6. **Detect testing stack** — Vitest, Jest, RTL, Playwright, Cypress,
   Storybook visual tests, workspace scoping.
7. **Detect analytics and observability** — Mixpanel, PostHog, Segment,
   Sentry, LogRocket, Datadog RUM. Do not force a tool if none is present.
8. **Detect CI/CD and workflow conventions** — CI provider, deploy platform,
   preview/sandbox tooling, release workflows, default branches, docs/planning
   folder conventions.
9. **Write applicability guidance** — mark each lane as `applies`, `partial`,
   or `out_of_scope`.

### Digest output

Write to `docs/frontend-skill-digest/AGENTS.md` (operating contract) and
`docs/frontend-skill-digest/project-digest.md` (full fingerprint). Both files
have required schemas defined in `references/digest-schema.md`.

Include freshness evidence: generated commit SHA, inspected file list, key
file hashes or mtimes.

## Lane Routing

After loading or detecting context, route the work into one lane.

### refresh-digest

Run the full Detection Workflow and persist both
`docs/frontend-skill-digest/AGENTS.md` and
`docs/frontend-skill-digest/project-digest.md`.

This is the only lane allowed to write digest files to the repo.

### review

PR review using Bumang-style priorities. Collect inline review threads,
resolved comments, and author replies via `gh api` for thread-aware review.

See `references/review.md` and `references/review-taste.md`.

### api

Frontend API integration using the repo's real contract source.

See `references/api-integration.md`.

### testing

Unit, component, integration, and E2E testing using detected stack.

See `references/testing.md`.

### analytics

Analytics tracking (Mixpanel, PostHog, Segment, etc.). Verify the tool
exists before proceeding; refuse if absent.

See `references/analytics.md`.

### observability

Error monitoring and observability (Sentry, LogRocket, Datadog RUM, etc.).
Verify the tool exists before proceeding; refuse if absent.

See `references/observability.md`.

### cicd

CI/CD pipeline debugging, deploy, preview, and release workflows.

See `references/cicd.md`.

### plan / new-branch

Feature planning and branch creation using detected conventions.

See `references/planning.md`.

### commit / pre-commit

Atomic commit creation and pre-commit quality gates.

See `references/commit-hygiene.md`.

### create-pr

PR creation using detected branch model, templates, and quality gates.

See `references/pr-workflow.md`.

## Applicability Rules

The digest must identify which lanes are safe:

- `design-system` repos: review, testing, planning, CI/CD, and
  release-dependency review usually apply. API integration or app analytics
  may be out of scope.
- `frontend-app` repos: all lanes may apply depending on local tooling.
- `monorepo-frontend` repos: lanes must identify the affected package(s)
  before choosing commands.

If the user requests a lane that does not fit the repo type, explain why and
stop or narrow the task.

## Missing Context Rules

Do not guess when important context is absent.

- If the frontend consumes an API but the contract lives only in a separate
  backend repo, record that and ask for a backend directory.
- If the repo has Bruno collections but no backend code, prefer Bruno as the
  contract source.
- If the repo has OpenAPI/Swagger, prefer that over reverse-engineering.
- If the repo is a monolith with frontend and backend together, detect the
  local backend path instead of asking.

## Output Expectations

When this skill is active:

- Mention whether you reused, refreshed, or ran ephemeral detection for the
  digest.
- State the detected repo class and the lane chosen.
- Name any missing context you had to ask for.
- Keep guidance repo-aware and dynamic.
