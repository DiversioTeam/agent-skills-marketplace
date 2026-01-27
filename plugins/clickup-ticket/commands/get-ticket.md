---
description: "Fetch and display a single ClickUp ticket by ID or URL."
---

Use your `clickup-ticket` Skill in **get-ticket** mode.

Retrieves complete details for a single ticket including:
- Title, status, priority, list
- Assignees, watchers, creator
- Description (markdown supported)
- Due date, start date, time estimate
- Tags, custom fields, checklists
- Subtasks, dependencies, links
- Activity summary (comments count, attachments)

**Input formats:**
- Task ID: `abc123` or `#abc123`
- Task URL: `https://app.clickup.com/t/abc123`
- Custom ID (if enabled): `DEV-123` (requires `--org` flag)

**Flags:**
- `--org=<slug>` - Specify organization (for custom IDs)
- `--subtasks` - Include full subtask details
- `--comments` - Include recent comments
- `--markdown` - Return description with markdown formatting

**Output:**
```
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
Updated:    2 hours ago

📝 Description:
   The dashboard API has N+1 queries when loading widgets...

📋 Checklist (2/5):
   ✓ Identify problematic queries
   ✓ Add select_related
   ○ Add prefetch_related
   ○ Write tests
   ○ Verify with django-debug-toolbar

🔗 https://app.clickup.com/t/abc123
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

See the SKILL.md for API details and full workflow.
