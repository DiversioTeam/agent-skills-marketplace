---
description: Backend pre-commit fixer using the backend-atomic-commit Skill.
---

Run your `backend-atomic-commit` Skill in **pre-commit** mode.

Focus on:

- Actively fixing the files in `git status` so they match backend `AGENTS.md`,
  `.pre-commit-config.yaml`, `.security/*` helpers, and Monty's backend taste.
- Eliminating local imports, debug statements, PII-in-logs issues, and obvious
  type-hint problems.
- Running the following checks in order:
  1. `.bin/ruff check --fix` and `.bin/ruff format` on modified Python files.
  2. `.bin/ty check` on **modified Python files only** to catch type errors
     before CI (avoids baseline errors in unmodified code).
  3. `python manage.py check --fail-level WARNING` for Django system checks.
  4. Any pre-commit hooks defined in `.pre-commit-config.yaml`.
- **IMPORTANT**: For any file you touch, resolve **ALL** ruff and ty errors in
  that file—not just the ones you introduced. CI will fail on pre-existing
  errors in modified files. Do not dismiss errors as "pre-existing".

Do **not** propose a commit message in this mode; just leave the working tree
and index in the cleanest, most standards-compliant state you can, and report:

- Fixes you applied.
- Remaining `[BLOCKING]`, `[SHOULD_FIX]`, and `[NIT]` issues.
- Which checks you ran and their status.

