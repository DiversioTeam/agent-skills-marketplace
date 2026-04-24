Sentry guidance for the frontend using the repo-local digest and local
observability setup.

## Input

The user optionally provides: `$ARGUMENTS` (`debug`, `context`, or `verify`)

## Routing

- `debug` - Investigate a Sentry error using the repo’s real init/release flow
- `context` - Add breadcrumbs or tags using the local abstraction
- `verify` - Check Sentry is working if the repo actually uses it
- (none) - Show architecture overview

## Quick Reference

- First confirm the repo actually uses Sentry.
- Use the repo’s local bootstrap/wrapper/release flow.
- Do not assume Vite, Redux, or URL-derived feature-area tagging.
