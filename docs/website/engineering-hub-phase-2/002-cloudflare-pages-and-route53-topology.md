# 002 - Cloudflare Pages and Route53 topology

## Locked working topology

- DNS authority remains in AWS Route53 for `diversio.com`
- Production site hosting uses Cloudflare Pages
- Production hostname is `engineering.diversio.com`
- Production deploys happen automatically from merges to `main`
- Preview deploys stay enabled for branches and PRs

## Cloudflare Pages settings

- Repo: `DiversioTeam/agent-skills-marketplace`
- Root directory: `website/`
- Build command: `npm run build`
- Output directory: `dist`
- Production branch: `main`
- Node version: `24`

## DNS shape

Default to the simplest Route53-managed path:

- create the Cloudflare Pages project
- attach `engineering.diversio.com` as a custom domain
- add the required Route53 validation record(s) if prompted
- point `engineering.diversio.com` at the Cloudflare Pages target using the record pattern Cloudflare provides

Do not delegate the root zone or move `diversio.com` off Route53.

## Legacy hostname behavior

- `agents.diversio.com/` should redirect to `https://engineering.diversio.com/agentic-tools`
- deep docs should preserve paths on host migration where possible:
  - `/docs/*` -> `/docs/*`
  - `/skills/*` -> `/skills/*`
  - `/pi/*` -> `/pi/*`
  - `/registry` -> `/registry`
- same-project path aliases now live in `website/public/_redirects`; hostname migration still needs Cloudflare domain-level configuration during rollout

## Rollback

If the cutover needs to be reversed:

1. remove or disable the custom-domain mapping in Cloudflare Pages
2. restore the previous Route53 record target for `engineering.diversio.com`
3. leave the apex zone and Route53 authority unchanged
