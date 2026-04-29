---
name: ci
description: Check CI status for the current branch, analyze failures, distinguish failures caused by our changes from pre-existing flakes, and propose specific fixes. Use when the user asks about CI, build status, failing checks, failing jobs, test failures in CI, or whether the branch is ready after a push.
---

# CI Check

Use this skill when the user asks to check CI, build status, failing checks, or whether a branch is green. Prefer the separate `ci-status` pi package when it is installed because it gives the user an interactive TUI view. If the slash commands are unavailable, use `get_ci_status` and `ci_fetch_job_logs` only if the current harness exposes those tools; otherwise ask the user to install `ci-status`.

## Tools available

Primary, when the `ci-status` package is installed:
- `/ci` — Quick status overview in the widget area with per-job breakdown.
- `/ci-detail` — Interactive TUI view: CI providers and workflow/cycles grouped separately, Tab and cycle switching, native pickers, in-place refresh, automatic focus on failing provider/cycle, sorted job list, detail view, log fetch, first-error jump, browser open, copy URL, jump to failures.
- `/ci-logs <job>` — Pull logs for a specific failing job.

Fallback tools, when exposed by the current harness:
- `get_ci_status` — Fetch the latest CI status for the current git branch/PR. Returns a per-job breakdown with IDs, URLs, and durations. Uses gh CLI for GitHub Actions. Set `CIRCLECI_TOKEN` for CircleCI enrichment.
- `ci_fetch_job_logs` — Fetch failure logs for a specific CI job. Pass the job id from `get_ci_status` output, a GitHub run databaseId (for GH Actions), or a CircleCI job number. Returns the log output truncated to 500 lines.

## Process

1. **Fetch status.**
   - Prefer `/ci` for a quick overview, then `/ci-detail` if there are failures or running jobs to inspect.
   - If `/ci` or `/ci-detail` is unavailable, call `get_ci_status` with no arguments — it auto-detects the current branch.
   - Status should include a per-job breakdown: job name, status (passing/failing/cancelled), URL, duration.
   - If it returns no data or errors, confirm the branch is pushed and `gh` CLI is authenticated.

2. **For every failing job**, pull the logs:
   - Prefer `/ci-logs <job>` or the `r` log action inside `/ci-detail`.
   - If using fallback tools, call `ci_fetch_job_logs` with the appropriate id from the status output.
   - Use `jobId` for GitHub runs, `runId` for the databaseId, or `jobNumber` for CircleCI jobs.
   - Logs may be truncated — focus on the tail (last 100-200 lines) where errors typically appear.

3. **For each failure, determine: ours or flake?**
   - **Ours** — the failure is in code we touched or is clearly related to our changes. Examples: a test we modified now fails, a new import breaks lint, our code change causes a type error.
   - **Pre-existing flake** — the same job fails intermittently on other branches/PRs, the error is in code we didn't touch, or the failure is a timeout/infra issue unrelated to our diff.
   - **Pre-existing (not flake)** — a known failing test or build step that was broken before our branch. Note it but don't propose fixing it unless explicitly asked.

4. **For each "ours" failure**, propose a fix:
   - Identify the root cause — what exactly broke?
   - Propose the specific code change, test update, or config tweak.
   - If the fix is non-trivial, outline the approach before editing.

5. **For each flake**, note it and move on:
   - Mark it clearly as pre-existing so we don't waste time.
   - If it's consistently flaky, suggest ignoring it. If it's clearly broken infrastructure, suggest reporting it.

6. **Summarize at the end** in a scannable format:
   - Overall status: ✅ all green / ❌ X failing / ⚠️ Y flaky
   - Per-job verdict table or list with ours/flake callout
   - Actionable fixes (if any)

## Output format

Prefer a clear, scannable summary. Example:

```
CI Status: ❌ 2 failing, ⚠️ 1 flaky

| Job | Status | Ours? | Action |
|-----|--------|-------|--------|
| backend-tests | ❌ | ✅ ours | Fix import in views.py |
| frontend-lint | ❌ | ✅ ours | Run prettier on App.tsx |
| e2e-safari | ❌ | 🚫 flake | Pre-existing — ignore |
```

## Safety rules

- Do not edit code without understanding the failure first.
- Do not propose fixes for code we didn't touch unless it's clearly a side-effect cleanup.
- Do not mark a failure as a flake unless you can see evidence it also fails on other branches.
- If you cannot determine whether a failure is ours or a flake, flag it as "unclear" and ask the user.
- If CI is all green, confirm and stop — don't dig into passing jobs.
