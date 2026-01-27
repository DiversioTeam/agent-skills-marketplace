---
description: "Quick view of ClickUp tickets assigned to you."
---

Use your `clickup-ticket` Skill in **my-tickets** mode.

A convenience command that shows tickets assigned to the current user.
Equivalent to `list-tickets --assignee=me` with sensible defaults.

**Default behavior:**
- Shows open tickets only
- Sorted by due date (soonest first)
- Includes all spaces/lists
- Limited to 25 results

**Flags:**
- `--status=<status>` - Filter by status (default: all open statuses)
- `--space=<name|id>` - Filter by space
- `--list=<name|id>` - Filter by list
- `--include-closed` - Include completed tickets
- `--overdue` - Show only overdue tickets
- `--due-today` - Show tickets due today
- `--due-this-week` - Show tickets due this week
- `--limit=<n>` - Limit results (default: 25)
- `--org=<slug>` - Use different organization

**Examples:**

```bash
# My open tickets (default)
/clickup-ticket:my-tickets

# My overdue tickets
/clickup-ticket:my-tickets --overdue

# My tickets due this week in Engineering
/clickup-ticket:my-tickets --due-this-week --space=Engineering

# All my tickets including closed
/clickup-ticket:my-tickets --include-closed
```

**Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
My Tickets (8 open) - Diversio
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 OVERDUE (2)
   #abc123  Fix N+1 query           Due: Jan 25 (2 days ago)
   #def456  Update auth flow        Due: Jan 26 (yesterday)

📅 DUE THIS WEEK (3)
   #ghi789  Add rate limiting       Due: Jan 28 (tomorrow)
   #jkl012  Review PR #456          Due: Jan 30 (Thu)
   #mno345  Deploy staging          Due: Jan 31 (Fri)

📋 NO DUE DATE (3)
   #pqr678  Tech debt: cleanup      Backlog
   #stu901  Investigate memory      Backlog
   #vwx234  Add logging             Tech Debt

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

See the SKILL.md for full details.
