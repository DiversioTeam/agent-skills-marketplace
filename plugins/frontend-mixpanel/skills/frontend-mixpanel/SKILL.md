---
name: frontend-mixpanel
description: "Digest-first Mixpanel workflow for frontend repos. Verifies that Mixpanel is actually present, adapts to the local tracking layer, and refuses to assume a specific service, enum, or impersonation model."
---

# Frontend Mixpanel Skill

Use this only when the repo’s analytics stack actually includes Mixpanel or a
Mixpanel-backed wrapper.

## Digest-First Preflight

1. Load `docs/frontend-skill-digest/project-digest.md`.
2. Refresh it first if missing or stale.
3. Check the detected analytics stack.

If the digest shows PostHog, Segment, RudderStack, or no analytics instead of
Mixpanel, say so explicitly. Do not pretend the repo is Mixpanel-based.

## Workflow

### 1. Verify local applicability

Confirm:
- Mixpanel exists in the repo
- the local service/bootstrap layer location
- event naming / typing pattern
- repo-specific privacy rules

### 2. Match the local tracking architecture

Possible patterns:
- service wrapper
- analytics hooks
- typed event registry
- direct SDK bootstrap with a shared helper

Use the local abstraction if one exists. Do not force enums, localStorage
persistence, or impersonation rules unless the repo actually uses them.

### 3. Add or review tracking

When implementing:
- add events and properties in the repo’s local pattern
- avoid PII unless the repo’s approved policy explicitly allows a field
- keep event/property names consistent with the local taxonomy

When reviewing:
- check for direct SDK bypasses when a wrapper exists
- check privacy/PII compliance
- check readiness guards and user/session handling if the repo uses them

## Output

Report:
- digest status
- whether Mixpanel is actually present
- local tracking layer used
- privacy / quality findings
