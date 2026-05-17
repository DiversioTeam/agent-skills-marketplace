---
name: pr-status
description: >
    Check the status of your GitHub PRs. Shows review state, CI checks, merge
    status, and highlights PRs needing attention. Supports filtering by repo,
    count, or specific PR numbers.
user-invocable: true
argument-hint: '[pr-numbers...] [--repo OWNER/REPO] [--merged] [--all] [--refresh]'
allowed-tools: [Bash, Read]
---

# PR Status Skill

Quick dashboard for your GitHub PRs. Shows what needs attention, what's
approved, what has changes requested, and what merged recently.

## Freshness Guarantee

**The #1 bug in this skill is stale data.** `gh pr list` returns cached
results that can be minutes to hours old. This skill MUST use the freshest
available data path for each field:

| Field | Freshness path | Reason |
|-------|---------------|--------|
| Review decision | `gh pr view --json reviewDecision` | Per-PR fetch, not list cache |
| CI status | `gh pr checks` | Real-time check run API |
| Mergeable | `gh pr view --json mergeable,mergeStateStatus` | Requires real-time computation |
| Review threads | GraphQL query | `gh pr list` reviewDecision is aggregate only |
| Comment count | GraphQL unresolved threads | More accurate than list rollup |

**Always prefer `gh pr view` over `gh pr list` for detail fields.**
`gh pr list` is acceptable for discovery (finding which PRs exist) but
not for the status data displayed to the user.

---

## Step 1: Determine Scope

Parse arguments to decide what to fetch:

- **No arguments**: all open PRs where you are author, assignee, or requested reviewer
- **PR numbers** (e.g. `123 456`): fetch those specific PRs
- **`--repo OWNER/REPO`**: target a different repo (default: detect from `gh repo view`)
- **`--merged`**: include PRs you were involved in that merged in the last 48 hours
- **`--all`**: all open PRs across all your repos
- **`--refresh`**: force-refresh all data — skip `gh pr list` cache, use `gh pr view` for every PR

**When `--refresh` is passed**: do NOT use `gh pr list` at all. Fetch PR numbers
directly via the search API, then enrich each one with `gh pr view`.

```bash
ME="$(gh api user --jq '.login')"
```

### Default (current repo, open PRs involving you)

**Discovery step** — use `gh pr list` only for discovery (finding which PRs
exist). Do NOT use its `reviewDecision`, `statusCheckRollup`, or other
detail fields.

```bash
# PRs you authored — numbers only for discovery
gh pr list --author "$ME" --state open --json number,title,url,headRefName,isDraft,createdAt,updatedAt

# PRs assigned to you
gh pr list --assignee "$ME" --state open --json number,title,url,headRefName,isDraft,createdAt,updatedAt

# PRs where you are a requested reviewer
gh pr list --search "review-requested:$ME state:open" --json number,title,url,headRefName,isDraft,createdAt,updatedAt
```

Merge all results, deduplicate by PR number. Tag each PR with your role:
- **Author** — you created it
- **Assignee** — you're assigned
- **Reviewer** — your review is requested

A PR can have multiple roles.

**Enrichment step** — for every discovered PR, fetch fresh detail via
`gh pr view`. This bypasses `gh pr list` caching:

```bash
# For each PR number discovered above, get FRESH detail:
gh pr view "$PR_NUMBER" --json number,title,url,headRefName,reviewDecision,isDraft,state,mergeable,mergeStateStatus,createdAt,updatedAt
```

### With --refresh

Skip `gh pr list` entirely. Use the search API to discover PR numbers,
then `gh pr view` for every PR:

```bash
# Discover via search (author, assignee, review-requested)
gh api "search/issues?q=type:pr+state:open+author:$ME+repo:$OWNER/$REPO" \
  --jq '.items[].number'
gh api "search/issues?q=type:pr+state:open+assignee:$ME+repo:$OWNER/$REPO" \
  --jq '.items[].number'
gh api "search/issues?q=type:pr+state:open+review-requested:$ME+repo:$OWNER/$REPO" \
  --jq '.items[].number'

# Enrich EACH one — no caching
for pr in $ALL_PR_NUMBERS; do
  gh pr view "$pr" --json number,title,url,headRefName,reviewDecision,statusCheckRollup,isDraft,state,mergeable,mergeStateStatus,createdAt,updatedAt
done
```

### Specific PRs

```bash
for pr in <numbers>; do
  gh pr view "$pr" --json number,title,url,headRefName,reviewDecision,statusCheckRollup,isDraft,state,mergedAt,createdAt,updatedAt,reviews,assignees
done
```

### With --merged

```bash
# PRs you authored that merged recently
gh pr list --author "$ME" --state merged --json number,title,url,mergedAt,headRefName

# PRs you reviewed that merged recently
gh pr list --search "reviewed-by:$ME state:closed is:merged" --json number,title,url,mergedAt,headRefName
```

Merge both lists, deduplicate, then filter to last 48 hours:

```bash
jq '[.[] | select(.mergedAt > "'"$(date -u -v-48H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '48 hours ago' +%Y-%m-%dT%H:%M:%SZ)"'")]'
```

### With --all

```bash
gh search prs --involves "$ME" --state open --json repository,number,title,url,updatedAt
```

Note: `gh search` returns limited fields. For each result, enrich with
`gh pr view` in the target repo to get review decision, CI status, and
draft state. Limit enrichment to the first 20 results to avoid rate limits.

---

## Step 2: Enrich with Review and Merge Details

**Use the `gh pr view` detail data from Step 1 enrichment.** Do not use
`gh pr list` reviewDecision — it's cached and can be stale.

### Staleness Detection

Before displaying any PR, check if the data is fresh:

```bash
# Check if updatedAt is older than the last known review activity
LAST_REVIEW=$(gh api "repos/$OWNER/$REPO/pulls/$PR/reviews" --paginate \
  --jq '[.[] | select(.user.login != "'"$ME"'")] | sort_by(.submitted_at) | last.submitted_at')

PR_UPDATED=$(gh pr view "$PR" --json updatedAt --jq '.updatedAt')
```

If `updatedAt` is older than the last review submission, or if the data
is more than 5 minutes old while the user reports it looks wrong, add
a warning:

> "⚠️ Data may be stale. Last updated: <timestamp>. Run with --refresh to force re-fetch."

### Per-Reviewer Breakdown

Only call the reviews API when you need **per-reviewer breakdown**
(e.g. which specific reviewer requested changes):

```bash
gh api "repos/$OWNER/$REPO/pulls/$PR/reviews" --paginate \
  --jq '[.[] | {user: .user.login, state, submitted_at}] | group_by(.user) | map({user: .[0].user, state: last.state})'
```

Classify each reviewer's latest state:
- **APPROVED**
- **CHANGES_REQUESTED**
- **COMMENTED** (reviewed but no decision)
- **PENDING** (requested but hasn't reviewed)

### Merge Status (fresh)

```bash
gh pr view "$PR" --json mergeable,mergeStateStatus
```

- `MERGEABLE` — no conflicts
- `CONFLICTING` — has merge conflicts (status = Blocked)

### Unresolved Threads (GraphQL — freshest)

```bash
gh api graphql -f query='
  query($owner:String!, $repo:String!, $pr:Int!) {
    repository(owner:$owner, name:$repo) {
      pullRequest(number:$pr) {
        reviewThreads(first:100) {
          nodes { isResolved }
        }
      }
    }
  }' -f owner="$OWNER" -f repo="$REPO" -F pr="$PR" \
  --jq '[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false)] | length'
```

- Unresolved threads > 0 — show count in Reviews column (e.g. "Changes req. (3 unresolved)")

---

## Step 3: Check CI Status

For each open PR, get the CI check rollup:

```bash
gh pr checks <number> --json name,state,conclusion
```

Summarize as:
- **All passing**
- **N failing** (list names)
- **Pending** (still running)

---

## Step 4: Present Dashboard

Display a summary table, then details for PRs needing attention.

### Summary Table

```text
PR Status Dashboard (@username)
================================

 #   | Role     | Title                          | Reviews        | CI      | Age  | Status
-----|----------|--------------------------------|----------------|---------|------|--------
 939 | Author   | Widen maxScore type            | Changes req. (3)| Passing | 3d   | Needs work
 935 | Author   | Add inclusion descriptions     | 1/2 approved   | Failing | 5d   | Blocked
 941 | Reviewer | Fix survey reminder task       | Pending        | Passing | 1d   | Needs your review
 928 | Author   | Fix pulse survey export        | Approved       | Passing | 1d   | Ready to merge
 927 | Assignee | Update survey constants        | Pending        | Passing | 7d   | Needs review
```

### Status Categories (in this order)

1. **Needs work** — changes requested by at least one reviewer (you are author)
2. **Needs your review** — your review is requested and you haven't submitted one
3. **Blocked** — CI failing or merge conflicts (check `mergeable` field)
4. **Needs review** — no reviews yet, or only comments (no decision)
5. **Ready to merge** — approved + CI passing + no conflicts
6. **Draft** — still in draft state

### Recently Merged (if --merged)

```text
Recently Merged (last 48h)
===========================
 #   | Title                          | Merged         | Branch
-----|--------------------------------|----------------|--------
 930 | Fix tenant scoping in export   | 2h ago         | clickup_GH-4950_...
```

---

## Step 5: Highlight Action Items

After the table, list specific actions needed:

```text
Action Items
============
- PR #939: @ashwch requested changes 1d ago — 3 unresolved comments
- PR #941: Your review requested by @teammate — pending since 1d ago
- PR #935: CI check "pytest-parallel" failing since last push
- PR #927: No reviewers assigned — consider requesting review
- PR #928: Approved and green — ready to merge
```

---

## Rules

- **Read-only** — this skill never modifies PRs, code, or reviews.
- **Your PRs** — authored by, assigned to, or review requested from `$ME`.
- **Concise output** — summary table first, details only for PRs needing action.
- **Stale detection** — flag PRs with no activity for 7+ days as stale.
- **FRESH DATA MANDATORY** — Never display `reviewDecision` or CI status from
  `gh pr list`. Always enrich with `gh pr view` (per-PR, not cached).
  This is the #1 cause of "showing old status" bugs.
- **`--refresh`** uses search API for discovery and `gh pr view` for every PR.
  Use it when the user reports stale data.
- **Staleness warning** — if `updatedAt` suggests cached data, show a
  warning and suggest `--refresh`.

---

## Example Prompts

> `/pr-status` — dashboard of all your open PRs in the current repo.

> `/pr-status 939 935` — check status of specific PRs.

> `/pr-status --merged` — include recently merged PRs.

> `/pr-status --all` — all your open PRs across all repos.

> `/pr-status --repo DiversioTeam/Django4Lyfe` — PRs in a specific repo.
