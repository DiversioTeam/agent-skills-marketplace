# 006 - Launch, validate, and ops

## Goal

Publish the Diversio Engineering site to Cloudflare Pages, keep `diversio.com`
under Route53, and make production deploy automatically from merges to `main`.

## Repo-side setup completed here

- Shared site config points at `https://engineering.diversio.com`
- Static redirects live in `website/public/_redirects`
- Static headers live in `website/public/_headers`
- GitHub Actions deploy workflow lives in `.github/workflows/deploy-website-cloudflare-pages.yml`
- Preview deploys run for same-repo PRs
- Production deploys run for pushes to `main`

## One-time Cloudflare setup

```text
GitHub Actions builds website/dist
  -> Wrangler uploads website/dist
  -> Cloudflare Pages serves the static site
  -> Route53 points engineering.diversio.com at that Pages project
```

1. Create a Cloudflare Pages project.
   - recommended project name: `diversio-engineering`
   - if you use a different name, set repo variable `CLOUDFLARE_PAGES_PROJECT`
2. Create a Cloudflare API token with Pages deploy permissions for the target account.
3. Add GitHub repo secrets:
   - `CLOUDFLARE_API_TOKEN`
   - `CLOUDFLARE_ACCOUNT_ID`
4. Add the custom domain in Cloudflare Pages:
   - `engineering.diversio.com`
5. Add the required Route53 DNS record(s) and validation record(s) if Cloudflare prompts for them.

## GitHub setup

Optional repo variable:

- `CLOUDFLARE_PAGES_PROJECT`

Required repo secrets:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

Useful verification commands:

```bash
gh secret list -R DiversioTeam/agent-skills-marketplace | rg 'CLOUDFLARE_(API_TOKEN|ACCOUNT_ID)'
gh variable list -R DiversioTeam/agent-skills-marketplace | rg '^CLOUDFLARE_PAGES_PROJECT\s'
```

## Validation checklist

Local build:

```bash
cd website
npm install --package-lock=false
npm run build
```

CI/deploy checks:

- open a PR from this repo and confirm the `Deploy Website to Cloudflare Pages` preview job runs
- merge to `main` and confirm the production deploy job runs
- use `workflow_dispatch` when you need a manual redeploy without a new commit:
  - preview can run from any selected ref
  - production should only be dispatched from `main`
- verify `engineering.diversio.com` serves the production build
- verify `_redirects` aliases work
- configure hostname-level redirect for `agents.diversio.com` -> `engineering.diversio.com`
- validate HTTPS and social previews

Helpful smoke checks:

```bash
curl -I https://engineering.diversio.com
curl -I https://engineering.diversio.com/agentic-tools
```

Manual deploy examples with Wrangler:

```bash
# Preview-style branch deploy
npx wrangler pages deploy website/dist \
  --project-name=diversio-engineering \
  --branch=<branch-name>

# Production-style deploy (use code from main)
npx wrangler pages deploy website/dist \
  --project-name=diversio-engineering \
  --branch=main
```

## Notes

- PR previews are intentionally limited to PRs whose head repo is this repo, so forked PRs do not fail because Cloudflare secrets are unavailable.
- The deploy workflow builds locally in GitHub Actions and uploads the built static output to Cloudflare Pages via Wrangler.
- This keeps production deploys deterministic and repo-owned.
