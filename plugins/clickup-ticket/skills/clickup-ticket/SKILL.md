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

This skill is designed to feel **personalized** - it learns your workspace
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

**Note:** If you have multiple ClickUp accounts (e.g., for different clients),
you can set up additional tokens. See [Multi-Org Setup](#multi-org-setup).

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

```
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

**Input formats accepted:**
- Task ID: `abc123` or `#abc123`
- Task URL: `https://app.clickup.com/t/abc123`
- Custom ID: `DEV-123` (requires `--org` flag for workspace context)

**Example:**
```
/clickup-ticket:get-ticket abc123

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#abc123 - Fix N+1 query in dashboard API
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Status:     🔵 In Progress
Priority:   🔴 High
List:       Engineering > Bugs
Assignees:  @you, @teammate
Tags:       bug, backend, performance

Due:        Fri, Jan 31 (in 4 days)
Created:    Mon, Jan 20 by @creator

📝 Description:
   The dashboard API has N+1 queries when loading widgets.
   Need to optimize with select_related and prefetch_related.

📋 Checklist (2/5):
   ✓ Identify problematic queries
   ✓ Add select_related
   ○ Add prefetch_related
   ○ Write tests
   ○ Verify with django-debug-toolbar

🔗 https://app.clickup.com/t/abc123
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Flags:**
- `--subtasks` - Include full subtask details
- `--comments` - Include recent comments (last 10)
- `--markdown` - Return description with markdown formatting
- `--org=<slug>` - Specify organization (required for custom IDs)

### List and Filter Tickets

`/clickup-ticket:list-tickets [filters]`

Powerful workspace-wide filtering using the Get Filtered Team Tasks API.

**Available Filters:**

| Filter | Description | Example |
|--------|-------------|---------|
| `--list=<name\|id>` | Filter by list | `--list=Backlog` |
| `--space=<name\|id>` | Filter by space | `--space=Engineering` |
| `--project=<name\|id>` | Filter by project/folder | `--project=Projects` |
| `--status=<status>` | Filter by status | `--status="in progress"` |
| `--assignee=<email\|me>` | Filter by assignee | `--assignee=me` |
| `--tag=<tags>` | Filter by tags | `--tag=bug,urgent` |
| `--priority=<1-4>` | Filter by priority | `--priority=1` (urgent) |
| `--due-before=<date>` | Due before date | `--due-before=2024-02-01` |
| `--due-after=<date>` | Due after date | `--due-after=tomorrow` |
| `--created-after=<date>` | Created after | `--created-after="last week"` |
| `--include-closed` | Include closed tasks | (flag) |
| `--subtasks` | Include subtasks | (flag) |
| `--limit=<n>` | Limit results | `--limit=50` |
| `--page=<n>` | Pagination | `--page=2` |
| `--sort=<field>` | Sort by field | `--sort=due_date` |
| `--reverse` | Reverse sort | (flag) |

**Date formats supported:**
- ISO: `2024-01-31`
- Relative: `today`, `tomorrow`, `yesterday`
- Natural: `next week`, `last monday`, `in 3 days`

**Example:**
```
/clickup-ticket:list-tickets --space=Engineering --tag=bug --priority=2

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tickets (5 found) - Engineering bugs, High priority
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ID       Status        Title                          Due        Assignee
──────── ──────────── ────────────────────────────── ────────── ─────────
#abc123  🔵 Progress   Fix N+1 query in dashboard     Jan 31     @you
#def456  🟡 Review     Race condition in auth         Feb 2      @teammate
#ghi789  ⚪ To Do      Memory leak in worker          Feb 5      —
#jkl012  ⚪ To Do      Timeout handling in API        —          @you
#mno345  🔵 Progress   Broken pagination              Feb 1      @other

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### My Tickets

`/clickup-ticket:my-tickets`

Quick view of tickets assigned to you, grouped by urgency.

**Default behavior:**
- Shows open tickets only
- Grouped: Overdue → Due This Week → No Due Date
- Sorted by due date within groups

**Example:**
```
/clickup-ticket:my-tickets

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
My Tickets (8 open) - Diversio
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 OVERDUE (2)
   #abc123  Fix N+1 query           Bugs        Due: Jan 25 (2 days ago)
   #def456  Update auth flow        Sprint 47   Due: Jan 26 (yesterday)

📅 DUE THIS WEEK (3)
   #ghi789  Add rate limiting       Backlog     Due: Jan 28 (tomorrow)
   #jkl012  Review PR #456          Sprint 47   Due: Jan 30 (Thu)
   #mno345  Deploy staging          Sprint 47   Due: Jan 31 (Fri)

📋 NO DUE DATE (3)
   #pqr678  Tech debt: cleanup      Backlog
   #stu901  Investigate memory      Backlog
   #vwx234  Add logging             Tech Debt

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Flags:**
- `--overdue` - Show only overdue tickets
- `--due-today` - Show tickets due today
- `--due-this-week` - Show tickets due this week
- `--space=<name>` - Filter by space
- `--include-closed` - Include completed tickets

### API Limitations

**Important:** The ClickUp API does **not** support text search by task name
or description. This is a [highly requested feature](https://feedback.clickup.com/public-api/p/using-api-get-tasks-to-search-by-title)
that has been pending since 2020.

**Workarounds:**
1. Use filters (`--tag`, `--list`, `--status`, `--assignee`) to narrow results
2. If you know the ticket ID, use `get-ticket` directly
3. Use `list-spaces` to find the right list, then filter by list

**Response limits:**
- API returns max 100 tasks per request
- Use `--page` for pagination
- Use filters to reduce result set

## Configuration Workflow

### First-Time Setup

When you run `/clickup-ticket:configure` for the first time:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ClickUp Ticket Skill - First Time Setup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Checking for CLICKUP_TICKET_SKILL_TOKEN...
✓ Token found

Fetching your workspaces...
✓ Found 2 workspaces

Select your primary workspace:

   [1] Diversio (id: 12345)
   [2] Personal (id: 67890)

> 1

Fetching workspace data for "Diversio"...
✓ 3 spaces, 12 lists, 24 members, 18 tags

Select default space for new tickets:

   [1] Engineering
   [2] Product
   [3] Design

> 1

Select default list:

   [1] Backlog
   [2] Sprint 47
   [3] Tech Debt
   [4] Bugs

> 1

Default assignee:

   [1] Me (you@yourcompany.com)
   [2] Unassigned
   [3] Ask each time

> 1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Configuration complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Organization: Diversio
Default list: Backlog
Assignee:     you@yourcompany.com

Try: /clickup-ticket:quick-ticket "My first ticket"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Multi-Org Setup

To add additional organizations:

```bash
/clickup-ticket:add-org
```

Or if you need a separate token for a client workspace:

```bash
# Add to shell profile
export CLICKUP_ACME_CLIENT_TOKEN="pk_99999_YYYYYYYYYY"

# Then run
/clickup-ticket:add-org --token-env=CLICKUP_ACME_CLIENT_TOKEN
```

## Ticket Creation Workflows

### Full Interactive Creation

`/clickup-ticket:create-ticket`

Walks you through all options:

1. **Title** (required)
2. **List** - Shows your lists, defaults to configured default
3. **Priority** - Urgent / High / Normal / Low
4. **Assignee** - Shows team members from cache
5. **Tags** - Shows available tags, multi-select
6. **Description** - Optional markdown description
7. **Due date** - Optional, with quick picks (today, tomorrow, next week)

**Output:**
```
✅ Ticket Created!

   Title:    Fix N+1 query in dashboard API
   ID:       #abc123
   List:     Bugs
   Priority: High
   Assignee: you@yourcompany.com
   Tags:     bug, backend, performance
   Due:      Fri, Jan 17

   🔗 https://app.clickup.com/t/abc123
```

### Quick Ticket

`/clickup-ticket:quick-ticket "Title here"`

Creates a ticket instantly with defaults:

```
/clickup-ticket:quick-ticket "Add rate limiting to auth endpoints"

✅ [Diversio] Add rate limiting to auth endpoints
   List: Backlog | Priority: Normal | Assignee: me
   🔗 https://app.clickup.com/t/xyz789
```

**Flags:**
- `--priority=high` or `-p high` - Override priority
- `--list=bugs` - Override list (by name)
- `--org=personal` - Create in different org
- `--tag=backend,urgent` - Add tags

### Add to Backlog

`/clickup-ticket:add-to-backlog "Title"`

Ultra-fast backlog addition. Always uses your configured backlog list:

```
/clickup-ticket:add-to-backlog "Investigate memory leak in worker"

✅ Added to Backlog: "Investigate memory leak in worker"
   🔗 https://app.clickup.com/t/mem123
```

### Create Subtask

`/clickup-ticket:create-subtask <parent_id> "Title"`

```
/clickup-ticket:create-subtask abc123 "Write unit tests"

✅ Subtask created under #abc123
   #sub456 - Write unit tests
   🔗 https://app.clickup.com/t/sub456
```

The parent can be:
- Task ID: `abc123`
- Task URL: `https://app.clickup.com/t/abc123`
- Custom ID (if enabled): `DEV-123`

## Discovery Commands

### List Spaces

`/clickup-ticket:list-spaces`

Shows your workspace structure:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Workspace: Diversio (active)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📂 Engineering
   │
   ├── 📋 Backlog (list_id: 901234567) ⭐ default
   │      Statuses: to do → in progress → review → done
   │      Tags: bug, feature, tech-debt, urgent, backend, frontend
   │
   ├── 📋 Sprint 47 (list_id: 901234568)
   ├── 📋 Tech Debt (list_id: 901234569)
   │
   └── 📁 Projects/
       ├── 📋 Auth Refactor (list_id: 901234570)
       └── 📋 API v3 (list_id: 901234571)

📂 Product
   ├── 📋 Feature Requests (list_id: 901234600)
   └── 📋 User Research (list_id: 901234601)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Team Members: 24 cached | Tags: 18 cached
Last sync: 2 hours ago
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Flags:**
- `--org=personal` - Show different org
- `--members` - Also list team members
- `--tags` - Also list all tags

## Multi-Org Commands

### Switch Organization

`/clickup-ticket:switch-org`

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Switch Organization
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current: Diversio

   [1] Diversio ✓
   [2] Personal
   [3] Client: Acme Corp

> 2

Switched to: Personal
Default list: Personal Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Or switch directly: `/clickup-ticket:switch-org personal`

### Add Organization

`/clickup-ticket:add-org`

Interactive wizard to add a new org from your accessible workspaces.

## Technical Reference

For detailed technical documentation, see the `references/` directory:

- **[api-endpoints.md](references/api-endpoints.md)** - ClickUp API v2 endpoints used
- **[cache-format.md](references/cache-format.md)** - Cache directory structure and file formats
- **[error-handling.md](references/error-handling.md)** - Error messages and handling

### Quick Reference

**Cache location:** `~/.config/clickup-ticket/` (shared by Claude Code and Codex)

**Rate limits:** The skill handles 429 responses with automatic retry and backoff.

**Cache TTL:** 24 hours (configurable). Use `/clickup-ticket:refresh-cache` to force refresh.

## Interactive Prompts

When the skill needs information, it asks with numbered choices:

```
Priority?  [1] Urgent [2] High [3] Normal [4] Low
Assignee?  [1] Me [2] Unassigned [3] Other...
Tags?      [1] bug [2] feature... (comma-separated: 1,3)
List?      [1] Backlog ⭐ [2] Sprint 47 [3] Other...
```

Press Enter to accept defaults (marked with ⭐).

## Examples

**Quick bug report:**
```
User: Create a ticket for the login bug
→ ✅ Login bug | List: Bugs | 🔗 https://app.clickup.com/t/bug123
```

**Subtask from context:**
```
User: Add a subtask to abc123 for writing tests
→ ✅ Write tests (under #abc123) | 🔗 https://app.clickup.com/t/sub789
```

**Different org:**
```
/clickup-ticket:quick-ticket "Buy groceries" --org=personal
→ ✅ [Personal] Buy groceries | 🔗 https://app.clickup.com/t/xyz
```

## Advanced Features

- **Custom fields:** `--field="Story Points=3"`
- **Templates:** `--template=bug` (pre-fills tags, priority)
- **Branch detection:** Auto-detects `clickup_<id>_` branches
- **Batch creation:** Accepts markdown lists of tasks

## Integration

Works with other skills in this marketplace:
- **monty-code-review:** Create tickets from BLOCKING issues
- **backend-pr-workflow:** Links to ClickUp branch naming conventions

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Cache stale | `/clickup-ticket:refresh-cache` |
| Reset everything | `/clickup-ticket:configure --reset` |
| Token not working | `echo $CLICKUP_TICKET_SKILL_TOKEN` to verify |
| Find list IDs | `/clickup-ticket:list-spaces` or check ClickUp URL |

## Installation

**Claude Code:**
```bash
/plugin install clickup-ticket@diversiotech
```

**Codex:**
```bash
$CODEX_HOME/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo DiversioTeam/agent-skills-marketplace \
  --path plugins/clickup-ticket/skills/clickup-ticket
```

## Security Considerations

- **Tokens are never stored in files** - Always use environment variables
- **Cache contains workspace metadata only** - No sensitive task content
- **Tokens are scoped to your account** - They inherit your ClickUp permissions
- **Local cache files** - Store only in user's home directory, not in repos

## Changelog

### v0.2.0

- **New:** `get-ticket` - Fetch full ticket details by ID or URL
- **New:** `list-tickets` - Powerful filtering (status, assignee, tags, dates)
- **New:** `my-tickets` - View assigned tickets grouped by urgency
- **Updated:** API reference with correct query parameters
- **Note:** Text search by task name not available (ClickUp API limitation)

### v0.1.0

- Initial release
- Multi-org support with cached workspace data
- Interactive ticket creation with priority, assignees, tags
- Quick ticket and backlog commands
- Subtask creation
- Space/list discovery