---
description: Re-run an existing monolith review after the author has updated a PR or linked cross-repo PR pair, preserving prior findings and focusing on deltas plus still-open concerns.
---

Use the `monolith-review-orchestrator` skill.

Operate in reassessment mode:
- reuse the deterministic worktree if it exists
- refresh local state safely
- refresh thread-aware GitHub review history when GitHub access is available
- load compact structured review context first
- report live PR drift against the latest recorded batch state before trusting
  the cached reassessment identity
- treat reported head drift as the normal trigger for exact-head reassessment,
  not as a pre-review blocker
- inspect new commits and comment deltas since the prior pass
- verify whether previously raised concerns are actually resolved
- keep resolved comments in context when they explain the author's changes
- produce an updated verdict and only post to GitHub if the user asked
