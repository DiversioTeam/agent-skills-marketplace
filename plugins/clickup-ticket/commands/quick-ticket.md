---
description: Create a ClickUp ticket quickly using your configured defaults.
---

Use your `clickup-ticket` Skill in **quick-ticket** mode.

Creates a ticket instantly using your defaults (list, assignee, priority).

**Usage:**
```
/clickup-ticket:quick-ticket "Your ticket title"
/clickup-ticket:quick-ticket "Fix bug" --priority=high --tag=bug
```

**Flags:**
- `--priority=<level>` - urgent, high, normal, low
- `--list=<name>` - Override default list
- `--org=<slug>` - Create in different org
- `--tag=<tags>` - Add tags (comma-separated)

See the SKILL.md for full details.
