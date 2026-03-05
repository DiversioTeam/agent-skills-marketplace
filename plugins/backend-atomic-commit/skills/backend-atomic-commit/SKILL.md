---
name: backend-atomic-commit
description: "Pedantic backend pre-commit + atomic-commit skill for Django/Optimo repos that enforces local AGENTS.md, repo-local docs, pre-commit hooks, and security helpers (no AI signatures in commit messages)."
allowed-tools: Bash Read Edit Glob Grep
---

# Backend Atomic Commit Skill

## When to Use This Skill

Use this Skill in backend/Django repos (especially the Diversio monolith
backend) when you want:

- `/backend-atomic-commit:pre-commit` – to **actively fix** the current code
  (formatting, imports, type hints, logging, etc.) so that it matches:
  - Local `AGENTS.md`, linked repo-local docs, and quality gates.
  - `.pre-commit-config.yaml` expectations.
  - `.security/` diff helpers (ruff and local imports).
  - Monty’s backend taste.
- `/backend-atomic-commit:atomic-commit` – to run the same checks plus:
  - Enforce that the **staged changes are atomic** (one coherent change).
  - Ensure all quality gates are green (no shortcuts).
  - Propose a strict, ticket-prefixed commit message **without** any Claude or
    AI signatures.
- `/backend-atomic-commit:commit` – to run `atomic-commit`, then **create the
  commit** once all gates are green (no bypassing commit-msg hooks).

Representative prompt shapes live in `references/usage-examples.md`.

If you’re not in a backend repo (no `manage.py`, no backend-style `AGENTS.md`,
no `.pre-commit-config.yaml`, no backend quality docs), this Skill should say
so explicitly and fall back to a lighter “generic Python pre-commit” behavior.

## Modes

This Skill behaves differently based on how it is invoked:

- `pre-commit` mode – invoked via `/backend-atomic-commit:pre-commit`:
  - Actively applies changes to make the working tree and staged files conform
    to repo standards and pre-commit requirements.
  - Runs all relevant static checks and auto-fixers.
  - Does **not** propose or drive a commit.
- `atomic-commit` mode – invoked via `/backend-atomic-commit:atomic-commit`:
  - Runs everything from `pre-commit` mode.
  - Enforces atomicity of staged changes.
  - Requires all gates to be green.
  - Proposes a commit message, but **must never** add AI signatures or plugin
    branding to the message.
- `commit` mode – invoked via `/backend-atomic-commit:commit`:
  - Runs everything from `atomic-commit` mode.
  - Creates the commit once all gates are green.
  - Must still never add AI signatures or plugin branding to the message.

The command markdown sets the mode. You should detect the mode from the command
description/context and adjust behavior accordingly.

## Core Priorities

Emulate Monty’s backend engineering and review taste, tuned for pre-commit:

1. **Correctness & invariants** – multi-tenancy, time dimensions, and security
   constraints come first.
   - Never eyeball date/time math (day-of-week, "yesterday", timezone edges).
     Always verify using `date +%Y-%m-%d` or Python `datetime` — never compute
     dates manually. Date calculation errors have been a recurring friction
     point in real sessions.
2. **Safety & reviewability** – avoid dangerous schema changes, large risky
   try/except blocks, hidden PII, or untyped payloads.
3. **Atomic commits** – one commit should represent one coherent change; split
   unrelated work.
4. **Local harness first** – treat `AGENTS.md` as the canonical entrypoint,
   follow linked repo-local docs and directory-scoped `AGENTS.md` files for
   per-topic truth, and do not treat `CLAUDE.md` as a unique rule source.
5. **Tooling alignment** – use uv wrappers, `.security/*` helpers, and
   `.pre-commit-config.yaml` hooks as documented, not ad-hoc commands.
6. **Type and structure** – prefer precise type hints, `TypedDict`/dataclasses,
   and structured logging over untyped dicts and log soup.
7. **No AI signatures in commits** – commit messages must look like a human
   wrote them; this Skill should be invisible from `git log`.

Always prioritize `[BLOCKING]` issues over style and nits.

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
  - Load any linked repo-local docs relevant to the changed files, especially
    quality gates, runbooks, architecture docs, and directory-scoped
    `AGENTS.md` files.
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

## Backend Fix Rules

When you need concrete auto-fix heuristics, load:

- `references/backend-taste-and-fix-rules.md`

Use that reference when actively editing backend code, templates, logging,
types, tests, migrations, or other recurring lint targets. It contains the
safe-fix guidance that used to live inline here.

If you discover a recurring failure that is hard to infer from the repo
harness, emit a `[SHOULD_FIX]` follow-up recommending a docs, wrapper, or CI
improvement instead of letting the rule stay tribal.

## Atomic-Commit Mode – Extra Strictness

In `atomic-commit` mode (invoked via `/backend-atomic-commit:atomic-commit`),
you must be **very strict**:

1. **Atomicity of staged changes**
   - From `git diff --cached --name-only`, determine if staged changes belong
     to one coherent change:
     - Example of non-atomic:
       - Refactor in `survey/` plus an unrelated optimo bugfix and docs tweak.
   - Emit:
     - `[BLOCKING]` if the staged set is clearly multiple logical changes.
     - `[SHOULD_FIX]` for minor opportunistic cleanups that could be split.
   - You may suggest a split (e.g. “extract the optimo fix into a separate
     commit”) but must not label a non-atomic set as “ready”.

2. **All gates must be green**
   - The commit is **not** ready if any of these fail:
     - `./.security/ruff_pr_diff.sh`
     - `./.security/local_imports_pr_diff.sh`
     - `.bin/ruff check` / `ruff format`
     - active type gate on staged Python files (`ty`/`pyright`/`mypy`)
     - `.bin/django check` / `manage.py check`
     - Relevant `pytest` subsets for risky changes
     - Pre-commit hooks defined in `.pre-commit-config.yaml`
   - A passing pre-commit hook execution counts as satisfying the matching gate.
     Do not require duplicate direct-command reruns unless diagnosing failures.
   - Where available, heavy gates should run via `./.security/gate_cache.sh`
     instead of ad-hoc direct invocation.
   - In `--auto` style usage, you may skip conversational confirmation, but
     you **must not** relax these gates.
   - If tests or checks are skipped for any reason, clearly state that and
     treat it as at least `[SHOULD_FIX]` and usually `[BLOCKING]`.

3. **Commit message generation (no AI signature)**

- Extract ticket ID from branch name using repo conventions:
  - For the Diversio backend:
    - Branch name: `clickup_<ticket_id>_...`
    - Commit format per `AGENTS.md`: `<ticket_id>: Description`.
  - If commit message hooks like `commit_msg_hook.py` exist:
    - Avoid double-prefixing ticket IDs.
    - If hooks and docs disagree, call that out as `[SHOULD_FIX]` and follow
      the documented `AGENTS.md` convention for suggestions.
- Generate a concise, human-looking subject line:
  - Summarize what changed and why in one line.
  - Do **not** mention Claude, AI, this Skill, or plugin names.
- Do **not** add any footer or signature:
  - No “via Claude Code”.
  - No “Generated by backend-atomic-commit”.
  - Commit messages must look like a human wrote them.

4. **Final preview and verdict**

Your `atomic-commit` output should include:

- A short summary of what was checked.
- `Checks run` – listing each gate and its status.
- `What’s aligned` – strengths and good patterns in the staged changes.
- `Needs changes` – bullets with `[BLOCKING]`, `[SHOULD_FIX]`, `[NIT]`.
- `Proposed commit` – suggested commit message and list of files.
- An explicit verdict:
  - “✅ Commit ready” only if there are **no `[BLOCKING]` items**.
  - Otherwise:
    - “❌ Not ready to commit” with concrete next steps.

You should **never** encourage the user to run `git commit` as-is if any
`[BLOCKING]` issues remain.

## Pre-Commit Mode – Fixing Without Committing

In `pre-commit` mode (invoked via `/backend-atomic-commit:pre-commit`):

- You may aggressively auto-fix:
  - Formatting, linting, local imports, obvious type hints, logging patterns,
    removal of debug code, and consistent fixtures.
- You must:
  - Run the same gates described above (Ruff, `.security/*`, active type gate, Django
    checks, tests as appropriate).
  - Re-run or re-stage files modified by tools or hooks.
- You do **not** propose a commit or check atomicity.
- Your output should focus on:
  - `Fixes applied` – concrete edits you made.
  - `Remaining issues` – with severity tags.
  - `Checks run` – which gates passed/failed.

This mode is the “make my working tree clean and standards-compliant” helper
before running an atomic commit.

## Severity Tags & Output Shape

Always structure findings using severity tags and sections:

- `[BLOCKING]` – must be fixed before a commit is considered ready:
  - Failing `.security` scripts or pre-commit hooks.
  - New banned patterns from `AGENTS.md` (e.g., Ninja Query constants, legacy
    survey models).
  - Obvious multi-tenant or security regressions.
  - Non-atomic staged changes in `atomic-commit` mode.
- `[SHOULD_FIX]` – important, strongly recommended changes:
  - Style/structure that harms readability or maintainability.
  - Missing type hints where types are clear.
  - Ambiguous commented code or TODOs without tickets.
  - Missing tests for non-trivial new behavior.
- `[NIT]` – minor cleanups:
  - Docstring tone/punctuation.
  - Minor naming and formatting nits not covered by Ruff.

Output shape for both modes:

- 1–3 sentence summary of what was checked.
- Sections (when appropriate):
  - `What’s aligned`
  - `Needs changes`
  - `Checks run`
  - `Harness follow-ups` (only when docs/tooling should be improved)
  - `Proposed commit` (only in atomic-commit mode)

Be direct, specific, and actionable in each bullet, pointing to file/area and
suggesting concrete corrections. Never hide behind vague "consider improving"
phrases when you can be precise.

## Compatibility Notes

Works in both Claude Code and OpenAI Codex. For installation, see this repo's
`README.md`.
