# 003 - Route and redirect working map

## Keep

- `/docs/*`
- `/skills/*`
- `/pi/*`
- `/registry`
- `/community`
- `/security`
- `/terms`

## New

- `/` -> Diversio Engineering homepage
- `/agentic-tools` -> tools landing page using the former homepage/tool overview content
- `/blog` -> blog index
- `/blog/<slug>` -> original or curated repost article pages

## Move / ownership changes

- the old tool-centric homepage content moves from `/` to `/agentic-tools`
- `/` becomes the broader engineering hub homepage

## Redirect strategy

Use both of these rules:

- app-level route preservation for pages that still exist at the same paths
- Cloudflare redirect rules for hostname-level migration and any moved routes

Implemented now:

- `website/public/_redirects` provides path aliases such as `/marketplace` -> `/agentic-tools`
- deep docs stay on their existing short routes, so no same-host redirects are needed for `/docs/*`, `/skills/*`, or `/pi/*`

Still required at deploy time:

- hostname-level redirect for `agents.diversio.com/*` -> `engineering.diversio.com/*`
- homepage special case so `https://agents.diversio.com/` lands on `https://engineering.diversio.com/agentic-tools`
