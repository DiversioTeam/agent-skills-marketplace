# ClickUp Ticket Usage Workflows

This reference holds the longer walkthroughs and examples that used to live in
`SKILL.md`.

## Example Outputs

### Get Ticket

```text
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

### List Tickets

```text
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
```

### My Tickets

```text
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
```

## Configuration Workflow

### First-Time Setup

```text
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
```

## Ticket Creation Workflow Examples

### Full Interactive Creation Output

```text
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

```text
/clickup-ticket:quick-ticket "Add rate limiting to auth endpoints"

✅ [Diversio] Add rate limiting to auth endpoints
   List: Backlog | Priority: Normal | Assignee: me
   🔗 https://app.clickup.com/t/xyz789
```

### Add To Backlog

```text
/clickup-ticket:add-to-backlog "Investigate memory leak in worker"

✅ Added to Backlog: "Investigate memory leak in worker"
   🔗 https://app.clickup.com/t/mem123
```

### Create Subtask

```text
/clickup-ticket:create-subtask abc123 "Write unit tests"

✅ Subtask created under #abc123
   #sub456 - Write unit tests
   🔗 https://app.clickup.com/t/sub456
```

## Discovery And Multi-Org Examples

### List Spaces

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Workspace: Diversio (active)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📂 Engineering
   ├── 📋 Backlog (list_id: 901234567) ⭐ default
   ├── 📋 Sprint 47 (list_id: 901234568)
   └── 📁 Projects/
       ├── 📋 Auth Refactor (list_id: 901234570)
       └── 📋 API v3 (list_id: 901234571)
```

### Switch Organization

```text
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

## Interactive Prompts

```text
Priority?  [1] Urgent [2] High [3] Normal [4] Low
Assignee?  [1] Me [2] Unassigned [3] Other...
Tags?      [1] bug [2] feature... (comma-separated: 1,3)
List?      [1] Backlog ⭐ [2] Sprint 47 [3] Other...
```

Press Enter to accept defaults (marked with ⭐).

## Short Examples

### Quick bug report

```text
User: Create a ticket for the login bug
→ ✅ Login bug | List: Bugs | 🔗 https://app.clickup.com/t/bug123
```

### Subtask from context

```text
User: Add a subtask to abc123 for writing tests
→ ✅ Write tests (under #abc123) | 🔗 https://app.clickup.com/t/sub789
```

### Different org

```text
/clickup-ticket:quick-ticket "Buy groceries" --org=personal
→ ✅ [Personal] Buy groceries | 🔗 https://app.clickup.com/t/xyz
```

## Advanced Features

- Custom fields: `--field="Story Points=3"`
- Templates: `--template=bug` (pre-fills tags, priority)
- Branch detection: Auto-detects `clickup_<id>_` branches
- Batch creation: Accepts markdown lists of tasks

## Integration

Works with other skills in this marketplace:

- `monty-code-review`: Create tickets from `BLOCKING` issues
- `backend-pr-workflow`: Links to ClickUp branch naming conventions

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Cache stale | `/clickup-ticket:refresh-cache` |
| Reset everything | `/clickup-ticket:configure --reset` |
| Token not working | `echo $CLICKUP_TICKET_SKILL_TOKEN` to verify |
| Find list IDs | `/clickup-ticket:list-spaces` or check ClickUp URL |

## Installation

### Claude Code

```bash
/plugin install clickup-ticket@diversiotech
```

### Codex

```bash
$CODEX_HOME/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo DiversioTeam/agent-skills-marketplace \
  --path plugins/clickup-ticket/skills/clickup-ticket
```

## Security Considerations

- Tokens are never stored in files; always use environment variables
- Cache contains workspace metadata only, not sensitive task content
- Tokens inherit your ClickUp permissions
- Cache files should live in the user's home directory, not in repos

## Changelog

### v0.2.0

- New: `get-ticket`
- New: `list-tickets`
- New: `my-tickets`
- Updated: API reference with correct query parameters
- Note: text search by task name is still unavailable in ClickUp's API

### v0.1.0

- Initial release
- Multi-org support with cached workspace data
- Interactive ticket creation
- Quick ticket and backlog commands
- Subtask creation
- Space/list discovery
