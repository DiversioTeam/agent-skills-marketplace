# Analytics Lane

Use this only when the repo's analytics stack actually includes a recognized
analytics tool (Mixpanel, PostHog, Segment, RudderStack, etc.).

## Preflight

Check the detected analytics stack from the digest or inline detection.

If the repo uses a different tool than expected, or no analytics tool at all,
say so explicitly. Do not pretend the repo uses Mixpanel or any other specific
tool.

## Workflow

### 1. Verify local applicability

Confirm:
- the analytics tool exists in the repo
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
- add events and properties in the repo's local pattern
- avoid PII unless the repo's approved policy explicitly allows a field
- keep event/property names consistent with the local taxonomy

When reviewing:
- check for direct SDK bypasses when a wrapper exists
- check privacy/PII compliance
- check readiness guards and user/session handling if the repo uses them

## Output

Report:
- digest status
- whether the analytics tool is actually present
- which tool was detected
- local tracking layer used
- privacy / quality findings
