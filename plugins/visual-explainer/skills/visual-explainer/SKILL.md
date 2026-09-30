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
6. Try to open the local HTML in the browser and report its path.
7. Publish only when the user explicitly asks or passes `--publish`.

## Default Page

Start with four sections when they fit:

1. Summary
2. Evidence or key details
3. Risks and unknowns
4. Next steps

Add comparisons, diagrams, implementation status, examples, or a reply draft
only when they help explain the material. Do not force every page into the same
structure.

Use plain language for a smart but busy audience unless the user asks for a
technical treatment. Keep stakeholder pages free of unnecessary file paths,
code references, and test commands.

## Load Only What You Need

Resolve all paths below from this skill directory, not from the user's current
working directory.

- Read `references/page-basics.md` for every page.
- Read `references/tables.md` only for audits, comparisons, or structured data.
- Read `references/mermaid.md` only when a diagram is useful.
- Read `references/slide-patterns.md` only when slides are requested.
- Read `references/internal-share-publishing.md` only when publishing is
  requested.

Use a template only when it matches the requested output:

- `templates/architecture.html` for text-heavy architecture pages
- `templates/data-table.html` for tables and audits
- `templates/mermaid-flowchart.html` for Mermaid diagrams
- `templates/slide-deck.html` for requested slide decks

Templates are examples, not mandatory designs. Adapt or simplify them.

## Quality Rules

- Prefer semantic HTML, readable text, and clear visual hierarchy.
- Use real HTML tables for tabular data.
- Use Mermaid when relationships or sequence matter more than prose.
- Keep content readable on narrow screens and prevent horizontal overflow.
- Use sufficient contrast and respect `prefers-reduced-motion` when adding
  animation.
- Avoid unsupported claims. Say what is true now and label assumptions.
- A self-contained page must not depend on local files.

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
