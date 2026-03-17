# Config Layout Reference

The visual-explainer publish flow uses a local config directory shared across
Claude Code and Codex:

```text
~/.config/visual-explainer/
```

Create it lazily on first publish. No manual setup is required beyond setting
the environment variables.

## Directory Layout

```text
~/.config/visual-explainer/
├── global.json
└── publish-history/
    └── 2026-03-17T15-30-12Z.json
```

## Rules

- Never store literal token values in config files.
- Store env-var names only.
- Keep the config JSON minimal and stable.
- Preserve prior publish receipts unless the user explicitly asks to clean them
  up.

## `global.json`

Recommended shape:

```json
{
  "version": "1.0",
  "publisher": "netlify",
  "publish_mode": "create_new_site",
  "netlify": {
    "token_env_var": "NETLIFY_VISUAL_EXPLAINER_TOKEN",
    "account_slug_env_var": "NETLIFY_VISUAL_EXPLAINER_ACCOUNT_SLUG",
    "site_prefix_env_var": "NETLIFY_VISUAL_EXPLAINER_SITE_PREFIX",
    "open_browser_env_var": "NETLIFY_VISUAL_EXPLAINER_OPEN_BROWSER"
  },
  "preferences": {
    "open_after_publish": false,
    "write_publish_receipt": true
  }
}
```

## Publish Receipt

Write one receipt per publish under `publish-history/`.

Example:

```json
{
  "created_at": "2026-03-17T15:30:12Z",
  "title": "Auth migration explainer",
  "local_html_path": "/Users/ashish/.agent/diagrams/auth-migration.html",
  "site_name": "visual-explainer-20260317-153012-ab12cd",
  "site_id": "12345678-abcd-1234-abcd-1234567890ab",
  "deploy_id": "abcdef12-3456-7890-abcd-ef1234567890",
  "deploy_url": "https://visual-explainer-20260317-153012-ab12cd.netlify.app",
  "admin_url": "https://app.netlify.com/sites/visual-explainer-20260317-153012-ab12cd",
  "state": "ready",
  "receipt_path": "/Users/ashish/.config/visual-explainer/publish-history/2026-03-17T15-30-12Z.json"
}
```

If publish fails after site creation begins, write the same receipt shape with:

- `state: "error"`
- `error_message`
- any IDs or URLs already known
