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

Run the full CI-matching gate sequence — not just scoped checks. Reviewer
comments often touch code that interacts with files you didn't edit, and
scoped checks can miss formatting drift in the full branch diff.

```bash
# Run the exact CI gate — this catches what ruff format on single files misses
./.security/ruff_pr_diff.sh
```

If `ruff_pr_diff.sh` fails:
1. Apply formatting: `.bin/ruff format $(git diff --name-only origin/release...HEAD --diff-filter=ACMRT | grep '\.py$')`
2. Re-run until clean: `./.security/ruff_pr_diff.sh`

Then run remaining gates:

```bash
./.security/local_imports_pr_diff.sh
.bin/ty check $(git diff --name-only origin/release...HEAD --diff-filter=ACMRT | grep '\.py$')
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

## Step 5.5: Merge Drift Detection

After fixing reviewer comments, verify the branch hasn't accidentally
regressed files that should only move forward:

```bash
# Check version metadata — must move forward only
git diff origin/release...HEAD -- pyproject.toml uv.lock

# Check for unrelated file regression
git diff --stat origin/release...HEAD -- \
  $(git diff --name-only origin/release...HEAD | grep -v "$(git diff --name-only HEAD~1)")
```

If `pyproject.toml` or `uv.lock` show a version downgrade relative to
`origin/release`, this is `[BLOCKING]` — restore the release version
and refresh `uv.lock`:

```bash
git checkout origin/release -- pyproject.toml
uv lock
git add pyproject.toml uv.lock
```

Also check for **WhiteLabel asset drift**, **fixture regression**,
and **config constant regression** — any file outside the feature area
that now differs from release. `[BLOCKING]` per silent regression.

---

## Step 5.6: Admin Form / Readonly Interaction Check

If any fix touched admin `get_readonly_fields()`, `ModelForm.__init__()`,
or inline admin configuration, verify the admin save path is consistent:

```bash
# Find all InlineModelAdmin classes for the changed model
grep -rn "class.*Inline.*admin\.TabularInline\|class.*Inline.*admin\.StackedInline" \
  --include="*.py" <app>/admin/

# Find all ModelForm.__init__ definitions that reference the changed fields
grep -rn "def __init__" --include="*.py" <app>/admin/ | while read line; do
  grep -A 30 "$line" | grep -q "<field_name>" && echo "$line — references changed field"
done
```

Read the full admin, inline, and form classes. The contract:
- If `get_readonly_fields()` excludes a field for certain states, NO
  `InlineModelAdmin` nor `ModelForm.__init__()` should re-add it as
  required for those same states.
- A POST of a locked-state record must succeed without the readonly
  field in form data.

Flag any mismatch as `[BLOCKING]`.

---

## Step 5.7: Historical Data / Config Reuse Check

When a fix prevents new bad data but existing rows may still have stale
or broken values, check:

```bash
# Are there existing rows with the affected pattern?
# Example: legacy sentinel overrides, old enum values, NULL arrays
grep -rn "<affected-field>\|<old-pattern>" --include="*.py" \
  | grep -v "tests/" | grep -v "migrations/" | head -20
```

Ask explicitly:
> "This fix prevents NEW bad data. Does existing data need cleanup?
> - Legacy configs can still carry old values through export/import.
> - Stale rows in the DB can still trigger the old behavior on reprocess."

If historical config reuse or legacy DB rows can reintroduce the bug,
flag as `[BLOCKING]` and suggest either:
- A data migration / backfill, or
- Runtime sanitization on the read path, or
- Import-time cleanup in config import.

---

## Step 5.8: Consumer Propagation Check (Lifecycle Parity)

If any fix introduced or modified a normalization, remapping, equivalence,
or canonicalization helper, verify it's applied at EVERY lifecycle stage:

| Stage | Check |
|-------|-------|
| Save / `pre_save` signal | Field canonicalized before persistence |
| Generate / build | Generation routines emit canonical form |
| Import (CSV / config) | Imported values canonicalized on entry |
| Export (CSV / config) | Exported values match canonical form |
| Apply / migrate | One-shot apply scripts canonicalize |
| Revert / rollback | Revert routines compare against canonical form |
| Consolidate / dedupe | Equivalence collisions detect canonical match |
| Admin `TextChoices` enum | The choice surface admits the canonical value |

```bash
# Grep for the helper name across the entire codebase
grep -rn "<helper_name>" --include="*.py" | grep -v tests/
```

For each stage where the helper is NOT applied, either:
- Apply the helper at that stage, or
- Document why the stage is explicitly exempt.

Flag each missed stage as `[BLOCKING]`.

Also grep for the OLD inline pattern that the helper replaces:

```bash
grep -rn "<old_inline_pattern>" --include="*.py" | grep -v tests/
```

Every consumer of the old pattern must call the new helper or be listed
as explicitly exempt.

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
- **Track addressed comment IDs** for `/commit-and-reply`.
- **Run ruff after every fix** — do not accumulate lint errors.
- **Do not modify files** not referenced by reviewer comments.

---

## Example Prompts

> `/pr-review-fix` — detect PR from branch, walk through comments interactively.

> `/pr-review-fix 2750` — fetch comments for PR #2750.

> `/pr-review-fix --auto` — auto-fix all comments on current branch's PR.
