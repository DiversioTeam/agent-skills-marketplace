# Cache Format Reference

The skill caches workspace data locally for fast access.

## Cache Location

The skill detects the cache directory based on platform:

1. `$CODEX_HOME/skills/clickup-ticket/cache/` (if `$CODEX_HOME` is set)
2. `~/.codex/skills/clickup-ticket/cache/` (Codex default)
3. `~/.config/claude/skills/clickup-ticket/cache/` (Claude Code v1.0.30+)
4. `~/.claude/skills/clickup-ticket/cache/` (Claude Code legacy)
5. Fallback: `<skill_dir>/cache/`

**Directory Creation:** If the detected path doesn't exist, the skill creates it
automatically. No manual setup is required.

## Directory Layout

```
cache/
├── global.json                 # Active org, global preferences
└── orgs/
    ├── diversio-12345/         # {slug} = {name}-{workspace_id}
    │   ├── config.json         # Org-specific defaults
    │   ├── workspace.json      # Spaces, folders, lists
    │   ├── members.json        # Team members
    │   ├── tags.json           # Tags by space
    │   └── .last-sync          # Timestamp (ISO 8601)
    └── personal-67890/
        └── ...
```

## File Formats

### global.json

```json
{
  "version": "1.0",
  "active_org": "diversio-12345",
  "orgs": [
    {
      "id": "12345",
      "slug": "diversio-12345",
      "name": "Diversio",
      "token_env_var": "CLICKUP_TICKET_SKILL_TOKEN"
    }
  ],
  "preferences": {
    "cache_ttl_hours": 24,
    "show_url_after_create": true
  }
}
```

### config.json (per org)

```json
{
  "defaults": {
    "space_id": "67890",
    "space_name": "Engineering",
    "list_id": "901234567",
    "list_name": "Backlog",
    "assignee_id": "user123",
    "assignee_email": "you@yourcompany.com",
    "priority": 3
  },
  "backlog_list_id": "901234567",
  "branch_pattern": "clickup_{{id}}_"
}
```

### workspace.json

Contains the full hierarchy: spaces → folders → lists, with IDs and names.

### members.json

```json
{
  "fetched_at": "2025-01-13T10:00:00Z",
  "members": [
    {"id": "12345", "username": "jdoe", "email": "you@yourcompany.com"}
  ]
}
```

### tags.json

```json
{
  "fetched_at": "2025-01-13T10:00:00Z",
  "by_space": {
    "67890": [
      {"name": "bug", "tag_fg": "#fff", "tag_bg": "#ff0000"}
    ]
  }
}
```

## Cache TTL

Default: 24 hours. Configurable in `global.json` via `cache_ttl_hours`.

The skill auto-refreshes stale cache on command invocation, or you can force
refresh with `/clickup-ticket:refresh-cache`.
