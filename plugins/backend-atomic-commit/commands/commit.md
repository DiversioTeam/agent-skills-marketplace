---
description: Run all backend atomic-commit quality gates and create the commit when green.
---

Run your `backend-atomic-commit` Skill in **atomic-commit** mode, and **do not stop**
until one of these is true:

- A commit is successfully created, **or**
- You have a clearly explained `[BLOCKING]` issue that prevents committing.

Workflow:

1. Confirm there are staged changes (`git diff --cached --name-only`). If nothing is
   staged, do **not** guess: either stage what the user explicitly intends, or ask
   them to stage/select files first (atomic commits must stay atomic).
2. Run the full `atomic-commit` convergence loop (pre-commit hooks, `.security/*`,
   Ruff, active type gate checks (`ty`/`pyright`/`mypy`), Django checks,
   relevant pytest subsets), fixing and re-running until everything is green and
   hooks stop rewriting files.
   - Start with pre-commit hook execution on staged files; treat passing hooks
     as satisfying those gates without duplicate direct reruns.
   - Use direct commands only for targeted diagnosis of failing hooks or absent hooks.
   - If `./.security/gate_cache.sh` exists, use it for heavy deterministic
     checks by default.
   - Keep diff-helper fetch behavior fail-closed unless the user explicitly
     accepts a local skip via `CHECKS_ALLOW_FETCH_SKIP=1`.
   - Use `CHECK_CACHE_BUST=1` only when explicitly requested or debugging.
   - Apply the Skill’s explicit iteration budgets + stuck protocol (3 attempts per
     failing gate, 10 total pipeline passes). If a gate is stuck, stop and report
     it as `[BLOCKING]` with the exact error + what was tried.
   - Do **not** use TodoWrite to track gate results — report directly in output.
3. Verify atomicity of the staged diff (one coherent change).
4. Propose a ticket-prefixed commit message (derived from the branch name per local
   `AGENTS.md` rules) with **no AI signature**.
5. Create the commit:
   - `git commit -m "<message>"`
   - If commit-msg hooks fail, fix the cause and retry (do not silently bypass).

Output:
- Final verdict: **Committed** or **Not Committed**.
- Checks run + status, and any remaining issues with `[BLOCKING]`, `[SHOULD_FIX]`, `[NIT]`.
- If committed: show commit hash + subject (`git log -1 --oneline`) and the file list.
