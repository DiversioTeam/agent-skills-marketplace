---
description: "Orchestrated multi-skill code review with mandatory delegation for highest-recurring blind-spot patterns."
---

Use your `review-delegator` Skill to perform a multi-skill code
review, following the architecture defined in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:
1. Understand the PR (size, type, risk areas).
2. Run monty-v2 Phases 1-3 (intent, branch enumeration, adversarial inputs).
3. Delegate Tier 1 checks to focused sub-skills in parallel:
   - /contract-propagation-check (P10, P17, P18)
   - /merge-drift-check (P22, P24, P25)
   - /gate-runner
   - /historical-data-check (when applicable)
   - /test-quality-check (when applicable)
4. Run monty-v2 remaining phases.
5. Compile all findings, deduplicate, flag systemic patterns.
6. Write review.

For --quick: skip sub-skills unless monty-v2 flags a Tier 1 concern.
For --deep: run ALL sub-skills + monty-v2 deep-coverage mode.
For --self-review: bias check runs first.
