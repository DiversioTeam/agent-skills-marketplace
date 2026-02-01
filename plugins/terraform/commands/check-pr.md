---
description: Terraform PR workflow check using the terraform-pr-workflow Skill.
---

Use your `terraform-pr-workflow` Skill to review this PR’s workflow aspects:

- Branch naming (`feat/`, `fix/`, `chore/`, etc.) and consistent PR title.
- PR description includes a plan output or clearly explains why no plan was run.
- CI is read-only: fmt/lint/validate/plan only (no `apply` in GitHub Actions).
- Module/repo versioning expectations are met if the PR changes a module interface (inputs/outputs).
- Breaking changes are clearly called out with migration notes (and changelog/release notes updated when applicable).

Report findings with `[BLOCKING]`, `[SHOULD_FIX]`, and `[NIT]` tags and provide a succinct verdict.

