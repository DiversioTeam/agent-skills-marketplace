Implement new Mixpanel tracking events in the frontend.

## Input

The user optionally provides: `$ARGUMENTS` (event description)

## Steps

1. Add event name to `MIXPANEL_EVENTS` enum
2. Add any new property keys to `MIXPANEL_PARAMS` enum
3. Track using `mixpanelService.trackEvent()` (never `mixpanel.track()` directly)
4. Always check `mixpanelService.isReady()` before tracking
5. For lifecycle events, create a `useXxxTracking` hook
6. Verify no PII in event properties (UUIDs only)
7. Handle impersonation (check `session_id` is not null)

## PII Rules

- ALLOWED: uuid, organization_id, user_role, organization_name
- FORBIDDEN: email, full_name, name, any PII
