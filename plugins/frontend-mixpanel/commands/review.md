Review Mixpanel implementations for PII compliance and quality.

## Steps

1. Scan for direct `mixpanel.track()` calls (should use service layer)
2. Check all event properties for PII (email, name, etc.)
3. Verify event names use `MIXPANEL_EVENTS` enum
4. Verify property keys use `MIXPANEL_PARAMS` enum
5. Check `isReady()` guard before all tracking calls
6. Verify impersonation handling (session_id null check)
7. Check hook naming follows `useXxxTracking` convention

## Output

Report findings as a checklist with pass/fail status and specific file:line references.
