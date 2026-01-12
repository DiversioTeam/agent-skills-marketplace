# PR Description Writer — GitHub Context Gathering (gh CLI)

This file is referenced from `SKILL.md` and contains the command-heavy workflow for:
- detecting an existing PR,
- determining the base branch,
- gathering the full set of changes (committed + uncommitted),
- and updating/creating the PR via `gh`.

## Workflow: Gathering Context

Before writing the PR description, **always gather the complete picture** of
all changes that will be included in the PR. This means:

1. Local uncommitted changes (staged + unstaged)
2. Local commits not yet pushed
3. Commits already pushed to the remote branch
4. Existing PR details (if a PR already exists)

### Step 1: Detect If Current Branch Has a PR

Use `gh pr view` to check if the current branch already has an associated PR:

```bash
# Check if current branch has a PR (returns 0 if PR exists, non-zero otherwise)
gh pr view --json number,title,body,url 2>/dev/null

# If you just need to know if a PR exists (boolean check):
gh pr view --json number 2>/dev/null && echo "PR exists" || echo "No PR yet"
```

**Interpretation:**
- Exit code `0` + JSON output → PR exists, use the PR number for updates
- Exit code non-zero → No PR yet, description will be for a new PR

### Step 2: Identify the Base Branch

Determine what branch the PR targets (or will target). Use this detection order:

```bash
# 1. If PR exists, get base from the PR (most reliable)
gh pr view --json baseRefName --jq '.baseRefName' 2>/dev/null

# 2. Get the repo's default branch via GitHub API
gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'

# 3. Fallback: check git remote HEAD
git remote show origin 2>/dev/null | grep "HEAD branch" | cut -d: -f2 | xargs

# 4. Last resort: check which common branches exist
git branch -r | grep -E "origin/(main|master|release|develop)$" | head -1 | sed 's|origin/||'
```

**Detection Priority:**
1. **Existing PR base** – If PR exists, always use its base branch
2. **GitHub default** – `gh repo view --json defaultBranchRef` is authoritative
3. **Git remote HEAD** – Works offline, reflects GitHub's default
4. **Common branch names** – Check for main/master/release/develop

**Smart Detection Script:**

```bash
detect_base_branch() {
  # Try existing PR first
  local pr_base=$(gh pr view --json baseRefName --jq '.baseRefName' 2>/dev/null)
  if [[ -n "$pr_base" ]]; then
    echo "$pr_base"
    return
  fi

  # Try GitHub API for default branch
  local gh_default=$(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name' 2>/dev/null)
  if [[ -n "$gh_default" ]]; then
    echo "$gh_default"
    return
  fi

  # Try git remote HEAD
  local remote_head=$(git remote show origin 2>/dev/null | grep "HEAD branch" | cut -d: -f2 | xargs)
  if [[ -n "$remote_head" ]]; then
    echo "$remote_head"
    return
  fi

  # Fallback to checking common branches
  for branch in main master release develop; do
    if git rev-parse --verify "origin/$branch" &>/dev/null; then
      echo "$branch"
      return
    fi
  done

  echo "main"  # Ultimate fallback
}

BASE_BRANCH=$(detect_base_branch)
echo "Using base branch: $BASE_BRANCH"
```

### Step 3: Gather ALL Changes

**CRITICAL**: The PR description must account for ALL changes, not just the
latest commit. This includes:

```bash
# 1. Detect the base branch and form a remote base ref
# If you didn't define detect_base_branch above, set BASE manually (e.g. origin/main).
BASE_BRANCH_NAME=$(detect_base_branch)
BASE="origin/${BASE_BRANCH_NAME}"
echo "Using base ref: $BASE"

# 2. View ALL commits that will be in the PR
git log ${BASE}..HEAD --oneline

# 3. View the FULL diff of all changes (committed + uncommitted)
#    This shows what reviewers will see in the PR
git diff ${BASE}...HEAD --stat          # Files changed (committed only)
git diff ${BASE} --stat                 # Files changed (including uncommitted)

# 4. Check for uncommitted changes that should be included
git status --short

# 5. If there are uncommitted changes, include them in the diff
git diff --stat                                # Unstaged changes
git diff --cached --stat                       # Staged changes
```

### Step 4: Get Existing PR Details (If Updating)

When updating an existing PR, fetch current details to preserve/enhance:

```bash
# Get full PR details as JSON
gh pr view --json number,title,body,url,commits,files

# Get just the current body for reference
gh pr view --json body --jq '.body'

# Get list of files changed in the PR
gh pr view --json files --jq '.files[].path'

# Get commit history in the PR
gh pr view --json commits --jq '.commits[].messageHeadline'
```

### Step 5: Analyze Changes Comprehensively

```bash
# View the actual diff to understand what changed
git diff ${BASE_BRANCH}...HEAD

# For a specific file
git diff ${BASE_BRANCH}...HEAD -- path/to/file.py

# See commit messages for context on why changes were made
git log ${BASE_BRANCH}..HEAD --format="%h %s%n%b" | head -100
```

---

## Updating a PR with `gh` CLI

Once the description is generated, use `gh pr edit` to update:

```bash
# Update PR title and body
gh pr edit <number> --title "New Title" --body "$(cat <<'EOF'
## Summary
...full markdown body here...
EOF
)"

# Or update just the body
gh pr edit --body "$(cat <<'EOF'
...full markdown body here...
EOF
)"

# Update PR for current branch (no number needed if on the branch)
gh pr edit --body "..."
```

**Creating a new PR:**

```bash
gh pr create --title "Title" --body "$(cat <<'EOF'
## Summary
...
EOF
)" --base release
```

---

## Quick Reference: `gh` CLI Commands

### PR Detection & Info

```bash
# Check if current branch has a PR
gh pr view --json number 2>/dev/null && echo "Has PR" || echo "No PR"

# Get PR number for current branch
gh pr view --json number --jq '.number'

# Get full PR details
gh pr view --json number,title,body,baseRefName,headRefName,url,state,files,commits

# Get PR URL
gh pr view --json url --jq '.url'
```

### PR Creation & Updates

```bash
# Create new PR
gh pr create --title "Title" --body "Body" --base release

# Update existing PR (current branch)
gh pr edit --title "New Title" --body "New Body"

# Update specific PR by number
gh pr edit 1234 --title "New Title" --body "New Body"

# Add reviewers
gh pr edit --add-reviewer username1,username2

# Add labels
gh pr edit --add-label "enhancement,needs-review"
```

### Viewing Changes

```bash
# View PR diff
gh pr diff

# View PR diff for specific PR
gh pr diff 1234

# View PR files
gh pr view --json files --jq '.files[].path'

# View PR commits
gh pr view --json commits --jq '.commits[] | "\(.oid[0:7]) \(.messageHeadline)"'
```
