# Frontend Triage Matrix Reference

Use this matrix to classify each open Dependabot PR for the frontend base
branch (repo default unless overridden).

## Classification Rules

| Class | Definition | Typical Evidence | Action |
|---|---|---|---|
| `actionable` | PR applies to current base and still relevant | `git apply --check` passes; target package/version still needed | Wait checks, approve, merge in priority order |
| `obsolete` | PR target already satisfied or no longer applicable | requested target already in lockfile; branch change irrelevant | Close with explicit rationale comment |
| `stale-but-recreate` | Still relevant but stale/conflicting branch | merge conflict/dirty state; lockfile topology shifted | Comment `@dependabot recreate`, re-evaluate |

## Suggested Triage Commands

```bash
REPO="${REPO:-$(gh repo view --json nameWithOwner --jq '.nameWithOwner')}"
BASE_BRANCH="${BASE_BRANCH:-$(gh repo view "$REPO" --json defaultBranchRef --jq '.defaultBranchRef.name')}"

# Config presence
gh api "repos/$REPO/contents/.github/dependabot.yml" >/dev/null 2>&1 \
  && echo "dependabot.yml present" \
  || echo "dependabot.yml missing"

# Open Dependabot PRs
gh pr list --repo "$REPO" --state open --author "app/dependabot" --base "$BASE_BRANCH" \
  --json number,title,url,updatedAt

# PR-level details
gh pr view <PR> --repo "$REPO" --json mergeable,mergeStateStatus,reviewDecision,changedFiles

gh pr checks <PR> --repo "$REPO"

gh pr diff <PR> --repo "$REPO" --name-only

gh pr diff <PR> --repo "$REPO" > /tmp/pr-<PR>.patch
git apply --check /tmp/pr-<PR>.patch
```

## Matrix Template

| PR | Package | Severity | Class | Evidence | Next Action |
|---|---|---|---|---|---|
| #0000 | pkg | high/med/low/none | actionable/obsolete/stale-but-recreate | 1-line reason | close/recreate/merge |

## Close Comment Template

```text
Closing as obsolete after dependency graph changes on the current frontend base branch.
Reason: <specific reason tied to lockfile/descriptor/target version>.
If needed, we will rely on a fresh Dependabot PR against current base.
```
