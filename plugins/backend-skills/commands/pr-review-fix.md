---
description: Fetch and address PR reviewer comments interactively
---

Use your `pr-review-fix` Skill to fetch reviewer comments from the current PR,
present each with code context, and implement fixes following the workflow and
quality gates defined in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:

1. Identify the PR (from argument or current branch).
2. Fetch all reviewer comments (reviews, inline, general).
3. Classify by severity and present one-by-one using AskUserQuestion.
4. On Fix: edit code, run ruff immediately.
5. After all comments: run ty, stage modified files.
6. Output summary with addressed comment IDs.

If `--auto` is provided, fix all actionable comments without prompting.
Does NOT commit — use `/backend-skills:commit-and-reply` after.
