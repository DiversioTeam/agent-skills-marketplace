---
name: frontend-pr-workflow
description: "Create pull requests for React/TypeScript frontends. Handles feature PRs (branch to dev) and release PRs (dev to main) with template compliance, quality gates, and branch naming conventions."
---

# Frontend PR Workflow Skill

Handles creating both Feature PRs and Release PRs with strict template compliance.

## When to Use This Skill

- When creating a feature PR (branch → dev) or release PR (dev → main).
- `/frontend-pr-workflow:create-pr` — full PR creation with quality gates and template compliance.

## Example Prompts

- "Create a feature PR for this branch"
- "Create a release PR from dev to main"
- "/create-pr feature"

---

## Step 1: Determine PR Type

If the argument is `feature` or `release`, skip the prompt. Otherwise:

**Ask the user:**

> "Is this a **Feature PR** (branch -> dev) or a **Release PR** (dev -> main)?"

---

## Feature PR Workflow

### Step 2F: Code Quality Gates

Run these checks. ALL must pass with 0 errors AND 0 warnings. No exceptions.

```bash
yarn lint            # ESLint - zero warnings, zero errors
yarn type-check      # TypeScript - zero errors
```

**Manual verification (grep the codebase):**

- No new `eslint-disable` comments added in this branch's changes
- No `console.log` statements left in code

**Git verification:**

- No AI co-author signatures in any commit: `git log --format="%b" origin/dev..HEAD | grep -i "co-authored"`
- Each commit is atomic (one logical change per commit)
- Branch follows the repo convention: `feature/<slug>` or `feature/<issue-number>-<slug>`

If ANY check fails, fix the issue BEFORE creating the PR. Do NOT proceed with failures.

### Step 3F: Gather PR Information

**Ask the user (or extract from branch name):**

1. Linked GitHub issue or planning issue reference, if any (e.g., `#4757` or `Org/repo#4757`)
2. Brief summary of the change (1 line)
3. Sandbox preview URL (if available)
4. Backend branch (default: `release`). Ask: "Does this PR require a specific backend branch?"

**Auto-detect from git:**

- What changed: `git diff --stat origin/dev..HEAD`
- Which files: `git diff --name-only origin/dev..HEAD`
- Commit history: `git log --oneline origin/dev..HEAD`

### Step 4F: Create the Feature PR

Push the branch and create the PR against `dev`:

```bash
git push -u origin HEAD
```

Create PR with `gh pr create` using this template:

```markdown
## Related issues

- Closes #XXXX
- Refs Org/repo#XXXX

Sandbox Preview Link: [Sandbox URL or "Pending sandbox creation"]
Backend-Branch: release

## What has changed?

- [List each logical change as a bullet point]
- [Be specific: "Added X component", "Updated Y hook", "Fixed Z bug"]

## Why has it changed?

- [Explain the business reason or technical necessity]

## Which components will this change affect?

- [List affected components, modules, or services]
- [Include file paths where helpful]

I tested it and it works in:

- [x] Chrome
- [x] Firefox
- [x] Safari
- [ ] Edge
```

**CRITICAL:**

- Title format: concise summary (short, under 70 chars)
- Base branch: `dev` (always for feature PRs)
- Do NOT close and recreate PRs - get it right the first time
- `Backend-Branch:` defaults to `release`. Change it when the PR depends on backend changes.

---

## Release PR Workflow

### Step 2R: Verify Dev Branch State

```bash
git checkout dev
git pull origin dev
git fetch origin main
```

Verify dev is up to date with remote.

### Step 3R: Find Unreleased PRs

Get all merged PRs in dev that aren't in main:

```bash
git log main..dev --grep="Merge pull request" --oneline
```

Extract PR numbers and build the link list.

### Step 4R: Create the Release PR

Create the PR from `dev` to `main` with `gh pr create`:

**Title format (EXACT):**

```
Release [Month] [Day with ordinal suffix] [Year]
```

Examples: `Release February 10th 2026`, `Release December 1st 2025`

Ordinal suffixes: 1st, 2nd, 3rd, 4th-20th, 21st, 22nd, 23rd, 24th-30th, 31st

**Body format (EXACT):**

```markdown
- https://github.com/ORG/REPO/pull/296
- https://github.com/ORG/REPO/pull/308
```

**Rules:**

- Body MUST be a bulleted list using dashes (-)
- Each line starts with `- ` followed by the PR link
- NO additional text, sections, or explanations
- Base branch: `main`
- Head branch: `dev`

---

## Rules That Apply to ALL PRs

1. **NEVER include AI co-author signatures** in any commit. This is an auto-reject rule.
2. **0 errors, 0 warnings** from lint and type-check.
3. **No `eslint-disable`** comments added in the diff.
4. **Atomic commits** - each commit is one logical unit of change.
5. **Do NOT close and recreate PRs** - get the format right the first time.
6. **Follow pre-commit hooks** - do not bypass with `--no-verify`.
