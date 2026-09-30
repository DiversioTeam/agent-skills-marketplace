# Slide Decks

Use slides only when the user explicitly requests a deck or passes `--slides`.
Read `page-basics.md` as well. Read `tables.md` or `mermaid.md` only when the
deck uses those elements.

## Plan The Deck

1. Read the complete source.
2. List the points the audience must understand.
3. Group related points into a short narrative.
4. Give each slide one main purpose.
5. Keep supporting detail only when it is needed to preserve meaning.

Do not force a fixed slide count. A short source may need only a few slides; a
detailed source may need more.

## Useful Slide Types

Choose only those that fit:

- title
- summary
- section divider
- focused content
- side-by-side comparison
- diagram
- table
- code or quotation
- next steps

Vary layouts when it improves pacing, not merely for novelty.

## Layout

- Make each slide fit within the viewport without clipping.
- Use large, readable type and restrained text density.
- Prefer short bullets or a focused visual over paragraphs.
- Keep tables to a readable number of rows; continue on another slide when
  necessary.
- Use CSS steps for simple linear flows and Mermaid for more complex diagrams.
- Keep navigation controls keyboard accessible and visible.
- Support arrow keys and scrolling without blocking interactions inside tables,
  code blocks, or diagrams.

## Motion

Transitions are optional. If used, keep them brief and respect
`prefers-reduced-motion`. The deck must remain understandable with animation
disabled.

## Responsive Behaviour

Desktop presentation is the primary mode, but the deck should remain usable on
smaller screens. Stack split layouts, allow wide tables or code to scroll, and
avoid text that becomes unreadably small.

## Template

`templates/slide-deck.html` is an optional starting point. Reuse its viewport,
navigation, and accessibility patterns as needed. Its palette, typography,
number of slides, transitions, and decorative treatments are examples rather
than requirements.

## Final Check

- every slide has one clear purpose
- source meaning has not been dropped
- text and diagrams are readable at presentation size
- no slide clips at common viewport sizes
- keyboard and pointer navigation work
- reduced-motion mode works
