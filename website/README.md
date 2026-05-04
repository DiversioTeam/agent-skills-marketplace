# Diversio Engineering — Website

Astro static site for the Diversio Engineering hub at [engineering.diversio.com](https://engineering.diversio.com).

This README is for maintainers of the **website code**, not just visitors of the
site.

## Quick Start

```bash
cd website
npm install
npm run dev      # local dev at http://localhost:4321
npm run build    # production build -> dist/
npm run preview  # preview the production build locally
```

Node requirement: Astro 6 in this site currently needs Node `>=22.12.0`.

## The Big Idea

The website now has **three roles**:

1. **Hub** — present Diversio Engineering as the umbrella site
   - homepage
   - section routing
   - shared brand + canonical metadata

2. **Agentic Tools** — power the open tools section
   - `/agentic-tools`
   - `/registry`
   - `/docs/*`
   - `/skills/*`
   - `/pi/*`

3. **Editorial** — support engineering writing and curated reposts
   - `/blog`
   - `/blog/*`
   - original posts
   - reposts with explicit attribution and canonical handling

The current implementation extends the PR #77 Astro baseline instead of replacing it.

## First-Principles Mental Model

```text
marketplace.json
  -> cards, counts, registry summaries

plugins/*/skills/*/SKILL.md
pi-packages/*/skills/*/SKILL.md
pi-packages/*/README.md
  -> real human-authored source docs

src/data/site-docs.ts
  -> build-time extraction layer

/skills/* and /pi/*
  -> readable website pages built from the real repo docs
```

Why this shape works

Because the repo already has a source of truth.
We do **not** want a second website-only documentation schema that drifts.

## Source of Truth by Page Type

| Website surface | Source of truth | Why |
|---|---|---|
| Shared site name, primary hostname, nav routes | `site.config.mjs` | one place for public brand/domain strings |
| Homepage counts, registry cards, package summaries | `src/data/marketplace.json` | stable catalog metadata |
| Individual plugin skill pages | `plugins/*/skills/*/SKILL.md` | the skill itself is the canonical behavior |
| Pi-local skill pages | `pi-packages/*/skills/*/SKILL.md` | same reason: skill behavior lives in markdown |
| Pi extension pages | `pi-packages/*/README.md` | commands/tools/env vars already live there |
| Blog posts and repost metadata | `src/content/blog/*` + `src/content.config.ts` | explicit editorial schema with reviewable markdown |
| Contributor grid | git history via `src/data/contributors.ts` | community data should age with the repo |

## Project Structure

```text
website/
├── astro.config.mjs
├── package.json
├── site.config.mjs
├── tsconfig.json
├── README.md
├── public/
│   ├── _headers
│   ├── _redirects
│   ├── diversio-logo.svg
│   ├── favicon.svg
│   └── og-default.png
└── src/
    ├── styles/
    │   └── global.css
    ├── layouts/
    │   ├── BaseLayout.astro
    │   ├── PageLayout.astro
    │   └── DocsLayout.astro
    ├── components/
    │   ├── Header.astro
    │   ├── Footer.astro
    │   ├── Hero.astro
    │   ├── Terminal.astro
    │   ├── CodeBlock.astro
    │   ├── RuntimeCodeTabs.astro
    │   ├── Card.astro
    │   ├── CardGrid.astro
    │   ├── DataTable.astro
    │   ├── FeatureList.astro
    │   ├── SectionHeader.astro
    │   ├── Tag.astro
    │   └── Button.astro
    ├── content/
    │   └── blog/
    ├── content.config.ts
    ├── data/
    │   ├── marketplace.json
    │   ├── site-docs.ts
    │   └── contributors.ts
    └── pages/
        ├── index.astro
        ├── agentic-tools.astro
        ├── registry.astro
        ├── community.astro
        ├── security.astro
        ├── terms.astro
        ├── 404.astro
        ├── docs/
        │   ├── index.astro
        │   ├── [...slug].astro
        │   └── monty-code-review.astro
        ├── skills/
        │   ├── index.astro
        │   └── [skill].astro
        ├── pi/
        │   ├── index.astro
        │   └── [package].astro
        └── blog/
            ├── index.astro
            └── [slug].astro
```

## Why the New Files Exist

### `src/data/site-docs.ts`

This is the **bridge** between repo docs and website pages.

It exists because:

- plugin pages answer “what bundle is this?”
- skill pages need to answer “what does this one skill do?”
- Pi package pages need to answer “what is the extension surface?”

It intentionally does **simple extraction**, not clever parsing.

That simplicity is intentional.

If something breaks, a future maintainer should be able to read the file and say:

> “Okay, we read headings, bullets, code fences, and a few README table sections.
> I understand why this page rendered the way it did.”

### `src/components/RuntimeCodeTabs.astro`

This component exists because install/invoke examples are only useful if the
copy button matches the runtime the user is looking at.

Old approach:

```text
# Claude Code
...
# Codex
...
```

Problem: the user copies both blocks together.

New approach:

```text
[Claude Code] [Codex]   (inside the dark code header)
<only one code sample visible>
```

Why the toggle lives inside the black code header:

- it visually replaces the old `bash` label
- it keeps the runtime choice attached to the code itself
- the copy button can always copy the active tab only

### `src/data/contributors.ts`

This file exists because contributor lists should come from git history when
possible.

It keeps the logic simple:

- ask git for author history
- ignore obvious bots
- merge known human aliases
- infer GitHub profiles from noreply addresses when possible
- fall back to a small static list if git metadata is unavailable

### `site.config.mjs`

This file is the **single source of truth for site identity**.

It exists because the rebrand touched several things at once:

- site name
- primary hostname
- top-level nav labels
- top-level route names

Without a shared config file, those strings drift into layouts, headers,
footers, metadata, and docs.

Mental model:

```text
page copy          -> explains the content on one page
site.config.mjs    -> explains what the site is called and where sections live
```

If a future change renames a section or moves a top-level route, start there.

### `src/content.config.ts`

This file defines the **editorial contract** for blog content.

It exists because original posts and curated reposts have different rules.

```text
original post
  -> can be owned entirely by this site

repost
  -> must keep source attribution
  -> must keep canonical URL information
```

That is why reposts are validated more strictly than original posts.

### `public/_redirects`

This file exists to preserve **human entrypoints** after the site rebrand.

It handles simple aliases such as:

```text
/marketplace               -> /agentic-tools
/tools                     -> /agentic-tools
/agent-skills-marketplace  -> /agentic-tools
```

Why keep the rules exact instead of using broad wildcards?

- the tools landing page moved
- the deep docs routes mostly did not
- exact aliases are easier to reason about and harder to misconfigure

### `.github/workflows/deploy-website-cloudflare-pages.yml`

This workflow exists so deployment stays **repo-owned and repeatable**.

Mental model:

```text
GitHub Actions
  -> install dependencies
  -> build website/dist
  -> upload the finished static output to Cloudflare Pages
```

Why not rely on an opaque remote build only?

- build logs stay in GitHub where the change happened
- the same build command runs locally and in CI
- deployment is easier to audit when the upload step is explicit

## How Deep Docs Get Built

### Skill pages

Plugin skill pages come from:

```text
plugins/<plugin>/skills/<skill>/SKILL.md
plugins/<plugin>/commands/*.md
```

The page uses:

- SKILL frontmatter for name / description / allowed tools
- markdown sections for skimmable summaries
- command wrappers to infer the related slash commands
- `references/` and `scripts/` directories for resource listings

### Pi extension pages

Pi package pages come from:

```text
pi-packages/<package>/README.md
pi-packages/<package>/skills/*/SKILL.md
pi-packages/<package>/extensions/*
```

The page uses the README for:

- commands
- LLM tools
- environment variables
- UI shortcuts
- install / local test snippets
- first-principles sections like “What it does”, “Why this package exists”, etc.

That means:

> if you want a better `/pi/<package>` page, usually the right first fix is to
> improve the package README.

## Practical Maintainer Workflows

### 1. You changed a plugin skill

Edit the real skill docs first:

```bash
# examples
plugins/frontend/skills/frontend/SKILL.md
plugins/monty-code-review/skills/monty-code-review/SKILL.md
```

Then rebuild and check the generated site pages:

```bash
cd website
npm run build
npm run dev
```

Open:

- `http://localhost:4321/skills`
- `http://localhost:4321/skills/<skill-name>`
- the parent plugin page at `http://localhost:4321/docs/<plugin-name>`

### 2. You changed a Pi package README or extension surface

Edit the real package docs first:

```bash
# examples
pi-packages/ci-status/README.md
pi-packages/dev-workflow/README.md
pi-packages/image-router/README.md
```

Then rebuild and inspect:

- `http://localhost:4321/pi`
- `http://localhost:4321/pi/<package-name>`
- the package summary page at `http://localhost:4321/docs/<package-name>`

### 3. You added a new skill or package and the website looks wrong

Think in this order:

1. **Did I update the source docs?**
   - `SKILL.md`
   - Pi package `README.md`
2. **Did I update catalog metadata?**
   - `src/data/marketplace.json`
3. **Does the extractor understand the doc shape I used?**
   - `src/data/site-docs.ts`

That order matters.

Do not start by patching the final page template if the real docs are missing.

### 4. You added or edited blog content

The blog now supports two content types:

```text
sourceType: original   -> written for this site
sourceType: repost     -> mirrored/curated content with source attribution
```

A minimal original post looks like this:

```md
---
title: Example post
summary: Short summary for cards and metadata.
publishDate: 2026-05-03
author:
  name: Diversio Engineering
sourceType: original
---

Hello world.
```

A repost must carry more metadata:

```md
---
title: Example repost
summary: Why this external piece matters here.
publishDate: 2026-05-03
author:
  name: Original Author
sourceType: repost
sourceSiteName: Example Site
sourceUrl: https://example.com/post
canonicalUrl: https://example.com/post
---
```

That extra metadata is not optional ceremony. It exists so future readers and
social crawlers can tell where the piece came from.

## Commands Worth Remembering

### Rebuild the site

```bash
cd website
npm run build
```

### Run the local dev server

```bash
cd website
npm run dev
```

### Check the repo sources that feed the site

```bash
cd ..
find plugins -path '*/skills/*/SKILL.md' | sort
find pi-packages -path '*/skills/*/SKILL.md' | sort
find pi-packages -name README.md | sort
```

### Inspect the built output quickly

```bash
cd website
rg -n '/skills/|/pi/' dist
```

## Route Guide

### Hub pages

- `/`
- `/agentic-tools`
- `/blog`
- `/community`

Use these when you want the high-level engineering hub, tools landing page, editorial index, or collaboration entrypoints.

### Bundle-level pages

- `/docs/<plugin-or-package>`
- `/registry`

Use these when you want the tools overview for a specific bundle or the full registry inventory.

### Deep docs pages

- `/skills/<skill>`
- `/pi/<package>`
- `/blog/<slug>`

Use these when you want the actual behavior, commands, tools, references, installation flow, extension surface, or article body.

## Social Sharing Metadata

Every page now renders the metadata needed for share previews on Open Graph and
X/Twitter consumers.

That includes:

- canonical URL
- page title
- page description
- absolute social image URL
- image alt text
- Open Graph tags used by Slack, Facebook, LinkedIn, and similar clients
- X/Twitter card tags

The logic lives in:

- `site.config.mjs`
- `src/layouts/BaseLayout.astro`

First principles:

- page content owns the page title and description
- the layout turns that into share metadata for every route
- the fallback social image is shared, but the page title/description stay route-specific

If a future page needs a custom share image or article-style metadata, extend
`BaseLayout.astro` props instead of hardcoding tags in a single page.

## UI Decisions That Are Easy To Miss

### No search button

The header does **not** show a fake search control anymore.

Reason:

- a visible search affordance implies working search
- a dead button is worse than no button

If real static search gets added later, it should come back as a real feature,
not as a placeholder.

### Runtime toggles live inside the black code header

Reason:

- the runtime is part of the code sample, not a separate page control
- the copy button should copy the active runtime only
- the user should not have to visually stitch together two distant controls

### Contributor cards exclude bots

Reason:

- the community page is meant to show humans behind the repo
- git history still drives the data, but the display layer intentionally filters bot identities

## Known Build Notes

At the moment there are no intentionally accepted build warnings in the website
itself. If Astro starts warning again, treat that as a fresh issue to inspect,
not as normal background noise.

## Deployment

The site is fully static and deploys cleanly to Cloudflare Pages.

Current deploy shape:

- `Validate Website` remains the read-only build gate
- `.github/workflows/deploy-website-cloudflare-pages.yml` builds the site in GitHub Actions and uploads `website/dist` to Cloudflare Pages
- PR previews run for same-repo PRs
- production deploys run automatically on pushes to `main`

Current redirect split:

- `public/_redirects` handles same-project path aliases such as `/marketplace` -> `/agentic-tools`
- hostname migration from `agents.diversio.com` to `engineering.diversio.com` still needs host-level redirect configuration during rollout

Required GitHub secrets:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

Optional GitHub repo variable:

- `CLOUDFLARE_PAGES_PROJECT` (defaults to `diversio-engineering` in the workflow)

Recommended settings:

| Setting | Value |
|---|---|
| Pages project name | `diversio-engineering` |
| Deploy path | `website/dist` |
| Production branch | `main` |
| Node.js version | 24 |

### Local deploy-minded checks

Before you trust CI, run the same core steps locally:

```bash
cd website
npm install --package-lock=false
npm run build
```

Then sanity-check the output:

```bash
rg -n '/agentic-tools|/blog|/skills|/pi' dist
```

### What preview vs production means here

```text
pull request from this repo
  -> preview deployment on Cloudflare Pages

push to main
  -> production deployment on Cloudflare Pages

manual workflow_dispatch run
  -> preview from any selected ref
  -> production only when dispatched from main
```

This split exists for a simple reason: reviewers need a safe preview URL, while
production should only change after merge. Manual dispatch still exists so the
team can re-run a preview or production deploy without manufacturing a new code
change, but the workflow guards against deploying a feature-branch build to the
production Pages branch.

The canonical site URL is:

- `https://engineering.diversio.com`

## Branding Notes

The site uses real Diversio branding assets:

- `public/diversio-logo.svg`
- `public/favicon.svg`
- `public/og-default.png`

Header, footer, hero, favicon, and OG metadata all use this branding layer.

## What To Update When You Change The Website Architecture

If you add or remove a major route family, data source, or doc surface, update:

1. this `website/README.md`
2. `src/pages/docs/index.astro`
3. any affected registry or homepage navigation

That keeps the website code understandable for the next person, not just functional today.
