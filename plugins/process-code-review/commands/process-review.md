---
description: Process code review findings - interactively fix or skip issues from monty-code-review output
---

Use your `process-code-review` Skill to process the code review document specified
in the arguments, following the workflow, status markers, and quality gates defined
in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:

1. Parse the review document and extract all issues with severity tags.
2. Present issues one-by-one in severity order (BLOCKING -> SHOULD_FIX -> NIT).
3. For each issue, ask user to fix or skip.
4. Apply fixes and run quality checks.
5. Update the review document with status markers.
6. Summarize what was fixed vs skipped.

If asked to post processed findings to GitHub PR comments, follow the Skill's
`GitHub Review Comment Posting Mode` (`MUST_*`/`SHOULD_*`/`STEP_*` rules).

If `--dry-run` is provided, show all issues without modifying files.
If `--auto` is provided, apply all fixes without prompting (use with caution).
