---
description: "List and filter ClickUp tickets with powerful filtering options."
---

Use your `clickup-ticket` Skill in **list-tickets** mode.

Retrieves tickets from your workspace with comprehensive filtering. Uses the
powerful Get Filtered Team Tasks API endpoint for workspace-wide searches.

**Filters:**
- `--list=<name|id>` - Filter by specific list
- `--space=<name|id>` - Filter by space
- `--project=<name|id>` - Filter by project/folder
- `--status=<status>` - Filter by status (e.g., "in progress", "review")
- `--assignee=<email|me>` - Filter by assignee (`me` for current user)
- `--tag=<tags>` - Filter by tags (comma-separated)
- `--priority=<1-4>` - Filter by priority (1=urgent, 4=low)
- `--due-before=<date>` - Due before date (YYYY-MM-DD or "tomorrow", "next week")
- `--due-after=<date>` - Due after date
- `--created-after=<date>` - Created after date
- `--include-closed` - Include closed/completed tickets (default: open only)
- `--subtasks` - Include subtasks in results
- `--limit=<n>` - Limit results (default: 25, max: 100)
- `--page=<n>` - Page number for pagination
- `--sort=<field>` - Sort by: created, updated, due_date, priority
- `--reverse` - Reverse sort order
- `--org=<slug>` - Use different organization

**Examples:**

```bash
# All open tickets assigned to me
/clickup-ticket:list-tickets --assignee=me

# High priority bugs in the Engineering space
/clickup-ticket:list-tickets --space=Engineering --tag=bug --priority=2

# Tickets due this week
/clickup-ticket:list-tickets --due-before="next monday"

# Recent tickets in a specific list, sorted by creation
/clickup-ticket:list-tickets --list=Backlog --sort=created --reverse
```

**Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tickets (12 found) - Diversio
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ID       Status        Priority  Title                          Due
──────── ──────────── ───────── ────────────────────────────── ──────────
#abc123  🔵 Progress   🔴 High   Fix N+1 query in dashboard     Jan 31
#def456  🟡 Review     🟠 Med    Add rate limiting              Feb 2
#ghi789  ⚪ To Do      🟢 Low    Update API docs                —
...

Page 1/2 | Showing 12 of 23 | --page=2 for more
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Note:** ClickUp API does not support text search by task name. Use filters
like `--list`, `--tag`, `--status`, or `--assignee` to narrow results.

See the SKILL.md for API details and limitations.
