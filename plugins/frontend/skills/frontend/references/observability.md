# Observability Lane

Use this only when the repo's observability stack actually includes a
recognized error-monitoring or observability tool (Sentry, LogRocket, Datadog
RUM, etc.).

## Preflight

Check the detected observability stack from the digest or inline detection.

If the repo uses another tool or no frontend error-monitoring tool, say so
explicitly instead of forcing tool-specific advice.

## Workflow

### 1. Verify local applicability

Confirm:
- the observability tool is present
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
- use the repo's real release/environment flow
- check local source-map/upload path
- inspect breadcrumbs/tags/context already used in the repo

When extending:
- add context and breadcrumbs through the local abstraction when one exists
- preserve privacy rules
- keep tags and event grouping aligned with the repo's pattern

## Output

Report:
- digest status
- whether the observability tool is actually present
- which tool was detected
- local init/release pattern used
- debugging or instrumentation findings
