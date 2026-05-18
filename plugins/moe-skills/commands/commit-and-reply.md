---
description: Commit, push, and reply to addressed PR reviewer comments with SHA
---

Use your `commit-and-reply` Skill to invoke `/backend-atomic-commit:commit` for
quality gates and commit creation, then push to remote, then reply to each
addressed PR reviewer comment on GitHub with the commit SHA link, following
the workflow defined in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:

1. Verify staged changes exist and detect the PR.
2. Invoke `/backend-atomic-commit:commit` for quality gates and commit.
3. Push to remote.
4. Determine which comments to reply to (from context or `--all`).
5. Pre-audit for duplicate replies.
6. Post replies with commit SHA link.
7. Post-audit for duplicates.

If `--all` is provided, reply to all unresolved reviewer comments.
No AI signatures in commits or GitHub comments.
