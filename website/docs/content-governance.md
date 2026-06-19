# Website Content Governance

This guide is for staff maintaining the Diversio Engineering website.

Use `README.md` for orientation, this guide for page scope and ownership rules, `docs/editing-recipes.md` for common change tasks, and `docs/editorial-workflow.md` for page-vs-post judgment calls.

Use it when you need to answer:
- where should this content live?
- which file should I edit?
- what belongs on a top-level page versus a blog post?
- where did the stack logos come from?

If you already know what you want to change and just need the target file, jump to `docs/editing-recipes.md`.
If you are still deciding whether something belongs on a page, in shared data, or in a blog post, read `docs/editorial-workflow.md`.

## Top-level page scope

Keep each top-level page on one job:

- `/` = umbrella hub and routing surface
- `/how-we-work` = habits, standards, and decision rules
- `/systems` = stack, workflow architecture, and systems evidence
- `/community` = how to follow, engage, contribute, and contact
- `/agentic-tools` = tools, packages, and docs surface
- `/blog/*` = depth, examples, and longer-form thinking

When in doubt:
- if it is a durable engineering habit, start with `/how-we-work`
- if it is architecture, stack, or workflow structure, start with `/systems`
- if it explains a reusable tool/package, it probably belongs under `/agentic-tools` or `/docs`
- if it needs nuance or examples, write a blog post instead of expanding a top-level page

## Source repo resolution

The website depends on an `agent-skills-marketplace` checkout for tool docs and metadata.

Resolution order currently prefers:
1. `AGENT_SKILLS_REPO_DIR`
2. the current git repo root when it contains `plugins/` and `pi-packages/`
3. `../agent-skills-marketplace`
4. `../vendor/agent-skills-marketplace`
5. `./vendor/agent-skills-marketplace`

That keeps normal local builds fast and offline while still allowing future split-repo setups to point at an external checkout explicitly.

## Current sources of truth

- `site.config.mjs`
  - shared site name, routes, nav labels, and primary URLs
- `src/data/marketplace.json`
  - tool/package counts and registry metadata
- `src/data/engineering-principles.ts`
  - `/how-we-work` principles
- `src/data/engineering-practices.ts`
  - `/how-we-work` concrete practice rows and related links
- `src/data/how-we-work.ts`
  - `/how-we-work` page-specific featured example selection
- `src/data/engineering-highlights.ts`
  - `/systems` highlight rows and canonical lane order
- `src/data/engineering-stack.ts`
  - stack layers, stack logos, and supporting tools
- `src/data/site-entry-points.ts`
  - reused route/entry-point summaries for top-level pages
- `src/data/agentic-tools.ts`
  - featured plugin selections for homepage and the tools landing page
- `src/data/community.ts`
  - community-specific lead repo and contribution-summary content
- `src/utils/site-metrics.ts`
  - shared broad-site counts for homepage and community-style surfaces
- `src/content/blog/*`
  - blog posts and editorial metadata
- `plugins/*/skills/*/SKILL.md`
  - canonical plugin skill behavior
- `pi-packages/*/README.md`
  - canonical Pi package surface docs

## Blog ordering rules

Published blog surfaces use:
- `src/utils/blog-posts.ts`
- `src/utils/sort-blog-posts.ts`
- `src/utils/pick-featured-blog-post.ts`

Archive ordering:
1. `publishDate` descending
2. `updatedDate` descending
3. slug
4. title

Hero/featured selection:
1. one post with `featured: true` and `sourceType: original`
2. otherwise one post with `featured: true`
3. otherwise newest original post
4. otherwise newest post of any type

Important:
- keep **at most one** `featured: true` post at a time
- if same-day ordering matters, use full datetime precision in `publishDate`

## Systems lane ordering

`/systems` uses a canonical lane order from `src/data/engineering-highlights.ts`.

If a new lane is added:
- add it to `engineeringHighlightLaneOrder`
- `/systems` now validates that every highlight lane appears in that canonical order list
- if you forget, the build should fail with a clear error instead of silently changing page behavior

## Hero/support copy

Keep hero framing and short support blocks page-local unless they are clearly owned by one page family and likely to change independently from layout.

Use a scoped data file when:
- the copy belongs to one page family
- staff should be able to update it without touching markup
- the content is more durable than the surrounding layout

Examples:
- `src/data/how-we-work.ts` owns the `/how-we-work` notice copy and featured example selection
- `src/data/community.ts` owns specific reusable summary content for `/community`

If the same support copy is not intentionally reused across multiple pages, do not create a generic shared intro file for it.

## Shared tool curation

If homepage or tools-landing featured plugin choices should be updated, prefer `src/data/agentic-tools.ts` instead of editing hardcoded slug arrays inside page templates.

Use this for:
- homepage featured plugin selection
- `/agentic-tools` featured plugin selection

Keep plugin selection page-local only when it is truly one-off and not part of a maintained curation surface.

## Shared metrics

If a broad page needs counts that describe the site as a whole, prefer `src/utils/site-metrics.ts` instead of recomputing them in multiple pages.

Use shared metrics when:
- the same count appears on more than one broad page
- the count describes the site as a whole
- consistency matters more than page-local nuance

Keep counts page-local when:
- the number only belongs to one page
- the metric is tightly tied to local page logic
- the dynamic count would distort the page’s purpose more than help it

Rule of thumb:
- homepage and community should prefer shared metrics
- highly specific docs pages should compute only the local counts they actually need

## Shared entry-point copy

Repeated directional copy should come from `src/data/site-entry-points.ts` when it is reused across multiple pages.

Use that file for:
- route titles
- short section summaries
- CTA text

Keep copy inside the page only when it is genuinely specific to that page's local context.

## Stack editing rules

Only add something to `src/data/engineering-stack.ts` if it is:
- part of the core product stack
- part of infrastructure or deployment
- part of design/analytics workflow
- or a truly important daily engineering tool

Prefer:
- a few primary technologies per layer
- supporting tools in `supportingTools`

Avoid:
- turning the stack into an exhaustive inventory
- adding one-off tools that do not materially shape the work
- adding another layer unless the current layers clearly cannot hold the concept

## Stack asset provenance

Stack logos live in `public/logos/stack/`.

| Local file | Source URL | Notes |
|---|---|---|
| `django.svg` | `https://static.djangoproject.com/img/logos/django-logo-positive.svg` | official Django logo |
| `python.svg` | `https://www.python.org/static/community_logos/python-logo-generic.svg` | official Python logo |
| `react.png` | `https://react.dev/apple-touch-icon.png` | icon-grade fallback |
| `typescript.png` | `https://www.typescriptlang.org/icons/icon-48x48.png` | official icon |
| `postgresql.png` | `https://www.postgresql.org/media/img/about/press/elephant.png` | official PostgreSQL elephant |
| `aws.png` | `https://a0.awsstatic.com/libra-css/images/site/touch-icon-ipad-144-smile.png` | icon-grade fallback |
| `terraform.svg` | `https://developer.hashicorp.com/favicon.svg` | favicon-grade fallback |
| `github.svg` | `https://github.githubassets.com/favicons/favicon.svg` | favicon-grade fallback |
| `bruno.png` | `https://www.usebruno.com/bruno-logo.png` | official Bruno logo |
| `figma.svg` | `https://static.figma.com/app/icon/2/favicon.svg` | favicon-grade fallback |
| `mixpanel.svg` | `https://framerusercontent.com/images/LQGlUOsWA5MZ1jvvodsRAoGkNw.svg` | current Mixpanel-mark asset |
| `circleci.svg` | `https://d2qm0z2kzhiwa.cloudfront.net/assets/safari-pinned-tab-4b4ee212af4cd7e2665d09761df7f3c8.svg` | favicon-grade fallback |
| `astro.svg` | `https://astro.build/favicon.svg` | favicon-grade fallback |
| `terragrunt.png` | `https://cdn.prod.website-files.com/69264bc8388d5b45ee9bd175/69a5ebe7746f8b6e10212b45_favicon.png` | favicon-grade fallback |
| `uv.svg` | `https://raw.githubusercontent.com/astral-sh/uv/main/assets/svg/Astral.svg` | Astral brand mark used for uv |
| `ruff.svg` | `https://raw.githubusercontent.com/astral-sh/ruff/main/assets/svg/Astral.svg` | Astral brand mark used for Ruff |
| `jupyter.svg` | `https://raw.githubusercontent.com/jupyter/design/main/logos/Logo%20Mark/logomark-orangebody-greyplanets/logomark-orangebody-greyplanets.svg` | official Jupyter mark |
| `ipython.png` | `https://raw.githubusercontent.com/ipython/ipython/main/docs/source/_static/logo.png` | official IPython logo |
| `colab.png` | `https://colab.research.google.com/img/colab_favicon_256px.png` | icon-grade fallback |
| `zed.png` | `https://zed.dev/favicon_black_64.png` | favicon-grade fallback |
| `ghostty.png` | `https://ghostty.org/favicon-32.png` | favicon-grade fallback |
| `pi.svg` | `https://pi.dev/logo.svg` | official Pi logo |
| `docker.png` | `https://www.docker.com/app/uploads/2024/02/cropped-docker-logo-favicon-192x192.png` | icon-grade fallback |
| `sandboxes.svg` | `https://sandboxes.cloud/icon.svg` | official icon |
| `ngrok.png` | `https://ngrok.com/assets/apple-touch-icon.png` | icon-grade fallback |
| `cmux.png` | `https://cmux.com/logo.png` | official cmux logo |

If a better official asset becomes available later:
- replace the local file in place when possible
- keep the local file name stable if the meaning has not changed
- update this table so provenance stays obvious

## Maintenance rule of thumb

If one change requires editing the same idea in multiple pages by hand, pause and ask whether the content should live in structured data instead.
