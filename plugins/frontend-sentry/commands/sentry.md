Sentry error monitoring guidance for the frontend.

## Input

The user optionally provides: `$ARGUMENTS` (`debug`, `context`, or `verify`)

## Routing

- `debug` - Investigate a Sentry error (read logs, find source, reproduce)
- `context` - Add breadcrumbs or tags to improve future debugging
- `verify` - Check Sentry is working (staging test route)
- (none) - Show architecture overview

## Quick Reference

- **Add breadcrumb:** `Sentry.addBreadcrumb({ category, message, level, data })`
- **Capture with context:** `Sentry.captureException(error, { tags, extra })`
- **Profile operation:** `profileCriticalOperation('name', async () => { ... })`
- **Feature area rules:** `FEATURE_AREA_RULES` in Sentry init file
- **PII scrubbing:** Automatic - emails, tokens, employee IDs replaced
