# Page Basics

Use these basics for every scrolling HTML explainer.

## Content

- Lead with a short summary that answers the user's main question.
- Put evidence and important details next.
- Separate confirmed facts from assumptions when the distinction matters.
- End with risks, unknowns, or next steps only when they are useful.
- Prefer short sections and concrete examples over long introductions.

The default four-section shape is a starting point, not a required outline.
Remove empty sections and add specialized sections only when the source calls
for them.

## Layout

- Use semantic landmarks: `header`, `main`, `section`, and `footer` where
  appropriate.
- Keep the main text column readable, usually no wider than 70–80 characters.
- Use cards only when they clarify grouping or comparison.
- Use a simple grid for genuine side-by-side content and stack it on narrow
  screens.
- Add section navigation only for a long page where it improves orientation.
- Avoid decorative elements that compete with the explanation.

## Typography And Colour

- Choose readable system fonts or a small number of web fonts.
- Use a consistent type scale and spacing rhythm.
- Maintain sufficient text and control contrast.
- Choose colours that suit the topic; palettes and font pairings in templates
  are examples, not requirements.
- A light theme, dark theme, or both are acceptable. Do not select a theme
  randomly.

## Responsive And Accessible Output

- Include the viewport meta tag.
- Make grids collapse cleanly on narrow screens.
- Wrap long text and code; put genuinely wide tables in a labelled horizontal
  scroll container.
- Give controls accessible names and visible keyboard focus.
- Use colour as reinforcement, not the only status signal.
- Respect `prefers-reduced-motion` for non-essential animation.
- Check that headings follow a sensible order.

## Self-Contained Delivery

Prefer inline CSS and JavaScript. External CDN libraries and web fonts are
acceptable when the page needs them and internet access is expected, but do not
reference local project files. Keep the local HTML useful even when optional
visual libraries fail to load.

## Final Check

Before delivery, check:

- the page answers the request
- claims match the source
- assumptions are labelled
- text is readable at desktop and mobile widths
- nothing important is clipped or hidden
- links and interactive controls work
- motion is optional rather than required for understanding
