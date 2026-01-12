# Error Handling Reference

Common errors and how the skill handles them.

## Token Errors

### Missing Token

```
❌ CLICKUP_TICKET_SKILL_TOKEN not found

Please set it in your shell profile:

   export CLICKUP_TICKET_SKILL_TOKEN="pk_..."

Get your token at: https://app.clickup.com/settings/apps
```

### Invalid Token

```
❌ ClickUp API error: Invalid token (OAUTH_019)

Your token may have expired or been regenerated.
Get a new token at: https://app.clickup.com/settings/apps
Then update CLICKUP_TICKET_SKILL_TOKEN in your shell profile.
```

## API Errors

### Rate Limited

The skill automatically handles rate limiting:

1. Detects 429 response from ClickUp API
2. Displays: `⏳ Rate limited. Waiting before retry... (attempt 1/3)`
3. Waits with exponential backoff
4. Retries up to 3 times
5. Fails gracefully with guidance if all retries exhausted

### Network Error

```
❌ Could not reach ClickUp API

Check your internet connection and try again.
If the problem persists, ClickUp may be experiencing issues:
https://status.clickup.com/
```

## Cache Errors

### Entity Not Found

When a list, space, or tag isn't in the cache:

```
⚠️ List "Sprint 99" not found in cache.

Refreshing workspace data...
✓ Cache refreshed

Still not found. Available lists:
   [1] Backlog
   [2] Sprint 47
   [3] Tech Debt

Select a list or create the missing one in ClickUp first.
```

The skill automatically attempts a cache refresh before failing.

### Stale Cache

When cache is older than TTL (default 24h):

```
ℹ️ Cache is stale. Refreshing in background...
```

The skill proceeds with stale data while refreshing asynchronously.

## Org Errors

### Org Not Found

```
❌ Organization 'foo' not found.

Available organizations:
   • diversio (active)
   • personal

Use: /clickup-ticket:switch-org <name>
```

### No Orgs Configured

```
❌ No organizations configured.

Run /clickup-ticket:configure to set up your first organization.
```
