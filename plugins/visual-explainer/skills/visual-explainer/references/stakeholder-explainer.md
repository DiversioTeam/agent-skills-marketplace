# Stakeholder Explainer Mode

Use this mode for the default `/visual-explainer:explain` flow.

It turns plans, diffs, docs, notes, or live codebase findings into a visual,
presentation-ready HTML page for a smart but busy audience.

## Required Inputs

Resolve these before writing HTML:

- topic
- audience
- goal
- source material

Infer them when obvious from the request and context. Ask one concise follow-up
only for what is still missing.

## Default Intake

Use this order:

1. Read the source material first.
2. Validate the current state before explaining it.
3. Write down:
   - confirmed facts
   - inferred points
   - items needing external verification
4. Collect optional preferences only when they materially affect delivery:
   - technical vs mixed-audience depth
   - Markdown summary
   - reply draft
   - slide deck
   - publish after local generation
   - open the deploy URL after publish
5. Choose the lowest-complexity page shape that still explains the topic well.

## Default Content Shape

Include these sections unless the material clearly does not need one:

1. **Headline summary**
   - One or two sentences.
   - The reader should understand the core point immediately.

2. **What is confirmed / inferred / still needs verification**
   - Make trust boundaries visible.
   - Keep this concise and easy to scan.

3. **Before vs after**
   - Use side-by-side cards when there is a meaningful change.
   - Skip this if there is no real comparison to make.

4. **How it works**
   - Use a simple flow, diagram, or comparison table.
   - Prefer diagrams over dense paragraphs when topology or sequence matters.

5. **Why the new approach is better**
   - Focus on outcomes and decisions, not implementation trivia.

6. **What is already done**
   - Show concrete progress.

7. **What is left**
   - Keep this short and specific.

8. **Key caveats or risks**
   - Include only the real ones.

9. **Recommended next step**
   - End with a clear recommendation when helpful.

10. **Reply draft**
   - Include only when the audience is external-facing or the user asks.

## Voice and Detail Level

Default voice:

- plain language
- calm, direct, and current-state
- smart-but-busy audience
- low jargon
- more solution/decision focused than implementation focused

Default exclusions in stakeholder mode:

- avoid file paths unless explicitly requested
- avoid code references unless explicitly requested
- avoid test commands unless explicitly requested
- do not make it read like an engineering memo

## Variants

### Executive / customer-facing

Bias toward:

- confidence
- clarity
- next steps
- minimal jargon
- fast skim time

### IT / security-facing

Bias toward:

- precise current-state language
- what is and is not in scope
- caveats and final verification steps
- calm, trust-building tone

### Internal / technical

Allow:

- supporting Markdown summary in `~/Downloads/`
- implementation references
- validation notes
- deeper caveats

Keep the HTML itself stakeholder-friendly unless the user asks for a deeply
technical page.

## Diagram Guidance

Use the lightest-weight visual that explains the point:

- Mermaid for flows, topology, states, sequence, ER, and mind maps
- CSS card layout for text-heavy architecture overviews
- semantic HTML tables for audits, comparisons, and inventories
- timeline or roadmap layout for staged work

Do not use styled cards when the reader actually needs a flow diagram.

## Delivery

Write the HTML to `~/.agent/diagrams/` with a clear filename.

Try to open it in the browser after writing it.

Tell the user:

- the final file path
- whether a Markdown summary was also written
- any important unverified points
- if publish mode was used, the deploy URL and publish receipt path

If publish mode was requested:

- publish only after the local HTML exists
- use a fresh Netlify preview site for this run
- keep secrets in env vars only
- preserve the local HTML even if the publish fails

If publish mode was not requested and sharing would help, you may end with this
optional suggestion:

- Post it on Netlify Drop and, if site access controls are configured, share the
  link and password with the team.
