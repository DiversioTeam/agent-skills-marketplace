---
description: "Backward-compatible alias for /review-delegator:review-delegator. Orchestrates parallel delegated checks and lane transport fallback."
---

Use your `review-delegator` Skill to perform a multi-skill code
review, following the architecture defined in its SKILL.md.

**Arguments:** `$ARGUMENTS`

`/review-delegator:delegate` is retained for compatibility and invokes the same
skill behavior as the canonical `/review-delegator:review-delegator` command.

Focus order:
1. Understand the PR (size, type, risk areas).
2. Run monty-v2 Phases 1-3 (intent, branch enumeration, adversarial inputs).
3. Determine lane policy (`--lanes=auto|on|off`) and use the best feature-detected transport.
4. Delegate Tier 1 checks to focused sub-skills in parallel:
   - /contract-propagation-check (P10, P17, P18 + concurrency/atomicity/edge-state extensions)
   - /import-export-roundtrip-check (round-trip I/O parity)
   - /merge-drift-check (P22, P24, P25 + lockfile/build-artifact checks)
   - /gate-runner
   - /historical-data-check (when applicable)
   - /test-quality-check (when applicable)
5. Run inline Tier 2 checks when relevant:
   - multi-tenant safety
   - API contract/version compatibility
6. Run monty-v2 remaining phases.
7. Compile all findings, deduplicate, flag systemic patterns.
8. Write review.

Lane policy flags: `--lanes=auto|on|off`.
- auto: small/low-risk PRs may stay inline; medium/high-risk PRs use lanes if available.
- on: force delegated lanes when transport is available.
- off: inline-only.

For --quick: low-risk PRs still run contract-propagation, merge-drift, and gate guard checks.
For --deep: run all sub-skills plus the inline Tier 2 checks.
For --self-review: bias check runs first.
