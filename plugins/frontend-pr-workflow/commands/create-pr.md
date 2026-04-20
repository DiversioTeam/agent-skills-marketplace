Create a pull request for the frontend repository.

## Input

The user optionally provides: `$ARGUMENTS` (`feature` or `release`)

## Steps

1. Ask the user: "Is this a **Feature PR** (branch -> dev) or a **Release PR** (dev -> main)?"

2. Follow the frontend-pr-workflow skill based on their answer:
    - **Feature PR**: Run quality gates, gather ticket info, create PR against dev with template
    - **Release PR**: Find unreleased PRs, create PR from dev to main with bulleted links

## Quick Reference

### Feature PR

- Base: `dev`
- Template: ticket link + what/why/components + browser checklist
- Gates: `yarn lint` + `yarn type-check` (0 errors, 0 warnings)
- No `eslint-disable`, no AI co-author, atomic commits

### Release PR

- Base: `main`, Head: `dev`
- Title: `Release [Month] [Day with ordinal] [Year]`
- Body: Bulleted PR links only (dashes, no extra text)
- Find PRs: `git log main..dev --grep="Merge pull request" --oneline`
