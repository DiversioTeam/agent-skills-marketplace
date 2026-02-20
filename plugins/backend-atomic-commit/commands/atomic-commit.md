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
  - Active type gate checks (`ty` if configured; else `pyright`; else `mypy`)
  - Django system checks
  - Relevant pytest subsets
  - Pre-commit hooks
- Run pre-commit first for the staged set. A passing hook execution counts as
  satisfying the matching gate; do not rerun duplicate direct commands unless
  diagnosing a hook failure.
- Use `./.security/gate_cache.sh` for heavy deterministic checks (type gates,
  Django checks, and other wrapped hooks) when the repo provides it.
- Treat the above as a **convergence loop** (not one pass): if any gate fails,
  fix the reported issue, re-run the same gate, and keep going until everything
  is green and hooks stop rewriting files.
- Budget: up to **3 attempts per failing gate** and **10 total pipeline
  passes**. If a gate is stuck (same error after 3 fix attempts), report it as
  `[BLOCKING]` and continue with other gates.
- Keep fetch failures fail-closed by default in diff helpers; only use
  `CHECKS_ALLOW_FETCH_SKIP=1` when the user explicitly accepts a local skip.
- Use `CHECK_CACHE_BUST=1` only when explicitly requested or debugging.
- Do **not** use TodoWrite to track gate results — report directly in output.
- Propose a commit message that:
  - Extracts the ticket ID from the branch name using local `AGENTS.md`
    conventions (e.g. `clickup_<ticket_id>_...` → `<ticket_id>: Description`).
  - Contains **no** Claude/AI/plugin signature or footer.

Your output should clearly state whether the commit is ready:

- Summarize checks run and their status.
- List `What’s aligned`.
- List `Needs changes` with `[BLOCKING]`, `[SHOULD_FIX]`, and `[NIT]` tags.
- Show the proposed commit message and list of files it would cover.

If any `[BLOCKING]` issues remain (failed checks, non-atomic changes, banned
patterns, etc.), mark the commit as **not ready** and explain exactly what must
be fixed before committing.
