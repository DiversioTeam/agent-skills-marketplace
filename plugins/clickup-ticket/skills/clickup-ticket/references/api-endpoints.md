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

## Task Read Operations

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v2/task/{task_id}` | GET | Get single task details |
| `/api/v2/list/{list_id}/task` | GET | Get tasks in a list (100/page max) |
| `/api/v2/team/{team_id}/task` | GET | **Filtered team tasks** (most powerful) |

### Get Task (`GET /api/v2/task/{task_id}`)

Query parameters:
- `custom_task_ids` (boolean) - Use custom task ID instead of system ID
- `team_id` (number) - Required when using custom_task_ids
- `include_subtasks` (boolean) - Include subtask details
- `include_markdown_description` (boolean) - Return markdown description

Returns: Full task object with id, name, status, description, assignees,
due_date, custom_fields, checklists, attachments (metadata only), watchers,
parent, linked_tasks, and more.

### Get Tasks in List (`GET /api/v2/list/{list_id}/task`)

Query parameters:
- `page` (integer) - Page number (0-indexed)
- `include_closed` (boolean) - Include closed tasks (default: false)

Returns: Array of tasks (max 100 per page). Only includes tasks where the
specified list is their home list.

### Get Filtered Team Tasks (`GET /api/v2/team/{team_id}/task`)

The most powerful endpoint for filtering tasks across a workspace.

Query parameters (all optional):
- `page` (integer) - Page number (0-indexed)
- `order_by` (string) - Sort field: `created`, `updated`, `due_date`
- `reverse` (boolean) - Reverse sort order
- `include_closed` (boolean) - Include closed tasks
- `subtasks` (boolean) - Include subtasks in results
- `statuses[]` (array) - Filter by status names
- `assignees[]` (array) - Filter by user IDs
- `tags[]` (array) - Filter by tag names
- `due_date_gt` (integer) - Due after (Unix timestamp ms)
- `due_date_lt` (integer) - Due before (Unix timestamp ms)
- `date_created_gt` (integer) - Created after (Unix timestamp ms)
- `date_created_lt` (integer) - Created before (Unix timestamp ms)
- `date_updated_gt` (integer) - Updated after (Unix timestamp ms)
- `date_updated_lt` (integer) - Updated before (Unix timestamp ms)
- `space_ids[]` (array) - Filter by space IDs
- `project_ids[]` (array) - Filter by folder/project IDs
- `list_ids[]` (array) - Filter by list IDs
- `custom_fields` (string) - JSON array of custom field filters

**Custom field filter format:**
```json
[{"field_id": "abc123", "operator": "=", "value": "some text"}]
```

Operators: `=` (contains), `!=`, `<`, `<=`, `>`, `>=`, `IS NULL`, `IS NOT NULL`

**Important limitations:**
- No text search by task name/title (feature not available in API)
- Max 100 tasks per response
- Requires pagination for large result sets

## Task Write Operations

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v2/list/{list_id}/task` | POST | Create task (use `parent` field for subtasks) |
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
