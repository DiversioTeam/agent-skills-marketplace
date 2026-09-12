## Step Details

### Step 1: Review the Plan
**Before writing code**, challenge the plan itself. Have the AI reread the plan and surrounding code with fresh eyes, looking for bugs, ambiguity, and conflicts. Update the plan based on findings.

**Command:** `/workflow:plan` (append extra context like `/workflow:plan focus on auth module`)

### Step 2: Park the Reviewer
When AI finishes implementation and outputs "details of what it did":
1. Copy those details into a reviewer session (or the original planner session)
2. **Do not run the reviewer yet** — the implementor needs to self-review first

This step is manual orchestration. No command for it.

### Step 3: Implementor Self-Review
Force the implementor (same AI session that wrote the code) to reread all new and modified code with fresh eyes. Catch obvious bugs before the independent reviewer spends time on them.

**Command:** `/workflow:self`

### Step 4: Standards Pass
Run the coding standards and pre-commit cleanup. This is the policy and hygiene pass:

Use repository rules first; the defaults below apply to Python/Django, not
unrelated stacks:

- Follow import rules and fix circular dependencies
- No unnecessary `getattr()`, use `hasattr()` only if needed
- No overly large `try`/`except` blocks
- Structured logging in `optimo_` apps
- No hardcoded strings/numbers where structured fields should be used
- Use `TypedDict` instead of loose `dict` with `Any`
- Ruff must be happy with all files
- No string-based type hints
- Prefer types that prove the contract; do not hide type errors with casts
- Don't repeat fixtures in tests
- Use Django ORM reverse relations to avoid unnecessary model imports
- Be pedantic about type hints, avoid `Any`
- Use `ast-grep` where helpful

**Command:** `/workflow:standards`

### Step 5: CI Check
Before manual verification, check CI for the current branch using the separate **ci-status** pi package when installed. If it is unavailable, use `get_ci_status` and `ci_fetch_job_logs` only if the current harness exposes those tools; otherwise ask the user to install `ci-status` before proceeding.

**Primary commands:**
- `/ci` — quick status overview in the widget area
- `/ci-detail` — interactive TUI view grouped by CI provider and workflow/cycle, Tab and cycle switching, native pickers, in-place refresh, automatic failure focus, detail view, and log access
- `/ci-logs <job>` — pull failure logs for a specific job

**Orchestration command:**
- `/workflow:ci` — guides the AI through the full CI check: run `/ci` or `/ci-detail`, analyze each failure (ours vs flake), propose fixes, summarize.

Boundary: `/workflow:ci` is for remote CI status. If `local-ci` is on PATH and
repo root contains `.local-ci.toml`, use local-ci later as the repo-owned local
validation path; do not replace `/ci` with local-ci here.

The ci-status extension auto-watches CI on startup and after git pushes. Failure notifications appear automatically. Covers GitHub Actions and CircleCI (set `CIRCLECI_TOKEN` for CircleCI enrichment).

**Command:** `/workflow:ci` (orchestrated) or `/ci-detail` (direct interactive UI)

### Step 6: Verify Locally & Run Reviewer
The engineer verifies everything locally (backend, frontend, etc.). Then wakes the waiting reviewer session. If the reviewer finds issues, paste findings back into the implementor and repeat steps 2-5 until satisfied.

This step is manual orchestration. No command for it.

### Step 7: Documentation Pass
Document changed contracts, commands, and non-obvious decisions in the existing
docs. Do not add prose that merely restates code or create an artifact for every
changed file.

**Command:** `/workflow:docs`

### Step 8: Ship It
Finalize and ship the work:

1. **Discover context** — repository, branch, intended diff, existing PR, issues,
   and target. Ask only about consequential uncertainty; API failure is not
   evidence that no PR exists.
2. **Inspect existing CI** as diagnostic context, not proof for unpushed changes.
   An unpublished branch may not have checks yet.
3. **Validate locally** — use the atomic commit skill and required repository
   gates. Use `local-ci run --no-github` for authorized local validation when
   configured; a missing binary cannot waive a required gate. Fix related
   failures and required touched-file gate errors; rerun affected checks.
4. **Commit and push** — only when authorized, commit atomically and push
   normally. Preserve no-commit/no-push limits and unrelated work. If prohibited,
   deliver the corresponding local handoff with publication pending.
5. **Create or update the PR** — use the PR description writer for the actual
   pushed diff and observed results, with issue links and repo-local base/draft
   conventions. Update the existing PR rather than duplicating it.
6. **Verify the final remote head** — after push and PR creation/update, inspect
   required CI for that exact SHA using `/ci`/`/ci-detail` or exposed CI tools.
   Investigate failures and repeat authorized fixes and publication as needed;
   a new head requires a new status check. Report pending/missing checks and
   discovery failures, never infer readiness from an earlier green head.
   Reuse local evidence only when code, configuration, environment, and required
   commit identity still match. Return PR URL, head SHA, results, and blockers.

For separately authorized backend deployments, PR-head local-ci is only a
preflight. Follow the release skill's exact clean `origin/release` or
`origin/master` validation and deploy contract. A helper's existence or a green
preflight does not authorize invoking it.

Include all files required for the requested change without sweeping unrelated
cleanup into it. A ship request does not override explicit no-commit/no-push
instructions and never authorizes deployment by itself.

**Command:** `/workflow:ship`
