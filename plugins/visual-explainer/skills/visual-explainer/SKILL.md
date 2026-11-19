---
name: visual-explainer
description: "Create clear HTML explainers for plans, changes, diagrams, audits, and updates. Label facts and assumptions, and optionally upload the result to Diversio Internal Share."
allowed-tools: Bash Read Write Grep Glob
---

# Visual Explainer

## When to Use

Use this skill when the user asks for a visual HTML explanation of a plan,
change, architecture, audit, comparison, or update. Use slides only when the
user asks for them.

## Example Prompts

- Explain this implementation plan for a mixed technical audience.
- Turn these audit findings into a clear HTML page with a table.
- Create and publish a diagram showing this request flow.

## Workflow

1. Read the request and all referenced source material.
2. Work out the topic, audience, goal, and source. Ask one short question only
   when a missing detail would materially change the result.
3. Check the source before making claims. Distinguish:
   - confirmed facts
   - likely but unconfirmed assumptions
   - facts that still need checking
4. Use the simplest useful layout.
5. Write the final HTML to `~/.agent/diagrams/` with a descriptive filename.
6. Run `python3 <skill dir>/scripts/check_page.py <page>` (add `--kind slides`
   for a slide deck) and fix everything it lists. A page that fails is not
   finished, and the publisher refuses it.
7. Try to open the local HTML in the browser and report its path.
8. Publish only when the user explicitly asks or passes `--publish`.

## Default Page

The reader should get the point in ten seconds. Start with:

1. A summary box: the answer or decision and what the reader does next (or
   "nothing for you to do"), in one or two plain sentences.
2. The point as a visual when it is a number or comparison: stat tiles or one
   small bar chart.
3. Evidence or key details.
4. Risks, unknowns or what is left, only when useful.

Add comparisons, diagrams, implementation status, examples, or a reply draft
only when they help explain the material. Do not force every page into the same
structure.

Use plain language for a smart but busy audience unless the user asks for a
technical treatment. Name things in words: commit hashes, run ids, account
numbers and file paths go in one folded `<details class="evidence">` section.
A change or review explainer reads like a guided tour: what changed and why, the
risky part with a short code excerpt, what was verified, and what is left.

## Load Only What You Need

Resolve all paths below from this skill directory, not from the user's current
working directory.

- Read `references/page-basics.md` for every page.
- Read `references/tables.md` only for audits, comparisons, or structured data.
- Read `references/diagrams.md` only when a diagram or chart is useful.
- Read `references/slide-patterns.md` only when slides are requested.
- Read `references/internal-share-publishing.md` only when publishing is
  requested.

Use a template only when it matches the requested output:

- `templates/architecture.html` for text-heavy architecture pages
- `templates/data-table.html` for tables and audits
- `templates/diagram.html` for a flow drawn as inline SVG
- `templates/slide-deck.html` for requested slide decks

Templates are examples, not mandatory designs. Adapt or simplify them.

## Quality Rules

- Prefer semantic HTML, readable text, and clear visual hierarchy.
- Use real HTML tables for tabular data.
- Draw diagrams as inline SVG with direct labels, never Mermaid.
- Keep content readable on narrow screens: tables scroll, and tables of four or
  more columns stack into cards on a phone.
- Light and dark themes, both with 4.5:1 text contrast; respect
  `prefers-reduced-motion` when adding animation.
- Avoid unsupported claims. Say what is true now and label assumptions.
- Self-contained: no web fonts, CDN scripts or local file references.

## Publishing

Publishing is optional. Follow `references/internal-share-publishing.md` when it
is requested.

Never request, print, or store the user's emailed one-time PIN or Cloudflare
Access token. The user completes authentication in the browser.

The publishing helper is relative to this skill directory. Invoke it with the
resolved absolute skill path; do not assume the user's project contains a
`scripts/` directory.

After publishing, report:

- local HTML path
- Diversio Internal Share URL
- that viewers must sign in with a Diversio account

If publishing fails, keep and report the local HTML path.

## Optional Flags

- `--technical`: include more implementation detail
- `--summary`: also write a Markdown summary to `~/Downloads/` when useful
- `--reply-draft`: include a reply draft when useful
- `--slides`: create a slide deck instead of a scrolling page
- `--publish`: upload the finished HTML to Diversio Internal Share
- `--open-url`: open the Internal Share URL after upload
