---
name: frontend-mixpanel
description: "Mixpanel analytics integration for React frontends: event tracking with enums, PII compliance, impersonation handling, session management, opt-out/in behavior, and privacy-first patterns."
---

# Frontend Mixpanel Skill

Analytics tracking and integration guide for frontend Mixpanel implementations.

## When to Use This Skill

- When adding new Mixpanel tracking events, reviewing PII compliance, or debugging analytics.
- `/frontend-mixpanel:implement` — add a new tracking event with enum registration.
- `/frontend-mixpanel:review` — audit existing Mixpanel implementation for compliance.

## Example Prompts

- "Add a Mixpanel event for the dashboard page view"
- "Review the login tracking for PII compliance"
- "Debug why page view events aren't firing"

---

## Argument Routing

| Argument       | Action                                                        |
| -------------- | ------------------------------------------------------------- |
| (none)         | Show architecture overview and quick reference                |
| `track`        | Guide for adding a new tracking event                         |
| `review`       | Review existing implementation for PII compliance and quality |
| `debug`        | Debug analytics issues (events not firing, missing data)      |
| `architecture` | Deep dive into the full Mixpanel architecture                 |

---

## Architecture Overview

### High-Level Flow

```
App Start -> MixpanelService.init()
  |
  +--> API Key from env var
  +--> Autocapture: DISABLED (manual tracking only)
  +--> Persistence: localStorage
  |
Login -> identify(user.uuid) + register super properties
  |
  +--> Check session_id (null = impersonation -> opt out)
  +--> trackEvent('Session Started', { login_method, device_type })
  |
Navigation -> Page View tracking
  +--> First Page View (once per session)
  +--> Page View (subsequent navigations, excludes auth routes)
  |
Tab Events -> Visibility tracking
  +--> Tab Closed (sendBeacon transport for guaranteed delivery)
  +--> Tab Reopened (tracks time away)
  |
Logout -> trackEvent('Session Ended') + optOut + reset
```

---

## PII Policy (CRITICAL)

**ALLOWED:**
- `uuid` (user UUID)
- `organization_id` (org UUID)
- `user_role` (EMPLOYEE, MANAGER, HR_MANAGER, etc.)
- `organization_name` (if management approved)

**FORBIDDEN:**
- `email`
- `full_name` / `name`
- Any other personally identifiable information

**Impersonation:** When `session_id` is `null`, call `mixpanelService.optOutTracking()` to prevent ALL tracking.

---

## Identity Management

### Identify Timing Rules

- **Call `identify()` ONLY at login/registration** - when you know the user's backend UUID.
- **NEVER call `identify()` for anonymous/unauthenticated visitors.** The SDK auto-assigns a `$device_id`.
- **Call `reset()` on logout** to generate a new anonymous `$device_id` for the next session.

### Identity Merge Models

- **Simplified ID Merge** (default for new orgs after April 2024): Auto-links `$device_id` to `$user_id` on first `identify()`.
- **Original ID Merge** (legacy): Requires explicit `alias()`.

---

## Adding a New Tracking Event

### Step 1: Add the event name to the enum

```typescript
// src/types/mixpanel/events.enum.ts
export enum MIXPANEL_EVENTS {
    // ... existing events
    MY_NEW_EVENT = 'My New Event',
}
```

### Step 2: Add any new property keys

```typescript
// src/types/mixpanel/parameters.enum.ts
export enum MIXPANEL_PARAMS {
    // ... existing params
    MY_NEW_PARAM = 'my_new_param',
}
```

### Step 3: Track the event using the service layer

```typescript
import { mixpanelService } from '@/services/mixpanel'
import { MIXPANEL_EVENTS } from '@/types/mixpanel/events.enum'
import { MIXPANEL_PARAMS } from '@/types/mixpanel/parameters.enum'

if (mixpanelService.isReady()) {
    mixpanelService.trackEvent(MIXPANEL_EVENTS.MY_NEW_EVENT, {
        [MIXPANEL_PARAMS.MY_NEW_PARAM]: 'value',
    })
}
```

### Step 4: For lifecycle events, create a hook

```typescript
// src/hooks/mixpanel/useMyTracking.ts
import { useCallback } from 'react'
import { mixpanelService } from '@/services/mixpanel'
import { MIXPANEL_EVENTS } from '@/types/mixpanel/events.enum'

export function useMyTracking() {
    const trackMyEvent = useCallback((data: SomeType) => {
        if (!mixpanelService.isReady()) return
        mixpanelService.trackEvent(MIXPANEL_EVENTS.MY_NEW_EVENT, { /* properties */ })
    }, [])

    return { trackMyEvent }
}
```

---

## Opt-Out / Opt-In Behavior

### How opt-out works

When `optOutTracking()` is called:
- ALL tracking calls are silently ignored
- State is **persisted to localStorage** and survives page refresh
- No data is transmitted to Mixpanel servers

### How opt-in works

When `optInTracking()` is called:
- Tracking resumes normal operation
- **Mixpanel fires a `$opt_in` event automatically**
- State is persisted to localStorage

### Order matters

```typescript
// CORRECT: Track final event BEFORE opting out
trackSessionEnded(LOGOUT_REASONS.USER_INITIATED)
mixpanelService.optOutTracking()  // Now silence everything

// WRONG: Opting out first drops the event
mixpanelService.optOutTracking()
trackSessionEnded(...)  // Silently dropped!
```

---

## Event Taxonomy

### Property Tiers

1. **Super Properties** (session-scoped, auto-appended to ALL events):
   - `session_id`, `user_id`, `user_role`, `organization_id`, `impersonation`

2. **Event Properties** (per-event, passed to `trackEvent()`):
   - `login_method`, `logout_reason`, `page_path`, `time_on_page_seconds`, etc.

3. **Auto-Injected** (by service `trackEvent()`):
   - `src: "frontend"`, `$insert_id`, `impersonation`

---

## Key Rules

1. **Use the service layer** - Never call `mixpanel.track()` directly.
2. **Use enums** - Event names via `MIXPANEL_EVENTS`, property keys via `MIXPANEL_PARAMS`.
3. **Check readiness** - Always verify `mixpanelService.isReady()` before tracking.
4. **No PII** - Never include email, name, or other PII. UUIDs only.
5. **Handle impersonation** - Check `session_id` is not null before tracking.
6. **Use sendBeacon** for tab close/unload events: `{ transport: 'sendBeacon' }`.
7. **Autocapture is disabled** - All tracking is manual via hooks and service methods.
8. **Only identify authenticated users** - Never call `identify()` for anonymous visitors.

---

## MixpanelService API Reference

| Method                          | Purpose                                        |
| ------------------------------- | ---------------------------------------------- |
| `init()`                        | Initialize Mixpanel (called once at app start) |
| `trackEvent(name, props, opts)` | Track an event with auto-injected properties   |
| `identifyUser(userId)`          | Link browser distinct_id to backend UUID       |
| `optOutTracking()`              | Disable ALL tracking (impersonation)           |
| `optInTracking()`               | Re-enable tracking                             |
| `hasOptedOut()`                 | Check opt-out status                           |
| `reset()`                       | Clear all state on logout                      |
| `isReady()`                     | Check if initialized                           |
| `timeEvent(name)`               | Start timing an event                          |

---

## Debugging Checklist

1. **Events not firing?**
   - Check Mixpanel API key env var is set
   - Check `mixpanelService.isReady()` returns `true`
   - Check `mixpanelService.hasOptedOut()` returns `false`
   - Check browser console for `[Mixpanel]` warnings

2. **Missing properties?**
   - Verify super-properties are registered (happens on login)
   - Check if the event is using enum keys
   - Confirm `trackEvent()` auto-injects `src` and `$insert_id`

3. **Impersonation issues?**
   - `session_id: null` from backend = impersonation session
   - Must call `optOutTracking()` to silence ALL events

---

## Review Checklist (PII & Quality)

- [ ] No email, name, or PII in event properties
- [ ] Uses event name enum (not string literals)
- [ ] Uses params enum for property keys
- [ ] Uses service `trackEvent()` (not `mixpanel.track()` directly)
- [ ] Checks `isReady()` before tracking
- [ ] Handles impersonation (checks `session_id`)
- [ ] Hook follows `useXxxTracking` naming convention
- [ ] 0 lint errors, 0 type-check errors
