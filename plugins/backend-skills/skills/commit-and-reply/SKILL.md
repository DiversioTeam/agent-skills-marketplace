---
name: commit-and-reply
description: >
    Invoke /backend-atomic-commit:commit for quality gates and commit creation,
    then push to remote, then reply to each addressed PR reviewer comment on
    GitHub with the commit SHA link. No AI signatures anywhere.
user-invocable: true
argument-hint: '[--all]'
allowed-tools: [Bash, Read, Edit, Glob, Grep, Skill]
---

# Commit and Reply Skill

Commit staged changes via `/backend-atomic-commit:commit`, push to remote, and
reply to each addressed PR reviewer comment with a commit SHA link. Designed to
run after `/pr-review-fix`.

**Reference documentation:**

- `docs/runbooks/pr-review-posting-hygiene.md` — posting protocol and dedupe rules
- `docs/quality/gates.md` — quality gate definitions
- `AGENTS.md` — product boundaries, commit conventions, and global rules

---

## Step 1: Verify Preconditions

Check that there are staged changes and detect the PR:

```bash
# Verify staged changes exist
git diff --cached --name-only

# Detect PR from current branch
gh pr view --json number,url,headRefName
```

Set up environment:

```bash
OWNER="DiversioTeam"
REPO="Django4Lyfe"
ME="$(gh api user --jq '.login')"
PR=<detected-pr-number>
```

**If nothing is staged**, stop and tell the user:

> "No staged changes found. Run `/pr-review-fix` first to address reviewer
> comments and stage fixes."

**If no PR is found**, stop and tell the user to push the branch and open a PR
first.

---

## Step 2: Invoke Atomic Commit

Invoke the backend atomic commit skill to handle all quality gates and create
the commit:

```
/backend-atomic-commit:commit
```

This handles:

- Ruff check and format
- `ty` check
- Django system checks
- Ticket-prefixed commit message (extracted from branch name)
- Pre-commit hook compliance
- **No AI signatures** in the commit message

**If BLOCKING issues are found**, stop. The atomic commit skill will report
what needs to be fixed. Fix the issues, re-stage, and re-run this skill.

---

## Step 3: Push to Remote

Push the commit to the remote branch:

```bash
git push
```

**If push fails** (e.g., remote has new commits):

> "Push failed. Try `git pull --rebase` to incorporate remote changes, then
> re-run `/commit-and-reply`."

Do not force-push.

---

## Step 4: Get Commit SHA

Capture the commit SHA for use in reply comments:

```bash
FULL_SHA="$(git rev-parse HEAD)"
SHORT_SHA="$(git rev-parse --short HEAD)"
COMMIT_MSG="$(git log -1 --format='%s')"
```

---

## Step 5: Determine Comments to Reply To

Three modes for selecting which comments get replies:

### Mode A: Conversation Context (default)

If `/pr-review-fix` was run earlier in this conversation, use the addressed
comment IDs it tracked. This is the preferred flow.

### Mode B: `--all` Flag

If `--all` is passed, fetch all unresolved reviewer comments:

```bash
# Inline comments from other reviewers
gh api "repos/$OWNER/$REPO/pulls/$PR/comments" --paginate \
  --jq "[.[] | select(.user.login != \"$ME\") | {id, path, body}]"

# General comments from other reviewers
gh api "repos/$OWNER/$REPO/issues/$PR/comments" --paginate \
  --jq "[.[] | select(.user.login != \"$ME\") | {id, body}]"
```

### Mode C: No IDs, No `--all`

If no addressed IDs are available and `--all` was not passed, ask the user:

> "I don't have a list of addressed comments from a prior `/pr-review-fix` run.
> Would you like me to:
>
> 1. Reply to **all** reviewer comments with this commit SHA
> 2. **Skip** replies (just commit and push)
> 3. **List** reviewer comments so you can pick which ones to reply to"

---

## Step 6: Pre-Audit for Duplicates

Before posting any replies, check for existing replies from self to avoid
duplicates (per `pr-review-posting-hygiene.md` MUST_04):

```bash
# Check existing inline comment replies from self
gh api "repos/$OWNER/$REPO/pulls/$PR/comments" --paginate \
  --jq "[.[] | select(.user.login == \"$ME\") | {id, in_reply_to_id, body, created_at}]"

# Check existing issue-level comments from self
gh api "repos/$OWNER/$REPO/issues/$PR/comments" --paginate \
  --jq "[.[] | select(.user.login == \"$ME\") | {id, body, created_at}]"
```

For each comment we plan to reply to:

- If a reply from self already exists with the same SHA → **skip** (already
  replied)
- If a reply from self exists with a different SHA → **skip** (previous
  attempt, don't double-post)

---

## Step 7: Post Replies

### Reply format

All replies use the same format — short, factual, no AI signatures:

```
Addressed in [<SHORT_SHA>](https://github.com/DiversioTeam/Django4Lyfe/commit/<FULL_SHA>).
```

### For inline review comments

Reply as a thread response to the original comment:

```bash
gh api "repos/$OWNER/$REPO/pulls/$PR/comments/$COMMENT_ID/replies" \
  -f body="Addressed in [$SHORT_SHA](https://github.com/DiversioTeam/Django4Lyfe/commit/$FULL_SHA)."
```

### For general PR comments

Post a new issue comment referencing the original:

```bash
gh api "repos/$OWNER/$REPO/issues/$PR/comments" \
  -f body="Addressed in [$SHORT_SHA](https://github.com/DiversioTeam/Django4Lyfe/commit/$FULL_SHA)."
```

### Posting rules

- Post **one reply per comment** — do not batch multiple comments into one reply
- Do **not** retry blindly on failure — check state first
- If a reply fails with HTTP 422, log the error and continue to the next comment
- No AI signatures, no co-author tags, no emoji

---

## Step 8: Post-Audit for Duplicates

Run the dedupe detector from `pr-review-posting-hygiene.md` STEP_05:

```bash
# Check inline comment duplicates
gh api "repos/$OWNER/$REPO/pulls/$PR/comments" --paginate --slurp \
  | jq --arg me "$ME" '
      map(if type == "array" then . else [.] end)
      | flatten
      | map(select(.user.login == $me))
      | group_by([.path, (.line // -1), ((.body // "") | split("\n")[0])])
      | map(select(length > 1) | {
          duplicate_count: length,
          path: .[0].path,
          line: .[0].line,
          sample_ids: map(.id)
        })
    '

# Check issue-level comment duplicates
gh api "repos/$OWNER/$REPO/issues/$PR/comments" --paginate --slurp \
  | jq --arg me "$ME" '
      map(if type == "array" then . else [.] end)
      | flatten
      | map(select(.user.login == $me))
      | group_by(((.body // "") | split("\n")[0]))
      | map(select(length > 1) | {
          duplicate_count: length,
          first_line: ((.[0].body // "") | split("\n")[0]),
          sample_ids: map(.id)
        })
    '
```

**If duplicates are found**, delete the extras immediately:

```bash
# Delete duplicate inline comments
gh api -X DELETE "repos/$OWNER/$REPO/pulls/comments/$DUPLICATE_ID"

# Delete duplicate issue comments
gh api -X DELETE "repos/$OWNER/$REPO/issues/comments/$DUPLICATE_ID"
```

Keep only the earliest comment per unique intent.

---

## Step 9: Output Summary

```
Commit and Reply Summary
========================
Commit: <SHORT_SHA> — <commit-message>
Push: success
PR: #<number> — <url>

Replies posted: <N>
  - Comment #<id> by <reviewer> → replied
  - Comment #<id> by <reviewer> → replied
  - Comment #<id> by <reviewer> → skipped (already replied)

Dedupe audit: clean (no duplicates) | removed <N> duplicates
```

---

## Rules

- **No AI signatures** — no `Co-Authored-By: Claude`, no bot tags, no emoji
  signatures in commits or GitHub comments.
- **Follow `pr-review-posting-hygiene.md`** — dedupe audit before and after
  posting, one reply per comment, no blind retries.
- **Never post duplicate replies** — always check existing replies first.
- **Do not force-push** — if push fails, tell the user to rebase.
- **Skill invocation** — step 2 must use `/backend-atomic-commit:commit`, not
  manual commit logic. This keeps commit quality gates DRY.

---

## Example Prompts

> `/commit-and-reply`
>
> After running `/pr-review-fix`, commits staged changes, pushes, and replies
> to each addressed comment with the commit SHA.

> `/commit-and-reply --all`
>
> Commits, pushes, and replies to ALL reviewer comments on the PR (not just
> those addressed in the current session).
