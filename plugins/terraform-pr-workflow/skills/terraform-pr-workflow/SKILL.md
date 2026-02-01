---
name: terraform-pr-workflow
description: "PR workflow Skill for Terraform/Terragrunt repos: branch naming, PR hygiene, read-only CI gates, and versioning expectations for interface changes."
allowed-tools: Bash Read Edit Glob Grep
---

# Terraform PR Workflow Skill

## When to Use This Skill

Use this Skill when preparing or reviewing a PR in Terraform/Terragrunt repos, especially shared module libraries and their consumers.

Goal: catch workflow/process issues early (before apply-time surprises).

## Severity Tags

- `[BLOCKING]` – cannot merge as-is (missing plan rationale, unsafe workflow, breaking change not called out).
- `[SHOULD_FIX]` – strongly recommended before merge (docs drift, missing versioning note).
- `[NIT]` – minor polish.

## Checks This Skill Enforces

### 1) Branch and PR hygiene

- Branch name uses a standard prefix (`feat/`, `fix/`, `chore/`, `docs/`, `refactor/`).
- PR title matches intent (don’t hide breaking changes behind “chore” wording).
- One PR = one coherent change; if it’s a stack of unrelated edits, recommend splitting.

### 2) PR description quality

PR description must include either:

- **Plan evidence** (preferred):
  - module-level validation summary, or
  - `terragrunt plan` output summary for the relevant stacks, or
- **A clear explanation** of why plans weren’t run (missing creds, non-executable change, doc-only PR, etc.) plus what validation was done instead (fmt/validate/lint).

### 3) CI must be read-only

- CI should run `fmt`, `validate`, `tflint`, and optionally `plan`.
- CI should **not** run `apply`.
- If the repo currently has `apply` in CI, flag as `[BLOCKING]` and recommend moving applies to a gated/manual workflow.

### 4) Versioning expectations for module libraries

If the PR changes module interface (examples):
- `variables.tf` inputs added/renamed/removed
- `outputs.tf` outputs added/renamed/removed
- required provider/terraform versions changed

Then require:

- Explicit callout in PR description (“Interface change”) with migration notes.
- A versioning plan aligned with the repo’s conventions (tags/releases/`VERSIONING.md` when present).

### 5) Breaking changes and changelog/release notes

If changes are breaking (renames/removals, behavior changes, tighter validations):

- PR must include a `Breaking changes` section with:
  - what changed,
  - why,
  - how to migrate,
  - what version/tag will contain the change.
- If the repo maintains a changelog, require an entry.
  - If it doesn’t, require release notes in the PR body.

## Output Format

Return:

- `Verdict:` **MERGE-READY** / **NOT READY**
- `Findings:` bullets with `[BLOCKING]` / `[SHOULD_FIX]` / `[NIT]`
- `Suggested edits:` concrete fixes to branch name / PR title / PR body sections

