---
description: "Deep-coverage code review with branch enumeration, adversarial inputs, and bias mitigation."
---

Use your `monty-v2-code-review` Skill to perform a deep code review of the
current change (PR, diff, or working tree), following the 8-phase workflow
defined in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:
1. Correctness, security, data integrity.
2. API and contract changes (including migrations).
3. Performance on hot paths.
4. Tests with branch enumeration and input matrix.
5. Unchanged code impact (callers, consumers).
6. Maintainability and nits.

For thorough per-file analysis, load `references/per-lens-checklist.md`.
For blind-spot patterns (Phase 7), load `references/blind-spot-patterns.md`.
For style rules, load `references/style-guidelines.md`.
