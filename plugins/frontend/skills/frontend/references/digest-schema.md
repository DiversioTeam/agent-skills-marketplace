# Frontend Digest Schemas

## Generated `AGENTS.md` — Operating Contract

Use this schema when writing `docs/frontend-skill-digest/AGENTS.md` in a target
repo. This file is the operating contract that all frontend lanes read before
acting on the digest.

### Required Sections

#### 1. `## Purpose`

- What this digest folder contains and why it exists.
- That `project-digest.md` is the authoritative fingerprint; `AGENTS.md` is the
  operating contract that governs how lanes consume it.

#### 2. `## Authoritative File`

- State that `project-digest.md` is the single source of truth for repo
  detection results.
- `AGENTS.md` (this file) governs trust, freshness, and re-check rules.

#### 3. `## When to Refresh`

- List the signals that should trigger a digest refresh: lockfile change,
  workspace layout change, primary framework change, new analytics/observability
  tool, CI provider change, branch model change, or any signal listed in the
  freshness section of `project-digest.md`.
- State that only `/frontend:refresh-digest` persists updates; all other
  commands use ephemeral inline detection when the digest is stale.

#### 4. `## Trust and Re-check Rules`

- Which digest fields lanes should trust without re-checking: repo
  classification, package manager, framework, workspace layout.
- Which fields lanes should verify at runtime when staleness is possible:
  analytics/observability stack, API contract sources, CI provider, test
  commands, branch model.
- That lanes must never silently override digest values; if a lane detects a
  mismatch, it should note the discrepancy and recommend a refresh.

---

## Generated `project-digest.md` — Full Fingerprint

Use this schema when writing `docs/frontend-skill-digest/project-digest.md` in a
target repo.

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
- generated commit SHA
- files/signals inspected
- key file hashes or mtimes
- what should trigger a refresh

### 12. `## Open Questions`

List unresolved items that later skills must confirm instead of guessing.

## Example Missing-Context Notes

- "The repo consumes backend APIs but does not contain backend code, OpenAPI, or
  Bruno collections. Future API-integration work must ask the user for a
  backend working directory or API spec path."
- "This monorepo contains both app and design-system packages. Later commands
  must identify the affected package before selecting lint/test commands."
