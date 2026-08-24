---
description: "Canonical entry for Review Delegator. Orchestrates parallel delegated checks and lane transport fallback; use this instead of /review-delegator:delegate for naming consistency."
---

Use your `review-delegator` Skill to perform a multi-skill code
review, following the architecture defined in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:
1. Understand the PR (size, type, risk areas).
2. Run monty-v2 Phases 1-3 (intent, branch enumeration, adversarial inputs).
3. Determine lane policy (`--lanes=auto|on|off`) and use the best feature-detected transport.
4. Run applicable focused checks, including contract propagation, import/export
   round trips, merge drift, CI gates, historical data, test quality, and
   reuse/precise-type searches when the diff adds stable shapes or duplicates.
5. Run inline multi-tenant and API compatibility checks when relevant.
6. Run monty-v2 remaining phases.
7. Compile all findings, deduplicate, flag systemic patterns.
8. Write review.

Lane policy flags: `--lanes=auto|on|off`.
- auto: small/low-risk PRs may stay inline; medium/high-risk PRs use lanes if available.
- on: force delegated lanes when transport is available.
- off: inline-only.

For --quick: low-risk PRs still run contract-propagation, merge-drift, and gate guard checks.
For --deep: run ALL sub-skills + monty-v2 deep-coverage mode.
For --self-review: bias check runs first.

---

## Backward-compatible alias

`/review-delegator:delegate` remains supported as a legacy alias and invokes
the same skill behavior.
