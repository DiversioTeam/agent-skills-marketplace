---
description: "Render, review, and publish this branch's redacted agent session transcript, then link it in the PR."
argument-hint: "[pr-number] [--drop-turn N] [--include-output N] [--session ID] [--none 'reason']"
---

Use the `agent-session` skill for $ARGUMENTS.
Find the sessions behind the current branch, render the redacted preview, and
show the developer the redaction summary and preview path. Publish only after
they confirm, then put the link in the PR body's `## Agent sessions` section.
With `--none`, write the `No agent session: <reason>` declaration instead.
