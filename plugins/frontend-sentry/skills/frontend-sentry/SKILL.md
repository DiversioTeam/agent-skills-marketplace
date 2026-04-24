---
name: frontend-sentry
description: "Digest-first Sentry workflow for frontend repos. Verifies that Sentry is present, adapts to local bootstrap and release patterns, and avoids assuming Redux/Vite/url-tagging specifics."
---

# Frontend Sentry Skill

Use this only when the repo’s observability stack actually includes Sentry.

## Digest-First Preflight

1. Load `docs/frontend-skill-digest/project-digest.md`.
2. Refresh it first if missing or stale.
3. Check the detected observability stack.

If the repo uses another tool or no frontend error-monitoring tool, say so
explicitly instead of forcing Sentry-specific advice.

## Workflow

### 1. Verify local applicability

Confirm:
- Sentry is present
- local bootstrap/init location
- release/sourcemap flow
- privacy or scrubbing rules
- user/context tagging conventions

### 2. Match the local architecture

Possible patterns:
- framework bootstrap init file
- shared observability wrapper
- route/component-level capture helpers
- CI-based sourcemap upload

Do not assume:
- Vite
- Redux middleware
- feature area from URL rules
- one specific release naming pattern

### 3. Debug or extend instrumentation

When debugging:
- use the repo’s real release/environment flow
- check local source-map/upload path
- inspect breadcrumbs/tags/context already used in the repo

When extending:
- add context and breadcrumbs through the local abstraction when one exists
- preserve privacy rules
- keep tags and event grouping aligned with the repo’s pattern

## Output

Report:
- digest status
- whether Sentry is actually present
- local init/release pattern used
- debugging or instrumentation findings
