Implement Mixpanel tracking using the repo-local digest and local tracking
architecture.

## Input

The user optionally provides: `$ARGUMENTS` (event description)

## Steps

1. Load or refresh `docs/frontend-skill-digest/project-digest.md`.
2. Confirm the repo actually uses Mixpanel.
3. Use the repo’s existing wrapper/service/hook pattern for event registration.
4. Follow the repo’s privacy rules and readiness/session guards.
5. Do not assume enum names, impersonation handling, or persistence details
   unless they exist locally.

## PII Rules

Follow the repo’s approved analytics privacy policy. If that policy is not
discoverable, default to treating direct PII as forbidden.
