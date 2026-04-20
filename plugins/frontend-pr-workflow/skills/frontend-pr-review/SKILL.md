---
name: frontend-pr-review
description: "Interactive PR quality review for React/TypeScript frontends. Checks template compliance, code quality, design system standards, commit hygiene, and runs quality gates with structured verdict output."
---

# Frontend PR Review Skill

Interactive review of a pull request against frontend code quality standards.

---

## Input

The user provides: `$ARGUMENTS` (PR number, e.g., `309`)

If no argument is provided, ask for the PR number.

---

## Step 1: Load PR Context

```bash
# Get PR metadata
gh pr view $PR_NUMBER --json title,body,headRefName,baseRefName,commits,files

# Get the full diff
gh pr diff $PR_NUMBER
```

Extract:

- PR title and description
- Branch name (check naming convention: `feature/<slug>` or `feature/<issue-number>-<slug>`)
- Target branch (should be `dev` for feature PRs, `main` for release PRs)
- List of changed files
- Number of commits

---

## Step 2: Template Compliance Check

**For feature PRs (branch -> dev):**

Verify ALL required sections are present in the PR body:

- [ ] GitHub issue linkage when the work is tracked: `Closes #1234` or `Refs Org/repo#1234`
- [ ] "What has changed?" section with bullet points
- [ ] "Why has it changed?" section with explanation
- [ ] "Which components will this change affect?" section
- [ ] Browser testing checklist (Chrome, Firefox, Safari, Edge)
- [ ] No placeholder/generic text

**For release PRs (dev -> main):**

- [ ] Title format: `Release [Month] [Day with ordinal] [Year]`
- [ ] Body contains only bulleted PR links
- [ ] All listed PRs are merged into dev

---

## Step 3: Code Quality Scan

Review the diff for project conventions:

**File structure:**

- `.styles.ts` files use `styled-components` with design token imports
- `.types.ts` files contain interfaces (prefixed with `I`)
- `index.tsx` uses function declarations (no `React.FC`)

**Styling compliance:**

- Design system tokens preferred
- Hex fallback acceptable if no matching token exists
- No Tailwind classes
- No `className` mixing with styled-components
- Transient props (`$`) on all styled-component custom props

**Import order:**

1. React -> 2. External libs -> 3. Design System -> 4. Internal components -> 5. Hooks -> 6. Utils -> 7. Types -> 8. Styles

---

## Step 4: Commit Quality

```bash
gh pr view $PR_NUMBER --json commits --jq '.commits[].messageHeadline'
```

Check:

- [ ] Conventional commit format: `type(scope): description`
- [ ] Atomic - each commit is one logical change
- [ ] No AI co-author signatures (auto-reject if found)
- [ ] No WIP or fixup commits in final PR
- [ ] Subject lines under 72 characters

---

## Step 5: Run Quality Gates

```bash
# Checkout the PR branch
gh pr checkout $PR_NUMBER

# Run quality checks
yarn lint
yarn type-check
```

- 0 errors, 0 warnings required from both commands
- Check for any `eslint-disable` comments added in the diff

---

## Step 6: Output Review Report

```markdown
# PR Review: #$PR_NUMBER

## Template Compliance

- [x/fail] Items checked...

## Code Quality

- [x/fail] Items checked...

## Commit Quality

- [x/fail] Items checked...

## Quality Gates

- Lint: pass/fail (X errors, Y warnings)
- Type-check: pass/fail (X errors)

## Issues Found

1. **[Critical/Warning]** Description - file:line

## Verdict

- [ ] APPROVED - Ready to merge
- [ ] REQUEST CHANGES - Must address issues listed above
- [ ] COMMENT - Minor suggestions, can merge after discussion
```

---

## Quick Checks Reference

```bash
# Check for AI co-author in PR commits
gh pr view $PR_NUMBER --json commits --jq '.commits[].messageBody' | grep -i "co-authored"

# Check for eslint-disable in diff
gh pr diff $PR_NUMBER | grep "eslint-disable"

# Check for console.log in diff
gh pr diff $PR_NUMBER | grep "console\.log"

# Check for React.FC in diff
gh pr diff $PR_NUMBER | grep "React\.FC"
```
