---
description: Check status of your GitHub PRs — reviews, CI, merge readiness
---

Use your `pr-status` Skill to show a dashboard of your GitHub PRs, following
the workflow defined in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:
1. Fetch open PRs (or specified PRs).
2. Enrich with review decisions and CI status.
3. Present summary table sorted by urgency.
4. Highlight action items (changes requested, CI failing, ready to merge).

If `--merged` is provided, include PRs merged in the last 48 hours.
If `--all` is provided, check all repos, not just the current one.
