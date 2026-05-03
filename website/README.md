# Agent Skills Marketplace — Website

Astro static site for [agents.diversio.com](https://agents.diversio.com).

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

The website has **two jobs**:

1. **Catalog job** — show the marketplace at a glance
   - plugins
   - Pi packages
   - counts
   - summaries

2. **Deep docs job** — explain the thing itself
   - individual skills
   - Pi extension surfaces
   - runtime-specific install/invoke examples
   - commands, tools, env vars, references, scripts

The first version of the site did the catalog job well enough.
It did a much worse job on deep docs.

So the site now has two extra route families:

- `/skills/*` — individual skill pages
- `/pi/*` — Pi package / extension pages

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

Why do it this way?

Because the repo already has a source of truth.
We do **not** want a second website-only documentation schema that drifts.

## Source of Truth by Page Type

| Website surface | Source of truth | Why |
|---|---|---|
| Homepage counts, registry cards, package summaries | `src/data/marketplace.json` | stable catalog metadata |
| Individual marketplace skill pages | `plugins/*/skills/*/SKILL.md` | the skill itself is the canonical behavior |
| Pi-local skill pages | `pi-packages/*/skills/*/SKILL.md` | same reason: skill behavior lives in markdown |
| Pi extension pages | `pi-packages/*/README.md` | commands/tools/env vars already live there |
| Contributor grid | git history via `src/data/contributors.ts` | community data should age with the repo |

## Project Structure

```text
website/
├── astro.config.mjs
├── package.json
├── tsconfig.json
├── README.md
├── public/
│   ├── _headers
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
    ├── data/
    │   ├── marketplace.json
    │   ├── site-docs.ts
    │   └── contributors.ts
    └── pages/
        ├── index.astro
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
        └── pi/
            ├── index.astro
            └── [package].astro
```

## Why the New Files Exist

### `src/data/site-docs.ts`

This is the **bridge** between repo docs and website pages.

It exists because:

- plugin pages answer “what bundle is this?”
- skill pages need to answer “what does this one skill do?”
- Pi package pages need to answer “what is the extension surface?”

It intentionally does **simple extraction**, not clever parsing.

That is a feature, not a bug.

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

## How Deep Docs Get Built

### Skill pages

Marketplace skill pages come from:

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

### 1. You changed a marketplace skill

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

### Check the marketplace repo sources that feed the site

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

### Bundle-level pages

- `/docs/<plugin-or-package>`
- `/registry`

Use these when you want the overview.

### Deep docs pages

- `/skills/<skill>`
- `/pi/<package>`

Use these when you want the actual behavior, commands, tools, references,
installation flow, or extension surface.

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

Recommended settings:

| Setting | Value |
|---|---|
| Framework preset | Astro |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Root directory | `website/` |
| Node.js version | 22.12+ |

The canonical site URL is:

- `https://agents.diversio.com`

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
