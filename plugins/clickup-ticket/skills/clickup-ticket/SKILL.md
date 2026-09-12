---
name: clickup-ticket
description: "Read or create ClickUp tickets and configure ClickUp workspace defaults."
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
tokens. See [Usage workflows](references/usage-workflows.md) for the multi-org
flow.

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

## Choose A Command

Read the requested mode in [command modes](references/command-modes.md):

- `get-ticket`, `list-tickets`, `my-tickets`: inputs, filters, pagination, and
  API limits for reads; do not enter the creation workflow.
- `configure`, organization/cache commands: setup and defaults.
- `create-ticket`: interactive creation; retain its requested prompts.
- `quick-ticket`, `add-to-backlog`, `create-subtask`: use supplied inputs and
  configured defaults; ask only for consequential missing targets.

Read requests do not authorize ticket creation or workspace changes.

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
