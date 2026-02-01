---
name: terraform-atomic-commit
description: "Terraform-focused pre-commit + atomic-commit Skill for IaC repos (fmt/validate/tflint/terraform-docs) with strict atomicity and no AI commit signatures."
allowed-tools: Bash Read Edit Glob Grep
---

# Terraform Atomic Commit Skill

## When to Use This Skill

Use this Skill in Terraform / Terragrunt repos (for example `terraform-modules/` and `infrastructure/`) when you want:

- `/terraform:pre-commit` – to actively fix formatting + lint issues and get the working tree into a clean, reviewable state.
- `/terraform:atomic-commit` – to enforce atomicity of the staged diff, run the repo’s quality gates, and propose a commit message (no AI signatures).

## Example Prompts

- “Run `/terraform:pre-commit` and fix all issues in the files shown by `git status` (fmt, validate, docs).”
- “Use `/terraform:atomic-commit` to confirm the staged diff is atomic and ready; propose a commit message.”
- “We’re in a Terragrunt repo: enforce formatting, skip any apply, and run read-only validation checks where possible.”

## Modes

This Skill behaves differently based on how it is invoked:

- `pre-commit` mode:
  - Actively applies changes to make the working tree/staged files conform to repo standards.
  - Runs auto-fixers and focused validation.
  - Does **not** propose or drive a commit.
- `atomic-commit` mode:
  - Runs everything from `pre-commit` mode.
  - Enforces atomicity of staged changes.
  - Requires all gates to be green.
  - Proposes a commit message **without** any AI signatures.

## Severity Tags

- `[BLOCKING]` – must fix before merge/commit (broken fmt/validate, dangerous workflow, non-atomic diff).
- `[SHOULD_FIX]` – strongly recommended before merge (lint warnings, missing docs update, missing pins).
- `[NIT]` – minor polish.

## Core Priorities

1. **No hidden blast radius** – prefer pinned refs, explicit versions, and documented breaking changes.
2. **Read-only by default** – never run `terraform apply` / `terragrunt apply` as part of this Skill.
3. **Atomic diffs** – split unrelated module/workflow changes into separate commits.
4. **Repo rules first** – `AGENTS.md`, `CLAUDE.md`, `.tool-versions`, and `.pre-commit-config.yaml` override defaults here.
5. **Docs reflect reality** – keep `terraform-docs` sections accurate when present.

## Environment & Context Gathering

Start by gathering:

- Git context:
  - `git status --porcelain`
  - `git diff --stat`
  - `git diff --cached --stat`
  - `git diff --cached --name-only`
- Repo standards:
  - Read `AGENTS.md` / `CLAUDE.md` if present.
  - Detect `.pre-commit-config.yaml`, `.tool-versions`, `Taskfile.yml`.
- Tooling:
  - `terraform version`
  - `terragrunt --version` (if present)
  - `tflint --version` (if present)
  - `terraform-docs --version` (if present)

If pre-commit hooks fail due to tool-version mismatch, prefer installing the repo’s pinned tool versions (e.g. via `asdf install` or a repo `task install:tools`) over bypassing checks.

## Checks Pipeline (Both Modes)

1. **Scope changed files**
   - Focus on changed `.tf`, `.hcl`, `.json`, `.yml`, and module `README.md` files.

2. **Formatting**
   - Terraform modules:
     - Run `terraform fmt -recursive` (or repo-preferred equivalent) on changed module directories.
   - Terragrunt repos:
     - Prefer running repo pre-commit hooks for formatting.
     - If formatting is manual, use the Terragrunt formatting command compatible with the pinned Terragrunt version.

3. **Validate (focused, read-only)**
   - Terraform modules:
     - For each changed module directory, run:
       - `terraform init -backend=false`
       - `terraform validate`
     - Clean up `.terraform/` and lockfiles created during local validation.
     - Practical pattern (handles modules that reference an `aws.global` alias):
       - Create a temporary `ci_providers.tf` inside the module directory:
         - `provider "aws" { region = "us-east-1" }`
         - `provider "aws" { alias = "global" region = "us-east-1" }`
       - Then run `init/validate`, and delete `ci_providers.tf` afterwards.
     - Avoid committing `.terraform/` directories. Only commit `.terraform.lock.hcl` if the repo explicitly wants lockfiles versioned.
   - Terragrunt repos:
     - Prefer focused validation/plans for only the changed stacks (avoid full `run-all` unless required).
     - If a pre-commit hook fails due to a Terragrunt CLI flag mismatch, treat it as a tool-version drift problem first:
       - Install the repo’s pinned Terragrunt version (e.g. via `.tool-versions` + `asdf install`).
       - Re-run `pre-commit run`.

4. **TFLint (when configured)**
   - If the repo uses `tflint` (pre-commit hook or `.tflint.hcl`), run it on changed modules/stacks.
   - If not configured, do not introduce a brand-new tflint setup as part of a formatting-only commit unless explicitly requested.
     - If tflint is desired but missing, propose a separate, atomic commit that adds a baseline `.tflint.hcl` + CI gate.

5. **terraform-docs consistency (when used)**
   - If a module README contains `<!-- BEGIN_TF_DOCS -->`, regenerate docs and ensure the resulting diff is committed.
   - Recommended command (adjust to repo conventions):
     - `terraform-docs markdown table --output-file README.md --output-mode inject <module_dir>`
   - If `terraform-docs` tries to generate provider lockfiles, prefer a repo-approved invocation (some repos use `--lockfile=false`).
   - After regeneration, check that `git diff` is clean (or explicitly commit the README changes as part of the same atomic change).
   - Treat “docs drift” as `[SHOULD_FIX]` (or `[BLOCKING]` when the repo enforces it in CI).

## Atomic Commit Mode Additions

In `atomic-commit` mode, additionally:

- Refuse to approve the commit if the staged diff includes unrelated changes (split commits).
- Require all checks relevant to the touched files to pass (fmt/validate/lint/docs).
- Propose a commit message with no AI signature.

## Output Format

Return:

- `Verdict:` **READY** or **NOT READY**
- `Checks:` list of commands run + pass/fail
- `Changes made:` brief list
- `Remaining issues:` with `[BLOCKING]` / `[SHOULD_FIX]` / `[NIT]`
- `Proposed commit message:` (atomic-commit mode only)
