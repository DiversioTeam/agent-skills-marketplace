---
description: Backend pre-commit fixer using the backend-atomic-commit Skill.
---

Run your `backend-atomic-commit` Skill in **pre-commit** mode.

Focus on:

- Actively fixing the files in `git status` so they match backend `AGENTS.md`,
  `.pre-commit-config.yaml`, `.security/*` helpers, and Monty’s backend taste.
- Eliminating local imports, debug statements, PII-in-logs issues, and obvious
  type-hint problems.
- Making sure Ruff, djlint, mypy, Django system checks, and pre-commit hooks
  are all happy for the current changes.

Do **not** propose a commit message in this mode; just leave the working tree
and index in the cleanest, most standards-compliant state you can, and report:

- Fixes you applied.
- Remaining `[BLOCKING]`, `[SHOULD_FIX]`, and `[NIT]` issues.
- Which checks you ran and their status.

