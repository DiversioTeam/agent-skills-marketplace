# Model-Aware Instructions

## Sources And Limits

- OpenAI / Eric Provencher, September 11, 2026:
  [Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra).
- OpenAI, February 11, 2026:
  [Harness engineering](https://openai.com/index/harness-engineering/).

The September article is the source for the Astra observations below, not a
local benchmark or a promise about every model. When asked for the latest
model behavior, check current official guidance and record its publication
date and URL. If unavailable, label this as the last sourced guidance; do not
invent newer capabilities, model IDs, configuration flags, or runtime detection.
Do not infer the active model from the user's mention of a model name.

## What The Astra Article Says

- Long skill descriptions consume shared context and may be shortened by Codex,
  making skill selection harder. Use a short purpose and a precise trigger.
- Overlapping or emphatic triggers can load irrelevant, conflicting skills.
- Multi-workflow skills benefit from a small router and on-demand references.
- Detailed itineraries and mandatory whole-repo reading can overconstrain Astra.
- Astra generally checks its work without repeated reminders, but may stop at
  a first implementation or hesitate at boundaries inherited from older models.
- Explicit completion criteria and permission for a known-safe workflow can
  help it finish without repeated approval checkpoints.
- Shared repository instructions may serve different models. An optimization
  for Astra is not automatically appropriate for every contributor's agent.

## Writing Shared Repository Docs

Keep operational contracts model-neutral. Describe the result, relevant source,
required evidence, and authority; omit generic encouragement and model personas.
Do not copy a model-comparison essay into every generated AGENTS.md.

Prefer task routes:

```markdown
- Use docs/architecture.md when changing service boundaries.
- Use docs/database.md for schema changes and migration rollout.
- Use docs/deployment.md only when preparing an authorized deployment.
```

Do not replace this with "read all three before every edit". Directory-scoped
AGENTS.md rules still apply. A small docs fix does not need application tests
unless the repository's actual gates require them. For code changes, preserve
required tests, type gates, and security checks; reuse valid results for the
same code/configuration/environment rather than rerunning merely for a new
review phase. Changed inputs or required wider gates require fresh evidence.

Permission language must be backed by the repository, not model confidence.
Only after verifying the named suite uses disposable fixtures, has no production
access, and needs no paid/live writes, a generated rule can say:

```markdown
For the requested change, run <verified local test command>, fix related
failures, and rerun affected checks without asking at each step. Stop for
missing credentials, unsafe side effects, or decisions outside this scope.
```

Replace the placeholder with a verified command; do not paste the safety claim
into repositories whose tests reach staging, production, billing, or shared data.
Local inspection is not permission to publish CI statuses or start validation.
An implementation request may authorize verified safe local checks; a status,
review-only, plan-only, or dry-run request retains its narrower contract.

## Completion And Decision Boundaries

Define completion in terms of the requested outcome: implementation or docs,
applicable verification, fixes for failures caused by the change, and an honest
report of what remains blocked. Do not require a pause after the first draft
unless review at that point is part of the requested workflow.

Ask about consequential unknowns: target environment, ambiguous repository or
scope, data replacement, conflicting policy, external publication, or cost.
Infer ordinary file names and discoverable commands instead of making the user
supply them. Preserve explicit interactive modes and user-requested checkpoints.
Never relax tenant isolation, privacy, irreversible-action consent, exact-SHA
release evidence, or mandatory repository gates because a model is described
as more capable or aligned.

## Review Generated Instructions

- Does each description activate only for its actual workflow?
- Can the agent choose the relevant reference without loading unrelated modes?
- Is each strict rule a real invariant, ordering dependency, or output contract?
- Are safe actions and the completion boundary clear without generic repetition?
- Are model-specific claims dated and attributed, with uncertain facts labeled?
- Do templates, wrappers, and command behavior agree with the new instructions?
