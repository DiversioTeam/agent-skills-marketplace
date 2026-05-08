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
run after `/moe-skills:pr-review-fix`.

**Dependency:** Requires `backend-atomic-commit@diversiotech` plugin to be
installed (`/backend-atomic-commit:commit` is invoked in Step 2).

**This skill is NOT done until the Step 9 summary is printed.** The commit
in Step 2 is only the first third of the workflow — push, replies, and
dedupe audit must all complete before this skill is finished.

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
ME="$(gh api user --jq '.login')"
REPO_INFO="$(gh repo view --json owner,name)"
OWNER="$(echo "$REPO_INFO" | jq -r '.owner.login')"
REPO="$(echo "$REPO_INFO" | jq -r '.name')"
PR=<detected-pr-number>
```

**If nothing is staged**, stop and tell the user:

> "No staged changes found. Run `/moe-skills:pr-review-fix` first to address reviewer
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

**CRITICAL: After the atomic-commit skill returns, you are NOT done.**
The commit exists only locally. You MUST continue with Steps 3–9 below
(pull, re-gate, push, get SHA, reply to comments, dedupe audit, summary).
Do not treat the atomic-commit completion as the end of this workflow.

---

## Step 3: Pull Latest from Release, Resolve Conflicts, Re-Gate, and Push

Pull latest from release:

```bash
git pull origin release --no-rebase
```

### If merge conflicts occur — resolve them by type

Check which files are conflicted:

```bash
git diff --name-only --diff-filter=U
```

Resolve each file according to its type:

#### Migration conflicts (most common)

Two branches added migrations with overlapping numbers for the same app.

1. Accept the **release** version of the conflicting migration (it's already
   deployed or ahead in the pipeline):
   ```bash
   git checkout --theirs <app>/migrations/<conflicting_file>.py
   ```
2. Delete the **branch's** migration file that conflicts.
3. Regenerate the branch's migration with the next available number:
   ```bash
   .bin/django makemigrations <app>
   ```
4. Run `.bin/ruff format` on the new migration file.
5. Verify: `.bin/django migrate --check` (no pending changes).
6. Stage the resolved files:
   ```bash
   git add <app>/migrations/
   ```

#### Lock files and generated files

Regenerate rather than manually merging:

```bash
# uv.lock
uv lock
git add uv.lock

# requirements.txt (if present)
git checkout --theirs requirements.txt
git add requirements.txt
```

#### Code conflicts — non-overlapping hunks

If git marked a conflict but both changes are in **different parts** of the
file (different functions, different sections), accept both changes. Read
both sides, verify they don't interact, then edit the file to include both.

#### Code conflicts — same function, additive changes

If both sides added different logic to the same function (e.g., release added
a new field and the branch added a new condition), merge both changes
manually. Read the full function, understand both intents, combine them.

#### STOP and ask the user for these conflicts

Do **not** auto-resolve:

- **Model field definition conflicts** — schema changes need human judgment
- **Security-related code** — auth, permissions, tenant scoping, PII gates
- **Business logic rewrites** — both sides rewrote the same logic differently
  with incompatible approaches
- **Test fixture conflicts** — wrong fixture alignment causes silent failures

For these, show the conflict diff and ask:

> "Conflict in `<file>` involves <security/schema/business logic>. This
> needs your judgment. Here's what each side did:
>
> - **Release**: <summary>
> - **Branch**: <summary>
>
> How should I resolve this?"

#### After all conflicts resolved

Complete the merge:

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

If any gate fails, fix the issue, stage, and amend the merge commit:

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

> "I don't have a list of addressed comments from a prior `/moe-skills:pr-review-fix` run.
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
