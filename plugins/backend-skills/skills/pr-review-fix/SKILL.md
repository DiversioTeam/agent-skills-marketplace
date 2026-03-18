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
quality gates, and stage changes. Does **not** commit — use `/commit-and-reply`
after.

---

## Step 1: Identify PR

```bash
OWNER="DiversioTeam"
REPO="Django4Lyfe"
ME="$(gh api user --jq '.login')"
```

If a PR number is provided as argument, use it. Otherwise detect from branch:

```bash
gh pr view --json number,title,url,headRefName
```

If no PR found, stop and tell the user.

---

## Step 2: Fetch All Comments

Run all three in parallel:

```bash
# Review submissions (exclude self)
gh api "repos/$OWNER/$REPO/pulls/$PR/reviews" --paginate

# Inline review comments (exclude self)
gh api "repos/$OWNER/$REPO/pulls/$PR/comments" --paginate

# General PR comments (exclude self)
gh api "repos/$OWNER/$REPO/issues/$PR/comments" --paginate
```

Filter out:

- Your own comments (`user.login == $ME`)
- Bot comments (GitHub Actions, CI bots)
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

3. **On Fix**: edit the code, then run ruff on that file immediately:

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

## Step 4: Final Quality Gates

After all comments are processed, run `ty` on all modified Python files:

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

## Step 5: Summary

```text
PR Review Fix Summary
=====================
PR: #<number> — <title>

Comments: <addressed> fixed, <skipped> skipped, <total> total
Files modified:
  - path/to/file1.py
  - path/to/file2.py

Quality gates: all passed
Next step: /commit-and-reply
```

Track addressed comment IDs in conversation context (both inline and general)
so `/commit-and-reply` knows which comments to reply to.

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
