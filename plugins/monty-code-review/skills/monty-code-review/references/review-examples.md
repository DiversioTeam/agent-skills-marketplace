# Review Examples

## Full Pedantic Review

- Preferred prompt:
  - “Use your `monty-code-review` skill to review this Django PR like Monty
    would, and be fully pedantic with your usual severity tags.”
- Also treat as this skill:
  - “Review this Django PR like Monty would! ultrathink”
- Expected output sketch:
  - Short intro paragraph summarizing the change and focus areas.
  - `What’s great` with specific positive bullets.
  - `What could be improved` with `[BLOCKING]`, `[SHOULD_FIX]`, and `[NIT]`
    findings.
  - `Tests` section calling out what’s covered and what’s missing.
  - `Verdict` section stating approve/request-changes posture.

## Quick / Non-Pedantic Pass

- Preferred prompt:
  - “Use your `monty-code-review` skill to skim this PR and only flag blocking
    or should-fix issues; skip most nits.”
- Also acceptable shorthand:
  - “Review this Django PR like Monty would, but only call out blocking or
    should-fix issues; skip the tiny nits.”
- Expected behavior:
  - Follow the same workflow and priorities.
  - Suppress most `[NIT]` items unless they are unusually important.
  - Keep the same output structure with a lighter strictness level.
