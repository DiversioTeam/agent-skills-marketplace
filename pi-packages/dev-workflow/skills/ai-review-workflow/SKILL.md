---
name: ai-review-workflow
description: "Multi-pass AI review workflow for shipping high-quality code. Use when the user is about to finalize a change, wants a standards review, or asks to ship/workflow/review their code. Covers plan review, self-review, standards pass, documentation, and PR creation."
---

# Dev Workflow

An 8-step daily developer workflow that forces multiple passes over the same change from different angles: planning quality, implementor self-checking, repository standards, CI analysis, end-to-end verification, independent review, documentation, and a final commit-and-PR handoff.

The package is named `dev-workflow`; the skill name remains `ai-review-workflow` for backward-compatible `/skill:ai-review-workflow` usage.

## Workflow Overview

```
1. Plan Review      → /review:plan       → Challenge the plan before code gains momentum
2. Park Reviewer    → [manual]           → Save implementation details, hold reviewer in reserve
3. Self-Review      → /review:self       → Implementor rereads own code with fresh eyes
4. Standards Pass   → /review:standards  → Lint, types, conventions, pre-commit hygiene
5. CI Check         → /review:ci         → Fetch CI status, analyze failures, distinguish ours vs flakes
6. Verify & Loop    → [manual]           → Verify locally, wake reviewer, iterate 2-6 if needed
7. Documentation    → /review:docs       → Explain the why and how for future readers
8. Ship             → /review:ship       → Verify CI green, discover PR context, atomic commit, open PR
```

## Step Details

### Step 1: Review the Plan
**Before writing code**, challenge the plan itself. Have the AI reread the plan and surrounding code with fresh eyes, looking for bugs, ambiguity, and conflicts. Update the plan based on findings.

**Command:** `/review:plan` (append extra context like `/review:plan focus on auth module`)

### Step 2: Park the Reviewer
When AI finishes implementation and outputs "details of what it did":
1. Copy those details into a reviewer session (or the original planner session)
2. **Do not run the reviewer yet** — the implementor needs to self-review first

This step is manual orchestration. No command for it.

### Step 3: Implementor Self-Review
Force the implementor (same AI session that wrote the code) to reread all new and modified code with fresh eyes. Catch obvious bugs before the independent reviewer spends time on them.

**Command:** `/review:self`

### Step 4: Standards Pass
Run the coding standards and pre-commit cleanup. This is the policy and hygiene pass:

- No local imports (check circular imports)
- No unnecessary `getattr()`, use `hasattr()` only if needed
- No overly large `try`/`except` blocks
- Structured logging in `optimo_` apps
- No hardcoded strings/numbers where structured fields should be used
- Use `TypedDict` instead of loose `dict` with `Any`
- Ruff must be happy with all files
- No string-based type hints
- Never use `typing.cast()` — it's a code smell
- Don't repeat fixtures in tests
- Use Django ORM reverse relations to avoid unnecessary model imports
- Be pedantic about type hints, avoid `Any`
- Use `ast-grep` where helpful

**Command:** `/review:standards`

### Step 5: CI Check
Before manual verification, check CI for the current branch using the separate **ci-status** pi package when installed. If it is unavailable, use `get_ci_status` and `ci_fetch_job_logs` only if the current harness exposes those tools; otherwise ask the user to install `ci-status` before proceeding.

**Primary commands:**
- `/ci` — quick status overview in the widget area
- `/ci-detail` — interactive TUI view grouped by CI provider and workflow/cycle, Tab and cycle switching, native pickers, in-place refresh, automatic failure focus, detail view, and log access
- `/ci-logs <job>` — pull failure logs for a specific job

**Orchestration command:**
- `/review:ci` — guides the AI through the full CI check: run `/ci` or `/ci-detail`, analyze each failure (ours vs flake), propose fixes, summarize.

The ci-status extension auto-watches CI on startup and after git pushes. Failure notifications appear automatically. Covers GitHub Actions and CircleCI (set `CIRCLECI_TOKEN` for CircleCI enrichment).

**Command:** `/review:ci` (orchestrated) or `/ci-detail` (direct interactive UI)

### Step 6: Verify Locally & Run Reviewer
The engineer verifies everything locally (backend, frontend, etc.). Then wakes the waiting reviewer session. If the reviewer finds issues, paste findings back into the implementor and repeat steps 2-5 until satisfied.

This step is manual orchestration. No command for it.

### Step 7: Documentation Pass
Make the outcome legible. Document all updated code, especially new additions, in simple, visual, first-principles-driven language. Explain **why** changes were made.

**Command:** `/review:docs`

### Step 8: Ship It
Finalize and ship the work:

1. **Verify CI green** — prefer `/ci` and `/ci-detail`; fall back to available CI tools if the harness exposes them
2. **Discover context** — check the current branch, look for existing GitHub PRs and issues
3. **Update existing PR** if one already exists for this branch
4. **Create new PR** if none exists, linking any related GitHub issues
5. **Ask questions** if uncertain about anything (existing PRs, issue linking, branch targets)
6. **Atomic commit** — use the atomic commit skill, ensure everything passes (lint, types, tests, pre-commit)
7. **PR description** — use the PR description writer skill for a reviewer-friendly summary
8. **Open the PR** on GitHub

Never compromise by excluding files that are part of the change. Everything touched must be improved.

**Command:** `/review:ship`

## Principles

1. **Challenge the plan before code gains momentum** — weak plans create expensive code
2. **Don't spend reviewer attention too early** — implementor must self-review first
3. **Keep policy checks separate from correctness checks** — standards vs. behavior
4. **Use repetition on purpose** — the loop (steps 2-5) turns review findings into concrete fixes
5. **Make future maintenance cheaper** — document at the end when the change is final
6. **End with a review-ready artifact** — atomic commit + clear PR description

## Placeholders (repo-specific)

| Placeholder | Meaning | Example |
|---|---|---|
| `[planner session]` | Session that wrote the plan | Original planning thread |
| `[reviewer session]` | Session waiting to review | Parked review thread |
| `[details of what it did]` | Implementor handoff summary | Files changed, tests run, open questions |
| `[backend command set]` | Backend verification commands | `ruff check`, type checks, Django tests |
| `[frontend command set]` | Frontend verification commands | Lint, type checks, unit tests, build |
| `[atomic commit skill]` | Approved atomic commit workflow | Backend or Terraform commit flow |
| `[pr description writer skill]` | PR description generation workflow | Structured summary with visuals |

## Subagent-Enhanced Workflow (with pi-subagents)

When [pi-subagents](https://github.com/nicobailon/pi-subagents) is installed, the workflow gains dedicated child agents with forked context:

```
                    ┌──────────────────────────────┐
                    │  pi-subagents builtin agents  │
                    │  scout · oracle · reviewer    │
                    │  planner · worker · delegate  │
                    └──────────────────────────────┘

1. /review:scout     → scout agent     → Codebase recon before planning
2. /review:plan      → [inline]        → Challenge the plan with fresh eyes
3. /review:self      → [inline]        → Implementor self-review
4. /review:standards → [inline]        → Coding standards pass
5. /review:oracle    → oracle agent    → Second opinion, challenge assumptions
6. /review:reviewer  → reviewer agent  → Independent review with forked context
7. /review:parallel  → 3× reviewer     → Parallel reviews (correctness, tests, complexity)
8. /review:docs      → [inline]        → Documentation pass
9. /review:ship      → [inline]        → Smart ship (discover PR context, atomic commit, PR)
```

### Subagent Commands

| Command | Agent | What it does |
|---|---|---|
| `/review:scout` | `scout` | Fast codebase recon: relevant files, entry points, data flow, risks |
| `/review:oracle` | `oracle` | Second opinion, challenges assumptions, no editing — just direction |
| `/review:reviewer` | `reviewer` | Independent review with forked context (correctness, edge cases, tests, simplicity) |
| `/review:parallel` | 3× `reviewer` | Three parallel reviewers (correctness, tests, complexity) → synthesized fixes |

All subagent commands fall back to inline execution if pi-subagents is not installed. The prompts guide the AI to use the subagent tool when available.

### Reusable Chains

The project includes a pre-built review pipeline chain:

```bash
/run-chain review-pipeline -- <task description>
```

This runs: `scout (recon) → reviewer (self-review) → worker (standards) → reviewer (docs) → delegate (ship)`

Each step forks context from the parent session. The package source keeps the chain at `agents/review-pipeline.chain.md`; after local install, customize the active copy at `.pi/agents/review-pipeline.chain.md` if needed.

## Session Bootstrap & Handoff

### Loading Context from Existing PRs
When starting a new pi session and you need to continue work on an existing PR:

```bash
/review:context
```

This tells the AI to:
1. Discover PRs on the current branch (`gh pr list --head`)
2. If none locally, list your open PRs and let you pick
3. Check out remote PRs if needed (`gh pr checkout <number>`)
4. Deep-read the full diff across all modified files
5. Check CI status, review comments, and unresolved threads
6. Note any submodule pointer changes (important in this monorepo)
7. Ask clarifying questions if unsure which PR to focus on
8. Present a summary and be ready for further instructions

### Generating Handoff Messages
When you need to hand work to another engineer or spawn a fresh subagent session:

```bash
/review:handoff
```

The AI generates a comprehensive handoff including:
- Task overview, current state, remaining work
- Key files, setup commands, test/verify commands
- Decisions made, risks, success criteria

You can refine it with back-and-forth until satisfied. Paste the result into a new pi session or share with an engineer.

### Onboarding Engineers
Generate a message explaining the multi-agent parallel workflow:

```bash
/review:onboard
```

Produces a message describing how engineers ("agents") use AI in parallel, readonly-only, with handoff patterns. Ready to share in Slack, email, or docs.

## Usage

```bash
# Core workflow (always available)
/review:plan              # Step 1 — Review the plan
/review:self              # Step 3 — Self-review new/modified code
/review:standards         # Step 4 — Coding standards pass
/review:ci                # Step 5 — CI check and failure analysis
/review:docs              # Step 7 — Documentation pass
/review:ship              # Step 8 — Smart ship

# Session bootstrap & handoff
/review:context           # Load context from existing PRs (local or remote)
/review:handoff           # Generate handoff for new engineer/subagent
/review:onboard           # Generate onboarding message for engineers

# Subagent-enhanced (requires pi-subagents)
/review:scout             # Scout codebase before planning
/review:oracle            # Second opinion, challenge assumptions
/review:reviewer          # Independent review, forked context
/review:parallel          # 3 parallel reviewers

# With extra context appended
/review:standards also check for missing DB indexes
/review:ship target is the staging branch

# See the full flow
/review:flow

# Interactive help panel (browse, learn, inject)
/review:help

# Run the full pipeline chain (requires pi-subagents)
/run-chain review-pipeline -- <task>

# Load this skill for AI context
/skill:ai-review-workflow
```
