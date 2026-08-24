---
name: pr-review-fix
description: >
    Fetch and address PR reviewer comments from GitHub. Reads reviewer feedback,
    presents each with code context, implements fixes, runs quality gates, and
    stages changes. Does NOT commit — use /moe-skills:commit-and-reply after.
user-invocable: true
argument-hint: '[pr-number] [--auto]'
allowed-tools: [Bash, Read, Edit]
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
gh pr view --json number,title,url,headRefName,baseRefName

# Derive the branch diff base from the PR target branch.
# Override by exporting BASE_BRANCH before invoking if needed.
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh pr view --json baseRefName --jq '.baseRefName' 2>/dev/null)"
fi
```

If no PR found, stop and tell the user.

---

## Step 2: Fetch Thread-Aware Review Feedback

Do **not** build the action queue from flat REST review-comment lists. They do
not expose `isResolved` or `isOutdated`, so they cannot safely distinguish open
review threads from stale history.

### Step 2a: Fetch review threads via GraphQL (thread-aware)

```bash
gh api graphql -f query='
  query($owner:String!, $repo:String!, $pr:Int!) {
    repository(owner:$owner, name:$repo) {
      pullRequest(number:$pr) {
        reviewThreads(first:100) {
          pageInfo { hasNextPage endCursor }
          nodes {
            id
            isResolved
            isOutdated
            path
            line
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
```

**Pagination rule:** If `reviewThreads.pageInfo.hasNextPage` is `true`, keep
paginating (or stop and tell the user the thread data is incomplete). If any
thread reports `comments.pageInfo.hasNextPage`, keep paginating that thread's
comments before proceeding.

Build two buckets from this response:
- **Actionable inline review threads**: `isResolved == false` and
  `isOutdated == false`
- **Context-only review threads**: resolved or outdated threads. Do not blindly
  reapply their old patch, but extract the root cause and search the current
  branch for a live sibling occurrence before declaring the pattern closed.

Filter out:
- your own comments
- bot comments (`[bot]`, `github-actions`, etc.)

### Step 2b: Fetch general PR comments separately

Issue-level PR comments do not have review-thread resolution state, so treat
them as conversation context rather than unresolved-review-thread evidence.

```bash
gh api "repos/$OWNER/$REPO/issues/$PR/comments" --paginate \
  --jq "[.[] | select(.user.login != \"$ME\" and (.user.login | contains(\"[bot]\") | not)) | {id, body, user: .user.login, created_at}]"
```

### Step 2c: Fetch review submissions for context

```bash
gh api "repos/$OWNER/$REPO/pulls/$PR/reviews" --paginate \
  --jq "[.[] | select(.user.login != \"$ME\") | {id, state, body, user: .user.login, submitted_at, commit_id}]"
```

Retain dismissed review submissions as history and label them `DISMISSED`; they
may still explain a recurring root, but they are not current approval/blocking
state. Preserve submitted timestamps and commit IDs so stale feedback is not
mistaken for current-head code.

### Step 2d: Build the action queue

Queue comments in this order:
1. comments from open, non-outdated review threads
2. actionable general PR comments
3. non-actionable questions / context-only items

When you summarize the fetch, separate the counts clearly:

```bash
echo "Open review threads: <N>; context-only threads: <M>; general comments: <K>"
```

Classify each actionable item by severity:

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

2. **Prompt the user in plain chat** — present a concise multiple-choice prompt:

```text
[SEVERITY] @reviewer on file.py:L120 — How should I handle this?
- Fix (Recommended): Implement the requested change
- Skip: Leave for now, move to next comment
- More context: Show more surrounding code, then ask again
- Reply only: Don't change code, draft a reply to the reviewer
```

If the fix is obvious, include a short proposed diff summary under the prompt.

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
   `/moe-skills:commit-and-reply` to post.

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
git diff --name-only origin/$BASE_BRANCH...HEAD -- '*/migrations/*.py' \
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

Ask the user in plain chat before squashing:

```text
Found N new migrations for <app>. Squash into one?
- Squash (Recommended): Delete branch migrations, regenerate a single one
- Skip: Leave multiple migrations as-is
```

---

## Step 5: Final Quality Gates

Run the full CI-matching gate sequence — not just scoped checks. Reviewer
comments often touch code that interacts with files you didn't edit, and
scoped checks can miss formatting drift in the full branch diff.

```bash
# Run the exact CI gate — this catches what ruff format on single files misses
./.security/ruff_pr_diff.sh
```

If `ruff_pr_diff.sh` fails:
1. Apply formatting: `.bin/ruff format $(git diff --name-only origin/$BASE_BRANCH...HEAD --diff-filter=ACMRT | grep '\.py$')`
2. Re-run until clean: `./.security/ruff_pr_diff.sh`

Then run remaining gates:

```bash
./.security/local_imports_pr_diff.sh
.bin/ty check $(git diff --name-only origin/$BASE_BRANCH...HEAD --diff-filter=ACMRT | grep '\.py$')
```

If any gate fails: fix, re-run until clean.

**Do NOT skip `ruff_pr_diff.sh`.** It runs `ruff format --check` on the
union of branch diff + local changes — this is the exact check CI runs,
and it's the #1 CI failure pattern. Running `ruff format` on a single
file is not sufficient.

Then stage:

```bash
git add <modified-files>
```

Do **not** stage unrelated changes. Do **not** commit.

---

## Step 5.5: Root-Cause and Sibling-Occurrence Closure

A reviewer points to evidence, not necessarily the only occurrence or the right
patch. Before marking an item fixed:

1. State the normalized root cause (for example: stable shape weakened with
   `Any`, speculative broad catch, missed existing enum, duplicated query,
   helper-only test, or lifecycle mismatch).
2. Search the **full branch diff and repository** for sibling occurrences,
   including the reviewer phrase's semantic equivalents.
3. Inspect the surrounding production contract and fix all branch-introduced
   occurrences with the same root where the correction is deterministic.
4. Cite each occurrence checked and explain exemptions. Do not count repeated
   replies in one thread as separate issues.

The fix may touch a file not named by the comment when required for a caller,
shared type/constant, lifecycle stage, or regression test. Keep that expansion
narrow and show it to the user. In `--auto`, apply only deterministic same-root
fixes; stop for product, architecture, migration, or behavior tradeoffs.

Route mechanics to one canonical owner instead of performing shallow copies:

| Trigger | Required check |
|---|---|
| New helper/field/admin/state/transaction or failure boundary | `/contract-propagation-check:check` |
| Existing rows, migration, config, rollback/reprocess | `/historical-data-check:check` |
| Added literals/enums/`Any`/resource wrappers/duplicate setup | `/moe-skills:codebase-reuse-finder` |
| Production behavior or test changes (including absent tests) | `/test-quality-check:check` |
| Long-lived branch, merge, migration number, unrelated files | `/merge-drift-check:check` |

Each invoked check must return search/call-chain evidence. Fix its blocking
sibling occurrences before staging, or record them as skipped with the user's
decision.

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

Quality gates: all passed (ruff_pr_diff ✅, local_imports ✅, ty ✅)
Merge drift: clean / <N issues found and fixed>
Admin form check: clean / <N issues flagged>
Historical data: no cleanup needed / <N issues flagged>
Lifecycle parity: all stages covered / <N stages missed>

Next step: /moe-skills:commit-and-reply
```

Track addressed comment IDs in conversation context (both inline and general)
so `/moe-skills:commit-and-reply` knows which comments to reply to.

---

## Step 7: Recommend Full-Branch Review

After fixing comments, check whether a full-branch review is warranted:

```bash
# How many files does this branch touch total?
git diff --name-only origin/$BASE_BRANCH...HEAD | wc -l
```

If **any** of these are true, recommend a full-branch review:

- Fixes touched shared helpers, utilities, or constants
- More than 3 files were modified across the branch
- Comments referenced contract changes, API changes, or migration issues
- The branch has been open for multiple review rounds
- Merge drift was detected and resolved
- Admin form/readonly interaction was flagged
- Historical data cleanup was flagged

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
- **Track addressed comment IDs** for `/moe-skills:commit-and-reply`.
- **Run ruff after every fix** — do not accumulate lint errors.
- **Follow the root, not only the anchor** — files outside the comment anchor may
  change only when required for the same branch-introduced root cause, consumer,
  shared abstraction/type, or regression test. Show and justify the expansion.

---

## Example Prompts

> `/moe-skills:pr-review-fix` — detect PR from branch, walk through comments interactively.

> `/moe-skills:pr-review-fix 2750` — fetch comments for PR #2750.

> `/moe-skills:pr-review-fix --auto` — auto-fix all comments on current branch's PR.
