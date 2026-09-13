---
description: Orchestrate a monolith PR review or one explicitly linked cross-repo PR pair end-to-end with deterministic worktree management, deep comment-history gathering, persistent review context, and optional GitHub posting.
---

Use the `monolith-review-orchestrator` skill.

Default to v1 intake, deterministic worktree reuse/bootstrap, deep PR/context
review, structured local state, and a final synthesis for the invoker.

Read existing review comments thoroughly, including resolved ones when they add
context about prior concerns or fixes.
When GitHub auth is available, use the orchestrator's thread-aware
`fetch_review_threads.py` helper instead of flat comment reads.

If the prompt includes backend/Django4Lyfe work, invoke `monty-code-review` for
the backend slice. For `frontend/`, `optimo-frontend/`, or `design-system/`,
invoke the `frontend` review lane when installed. Keep worktree state, synthesis,
and publication in this orchestrator.

If the prompt includes multiple PRs or multiple repos, keep v1 narrow:
coordinate a single PR or one explicitly linked cross-repo PR pair unless the
user clearly accepts experimental behavior.
