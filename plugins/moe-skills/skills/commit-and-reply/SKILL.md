---
name: commit-and-reply
description: >
    Invoke /backend-atomic-commit:commit for quality gates and commit creation,
    then push to remote, then reply to each addressed PR reviewer comment on
    GitHub with the commit SHA link. No AI signatures anywhere.
user-invocable: true
argument-hint: '[--all]'
allowed-tools: [Bash, Read]
---

# Commit and Reply Skill

Commit staged changes via `/backend-atomic-commit:commit`, or auto-stage the
current PR fixes first when nothing is staged, then push to remote and reply to
each addressed PR reviewer comment with a commit SHA link. This includes
resolved/outdated review threads when they became outdated because the fix
landed or the code moved. Designed to run after `/moe-skills:pr-review-fix`.

**Dependency:** Requires `backend-atomic-commit@diversiotech` plugin to be
installed (`/backend-atomic-commit:commit` is invoked in Step 2).

**This skill is NOT done until the Step 9 summary is printed.** The commit
in Step 2 is only the first third of the workflow — push, replies, and
dedupe audit must all complete before this skill is finished.

**Reference documentation:**

- `references/reply-posting-hygiene.md` — posting protocol, reply targeting, and dedupe rules
- `docs/quality/gates.md` — quality gate definitions
- `AGENTS.md` — product boundaries, commit conventions, and global rules
- `references/merge-conflict-resolution.md` — detailed merge-conflict handling for Step 3

---

## Step 1: Verify Preconditions / Auto-Stage If Needed

Check the current git state and detect the PR:

```bash
# Inspect git state
git status --short
git diff --cached --name-only
git diff --name-only
git ls-files --others --exclude-standard

# Detect PR from current branch
gh pr view --json number,url,headRefName,baseRefName
```

Set up environment:

```bash
ME="$(gh api user --jq '.login')"
REPO_INFO="$(gh repo view --json owner,name)"
OWNER="$(echo "$REPO_INFO" | jq -r '.owner.login')"
REPO="$(echo "$REPO_INFO" | jq -r '.name')"
PR=<detected-pr-number>

# Derive the branch diff base from the PR target branch.
# Override by exporting BASE_BRANCH before invoking if needed.
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh pr view --json baseRefName --jq '.baseRefName' 2>/dev/null)"
fi
```

**If no PR is found**, stop and tell the user to push the branch and open a PR
first.

**If nothing is staged but the working tree has changes**, auto-stage them first:

```bash
git add -A
git diff --cached --name-only
```

Auto-stage rules:
- Stage tracked modifications, deletions, renames, and untracked files.
- Do **not** stage ignored files.
- Show the staged file list before moving on.
- If this stages unrelated work, let `/backend-atomic-commit:commit` fail
  atomicity rather than silently committing a partial fix set.

**If nothing is staged and the working tree is clean**, stop and tell the user:

> "No staged changes found and no unstaged changes to auto-stage. Run `/moe-skills:pr-review-fix`
> first or make the intended fixes before using `/moe-skills:commit-and-reply`."

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

**CRITICAL: After the atomic-commit skill returns, you are NOT done.**
The commit exists only locally. You MUST continue with Steps 3–9 below
(pull, re-gate, push, get SHA, reply to comments, dedupe audit, summary).
Do not treat the atomic-commit completion as the end of this workflow.

### Step 2b: Hardened Ruff Format Gate

**After the atomic commit succeeds**, run the exact CI gate that will
validate this branch. The atomic-commit runs `ruff format` on staged files,
but CI runs `ruff_pr_diff.sh` which checks the union of branch diff +
local changes. Run it explicitly to catch formatting drift before push:

```bash
./.security/ruff_pr_diff.sh
```

If this fails:
1. Apply formatting: `.bin/ruff format $(git diff --name-only origin/$BASE_BRANCH...HEAD --diff-filter=ACMRT | grep '\.py$')`
2. Re-check: `./.security/ruff_pr_diff.sh`
3. Amend the commit: `git add <formatted-files> && git commit --amend --no-edit`

**Do not proceed to push until `ruff_pr_diff.sh` passes.** This is the #1
CI failure pattern — `ruff format` alone is not enough; the diff-based
check catches files that `ruff format` on staged files alone can miss.

---

## Step 3: Pull Latest from Base Branch, Resolve Conflicts, Re-Gate, and Push

Pull latest from the PR base branch:

```bash
git pull origin "$BASE_BRANCH" --no-rebase
```

### If merge conflicts occur

Check which files are conflicted:

```bash
git diff --name-only --diff-filter=U
```

Then resolve them using `references/merge-conflict-resolution.md`.
That reference covers:
- migration conflicts
- lock/generated file conflicts
- additive code conflicts
- stop-and-ask categories (schema/security/business-logic/test fixtures)

After all conflicts are resolved, complete the merge:

```bash
git commit --no-edit
```

### Re-run quality gates after merge

The merge can introduce formatting or lint issues that weren't in either
branch alone. Run the full gate sequence:

```bash
.bin/ruff check --fix .
.bin/ruff format .
./.security/ruff_pr_diff.sh
./.security/local_imports_pr_diff.sh
```

If `ruff_pr_diff.sh` fails (the #1 CI failure pattern):
1. Apply formatting to the specific files Ruff reports
2. Re-run `./.security/ruff_pr_diff.sh` until clean
3. Stage and amend: `git add <formatted-files> && git commit --amend --no-edit`

If any other gate fails, fix the issue, stage, and amend the merge commit:

```bash
git add <fixed-files>
git commit --amend --no-edit
```

Re-run gates until clean. Only then push:

```bash
git push
```

**If push fails** (e.g., remote has new commits on the feature branch):

> "Push failed. Try `git pull --rebase` to incorporate remote changes, then
> re-run `/moe-skills:commit-and-reply`."

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

If `/moe-skills:pr-review-fix` was run earlier in this conversation, use the addressed
comment IDs it tracked. This is the preferred flow.

**Important:** addressed comment IDs from conversation context stay eligible even if
GitHub now marks the thread `isResolved == true` or `isOutdated == true`.
That state often means the fix landed and the old diff position is stale — not
that we should skip replying.

### Mode B: `--all` Flag

If `--all` is passed, use a **thread-aware** acquisition path for inline review
comments. Do not use flat REST comment lists to decide which inline comments are
still open.

In `--all` mode, collect two inline-review buckets:
1. comments in open, non-outdated threads
2. comments in resolved/outdated threads that still do **not** have a reply from
   you after the latest reviewer comment in that thread

Bucket (2) is the catch-up path for comments that are "outdated" only because
we fixed them and the code moved.

```bash
# Inline review threads — fetch thread state and all thread comments for reply targeting
gh api graphql -f query='
  query($owner:String!, $repo:String!, $pr:Int!) {
    repository(owner:$owner, name:$repo) {
      pullRequest(number:$pr) {
        reviewThreads(first:100) {
          pageInfo { hasNextPage endCursor }
          nodes {
            isResolved
            isOutdated
            path
            comments(first:100) {
              pageInfo { hasNextPage endCursor }
              nodes {
                databaseId
                body
                createdAt
                author { login }
              }
            }
          }
        }
      }
    }
  }' -f owner="$OWNER" -f repo="$REPO" -F pr="$PR"

# General PR comments — these do not have thread resolution metadata, so keep
# them in a separate conversation-comment bucket.
gh api "repos/$OWNER/$REPO/issues/$PR/comments" --paginate \
  --jq "[.[] | select(.user.login != \"$ME\" and (.user.login | contains(\"[bot]\") | not)) | {id, body, user: .user.login}]"
```

**Pagination rule:** If the GraphQL response reports more review-thread pages or
more comments within a thread, keep paginating (or stop and tell the user the
thread data is incomplete).

Reply-target rules for `--all`:
- inline review comments → include:
  - comments in threads where `isResolved == false && isOutdated == false`
  - comments in resolved/outdated threads **when no reply from self exists after
    the latest non-self reviewer comment in that thread**
- general PR comments → include them as conversation comments; these do not
  have review-thread resolution metadata, so dedupe them only by existing self replies

### Mode C: No IDs, No `--all`

If no addressed IDs are available and `--all` was not passed, ask the user:

> "I don't have a list of addressed comments from a prior `/moe-skills:pr-review-fix` run.
> Would you like me to:
>
> 1. Reply to **all open inline review threads**, plus **resolved/outdated threads that still lack a reply from me**, plus general PR comments with this commit SHA
> 2. **Skip** replies (just commit and push)
> 3. **List** reviewer comments so you can pick which ones to reply to"

---

## Step 6: Pre-Audit for Duplicates and Stale Targets

Before posting any replies, check for existing replies from self to avoid
duplicates (per `references/reply-posting-hygiene.md`), and re-validate the
current thread state for each inline target.

```bash
# Check existing inline comment replies from self
gh api "repos/$OWNER/$REPO/pulls/$PR/comments" --paginate \
  --jq "[.[] | select(.user.login == \"$ME\") | {id, in_reply_to_id, body, created_at}]"

# Check existing issue-level comments from self
gh api "repos/$OWNER/$REPO/issues/$PR/comments" --paginate \
  --jq "[.[] | select(.user.login == \"$ME\") | {id, body, created_at}]"
```

If your reply-target source was conversation context rather than a fresh `--all`
thread fetch, re-run the Step 5 GraphQL query and confirm every inline target
comment ID still exists in the fetched thread graph.

Eligibility rules after refresh:
- **Conversation-context targets**: eligible even if the thread is now resolved
  or outdated. That is expected when the fix landed.
- **`--all` targets in open threads**: eligible.
- **`--all` targets in resolved/outdated threads**: eligible only if there is no
  later self reply already covering that reviewer comment/thread.

If you cannot find the target comment ID in the refreshed thread graph, stop and
ask the user which comments should receive replies instead of guessing from stale
history.

For each comment we plan to reply to:

- If a reply from self already exists with the same SHA → **skip** (already
  replied)
- If a reply from self exists with a different SHA **after the latest reviewer
  comment on that same review thread** → **skip** (already acknowledged later)
- For a general PR comment, skip only when a later self-authored issue comment
  clearly acknowledges that same target comment (for example: it was selected
  from conversation context, manually chosen by the user, or otherwise tied to
  that specific reviewer comment) → **skip** (already acknowledged later)
- If the thread is resolved/outdated **but this comment was explicitly addressed
  in the current session** → **reply anyway**
- If the thread is resolved/outdated in `--all` mode and no later self reply
  exists → **reply** (catch-up acknowledgement)
- Resolved/outdated status alone is **not** a skip reason

---

## Step 7: Post Replies

### Reply format

All replies use the same format — short, factual, no AI signatures:

```
Addressed in [<SHORT_SHA>](https://github.com/$OWNER/$REPO/commit/<FULL_SHA>).
```

### For inline review comments

Reply as a thread response to the original comment:

```bash
gh api "repos/$OWNER/$REPO/pulls/$PR/comments/$COMMENT_ID/replies" \
  -f body="Addressed in [$SHORT_SHA](https://github.com/$OWNER/$REPO/commit/$FULL_SHA)."
```

### For general PR comments

Post a new issue comment referencing the original:

```bash
gh api "repos/$OWNER/$REPO/issues/$PR/comments" \
  -f body="Addressed in [$SHORT_SHA](https://github.com/$OWNER/$REPO/commit/$FULL_SHA)."
```

### Posting rules

- Post **one reply per comment** — do not batch multiple comments into one reply
- Do **not** retry blindly on failure — check state first
- If a reply fails with HTTP 422, log the error and continue to the next comment
- No AI signatures, no co-author tags, no emoji

---

## Step 8: Post-Audit for Duplicates

Run the local dedupe detector described in `references/reply-posting-hygiene.md`:

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

Auto-stage: none needed | staged <N> file(s)
Replies posted: <N>
  - Comment #<id> by <reviewer> → replied
  - Comment #<id> by <reviewer> → replied (resolved/outdated thread catch-up)
  - Comment #<id> by <reviewer> → skipped (already replied)

Dedupe audit: clean (no duplicates) | removed <N> duplicates
```

---

## Rules

- **No AI signatures** — no AI/vendor co-author tags, no bot tags, and no
  emoji signatures in commits or GitHub comments.
- **Follow `references/reply-posting-hygiene.md`** — dedupe audit before and
  after posting, one reply per comment, no blind retries.
- **Never post duplicate replies** — always check existing replies first.
- **Resolved/outdated threads are valid reply targets** when they were addressed
  by the current fix set or still lack a later self reply.
- **Auto-stage before failing** — if the worktree has intended changes and the
  index is empty, stage them instead of stopping with "nothing to commit".
- **Do not force-push** — if push fails, tell the user to rebase.
- **Skill invocation** — step 2 must use `/backend-atomic-commit:commit`, not
  manual commit logic. This keeps commit quality gates DRY.

---

## Example Prompts

> `/moe-skills:commit-and-reply`
>
> After running `/moe-skills:pr-review-fix`, commits staged changes, pushes, and replies
> to each addressed comment with the commit SHA.

> `/moe-skills:commit-and-reply --all`
>
> Commits, pushes, and replies to all open inline review-thread comments plus
> general PR comments on the PR (not just those addressed in the current session).
