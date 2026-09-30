# Diversio Internal Share Publishing

Publish only when the user asks for it. Always create and keep the local HTML
first.

## Service Limits

- URL: `https://internal-share.diversio.com/`
- Diversio accounts only; public sharing is unavailable.
- Maximum file size: 25 MB.
- Files use one flat namespace and cannot overwrite an existing filename.
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

The helper first tries the existing Cloudflare Access session. If authentication
is missing or expired, it opens the browser and waits while the user enters
their Diversio email and emailed one-time PIN. It captures the login command's
output so the Access token is not printed, then retries the upload once.

Never ask the user to provide the PIN in chat.

## Result

On success, return:

- local HTML path
- uploaded filename
- Internal Share URL
- a reminder that viewers must sign in with a Diversio account

On failure, use the helper's message to say what failed and how to fix it. The
local HTML remains available.
