---
description: "Publish this branch's redacted agent session transcript for HEAD and link it in the PR."
argument-hint: "[pr-number] [--drop-turn N] [--include-output N] [--session ID] [--none 'reason']"
---

Use the `agent-session` skill for $ARGUMENTS.
Run its `share` command for the current branch and HEAD. On the branch's first
publish, show the developer the preview path and redaction summary and run
`share --yes` only after they agree; later republishes go straight through.
`share` links the newest transcript in the PR body's `## Agent sessions`
section and deletes the superseded upload. With `--none`, run `declare-none`
with the reason instead.
