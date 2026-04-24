# Bumang Frontend Review Taste

Use these rules to shape frontend PR review once the repo digest has provided
local stack and workflow context.

## Core Review Priorities

1. Shipped contract beats stated intent.
   - If the implementation changes what users or downstream consumers actually
     observe, review against the shipped behavior, not only the PR description.
   - Flag doc/code divergence when docs describe a state the code no longer
     matches.

2. Dependency readiness is part of correctness.
   - Do not approve frontend changes that rely on unpublished or unavailable
     design-system/runtime capabilities.
   - Treat app ↔ design-system version mismatches and missing consumer support
     as real review findings.

3. User-visible semantics matter.
   - A visual cleanup that removes state cues, hierarchy, affordance, or
     behavior is not “just styling.”
   - Preserve meaning, not just layout.

4. Prefer consumer-level regression tests when the defect lives at the
   integration surface.
   - If a bug breaks the consuming app or design-system contract, a low-level
     constant or helper test is not enough by itself.
   - Ask for tests where the regression can actually be observed.

5. Keep names and contracts explicit.
   - Prefer descriptive names, stable casing, unique query/mutation identifiers,
     and import patterns that match the repo norm.
   - Call out names that hide behavior or make follow-up review harder.

6. Final-state docs are better than investigation-story docs.
   - Planning notes, PR text, and docs should describe the final implemented
     contract clearly.
   - Remove stale rationale that contradicts the shipped code.

## Common Findings This Taste Produces

- hidden UI contract regressions
- design-system release dependency gaps
- stale docs or PR descriptions that no longer match the implementation
- weak regression testing at the wrong layer
- inconsistent import, naming, or key-registration patterns

## Tone

Be direct and specific. Lead with correctness, contract fidelity, and user
impact before style or formatting nits.
