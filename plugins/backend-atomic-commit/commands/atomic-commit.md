---
description: Strict backend atomic commit helper using the backend-atomic-commit Skill.
---

Run your `backend-atomic-commit` Skill in **atomic-commit** mode.

Do everything the `/backend-atomic-commit:pre-commit` command would do, plus:

- Verify that the **staged changes are atomic** – one coherent change, not a
  grab bag of unrelated edits.
- Enforce that all quality gates are green:
  - `.security/ruff_pr_diff.sh`
  - `.security/local_imports_pr_diff.sh`
  - Ruff lint + format
  - mypy / type checks
  - Django system checks
  - Relevant pytest subsets
  - Pre-commit hooks
- Propose a commit message that:
  - Extracts the ticket ID from the branch name using local `AGENTS.md`
    conventions (e.g. `clickup_<ticket_id>_...` → `#<ticket_id>: Description`).
  - Contains **no** Claude/AI/plugin signature or footer.

Your output should clearly state whether the commit is ready:

- Summarize checks run and their status.
- List `What’s aligned`.
- List `Needs changes` with `[BLOCKING]`, `[SHOULD_FIX]`, and `[NIT]` tags.
- Show the proposed commit message and list of files it would cover.

If any `[BLOCKING]` issues remain (failed checks, non-atomic changes, banned
patterns, etc.), mark the commit as **not ready** and explain exactly what must
be fixed before committing.

