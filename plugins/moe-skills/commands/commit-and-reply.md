---
description: Commit, push, and reply to addressed PR reviewer comments with SHA
---

Use your `commit-and-reply` Skill to invoke `/backend-atomic-commit:commit` for
quality gates and commit creation, then push to remote, then reply to each
addressed PR reviewer comment on GitHub with the commit SHA link, following
the workflow defined in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:

1. Detect the PR and auto-stage if the index is empty but the worktree has intended changes.
2. Invoke `/backend-atomic-commit:commit` for quality gates and commit.
3. Pull/re-gate/push the branch.
4. Determine which comments to reply to (from context or `--all`).
5. Pre-audit for duplicate replies.
6. Post replies with commit SHA link, including resolved/outdated-thread catch-up when appropriate.
7. Post-audit for duplicates.

If `--all` is provided, use thread-aware review-thread data for inline comments, include resolved/outdated threads that still lack a later self reply, and include general PR comments separately.
No AI signatures in commits or GitHub comments.
