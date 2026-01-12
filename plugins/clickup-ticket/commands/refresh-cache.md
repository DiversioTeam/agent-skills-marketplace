---
description: Force refresh the cached ClickUp workspace data.
---

Use your `clickup-ticket` Skill in **refresh-cache** mode.

Fetches fresh data from ClickUp API:
- Spaces, folders, lists
- Team members
- Tags and statuses

**Usage:**
```
/clickup-ticket:refresh-cache           # Refresh current org
/clickup-ticket:refresh-cache --all     # Refresh all orgs
/clickup-ticket:refresh-cache --org=x   # Refresh specific org
```

Cache auto-refreshes after 24 hours. Use this to force immediate refresh.

See the SKILL.md for full details.
