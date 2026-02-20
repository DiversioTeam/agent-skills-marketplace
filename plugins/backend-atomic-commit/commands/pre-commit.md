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
  1. `./.security/ruff_pr_diff.sh` and `./.security/local_imports_pr_diff.sh`
     (these include local staged/unstaged tracked files and cache-aware runs).
  2. `.bin/ruff check --fix` and `.bin/ruff format` on modified Python files.
  3. Active type gate (`ty` if configured; else `pyright`; else `mypy`) on
     **modified Python files only** during iteration, then any repo-required
     wider type gate before final readiness. If available, run heavy checks
     through `./.security/gate_cache.sh`.
  4. `python manage.py check --fail-level WARNING` for Django system checks
     (prefer `./.security/gate_cache.sh --gate django-system-check --scope index -- ...` when available).
  5. Any pre-commit hooks defined in `.pre-commit-config.yaml`.
- Treat the above as a **convergence loop** (not one pass): if a check fails or
  rewrites files, fix/restage, then re-run until all checks pass cleanly.
- Budget: up to **3 attempts per failing check** and **10 total pipeline
  passes**. If a check still fails after 3 real fix attempts, report it as
  `[BLOCKING]` and move on to other issues.
- Keep fetch failures fail-closed by default for diff helpers. Use
  `CHECKS_ALLOW_FETCH_SKIP=1` only when the user explicitly accepts a local skip.
- Force cache bust only when explicitly requested (`CHECK_CACHE_BUST=1`).
- Do **not** use TodoWrite to track gate results — report directly in output.
- **IMPORTANT**: For any file you touch, resolve **ALL** ruff and active
  type-check errors in that file—not just the ones you introduced. CI will fail
  on pre-existing errors in modified files. Do not dismiss errors as
  "pre-existing".

Do **not** propose a commit message in this mode; just leave the working tree
and index in the cleanest, most standards-compliant state you can, and report:

- Fixes you applied.
- Remaining `[BLOCKING]`, `[SHOULD_FIX]`, and `[NIT]` issues.
- Which checks you ran and their status.
