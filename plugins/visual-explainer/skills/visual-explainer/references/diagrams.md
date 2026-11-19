# Diagrams

Read this only when a flow, sequence, topology, state model or relationship
explains the material better than prose.

## Draw Inline SVG

- Draw the diagram as inline `<svg>` in the page (see `templates/diagram.html`).
  No Mermaid, no diagram scripts, no CDN: the page must work offline and on
  Internal Share, and `scripts/check_page.py` refuses Mermaid.
- Use simple HTML/CSS steps instead for a short linear process. Do not add a
  diagram only for decoration.
- If Mermaid helps you draft, render it to SVG first (open the page in a browser,
  copy the rendered `<svg>` into the page) and remove the Mermaid source and script.

## Make It Readable

- Flow top to bottom so the same drawing works on a phone and a laptop.
- Put labels on the shapes and arrows (direct labels); no legend.
- Colour only the part the reader must notice; everything else stays neutral.
- Keep text at 13px or more at phone width: use a narrow `viewBox` (about 300 to
  360 units wide) with `width: 100%` and a `max-width` of about 420px.
- Use colour tokens from `:root` (`fill: var(--accent)`), so the drawing follows
  light and dark mode.
- Give the `<svg>` `role="img"` and an `aria-label` that says what it shows, and
  add one sentence of text saying the same.

## Charts For Numbers

When the point is a comparison ("5 of 9 sign-ups came from login searches"), show it
as a small horizontal bar chart right after the summary: one bar per group, the
value at the end of each bar, the important bar in the accent colour, no
gridlines, no legend. In tables, draw bars only in the column that answers the
question (see `tables.md`).
