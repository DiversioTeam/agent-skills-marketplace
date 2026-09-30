# Diversio Internal Share Publishing

Publish only when the user asks for it. Always create and keep the local HTML
first.

## Service Limits

- URL: `https://internal-share.diversio.com/`
- Diversio accounts only; public sharing is unavailable.
- Maximum file size: 25 MB.
- Files share one filename list and cannot overwrite an existing file.
- The uploader can delete a file from the browser UI for 24 hours.

The helper adds a timestamp and short random suffix to avoid filename
collisions.

## Prerequisite

Publishing requires `cloudflared`:

```bash
brew install cloudflared
```

No API token or environment-variable setup is needed.

## Run The Helper

Resolve `SKILL_DIR` to the absolute directory containing this skill's
`SKILL.md`. Do not run a relative script path from the user's project.

```bash
SKILL_DIR="<absolute directory containing visual-explainer/SKILL.md>"
python3 "$SKILL_DIR/scripts/publish_internal_share.py" \
  --html-path ~/.agent/diagrams/example.html \
  --title "Example explainer"
```

Use `--open-url` only when the user asks to open the shared page.

## Authentication

Before uploading, the helper runs `cloudflared access login --quiet`. If the
user is already signed in, it continues immediately. Otherwise, Cloudflare
opens the browser for the Diversio email and one-time PIN.

The login command prints a fallback URL when the browser cannot open. The
`--quiet` flag hides the Access token. After sign-in, the helper uploads once.

Never ask the user to provide the PIN in chat.

## Result

On success, return:

- local HTML path
- uploaded filename
- Internal Share URL
- a reminder that viewers must sign in with a Diversio account

On failure, use the helper's message to say what failed and how to fix it. The
local HTML remains available.
