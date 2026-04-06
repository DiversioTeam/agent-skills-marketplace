---
description: Re-run an existing monolith review after the author has updated one or more PRs, preserving prior findings and focusing on deltas plus still-open concerns.
---

Use the `monolith-review-orchestrator` skill.

Operate in reassessment mode:
- reuse the deterministic worktree if it exists
- refresh local state safely
- load structured local review state first
- inspect new commits and comment deltas since the prior pass
- verify whether previously raised concerns are actually resolved
- produce an updated verdict and only post to GitHub if the user asked
