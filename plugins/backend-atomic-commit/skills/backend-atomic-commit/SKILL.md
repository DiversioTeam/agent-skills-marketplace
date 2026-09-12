---
name: backend-atomic-commit
description: "Validate Django/Optimo changes before commit, check atomicity, or create an explicitly requested commit."
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
  - Propose a commit message that follows the repo-local harness **without** any Claude or AI signatures.
- `/backend-atomic-commit:commit` – to run `atomic-commit`, then **create the commit** once all gates are green (no bypassing commit-msg hooks).

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
  - Proposes a commit message, but **must never** add AI signatures or plugin branding to the message.
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

## Validation

For any pre-commit, atomic-commit, or commit run, read
[validation](references/validation.md). It owns file selection, hook-first
execution, gate-cache identity, type gates, bounded fix loops, and no-publication
local-ci validation. Do not repeat a passing gate for unchanged inputs.

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
     - `local-ci run --no-github` when the repo supports local-ci
   - A passing pre-commit hook execution counts as satisfying the matching gate.
     Do not require duplicate direct-command reruns unless diagnosing failures.
   - Where available, heavy gates should run via `./.security/gate_cache.sh`
     instead of ad-hoc direct invocation.
   - In `--auto` style usage, you may skip conversational confirmation, but
     you **must not** relax these gates.
   - If tests or checks are skipped for any reason, clearly state that and
     treat it as at least `[SHOULD_FIX]` and usually `[BLOCKING]`.

3. **Commit message generation (no AI signature)**

- Read the local repo harness first:
  - `AGENTS.md`
  - linked workflow docs
  - any commit-msg hooks that actually enforce a pattern
- Follow the documented repo-local convention instead of inventing a global
  ticket-prefix rule.
- If the repo only asks for a clear summary, propose a clear summary.
- If the repo uses issue references for traceability, include them only when
  the repo docs or active hooks expect them.
- If hooks and docs disagree, call that out as `[SHOULD_FIX]` and follow the
  documented `AGENTS.md` convention for suggestions.
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
- `Workflow notes` – only when the current branch appears inconsistent with repo-local branch or PR conventions.
- An explicit verdict: “✅ Commit ready” only if there are **no `[BLOCKING]` items**; otherwise “❌ Not ready to commit” with concrete next steps.

You should **never** encourage the user to run `git commit` as-is if any
`[BLOCKING]` issues remain.

Workflow boundary: this skill does **not** own branch creation or PR state by
itself. See `references/workflow-boundary.md`.

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
