## Environment & Context Gathering

When this Skill runs, you should first gather context using `Bash`, `Read`,
`Glob`, and `Grep`:

- Git context:
  - `git status --porcelain`
  - `git branch --show-current`
  - `git diff --cached --stat`
  - `git diff --cached --name-only`
  - `git log --oneline -10`
- Repo configuration:
  - Read `AGENTS.md` first for repo-specific rules and doc routing.
  - Load linked repo-local docs relevant to the changed files, especially
    quality gates, runbooks, architecture docs, directory-scoped `AGENTS.md`
    files, and any GitHub-first workflow sections covering branch naming,
    issue linkage, or PR readiness.
  - If `CLAUDE.md` exists, treat it as a pointer to `AGENTS.md`, not as a
    source of unique behavioral rules.
  - If the harness is missing or obviously stale, recommend generating or
    canonicalizing docs via the `repo-docs` plugin so rules stop living in
    tribal knowledge.
  - Detect `.pre-commit-config.yaml`.
  - Detect `.security/` scripts, especially:
    - `./.security/gate_cache.sh`
    - `./.security/ruff_pr_diff.sh`
    - `./.security/local_imports_pr_diff.sh`
  - Detect `manage.py` / Django project layout.
- Tool availability:
  - `uv` and `.bin/` wrappers:
    - `.bin/ruff`, `.bin/ty`, `.bin/pyright`, `.bin/mypy`, `.bin/django`,
      `.bin/pytest`.
  - Detect repo-owned local-ci support only when `local-ci` is on PATH **and**
    repo root contains `.local-ci.toml`.
  - Fallback to `uv run` or plain `python` / `pytest` / `ruff` where necessary.
  - Read local typing policy docs when present (for example:
    `docs/python-typing-3.14-best-practices.md`, `TY_MIGRATION_GUIDE.md`) and
    follow them over this default.

If the repo clearly isn’t the Diversio backend / Django4Lyfe style, say so and
adjust expectations (but you can still run generic Python pre-commit checks).

### Gate cache behavior (when available)

If `./.security/gate_cache.sh` exists, treat it as the canonical wrapper for
heavy deterministic checks. Use it by default for type gates and Django checks.

```bash
./.security/gate_cache.sh --gate ty-check --scope index -- .bin/ty check .
./.security/gate_cache.sh --gate django-system-check --scope index -- uv run python manage.py check --fail-level WARNING
```

Use `scope=index` for commit-focused gating and `scope=working` when results are
expected to depend on unstaged edits. Do not bypass cache unless explicitly
requested or debugging:

```bash
CHECK_CACHE_BUST=1 ./.security/gate_cache.sh --gate ty-check --scope index -- .bin/ty check .
./.security/gate_cache.sh --clear-this-checkout
```

For Ruff/local-import diff helpers, call the scripts directly. They already use
cache-aware execution internally and include local staged/unstaged tracked files.
Prefer running them through pre-commit hooks first; call scripts directly only
for targeted diagnosis or when a matching hook is missing/disabled.

## Checks in Both Modes

In **both** `pre-commit` and `atomic-commit` modes, follow this pipeline:

1. **Scope changed files**
  - Start from files reported by `git status` and `git diff --cached`:
    - Distinguish staged vs unstaged vs untracked.
   - Categorize by type:
     - Python (src vs tests; `optimo_*`, `dashboardapp`, `survey`, etc.).
     - Templates (Django HTML).
     - Config (YAML, JSON, `.pre-commit-config.yaml`, `pyproject.toml`,
       `requirements*.txt`).
     - Docs/markdown.

2. **Run pre-commit first (primary execution path)**
   - If `.pre-commit-config.yaml` exists, run hooks on the intended file set
     before any direct per-tool commands.
   - `atomic-commit` mode:
     - run on staged files only:
     ```bash
     pre-commit run --files $(git diff --cached --name-only --diff-filter=ACMR)
     ```
   - `pre-commit` mode:
     - run on modified tracked + untracked files:
     ```bash
     CHANGED_FILES="$(
       {
         git diff --name-only --diff-filter=ACMR
         git ls-files --others --exclude-standard
       } | sed '/^$/d' | sort -u
     )"
     pre-commit run --files $CHANGED_FILES
     ```
   - If pre-commit already executed a gate successfully, do not rerun the same
     gate directly in the same pass.

3. **Direct command fallback (targeted, non-duplicative)**
   - Run direct commands only when:
     - a corresponding hook failed and you need focused diagnosis/fix loops, or
     - the repository does not expose that gate via pre-commit hooks.
   - Keep fetch behavior strict by default (fail closed); only allow
     `CHECKS_ALLOW_FETCH_SKIP=1` when a local skip is explicitly acceptable.
   - For Ruff/local-import helpers, direct invocation is:
     - `./.security/ruff_pr_diff.sh`
     - `./.security/local_imports_pr_diff.sh`
   - These helpers intentionally evaluate the union of `origin/<base>..HEAD`,
     staged, and unstaged tracked Python changes.

4. **Type checking with active repository gate (ty-first)**
   - Detect the type gate in this order (unless repo docs/CI explicitly differ):
     - `ty` if configured (`[tool.ty]`, `ty.toml`, `.bin/ty`, or CI/pre-commit).
     - Else `pyright` if configured.
     - Else `mypy` if configured.
   - Run the active checker on **modified Python files only** during iteration
     when the type hook is not already covered/passing via pre-commit:
     ```bash
     # ty example - staged files (atomic-commit mode):
     .bin/ty check $(git diff --cached --name-only --diff-filter=ACMR | grep '\.py$')

     # ty example - all modified files (pre-commit mode):
     .bin/ty check $(git diff --name-only --diff-filter=ACMR | grep '\.py$')

     # pyright example - staged files (atomic-commit mode):
     .bin/pyright $(git diff --cached --name-only --diff-filter=ACMR | grep '\.py$')

     # pyright example - all modified files (pre-commit mode):
     .bin/pyright $(git diff --name-only --diff-filter=ACMR | grep '\.py$')

     # mypy example - staged files (atomic-commit mode):
     .bin/mypy $(git diff --cached --name-only --diff-filter=ACMR | grep '\.py$')

     # mypy example - all modified files (pre-commit mode):
     .bin/mypy $(git diff --name-only --diff-filter=ACMR | grep '\.py$')
     ```
   - Scoped checks are for speed only; if the repo/CI requires a wider check
     before merge/commit, run that gate before final "ready" verdict.
   - **IMPORTANT**: For any file you touch, you must resolve **ALL** active
     type-check errors in that file—not just the ones you introduced. If CI
     checks modified files, pre-existing errors in touched files will still
     cause failures.
     Do **not** dismiss errors as "pre-existing" if the file is in your diff.
   - Common pitfall: Fixing ruff ARG002 (unused argument) by prefixing with `_`
     may satisfy ruff but break `ty` if the method signature must match a parent
     class (e.g., Django admin methods). Always run both checks together.
   - Treat **any** active type-check errors in modified files as `[BLOCKING]`
     for `atomic-commit` mode or `[SHOULD_FIX]` for `pre-commit` mode.

5. **Django system checks**
   - If Django check hook already passed via pre-commit, do not rerun directly.
   - Otherwise run through cache wrapper when present:
     - `./.security/gate_cache.sh --gate django-system-check --scope index -- uv run python manage.py check --fail-level WARNING`
   - If wrapper is missing, run `.bin/django check` or equivalent:
     - `uv run python manage.py check --fail-level WARNING`.
   - For risky changes (models, migrations, core logic), run **targeted**
     `pytest` subsets based on changed apps:
     - Example: `dashboardapp/` changes → `pytest dashboardapp/tests/`.
   - If tests cannot be run (e.g. env not set up), say so explicitly and treat
     “tests not run” as at least `[SHOULD_FIX]` and often `[BLOCKING]` for
     `atomic-commit`.

6. **Interaction with pre-commit hooks**
   - If `.pre-commit-config.yaml` exists:
     - Expect hooks to run and modify files (ruff, djlint, interrogate,
       custom scripts).
     - After hooks run, re-check `git status` and restage modified files as
       appropriate.
   - If a hook executable is missing (e.g. `check_prepare_commit_msg_hook.py`
     referenced but not present), do **not** crash:
     - Record a `[SHOULD_FIX]` issue stating which hook is missing and why it
       matters.

7. **Convergence loop (do not stop early)**
   - Treat the pipeline above as **iterative**, not one-shot.
   - You are **not done** until:
     - The relevant pre-commit hooks pass, and
     - Ruff/type-gate/djlint/Django checks you ran are green, and
     - The index/working tree is **stable** (hooks are no longer rewriting
       files).
   - Use a tight fix → rerun loop:
     1. Re-run the *smallest scoped* failing check on the relevant files.
     2. Fix only the reported file(s).
     3. Re-run the same check until it passes.
     4. Only then advance to the next gate.
   - Prefer rerunning only failing hooks/checks on the same file scope, then
     escalate to wider runs only if required by repo policy.
   - If hooks modify files, always re-check `git status` and restage *only* the
     intended files (atomic commits should not accidentally grow).

   ### Iteration budgets

   - **Per-check limit**: Do not attempt to fix the same check failure more than
     **3 times** with the same approach. If the same error (or substantively
     identical error) reappears after 3 real fix attempts, that check is
     **stuck**.
   - **Total pipeline limit**: Do not run more than **10 full pipeline passes**
     across the session. After 10, stop and report.

   ### Stuck detection

   You are stuck on a check when **any** of these are true:
   - The **same error message** reappears after you applied a fix for it (your
     fix is not working or is being reverted by another tool).
   - A fix for one tool **breaks another** in a cycle (e.g., djlint reformats →
     ruff flags → you fix → djlint re-reformats the same spot).
   - You have exhausted the 3-attempt per-check budget.

   When stuck:
   1. **Stop** attempting that specific fix.
   2. Report it as `[BLOCKING]` with:
      - The exact error.
      - What you tried (briefly).
      - Why it is not resolving (tool conflict, unfamiliar pattern, etc.).
   3. **Continue** fixing other unrelated issues if any remain.
   4. In final output, clearly separate "Fixed" from "Stuck / Needs Human".

   ### No TodoWrite for this pipeline

   Do **not** use `TodoWrite` or `TaskCreate` to track individual gate results.
   This is a fixed, known sequence — not an open-ended task list. Tracking ruff/
   djlint/type-check failures as todo items wastes tokens and context window. Report
   results directly in the final output using the existing severity-tagged
   sections (`Checks run`, `Needs changes`, etc.).

8. **Repo-owned local-ci validation (when available)**
   - Only after the normal gates above are green and the tree is stable, run:
     ```bash
     local-ci run --no-github
     ```
   - Do this only when `local-ci` is on PATH and repo root has `.local-ci.toml`.
   - This skill must **not** publish GitHub statuses or trigger deploy helpers.
