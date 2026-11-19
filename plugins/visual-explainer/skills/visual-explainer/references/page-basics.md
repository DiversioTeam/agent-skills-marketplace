# Page Basics

Use these basics for every scrolling HTML explainer. They are the Diversio
readable-page standard (shared with Courage's Internal Share gate), and
`scripts/check_page.py` checks them.

## Content

- Open with a summary box: the answer or decision and what the reader does next
  (or "nothing for you to do"), in one or two plain sentences, at most 80 words.
- Show the point next: a stat tile row or one small chart when the answer is a
  number or a comparison. Then the evidence and details.
- Plain words and short paragraphs (under 110 words). Name things in words, not
  ids: commit hashes, run ids, account numbers and machine paths go in one folded
  `<details class="evidence">` section at the end, or in code blocks.
- Separate confirmed facts from assumptions when the distinction matters.
- End with what is left, risks or next steps only when they are useful. Remove
  empty sections and placeholder text.

The default four-section shape is a starting point, not a required outline.

## Layout

- Use semantic landmarks: `header`, `main`, `section`, and `footer`.
- Keep the main text column readable, usually no wider than 70 to 80 characters.
- Use cards only when they clarify grouping or comparison.
- Use a simple grid for genuine side-by-side content and stack it on narrow
  screens. No fixed widths over 480px.
- Pages with five or more sections, or over 1,200 words, need a section nav
  (`<nav class="toc">` with links to each section) near the top.
- Avoid decorative elements that compete with the explanation.

## Typography And Colour

- System font stack only; no web fonts. Body text 15px or more, nothing under 12px.
- Define colours as tokens on `:root` (`--bg`, `--surface`, `--text`, `--muted`,
  `--accent`) and redefine them under `@media (prefers-color-scheme: dark)`. Both
  themes are required.
- Text, muted text and links reach 4.5:1 contrast on their backgrounds in both
  themes.

## Responsive And Accessible Output

- Include the viewport meta tag and `<html lang="en">`.
- Put every table in a horizontal scroll wrapper. A table of four or more columns
  must stack into one card per row on a phone: `class="stack"` on the table and a
  `data-label` with the column name on every cell after the first (see
  `templates/data-table.html`).
- Give controls accessible names and visible keyboard focus.
- Use colour as reinforcement, not the only status signal.
- Respect `prefers-reduced-motion` for non-essential animation.

## Self-Contained Delivery

Everything inline: CSS in `<style>`, scripts inline, images as `data:` URIs,
diagrams as inline SVG. No CDN libraries, web fonts or local file references.
Internal Share refuses pages that load anything from elsewhere.

## Final Check

Run `python3 <skill dir>/scripts/check_page.py page.html` and fix everything it
lists. Then check that claims match the source, assumptions are labelled, and the
page reads well at phone width in light and dark.
