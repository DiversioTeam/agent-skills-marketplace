# Mermaid Diagrams

Read this only when a flow, sequence, topology, state model, relationship, or
mind map explains the material better than prose.

## Use Mermaid When

- automatic edge routing helps
- the reader needs to follow relationships or sequence
- the diagram has enough structure to justify a diagram

Use simple HTML/CSS steps instead for a short linear process. Do not add a
diagram only for decoration.

## Authoring

- Keep node labels short and quote labels containing punctuation.
- Prefer one clear diagram over several dense diagrams.
- Split a diagram when labels become paragraphs or crossings obscure the flow.
- Use valid Mermaid syntax and a supported diagram type.
- Add a short text explanation so the page remains understandable if Mermaid
  fails to load.

## Presentation

- Put the diagram in a responsive container with `overflow: auto`.
- Ensure the rendered SVG can scale to the container width.
- Use readable node and edge-label sizes.
- Provide zoom or full-screen controls only for diagrams that actually need
  them.
- Maintain sufficient contrast in the Mermaid theme.

`templates/mermaid-flowchart.html` is an optional example with rendering and
zoom behaviour. Adapt only the parts needed for the requested diagram.
