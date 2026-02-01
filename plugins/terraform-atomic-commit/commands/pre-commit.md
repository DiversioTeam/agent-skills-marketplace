---
description: Terraform pre-commit fixer using the terraform-atomic-commit Skill.
---

Run your `terraform-atomic-commit` Skill in **pre-commit** mode.

Focus on:

- Actively fixing the files in `git status` so they match repo `AGENTS.md` and `.pre-commit-config.yaml` rules.
- Enforcing `terraform fmt` (and `terragrunt` formatting if applicable).
- Running targeted `terraform validate` (per module / per changed directory).
- Running `tflint` when configured.
- Keeping README docs consistent with `terraform-docs` when `<!-- BEGIN_TF_DOCS -->` markers exist.

Do **not** propose a commit message in this mode; just leave the working tree
in the cleanest, most standards-compliant state you can, and report:

- Fixes you applied.
- Remaining `[BLOCKING]`, `[SHOULD_FIX]`, and `[NIT]` issues.
- Which checks you ran and their status.

