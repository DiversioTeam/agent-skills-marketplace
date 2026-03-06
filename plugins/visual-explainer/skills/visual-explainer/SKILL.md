---
name: visual-explainer
description: "Generate self-contained, presentation-ready HTML explainers for plans, diffs, docs, architecture, audits, and stakeholder updates. Use when the user wants a visual explainer, diagram, comparison, roadmap, mixed technical/non-technical summary, or an HTML alternative to a complex ASCII table. Gather missing audience/goal/source context interactively, separate confirmed facts from inference, save under ~/.agent/diagrams/, and open in the browser."
allowed-tools: Bash Read Write Grep Glob
---

# Visual Explainer

Create self-contained HTML pages that explain complex material faster than a
terminal wall of prose or ASCII tables.

This skill is optimized for mixed audiences by default:
- stakeholder updates
- architecture explainers
- plan and diff walkthroughs
- audits, comparisons, and status reviews
- customer, IT, or security reassurance docs

If the user explicitly asks for a deeper technical explainer, include more code
and implementation detail. Otherwise, keep the page accessible and
presentation-ready.

## Core Rules

1. Default to HTML, not ASCII art
   - If you are about to produce a table with 4+ rows or 3+ columns, generate an
     HTML page instead.
   - Prefer real diagrams, structured cards, or semantic tables over dense text.

2. Validate before explaining
   - Read the actual source material first.
   - Validate the current state before making claims.
   - Separate what is confirmed, what is inferred, and what still needs
     verification.

3. Ask only for missing required inputs
   - Required inputs are:
     - topic
     - audience
     - goal
     - source material
   - Infer them from the request and local context when safe.
   - If anything required is still missing, ask one concise follow-up covering
     only the missing items.

4. Keep the tone audience-correct
   - Default: plain language, smart-but-busy audience, low jargon.
   - Do not sound like an engineering memo unless the user asks for that.
   - Avoid file paths, code references, and test commands in stakeholder mode.
   - Use direct current-state wording only when the evidence supports it.

5. Deliver a shareable artifact
   - Write the final HTML to `~/.agent/diagrams/` with a descriptive filename.
   - Attempt to open it in the browser.
   - Tell the user the file path.
   - If useful or explicitly requested, also write a Markdown summary to
     `~/Downloads/`.

## Intake Protocol

Follow this order:

1. Read the request and any provided files, notes, plans, or diffs.
2. Resolve the minimum viable brief:
   - topic
   - audience
   - goal
   - source material
3. Collect optional preferences only when they materially affect output:
   - non-technical vs technical
   - include Markdown summary
   - include reply draft
   - slide deck instead of scrollable page
4. If source material is referenced but not yet read, read it before making
   structural decisions.

## Verification Model

Before writing HTML, build a compact fact sheet for yourself:
- confirmed facts
- reasonable inferences
- items still needing external verification

Use that split in the page whenever it helps the reader trust the document.

If the request depends on unstable external facts and browsing is available,
verify them before presenting them as current.

## Page Structure

For the default stakeholder explainer flow, read:
- `references/stakeholder-explainer.md`

For layout, styling, and reusable UI patterns, read:
- `references/css-patterns.md`
- `references/libraries.md`
- `references/responsive-nav.md` for pages with 4+ sections

For reference templates, read only the relevant files:
- text-heavy architecture overviews:
  `templates/architecture.html`
- flowcharts, sequences, ER diagrams, state machines, mind maps:
  `templates/mermaid-flowchart.html`
- audits, comparisons, and structured tables:
  `templates/data-table.html`
- slide decks only when the user explicitly wants slides:
  `references/slide-patterns.md`
  `templates/slide-deck.html`

## Visual Taste

Apply these constraints consistently:

- Avoid generic AI styling.
- Do not default to Inter plus purple/indigo accents.
- Use a distinct palette and intentional typography.
- Prefer side-by-side comparison cards when "before vs after" matters.
- Use Mermaid when topology or flow matters more than rich card text.
- Use real HTML tables for audits and comparisons.
- Make the page easy to skim in under two minutes unless the user asks for a
  deeper technical artifact.

## Default Deliverable

Unless the user asks for a different structure, the HTML should usually include:

1. Short headline summary
2. Confirmed vs inferred vs still-unverified view
3. Before vs after explanation when relevant
4. How it works
5. Why this approach is better
6. What is already done
7. What is left
8. Key caveats or risks
9. Recommended next step
10. Reply draft when the audience is customer, IT, security, or leadership

Use 2-5 concrete examples where they improve clarity.

## Slide Deck Mode

Slides are opt-in only.

Use slide mode only when:
- the user explicitly asks for slides
- a command wrapper explicitly requests slides

When slide mode is requested:
- read `references/slide-patterns.md`
- read `templates/slide-deck.html`
- preserve the same factual coverage, not a watered-down summary

## Final Step

After delivering the HTML path, suggest this optional share-out step when it is
useful:

- Post the HTML on Netlify Drop for team review.
- If site access controls are configured in Netlify, share the URL and password
  with the team.

Do not imply that Netlify Drop itself is password-protected by default.

## References

- `references/stakeholder-explainer.md`
  - default mixed-audience workflow, content shape, and tone
- `references/css-patterns.md`
  - card, table, animation, overflow, and Mermaid interaction patterns
- `references/libraries.md`
  - fonts, Mermaid setup, Chart.js, and theming guidance
- `references/responsive-nav.md`
  - section navigation for multi-section pages
- `references/slide-patterns.md`
  - slide-specific layout guidance when slide mode is explicitly requested
- `references/provenance.md`
  - upstream attribution and MIT notice for copied/adapted assets
