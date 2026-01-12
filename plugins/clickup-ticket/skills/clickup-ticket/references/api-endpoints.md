# ClickUp API Endpoints Reference

This skill uses the ClickUp API v2. For official documentation, see:
https://developer.clickup.com/reference

## Discovery Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v2/team` | GET | List workspaces (called "teams" in API) |
| `/api/v2/team/{team_id}/space` | GET | List spaces in workspace |
| `/api/v2/space/{space_id}/folder` | GET | List folders in space |
| `/api/v2/folder/{folder_id}/list` | GET | Lists in folder |
| `/api/v2/space/{space_id}/list` | GET | Folderless lists in space |
| `/api/v2/space/{space_id}/tag` | GET | Tags in space |
| `/api/v2/list/{list_id}/member` | GET | Members with list access |
| `/api/v2/list/{list_id}` | GET | List details with statuses |
| `/api/v2/team/{team_id}/member` | GET | All workspace members |

## Task Operations

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v2/list/{list_id}/task` | POST | Create task (use `parent` field for subtasks) |
| `/api/v2/task/{task_id}` | GET | Get task details |
| `/api/v2/task/{task_id}` | PUT | Update task |
| `/api/v2/task/{task_id}/tag/{tag_name}` | POST | Add tag to task |

## Authentication

All requests include these headers:

```
Authorization: {token}
Content-Type: application/json
```

Where `{token}` is your `CLICKUP_TICKET_SKILL_TOKEN` value.

**Note:** Personal API tokens do not use the "Bearer" prefix.

## Terminology Note

ClickUp's API uses "team" to refer to what the UI calls "Workspace". This skill
uses "workspace" in user-facing text but "team_id" when referencing API parameters.

## Rate Limits

ClickUp enforces rate limits per token. Limits vary by plan tier—see official
docs for current values. This skill handles 429 responses with automatic retry
and exponential backoff.

https://developer.clickup.com/docs/getting-started#rate-limits
