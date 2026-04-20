---
name: frontend-atomic-commit
description: "Create atomic commits for React/TypeScript frontends with strict quality enforcement: one logical change per commit, 0 lint errors/warnings, 0 type-check errors, no eslint-disable, no AI co-author signatures."
---

# Frontend Atomic Commit Skill

Create atomic, quality-enforced commits for React/TypeScript frontend projects.

## When to Use This Skill

- Before committing frontend changes — ensures lint, type-check, and commit hygiene.
- `/frontend-atomic-commit:pre-commit` — run lint + type-check quality gates without committing.
- `/frontend-atomic-commit:atomic-commit` — validate staged changes are one logical unit and create a clean commit.

## Example Prompts

- "Run pre-commit checks on my staged files"
- "Create an atomic commit for the login page refactor"
- "Check if my changes are ready to commit"

---

## Core Principles

1. **One logical change per commit** - A commit should do ONE thing (add a component, fix a bug, update styles, etc.)
2. **0 errors, 0 warnings** - Every commit must pass lint and type-check cleanly
3. **No eslint-disable** - Never add `eslint-disable` comments to suppress warnings
4. **No AI co-author** - NEVER include `Co-Authored-By: Claude` or any AI signature
5. **No --no-verify** - Never bypass pre-commit hooks

---

## Step 1: Analyze Staged Changes

Check the current state of the working tree:

```bash
git status
git diff --cached --stat        # What's staged
git diff --cached --name-only   # Staged file list
git diff --stat                 # What's unstaged
```

**If nothing is staged**, help the user identify logical groups of changes to stage.

**Partial staging:** When a single file contains changes for multiple concerns, use `git add -p` to stage only the relevant hunks for each commit.

**If too many unrelated changes are staged**, advise the user to split into multiple atomic commits:

> "These changes touch [X feature] and [Y feature]. I recommend splitting into separate commits:
>
> 1. First commit: [description of logical group 1]
> 2. Second commit: [description of logical group 2]"

---

## Step 2: Validate Atomicity

Review the staged changes and verify they represent ONE logical change:

**Good atomic commits:**

- `feat(comments): add LoadMore button with counter-clock icon`
- `fix(auth): handle 403 error on token refresh`
- `refactor(upload): extract file validation into helper`
- `style(dashboard): update card spacing to use design tokens`

**Bad non-atomic commits:**

- Mixing a bug fix with an unrelated style change
- Adding a new component AND refactoring an existing one
- Updating types AND changing business logic in unrelated areas

**Ask the user if the staged changes aren't atomic:**

> "The staged changes include [X] and [Y] which are separate concerns. Would you like to:
>
> 1. Split into separate commits (recommended)
> 2. Proceed as a single commit"

---

## Step 3: Run Quality Gates

ALL checks must pass with **0 errors AND 0 warnings**. No exceptions.

```bash
yarn lint        # or: npm run lint
yarn type-check  # or: npx tsc --noEmit
```

**Additional verification on staged files:**

```bash
# Check for eslint-disable in staged changes
git diff --cached | grep -n "eslint-disable"

# Check for console.log in staged changes
git diff --cached | grep -n "console\.log"
```

**If lint or type-check fails:**

1. Show the errors to the user
2. Suggest specific fixes
3. After fixes, re-run the checks
4. Do NOT proceed until all checks pass

**If eslint-disable is found in staged changes:**

> "Found `eslint-disable` comment in staged changes. This is not allowed. Please fix the underlying issue instead of suppressing the warning."

---

## Step 4: Verify No Forbidden Patterns

```bash
# Verify no AI co-author in recent commits
git log --format="%b" -5 | grep -i "co-authored"
```

**If found in previous commits**, warn the user to amend those commits before continuing.

---

## Step 5: Craft Commit Message

If the user provided a message via argument, validate it. Otherwise, suggest one based on the staged changes.

### Commit Message Format

```
type(scope): concise description

Optional body explaining WHY, not WHAT.
```

### Types

| Type       | When to Use                                |
| ---------- | ------------------------------------------ |
| `feat`     | New feature or functionality               |
| `fix`      | Bug fix                                    |
| `refactor` | Code restructuring without behavior change |
| `style`    | Visual/CSS changes only                    |
| `chore`    | Build, config, tooling changes             |
| `docs`     | Documentation only                         |
| `test`     | Adding or updating tests                   |
| `perf`     | Performance improvement                    |

### Scope

Use the feature area or component name:

- `auth`, `comments`, `upload`, `dashboard`, `feedback`
- Component name: `FieldMapping`, `CommentTimeline`, `LoginForm`

### Rules

- **No AI co-author** - NEVER add `Co-Authored-By: Claude` or similar
- Keep the subject line under 72 characters
- Use imperative mood: "add" not "added", "fix" not "fixes"
- Don't end the subject with a period
- Separate subject from body with a blank line (if body is needed)

**Ask the user to confirm the message before committing.**

---

## Step 6: Create the Commit

```bash
git commit -m "$(cat <<'EOF'
type(scope): concise description
EOF
)"
```

**CRITICAL: Triple-check the commit message does NOT contain `Co-Authored-By: Claude` or any variation.**

After the commit, verify:

```bash
git log -1 --format="%s%n%n%b"   # Show the commit
git status                        # Verify clean state
```

---

## Step 7: Post-Commit Report

Report to the user:

```
Commit created successfully:
- Hash: [short hash]
- Message: [commit message]
- Files: [number] files changed
- Lint: 0 errors, 0 warnings
- Type-check: 0 errors
- eslint-disable: none added
- Co-author: none (clean)
```

---

## Multi-Commit Workflow

When the user has multiple logical changes, guide them through committing each one separately:

1. Identify all logical groups of changes
2. Present the plan: "I see N logical changes to commit..."
3. For each group: stage relevant files, run quality gates, create the commit
4. After all commits, show the full log:

```bash
git log --oneline -N   # Where N is the number of commits created
```

---

## Rules Summary

| Rule                      | Enforcement         |
| ------------------------- | ------------------- |
| 0 lint errors             | lint command         |
| 0 lint warnings           | lint command         |
| 0 type-check errors       | type-check command   |
| No eslint-disable added   | grep staged diff     |
| No AI co-author           | grep commit log      |
| No --no-verify            | never bypass hooks   |
| One logical change        | review staged files  |
| Imperative mood message   | validate message     |
| Subject under 72 chars    | validate length      |
