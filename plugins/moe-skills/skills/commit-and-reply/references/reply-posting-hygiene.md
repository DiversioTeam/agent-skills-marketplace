# Commit and Reply — Reply Posting Hygiene

This reference is the local source of truth for reply targeting and dedupe
behavior used by `commit-and-reply`.

## Core posting rules

- Post **one reply per target comment**.
- **Do not blind-retry** failed replies. Re-check current state first.
- Run a **dedupe audit before posting** and again after posting.
- Keep replies short and factual:
  ```text
  Addressed in [<SHORT_SHA>](https://github.com/$OWNER/$REPO/commit/<FULL_SHA>).
  ```
- Do not add AI/vendor signatures, bot tags, or emoji signatures.

## Targeting rules

### Inline review threads

- Open, non-outdated threads are valid reply targets.
- Resolved/outdated threads are still valid when:
  - the comment was explicitly addressed in the current session, or
  - `--all` is catching up a thread that still has no later self reply.
- Resolved/outdated status alone is **not** a reason to skip replying.

### General PR comments

- Treat issue comments as flat conversation comments.
- Skip only when a later self-authored issue comment clearly acknowledges that
  same target comment (for example: it was selected from conversation context,
  manually chosen by the user, or otherwise tied to that specific reviewer
  comment).

## Dedupe rules

### Before posting

For each target comment:
- If a self reply already exists with the same SHA, skip.
- If a later self reply already acknowledges that same target, skip.
- Otherwise, post exactly one reply.

### After posting

- Inspect inline replies from self and remove duplicates, keeping only the
  earliest comment per unique intent.
- Inspect issue comments from self and remove duplicates, keeping only the
  earliest comment per unique intent.
