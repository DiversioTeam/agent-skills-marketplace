---
description: "Verify propagation, lifecycle/admin parity, concurrency/transaction scope, and evidence-based boundary handling."
---

Use your `contract-propagation-check` Skill to verify every changed contract
propagates correctly to ALL consumers, following the workflow in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:
1. Identify changed contracts from branch diff.
2. Grep ALL consumers across 9 consumer paths.
3. Audit lifecycle parity at 9 stages per helper.
4. Check admin three-layer surface (get_readonly_fields, inlines, ModelForm).
5. Audit stale reads, external I/O under locks, and sequential action atomicity.
6. Tie every guard/catch to a real boundary; reject speculative defenses on
   stable typed internals.
7. Audit admitted null/empty/boundary states.
8. Output findings with line citations and completion gate verification.

Evidence rule: "Looks fine" is not a finding. Every check must produce either
a line citation or an explicit exemption with reason.
