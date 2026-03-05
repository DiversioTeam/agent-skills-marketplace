---
description: Backend PR workflow check using the backend-pr-workflow Skill.
---

Use your `backend-pr-workflow` Skill to review this backend pull request’s
workflow aspects:

- ClickUp-linked branch naming and PR title conventions.
- Commit message prefixes with the ClickUp ticket ID.
- Correct base branch for normal vs hotfix releases.
- PR description quality and self-review checklist completion.
- Django migrations cleanup and downtime-safe schema changes.
- Repo-local workflow docs / harness clarity when rules are non-obvious.

Report findings with `[BLOCKING]`, `[SHOULD_FIX]`, and `[NIT]` tags as defined
in the Skill, and give a succinct summary verdict for whether the PR is
workflow-ready to merge.
