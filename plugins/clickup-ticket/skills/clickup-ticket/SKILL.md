---
name: clickup-ticket
description: >
  Fetch, filter, and create ClickUp tickets directly from Claude Code or Codex.
  Read tickets by ID, filter by status/assignee/tags/dates, view your assigned
  tickets, create tickets interactively, and manage multi-org workspaces with
  intelligent caching.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
  - Grep
---

# ClickUp Ticket Skill

## When to Use This Skill

Use this skill when you want to:

- **Fetch ticket details** by ID or URL to understand requirements
- **List and filter tickets** by status, assignee, tags, due dates, and more
- **View your assigned tickets** with smart grouping by urgency
- **Create tickets** without leaving your terminal or IDE
- **Add subtasks** to existing tickets during development
- **Quick-add to backlog** when you spot TODOs or tech debt
- **Manage multiple ClickUp organizations** (work, personal, clients)
- **Discover your workspace structure** (spaces, lists, tags, members)

This skill is designed to feel **personalized**: it learns your workspace
structure, remembers your defaults, and asks simple questions when it needs
information.

## Prerequisites

### 1. ClickUp API Token

Generate a personal API token:

1. Log into ClickUp
2. Go to **Settings** → **Apps** (or visit https://app.clickup.com/settings/apps)
3. Under "API Token", click **Generate** (or **Regenerate**)
4. Copy the token (starts with `pk_`)

### 2. Environment Variable

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, or `~/.config/fish/config.fish`):

```bash
export CLICKUP_TICKET_SKILL_TOKEN="pk_12345_XXXXXXXXXX"
```

Then reload your shell:

```bash
source ~/.bashrc  # or restart your terminal
```

**Note:** If you have multiple ClickUp accounts, you can set up additional
tokens. See `references/usage-workflows.md` for the multi-org flow.

## Quick Start

```bash
# First time? Configure the skill
/clickup-ticket:configure

# Create a ticket interactively
/clickup-ticket:create-ticket

# Quick ticket with defaults
/clickup-ticket:quick-ticket "Fix login timeout bug"

# Add to backlog instantly
/clickup-ticket:add-to-backlog "Refactor auth module"
```

## Commands Overview

| Command | Purpose |
|---------|---------|
| `/clickup-ticket:get-ticket` | Fetch full details of a single ticket |
| `/clickup-ticket:list-tickets` | List/filter tickets with powerful filtering |
| `/clickup-ticket:my-tickets` | Quick view of tickets assigned to you |
| `/clickup-ticket:configure` | First-time setup, set defaults, refresh cache |
| `/clickup-ticket:create-ticket` | Full interactive ticket creation |
| `/clickup-ticket:quick-ticket` | Fast ticket creation with defaults |
| `/clickup-ticket:create-subtask` | Add subtask to an existing ticket |
| `/clickup-ticket:add-to-backlog` | Ultra-fast addition to backlog list |
| `/clickup-ticket:list-spaces` | Discover spaces, lists, folders, tags |
| `/clickup-ticket:switch-org` | Switch between organizations |
| `/clickup-ticket:add-org` | Add a new organization |
| `/clickup-ticket:refresh-cache` | Force refresh cached workspace data |

## Core Concepts

### ClickUp Hierarchy

```text
Workspace (Organization)
  └── Space (e.g., "Engineering", "Product")
       ├── Folder (optional grouping)
       │    └── List (e.g., "Auth Refactor")
       │         └── Task
       │              └── Subtask
       └── List (standalone, e.g., "Backlog")
            └── Task
                 └── Subtask
```

**Key points:**

- Every task belongs to a **List**
- Lists can be inside **Folders** or directly in a **Space**
- **Spaces** belong to a **Workspace** (organization)
- You need a `list_id` to create a task

### Multi-Org Support

This skill supports multiple ClickUp organizations:

- **Work** - Your company's workspace
- **Personal** - Your personal ClickUp
- **Clients** - Client workspaces you have access to

Each organization has its own:

- Cached workspace data (spaces, lists, tags, members)
- Default settings (list, assignee, priority)
- Optional separate API token

Switch between orgs with `/clickup-ticket:switch-org`.

### Cache Management

The skill caches your workspace data locally for fast access:

- **Workspace structure** - Spaces, folders, lists
- **Team members** - Names, emails, IDs for assignment
- **Tags** - Available tags per space
- **Statuses** - Available statuses per list

**Cache location:** `~/.config/clickup-ticket/` (shared by Claude Code and Codex)

**Cache refresh:**

- Auto-refreshes after 24 hours
- Manual refresh: `/clickup-ticket:refresh-cache`
- Refreshes automatically if an entity is not found

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
environment variable. See `references/usage-workflows.md` for the full example.

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

## Technical Reference

For detailed technical documentation, see the `references/` directory:

- **[api-endpoints.md](references/api-endpoints.md)** - ClickUp API v2 endpoints used
- **[cache-format.md](references/cache-format.md)** - Cache directory structure and file formats
- **[error-handling.md](references/error-handling.md)** - Error messages and handling
- **[usage-workflows.md](references/usage-workflows.md)** - Examples, prompts, installation, and troubleshooting

### Quick Reference

**Cache location:** `~/.config/clickup-ticket/` (shared by Claude Code and Codex)

**Rate limits:** The skill handles 429 responses with automatic retry and backoff.

**Cache TTL:** 24 hours (configurable). Use `/clickup-ticket:refresh-cache` to force refresh.

Use **[usage-workflows.md](references/usage-workflows.md)** for:

- worked examples and sample outputs
- interactive prompt shapes
- advanced features and integrations
- troubleshooting
- installation snippets
- security notes
- changelog history
