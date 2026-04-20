---
name: frontend-sentry
description: "Sentry error monitoring for React frontends: PII scrubbing, feature area tagging, distributed tracing, Redux breadcrumbs, sourcemap debugging, and production error investigation workflows."
---

# Frontend Sentry Skill

Error monitoring and debugging guide for frontend Sentry integrations.

---

## Argument Routing

| Argument  | Action                                |
| --------- | ------------------------------------- |
| (none)    | Show architecture overview            |
| `debug`   | Guide for investigating Sentry errors |
| `context` | How to add context to errors          |
| `verify`  | How to verify Sentry is working       |

---

## Architecture Overview

### Initialization Flow

```
App Start -> initSentry()
  |
  +--> DSN from env var
  +--> Environment: production | staging | development
  +--> Release: app-name@{version}
  |
  +--> Integrations:
  |     +--> replayIntegration (maskAllText in prod)
  |     +--> browserTracingIntegration (with trace propagation to API)
  |
  +--> beforeSend: enhance with context
  |     +--> Adds feature_area tag (from URL)
  |     +--> Adds user_role tag
  |     +--> Adds organization_id tag
  |     +--> Scrubs PII from all event data
  |
  +--> Sample Rates:
        +--> Traces: 2% production, 10% staging
        +--> Replays: 10% session, 100% on error
```

### User Context (Set on Auth)

```
Login -> setUserContext(user, organization)
  |
  +--> Sentry.setUser({ id: uuid, email, username })
  +--> Sentry.setTag('user_role', role)
  +--> Sentry.setTag('organization_id', org.uuid)

Logout -> clearUserContext()
  |
  +--> Sentry.setUser(null)
  +--> Tags reset
```

---

## PII Scrubbing

All Sentry events are scrubbed before sending. Apply these patterns recursively to all string values:

| Pattern                           | Matches         | Replaced With       |
| --------------------------------- | --------------- | ------------------- |
| Email regex                       | Email addresses | `[email]`           |
| `bearer\s+[\w-]+` (insensitive)  | Bearer tokens   | `bearer [redacted]` |
| Employee ID pattern               | Employee IDs    | `[employee-id]`     |

**When adding new error context or breadcrumbs, ensure no PII leaks through.**

---

## Feature Area Tagging

Every Sentry event is tagged with a `feature_area` based on the current URL path:

| URL Pattern   | Feature Area            |
| ------------- | ----------------------- |
| `/dashboard`  | `dashboard`             |
| `/upload`     | `uploads`               |
| `/intake`     | `hr_intake`             |
| `/people`     | `people_management`     |
| `/team`       | `team_management`       |
| `/alerts`     | `alerts`                |
| `/auth/`      | `authentication`        |
| `/403`, `/404`| `error_boundary`        |
| (no match)    | `unknown`               |

**To add a new feature area:** Add a rule to `FEATURE_AREA_RULES` in the Sentry init file.

---

## Distributed Tracing

The frontend propagates Sentry tracing headers to the backend API:

- Extracts API origin from the API URL env var
- Passes it to `tracePropagationTargets` in browser tracing
- Backend allows `sentry-trace` and `baggage` headers in CORS
- Enables linked traces: FE span -> BE transaction

---

## Debugging Sentry Errors

### Step 1: Identify the Error

In the Sentry dashboard, look for:
- **Feature area tag** - Which part of the app?
- **User role tag** - Which role?
- **Organization ID** - Which org?
- **Release version** - Which deploy?
- **Breadcrumbs** - What actions led to the error?

### Step 2: Find the Source Code

Sourcemaps are uploaded in CI. If sourcemaps are missing:
- Check auth token is set in the deploy workflow
- Check Vite config - sourcemaps upload is conditional on CI + auth token
- Check the Sentry release matches the expected format

### Step 3: Reproduce Locally

Use the feature area and breadcrumbs to navigate to the same flow. Check:
- Browser console for errors
- Network tab for failed API calls
- Redux DevTools for state issues

### Step 4: Add Context for Future Debugging

```typescript
import * as Sentry from '@sentry/react'

// Add a breadcrumb before a risky operation
Sentry.addBreadcrumb({
    category: 'feature-name',
    message: 'Starting risky operation',
    level: 'info',
    data: { operationId: '...' },
})

// Capture with extra context
try {
    await riskyOperation()
} catch (error) {
    Sentry.captureException(error, {
        tags: { feature_area: 'uploads' },
        extra: { jobId, fileSize },
    })
}
```

---

## Profiling Critical Operations

```typescript
import { profileCriticalOperation } from '@/lib/sentry'

const result = await profileCriticalOperation('operation-name', async () => {
    return await heavyOperation(data)
})
```

Creates a Sentry span with automatic error status on failure.

---

## Redux Middleware

The Sentry middleware adds breadcrumbs for auth actions and captures exceptions from Redux with state context (slice keys, action type).

Tracked actions:
- `auth/login/fulfilled`
- `auth/login/rejected`
- `auth/logout/fulfilled`
- `auth/logout/rejected`

---

## Environment Mapping

| Deploy Target | Sentry Environment | Sourcemaps           |
| ------------- | ------------------ | -------------------- |
| Production    | `production`       | Full release created |
| Staging       | `staging`          | Deploy record posted |
| Preview (PRs) | `staging`          | Deploy record posted |

### Release Flow (Production)

```bash
VERSION="app-name@${GITHUB_SHA}"
npx @sentry/cli releases new "$VERSION"
npx @sentry/cli releases set-commits "$VERSION" --auto
npx @sentry/cli releases deploys "$VERSION" new --env production
npx @sentry/cli releases finalize "$VERSION"
```

---

## Verifying Sentry (Non-Production Only)

Use a hidden test route (e.g., `/__sentry-test`) on staging to:
1. Trigger an unhandled error
2. Send a handled exception
3. Verify events appear in Sentry dashboard with correct environment tag
