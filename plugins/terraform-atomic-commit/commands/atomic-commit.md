---
description: Strict Terraform atomic commit helper using the terraform-atomic-commit Skill.
---

Run your `terraform-atomic-commit` Skill in **atomic-commit** mode.

Do everything the `/terraform-atomic-commit:pre-commit` command would do, plus:

- Verify that the **staged changes are atomic** – one coherent change, not a grab bag of unrelated edits.
- Enforce that all quality gates are green (fmt/lint/validate/docs).
- Propose a commit message that:
  - Uses a standard prefix (`feat:`, `fix:`, `chore:`) and a clear scope when appropriate (e.g. `chore(terragrunt): ...`).
  - Contains **no** Claude/AI/plugin signature or footer.

Your output should clearly state whether the commit is ready:

- Summarize checks run and their status.
- List `What’s aligned`.
- List `Needs changes` with `[BLOCKING]`, `[SHOULD_FIX]`, and `[NIT]` tags.
- Show the proposed commit message and list of files it would cover.

