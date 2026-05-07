---
name: pr-review-fix
description: >
    Fetch and address PR reviewer comments from GitHub. Reads reviewer feedback,
    presents each with code context, implements fixes, runs quality gates, and
    stages changes. Does NOT commit — use /commit-and-reply after.
user-invocable: true
argument-hint: '[pr-number] [--auto]'
allowed-tools: [Bash, Read, Edit, Glob, Grep, AskUserQuestion]
---

# PR Review Fix Skill

Fetch PR reviewer comments, present each interactively, implement fixes, run
quality gates, and stage changes. Does **not** commit — use `/moe-skills:commit-and-reply`
after.

---

## Step 1: Identify PR

```bash
ME="$(gh api user --jq '.login')"
REPO_INFO="$(gh repo view --json owner,name)"
OWNER="$(echo "$REPO_INFO" | jq -r '.owner.login')"
REPO="$(echo "$REPO_INFO" | jq -r '.name')"
```

If a PR number is provided as argument, use it. Otherwise detect from branch:

```bash
gh pr view --json number,title,url,headRefName
```

If no PR found, stop and tell the user.

---

## Step 2: Fetch All Comments

Fetch counts first, then fetch full comments. This prevents pagination
truncation — if the full fetch returns fewer than the count, you know
you missed some.

```bash
# Step 2a: Get counts to verify completeness
REVIEW_COUNT=$(gh api "repos/$OWNER/$REPO/pulls/$PR/comments" \
  --paginate --jq 'length' | paste -sd+ - | bc)
ISSUE_COUNT=$(gh api "repos/$OWNER/$REPO/issues/$PR/comments" \
  --paginate --jq 'length' | paste -sd+ - | bc)
echo "Expected: $REVIEW_COUNT inline + $ISSUE_COUNT general comments"
```

```bash
# Step 2b: Fetch full inline review comments (exclude self, pipe to jq)
gh api "repos/$OWNER/$REPO/pulls/$PR/comments" --paginate \
  --jq "[.[] | select(.user.login != \"$ME\") | {id, path, line, body, user: .user.login, created_at, in_reply_to_id}]"

# Step 2c: Fetch full general PR comments (exclude self)
gh api "repos/$OWNER/$REPO/issues/$PR/comments" --paginate \
  --jq "[.[] | select(.user.login != \"$ME\") | {id, body, user: .user.login, created_at}]"

# Step 2d: Fetch review submissions for context
gh api "repos/$OWNER/$REPO/pulls/$PR/reviews" --paginate \
  --jq "[.[] | select(.user.login != \"$ME\") | {id, state, body, user: .user.login}]"
```

**Verify completeness:** After fetching, count the results. If the fetched
count is less than the expected count from Step 2a (after accounting for
self-exclusion), re-fetch. Do NOT proceed with partial data.

```bash
echo "Fetched: <N> inline + <M> general (after filtering self/bots)"
```

Filter out:

- Your own comments (`user.login == $ME`) — already filtered in jq above
- Bot comments (GitHub Actions, CI bots) — filter `user.login` containing
  `[bot]` or known bot names like `github-actions`
- Reply chains you started

Classify each by severity:

| Tag | Criteria |
|-----|----------|
| `[BLOCKING]` | Correctness, security, data integrity, multi-tenant boundary |
| `[SHOULD_FIX]` | Performance, missing validation, confusing logic |
| `[NIT]` | Style, naming, minor readability |

Comments that are purely questions with no actionable fix get tagged as
non-actionable and presented last.

Sort: BLOCKING first, then SHOULD_FIX, then NIT, then non-actionable.

---

## Step 3: Interactive Loop

For each comment:

1. **Display context** — show the reviewer's comment, the diff hunk (for inline
   comments), and ~10 lines of current code around the referenced location.

2. **Prompt with `AskUserQuestion`** — use the interactive selection UI:

```yaml
question: "[SEVERITY] @reviewer on file.py:L120 — How should I handle this?"
header: "Action"
options:
  - label: "Fix (Recommended)"
    description: "Implement the requested change"
    preview: |
      <proposed diff when inferable from the comment>
  - label: "Skip"
    description: "Leave for now, move to next comment"
  - label: "More context"
    description: "Show more surrounding code, then ask again"
  - label: "Reply only"
    description: "Don't change code, draft a reply to the reviewer"
```

3. **On Fix** — draft the fix, then review it before applying:

   First, draft the proposed code change. Then re-read it once as if
   reviewing someone else's code:
   - Is this the simplest correct solution?
   - Does it match the patterns in surrounding code?
   - Could it break callers, tests, or other files?

   If the review finds a better approach, revise before applying. Then edit
   the file and run ruff:

```bash
.bin/ruff check --fix <file>
.bin/ruff format <file>
```

4. **On Skip**: record the comment ID as skipped, move on.

5. **On Reply only**: draft a reply message, record the comment ID for
   `/commit-and-reply` to post.

6. **Track progress** — after each comment, show a brief status line
   (e.g. `3/12 done — 2 fixed, 1 skipped`).

### `--auto` mode

When `--auto` is passed:

- Fix all actionable comments without prompting (skip non-actionable ones)
- Still display each comment and the fix applied
- Still run ruff after each fix

---

## Step 4: Migration Squash Check

After all comments are processed, check if the branch introduced multiple
migrations for the same app:

```bash
# Find new migration files on this branch vs release
git diff --name-only origin/release...HEAD -- '*/migrations/*.py' \
  | grep -v '__init__' \
  | awk -F'/migrations/' '{print $1}' \
  | sort | uniq -c | sort -rn
```

If any app has **more than one new migration**, squash them:

1. Identify the last migration **before** the branch's first new one.
2. Delete only the branch-specific migration files.
3. Run `.bin/django makemigrations` to regenerate a single migration.
4. Run `.bin/ruff check --fix` and `.bin/ruff format` on the new migration file.
5. Verify with `.bin/django migrate --check` (no pending changes).

Use `AskUserQuestion` to confirm before squashing:

```yaml
question: "Found N new migrations for <app>. Squash into one?"
header: "Migrations"
options:
  - label: "Squash (Recommended)"
    description: "Delete branch migrations, regenerate a single one"
  - label: "Skip"
    description: "Leave multiple migrations as-is"
```

---

## Step 5: Final Quality Gates

Run `ty` on all modified Python files:

```bash
.bin/ty check <modified-files>
```

If errors: fix, re-run until clean.

Then stage:

```bash
git add <modified-files>
```

Do **not** stage unrelated changes. Do **not** commit.

---

## Step 6: Summary

```text
PR Review Fix Summary
=====================
PR: #<number> — <title>

Comments: <addressed> fixed, <skipped> skipped, <total> total
Files modified:
  - path/to/file1.py
  - path/to/file2.py

Quality gates: all passed
Next step: /moe-skills:commit-and-reply
```

Track addressed comment IDs in conversation context (both inline and general)
so `/commit-and-reply` knows which comments to reply to.

---

## Step 7: Recommend Full-Branch Review

After fixing comments, check whether a full-branch review is warranted:

```bash
# How many files does this branch touch total?
git diff --name-only origin/release...HEAD | wc -l
```

If **any** of these are true, recommend a full-branch review:

- Fixes touched shared helpers, utilities, or constants
- More than 3 files were modified across the branch
- Comments referenced contract changes, API changes, or migration issues
- The branch has been open for multiple review rounds

Output:

> "Comments addressed and staged. This branch touches N files total.
> Consider running `/monty-v2-code-review:code-review` for a full-branch
> review before committing — comment-level fixes can miss systemic issues
> that only show up when reviewing the complete change set."

If the branch is a simple 1-2 file change with only NIT comments, skip
this recommendation.

---

## Rules

- **Do NOT commit.** Staging only.
- **Respect the Diversio/Optimo product boundary** — `optimo_*` must not import
  from `dashboardapp/`/`survey/`/`pulse_iq/`/`titan/` and vice versa. `utils/`
  is shared.
- **Track addressed comment IDs** for `/commit-and-reply`.
- **Run ruff after every fix** — do not accumulate lint errors.
- **Do not modify files** not referenced by reviewer comments.

---

## Example Prompts

> `/pr-review-fix` — detect PR from branch, walk through comments interactively.

> `/pr-review-fix 2750` — fetch comments for PR #2750.

> `/pr-review-fix --auto` — auto-fix all comments on current branch's PR.
