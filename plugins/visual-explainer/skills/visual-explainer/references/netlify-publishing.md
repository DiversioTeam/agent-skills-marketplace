# Netlify Publishing Reference

Use this reference only when the user explicitly wants a hosted preview or the
wrapper passes `--publish`.

## Publish Contract

- Publish mode is opt-in.
- Always write the local HTML first.
- Every publish creates a brand-new Netlify preview site.
- Do not reuse existing preview sites.
- Keep secret values in environment variables only.
- The helper resolves those values from the current process environment, not by
  reading `~/.zshrc`, `~/.bashrc`, or other startup files directly.
- Preserve the local HTML even if publish fails.

## Environment Variables

### How to get them

1. Generate a Netlify personal access token in Netlify:
   - `User settings` -> `Applications` -> `Personal access tokens`
   - create a token for visual-explainer publishing
2. Find the account slug from the Netlify team or personal account URL:
   - if the URL is `https://app.netlify.com/teams/my-team`, the slug is
     `my-team`
3. Add the exports to your shell startup file, for example `~/.zshrc`
4. Restart the current tool session after adding or changing the exports

### Required

```bash
export NETLIFY_VISUAL_EXPLAINER_TOKEN="..."
export NETLIFY_VISUAL_EXPLAINER_ACCOUNT_SLUG="your-team-slug"
```

### Optional

```bash
export NETLIFY_VISUAL_EXPLAINER_SITE_PREFIX="visual-explainer"
export NETLIFY_VISUAL_EXPLAINER_OPEN_BROWSER="1"
```

## Helper Script

Use the helper script to keep publish behavior deterministic:

```bash
python3 scripts/publish_netlify_preview.py \
  --html-path ~/.agent/diagrams/example.html \
  --title "Example explainer"
```

Add `--open-url` only when the user explicitly wants the deployed page opened
after publish.

## Runtime Flow

1. Ensure the generated local HTML file exists.
2. Bootstrap `~/.config/visual-explainer/global.json` if it does not exist.
3. Confirm the required `NETLIFY_VISUAL_EXPLAINER_*` variables are visible in
   the current runtime environment.
4. If the user just changed shell startup files and the variables are missing,
   have them restart the current tool session or rerun from an interactive shell
   session that inherited the exports.
5. Resolve env-var names from config, then load the real values from
   `os.environ`.
6. Build a unique site name from the configured prefix, UTC timestamp, and a
   short random suffix.
7. Create the site in the target Netlify account:

```http
POST https://api.netlify.com/api/v1/{account_slug}/sites
Authorization: Bearer <token>
Content-Type: application/json
```

Body:

```json
{
  "name": "visual-explainer-20260317-153012-ab12cd"
}
```

8. Copy the generated HTML into a temp directory as `index.html`.
9. Add a Netlify `_headers` file that forces `/` and `/index.html` to
   `Content-Type: text/html; charset=UTF-8`.
10. Zip that directory.
11. Create the deploy:

```http
POST https://api.netlify.com/api/v1/sites/{site_id}/deploys?title=<title>
Authorization: Bearer <token>
Content-Type: application/zip
```

12. Poll deploy status until it reaches `ready` or `error`:

```http
GET https://api.netlify.com/api/v1/deploys/{deploy_id}
Authorization: Bearer <token>
```

13. Prefer the canonical site alias URL (`site.ssl_url` / `site.url`) over
    deploy-specific permalinks when choosing the final URL, and avoid hostnames
    with DNS labels longer than 63 characters.
14. Write a publish receipt under
    `~/.config/visual-explainer/publish-history/`.
15. Return the deploy URL, local HTML path, and receipt path.

## Success Criteria

A publish is successful only when all of these are true:

- the local HTML file exists
- Netlify site creation succeeds
- the deploy reaches `ready`
- a DNS-safe deploy URL is returned
- the published page is served with `Content-Type: text/html; charset=UTF-8`
- a publish receipt is written unless local preferences disabled it

## Output Expectations

When publish succeeds, tell the user:

- local HTML path
- deploy URL
- publish receipt path
- any important unverified content still present in the explainer

When publish fails, tell the user:

- the local HTML path still exists
- which publish step failed
- the actionable fix from `references/error-handling.md`
