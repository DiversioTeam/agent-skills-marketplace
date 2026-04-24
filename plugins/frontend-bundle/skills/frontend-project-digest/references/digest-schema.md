# Frontend Project Digest Schema

Use this schema when writing `docs/frontend-skill-digest/project-digest.md` in a
target repo.

## Required Sections

### 1. `## Repo Classification`

- `repo_kind`: `frontend-app` | `design-system` | `monorepo-frontend` | `unknown`
- `confidence`: `high` | `medium` | `low`
- short explanation of the signals used

### 2. `## Tooling`

- package manager
- workspace manager / monorepo tooling
- install command
- lint command
- type-check command
- unit/component test command
- E2E test command

### 3. `## Framework & Runtime`

- primary frontend framework
- rendering model / packaging mode
- main app or package paths

### 4. `## Styling & Design System`

- styling solution(s)
- token source
- internal design-system packages
- whether the repo publishes a design system, consumes one, or both

### 5. `## Data, State & API`

- data fetching / state libraries
- API client pattern
- endpoint registry or generated client location
- API contract sources in ranked order
- backend directory mapping, if local
- explicit note when backend context is missing and must be requested later

### 6. `## Testing Stack`

- unit/component frameworks
- E2E framework
- test setup files or package paths
- workspace scoping notes

### 7. `## Analytics & Observability`

- analytics stack
- observability stack
- service-layer or bootstrap locations if obvious

### 8. `## CI/CD & Release Signals`

- CI provider
- deploy platform
- preview / sandbox platform
- release workflow hints

### 9. `## Workflow Conventions`

- default branch or branches
- PR/release branch model
- docs / planning folder conventions
- import / naming / package conventions worth reusing

### 10. `## Skill Applicability Map`

For each lane, mark one of:
- `applies`
- `partial`
- `out_of_scope`

Required lanes:
- PR review
- API integration
- testing
- analytics
- observability
- CI/CD
- planning
- commit hygiene

### 11. `## Freshness`

- generated timestamp
- files/signals inspected
- what should trigger a refresh

### 12. `## Open Questions`

List unresolved items that later skills must confirm instead of guessing.

## Example Missing-Context Notes

- “The repo consumes backend APIs but does not contain backend code, OpenAPI, or
  Bruno collections. Future API-integration work must ask the user for a
  backend working directory or API spec path.”
- “This monorepo contains both app and design-system packages. Later commands
  must identify the affected package before selecting lint/test commands.”
