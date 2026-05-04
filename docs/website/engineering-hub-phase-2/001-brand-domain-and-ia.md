# 001 - Brand, domain, and IA decision note

## Locked working direction

- Umbrella site name: `Diversio Engineering`
- Primary public hostname: `engineering.diversio.com`
- Tools section name: `Agentic Tools`
- Legacy label handling: keep `Agent Skills Marketplace` only as historical/explanatory copy where useful; do not keep it as the top-level site brand

## v1 top-level navigation

- Home: `/`
- Agentic Tools: `/agentic-tools`
- Docs: `/docs`
- Blog: `/blog`
- Community: `/community`

## Homepage ownership

The homepage should answer:

1. what Diversio Engineering publishes
2. where Agentic Tools lives
3. where blog posts and curated reposts live
4. how engineers can find the repo/community surface

It should not try to be the full tool registry page.

## Tools surface ownership

The existing PR #77 marketplace site becomes the `Agentic Tools` section:

- landing page: `/agentic-tools`
- inventory: `/registry`
- bundle docs: `/docs/*`
- skill docs: `/skills/*`
- Pi package docs: `/pi/*`

## Config source of truth

Public site strings should come from one shared config layer:

- site name
- tools section name
- primary hostname / canonical URL
- GitHub URL
- primary nav routes

Implementation path: `website/site.config.mjs`
