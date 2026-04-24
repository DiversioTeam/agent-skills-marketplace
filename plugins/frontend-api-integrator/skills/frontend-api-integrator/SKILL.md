---
name: frontend-api-integrator
description: "Digest-first frontend API integration workflow. Detects the repo’s real API contract source and local client pattern, supports monorepos and monoliths, and asks for backend/spec paths only when the repo does not already provide them."
---

# Frontend API Integrator Skill

Implement frontend API work by matching the current repo’s actual contract
source and client architecture.

## When to Use This Skill

- Adding or updating a frontend API integration.
- Wiring endpoint types, generated clients, hooks, or service functions.
- Investigating how a frontend should consume a backend contract in an app,
  monorepo, or monolith.

## Digest-First Preflight

Before changing code:

1. Load `docs/frontend-skill-digest/AGENTS.md` and
   `docs/frontend-skill-digest/project-digest.md`.
2. Refresh the digest first if it is missing, stale, or clearly inconsistent.
3. Use the digest’s repo class, package manager, workspace layout, data/state
   stack, and API contract sources.

Do not assume:
- React Query
- axios
- `src/api/actions`
- query/mutation enums
- a separate backend repo

## Step 1: Confirm Applicability

Use the digest to decide whether API integration applies:

- `frontend-app`: usually applies
- `monorepo-frontend`: applies, but first identify the affected package
- `design-system`: often out of scope unless the repo includes demo apps,
  contract fixtures, or API-bound examples

If the digest marks API integration as partial or out of scope, explain why
before proceeding.

## Step 2: Resolve The API Contract Source

Choose the best contract source in this order:

1. generated SDK / typed client already used in the repo
2. OpenAPI / Swagger files or generated schema artifacts
3. Bruno / Postman / Insomnia collections
4. backend code in the same repo or monorepo
5. backend code outside the repo, if provided by the user

### Missing-context rule

Only ask for a backend working directory when the repo does not already contain
enough contract context.

Examples:
- If OpenAPI or Swagger exists locally, use it instead of asking for backend code.
- If Bruno docs exist locally, use them instead of reverse-engineering endpoints
  from components.
- If the repo is a monolith with frontend and backend together, detect the local
  backend path and use it.
- If none of the above exist, ask the user for one of:
  - backend working directory
  - API spec path / URL
  - docs collection path

## Step 3: Inspect The Existing Frontend Pattern

Use the digest and local code to identify the real implementation pattern:
- generated client consumption
- service/module functions
- hooks wrapping services
- Redux/RTK Query slices
- TanStack Query hooks
- plain fetch utilities

Match the existing naming, folder layout, and error-handling style. Do not
force the old `actions + hooks + endpoints + enums` shape if the repo uses a
different one.

## Step 4: Identify The Affected Package And Working Directory

For monorepos or monoliths:
- identify the frontend package/app that consumes the API
- identify the backend service or docs path if local
- record both before editing

If backend context is external, ask for the backend directory only after
confirming it is actually needed.

## Step 5: Implement Using The Local Contract

Common valid implementation shapes:

### Generated client / SDK

- update generation inputs if needed
- use the existing generated client entrypoint
- avoid hand-writing duplicate endpoint wrappers

### OpenAPI / Swagger contract

- derive request/response types from the spec or the repo’s generation flow
- place code where the repo normally stores API clients or hooks

### Bruno / Postman / Insomnia contract

- treat the collection as the request/response source of truth
- reconcile with existing frontend client patterns
- ask for backend clarification only if the collection is ambiguous

### Backend-code contract

- inspect the backend serializer / handler / controller behavior
- model frontend types against the shipped response contract, not only comments

## Step 6: Verify The Integration

Run the digest-selected quality gates for the affected package:
- lint
- type-check
- relevant tests

In addition, verify:
- no duplicate client abstraction was introduced
- request/response types match the chosen contract source
- cache keys / invalidation / store updates are locally consistent
- error handling matches the repo’s pattern

## Output Expectations

Report:
- digest status (reused/refreshed)
- repo class and affected package
- chosen API contract source
- whether backend/spec context was local or requested from the user
- quality gates run
