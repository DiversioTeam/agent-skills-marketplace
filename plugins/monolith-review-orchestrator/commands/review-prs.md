---
description: Orchestrate one or more monolith PR reviews end-to-end with deterministic worktree management, deep context gathering, and optional GitHub posting.
---

Use the `monolith-review-orchestrator` skill.

Default to v1 intake, deterministic worktree reuse/bootstrap, deep PR/context
review, structured local state, and a final synthesis for the invoker.

If the prompt includes backend/Django4Lyfe work, invoke `monty-code-review` for
the backend slice instead of inventing a parallel backend rubric.

If the prompt includes multiple PRs or multiple repos, keep v1 narrow:
coordinate a single PR or one explicitly linked PR pair unless the user clearly
accepts experimental behavior.
