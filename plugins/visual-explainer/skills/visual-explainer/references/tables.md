# Tables

Read this only when the explainer contains an audit, comparison, inventory, or
other structured data.

- Use a real `<table>` with `<caption>`, `<thead>`, and `<tbody>`.
- Keep column headings short and specific.
- Align numbers consistently and use `font-variant-numeric: tabular-nums` when
  it improves scanning.
- Allow prose cells to wrap. Do not shrink text to fit a wide table.
- On narrow screens, wrap the table in an accessible horizontal scroll region.
- Use text or icons alongside colour for status.
- Put the most important conclusion above the table rather than expecting the
  reader to infer it from every row.
- Use summary cards only for metrics that materially help interpretation.

`templates/data-table.html` is an optional example. Reuse its semantic table and
responsive overflow patterns without copying its palette, fonts, animation, or
extra components unless they suit the request.
