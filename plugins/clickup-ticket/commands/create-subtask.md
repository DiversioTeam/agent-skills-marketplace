---
description: Create a subtask under an existing ClickUp ticket.
---

Use your `clickup-ticket` Skill in **create-subtask** mode.

**Usage:**
```
/clickup-ticket:create-subtask <parent> "Subtask title"
/clickup-ticket:create-subtask abc123 "Write unit tests"
/clickup-ticket:create-subtask https://app.clickup.com/t/abc123 "Add docs"
```

Parent can be: task ID, task URL, or custom ID (e.g., DEV-123).

**Flags:**
- `--assign=<email>` - Override assignee
- `--quick` - Skip prompts, use inherited values

See the SKILL.md for full details.
