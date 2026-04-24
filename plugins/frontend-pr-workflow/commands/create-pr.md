Create a frontend pull request using the repo-local digest and workflow rules.

## Input

The user optionally provides: `$ARGUMENTS` (`feature` or `release`)

## Steps

1. Load or refresh `docs/frontend-skill-digest/project-digest.md`.
2. Infer the PR type and branch model from repo-local docs plus the digest.
3. Ask a short clarifying question only if the PR type is still ambiguous.

4. Follow the `frontend-pr-workflow` skill:
    - **Feature/change PR**: run digest-selected quality gates, gather only the
      fields this repo actually uses, then create the PR with the right base
      branch and template
    - **Release PR**: use the repo’s detected release workflow rather than
      forcing `dev -> main`

## Quick Reference

### Feature / Change PR

- Base: use the branch model detected from the repo
- Template: prefer repo-local PR template, otherwise use the fallback structure
- Gates: use digest-selected lint/type-check/test commands
- No AI co-author, no unjustified suppressions, atomic commits

### Release PR

- Base/head/title/body: use the repo’s detected release workflow
- Do not force the old `dev -> main` and fixed-title model unless the repo uses it
