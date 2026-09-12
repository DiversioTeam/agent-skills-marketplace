## Ticket Reading Workflows

### Get Single Ticket

`/clickup-ticket:get-ticket <id|url>`

Fetch complete details for any ticket you have access to.

Accepted inputs:

- Task ID: `abc123` or `#abc123`
- Task URL: `https://app.clickup.com/t/abc123`
- Custom ID: `DEV-123` (requires `--org` when workspace context is needed)

**Flags:**

- `--subtasks` - Include full subtask details
- `--comments` - Include recent comments (last 10)
- `--markdown` - Return description with markdown formatting
- `--org=<slug>` - Specify organization for custom IDs

### List and Filter Tickets

`/clickup-ticket:list-tickets [filters]`

Powerful workspace-wide filtering using the Get Filtered Team Tasks API.

| Filter | Description | Example |
|--------|-------------|---------|
| `--list=<name\|id>` | Filter by list | `--list=Backlog` |
| `--space=<name\|id>` | Filter by space | `--space=Engineering` |
| `--project=<name\|id>` | Filter by project/folder | `--project=Projects` |
| `--status=<status>` | Filter by status | `--status="in progress"` |
| `--assignee=<email\|me>` | Filter by assignee | `--assignee=me` |
| `--tag=<tags>` | Filter by tags | `--tag=bug,urgent` |
| `--priority=<1-4>` | Filter by priority | `--priority=1` |
| `--due-before=<date>` | Due before date | `--due-before=2024-02-01` |
| `--due-after=<date>` | Due after date | `--due-after=tomorrow` |
| `--created-after=<date>` | Created after | `--created-after="last week"` |
| `--include-closed` | Include closed tasks | (flag) |
| `--subtasks` | Include subtasks | (flag) |
| `--limit=<n>` | Limit results | `--limit=50` |
| `--page=<n>` | Pagination | `--page=2` |
| `--sort=<field>` | Sort by field | `--sort=due_date` |
| `--reverse` | Reverse sort | (flag) |

Supported date formats:

- ISO: `2024-01-31`
- Relative: `today`, `tomorrow`, `yesterday`
- Natural: `next week`, `last monday`, `in 3 days`

### My Tickets

`/clickup-ticket:my-tickets`

Quick view of tickets assigned to you, grouped by urgency.

Default behavior:

- Shows open tickets only
- Grouped: Overdue → Due This Week → No Due Date
- Sorted by due date within groups

**Flags:**

- `--overdue` - Show only overdue tickets
- `--due-today` - Show tickets due today
- `--due-this-week` - Show tickets due this week
- `--space=<name>` - Filter by space
- `--include-closed` - Include completed tickets

### API Limitations

The ClickUp API does **not** support text search by task name or description.

Workarounds:

1. Use filters (`--tag`, `--list`, `--status`, `--assignee`) to narrow results.
2. If you know the ticket ID, use `get-ticket` directly.
3. Use `list-spaces` to find the right list, then filter by list.

Response limits:

- API returns max 100 tasks per request
- Use `--page` for pagination
- Use filters to reduce result set

## Configuration Workflow

### First-Time Setup

`/clickup-ticket:configure` should:

1. Validate the token.
2. Discover accessible workspaces.
3. Cache workspace structure.
4. Set default org, list, assignee, and backlog behavior.

### Multi-Org Setup

To add additional organizations:

```bash
/clickup-ticket:add-org
```

If a client workspace uses a separate token, point the command at a dedicated
environment variable. See `usage-workflows.md` for the full example.

## Ticket Creation Workflows

### Full Interactive Creation

`/clickup-ticket:create-ticket`

Walks you through:

1. **Title** (required)
2. **List** - Shows your lists, defaults to configured default
3. **Priority** - Urgent / High / Normal / Low
4. **Assignee** - Shows team members from cache
5. **Tags** - Shows available tags, multi-select
6. **Description** - Optional markdown description
7. **Due date** - Optional, with quick picks

### Quick Ticket

`/clickup-ticket:quick-ticket "Title here"`

Creates a ticket instantly with defaults.

**Flags:**

- `--priority=high` or `-p high` - Override priority
- `--list=bugs` - Override list
- `--org=personal` - Create in different org
- `--tag=backend,urgent` - Add tags

### Add to Backlog

`/clickup-ticket:add-to-backlog "Title"`

Ultra-fast backlog addition. Always uses your configured backlog list.

### Create Subtask

`/clickup-ticket:create-subtask <parent_id> "Title"`

The parent can be:

- Task ID: `abc123`
- Task URL: `https://app.clickup.com/t/abc123`
- Custom ID (if enabled): `DEV-123`

## Discovery Commands

### List Spaces

`/clickup-ticket:list-spaces`

Shows your workspace structure, cached members, and available tags.

**Flags:**

- `--org=personal` - Show different org
- `--members` - Also list team members
- `--tags` - Also list all tags

## Multi-Org Commands

### Switch Organization

`/clickup-ticket:switch-org`

Or switch directly: `/clickup-ticket:switch-org personal`

### Add Organization

`/clickup-ticket:add-org`

Interactive wizard to add a new org from your accessible workspaces.
