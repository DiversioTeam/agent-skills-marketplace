# Engineering Hub Phase 2

## Status

- [x] Branch created from `main`: `feature/engineering-hub-phase-2`
- [x] Lock working direction for brand, domain, and IA
- [x] Lock working Cloudflare Pages + Route53 topology
- [x] Preserve PR #77 site as the implementation baseline
- [x] Add shared website config for brand/domain strings
- [x] Split the broader hub homepage from the tools-specific landing page
- [x] Add initial blog scaffolding for original posts and curated reposts
- [x] Add initial redirect rules and path aliases in `website/public/_redirects`
- [ ] Configure hostname-level redirect behavior for `agents.diversio.com`
- [ ] Add first real blog/repost content entries
- [x] Add GitHub Actions deploy pipeline for Cloudflare Pages
- [ ] Configure the Cloudflare Pages project, repo secrets, and Route53 records
- [ ] Validate production deploy, TLS, redirects, and social previews

## Working Decisions

- Umbrella site: `Diversio Engineering`
- Primary production hostname: `https://engineering.diversio.com`
- Tools section name: `Agentic Tools`
- Existing marketplace repo/site content is preserved and extended, not rebuilt
- Deep docs stay on short routes for now: `/docs/*`, `/skills/*`, `/pi/*`
- New hub section routes begin with `/agentic-tools` and `/blog`

## Implementation Notes

- Shared site config now lives in `website/site.config.mjs`
- The former marketplace homepage content now lives on `website/src/pages/agentic-tools.astro`
- The broader engineering homepage now lives on `website/src/pages/index.astro`
- Blog collection schema lives in `website/src/content.config.ts`
- Blog routes live in `website/src/pages/blog/`
