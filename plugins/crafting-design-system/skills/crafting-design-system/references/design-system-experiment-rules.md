# Design-system experiment rules

## Read before editing

In the remote `diversio-ds` checkout, read:

- `AGENTS.md`
- `docs/design-constraints.md`
- `docs/quality/compositions.md`
- the relevant feature/review docs and existing stories/components

The live checkout wins over examples in this skill.

## Build order

Use the first option that fits:

1. Existing component and variant
2. Small extension to an existing component, without breaking consumers
3. New atomic component with a standalone story
4. Composition built from those pieces

A composition may own fixture data, page arrangement, and local simulation controls. It must not absorb services,
routing, auth, analytics, persistence, authorization, eligibility, or backend policy.

## New atomic component minimum

For a genuinely new reusable piece, add only what makes it independently reviewable:

- a precise public type/API based on supplied presentation state
- token/theme-aligned styles with keyboard focus and narrow-width behavior
- a standalone Storybook story for meaningful states
- one focused runnable test for non-trivial interaction or state logic
- the correct product/core export
- consumption from the experiment composition

Do not create speculative factories, registries, configuration layers, service adapters, or generic abstractions.

## Prototype fidelity

- Use the correct product theme.
- Use synthetic finite fixtures and preserve zero/unavailable distinctions.
- Include loading/error/empty states only when they matter to the idea.
- Keep hidden controls out of keyboard and accessibility navigation.
- Use native controls and semantic HTML where possible.
- Do not log private fixture text to Storybook Actions.
- Do not claim source parity, accessibility approval, or production readiness from a working preview.

## Checks during iteration

Run the smallest remote check that catches the changed behavior:

- focused unit test for new logic
- focused Storybook interaction case
- TypeScript/lint for touched files
- direct browser check at desktop and narrow width

Before a Git handoff, follow the current repo gates. A stakeholder preview is not authority to publish a package,
change a consumer, post local-ci statuses, merge, or release.
