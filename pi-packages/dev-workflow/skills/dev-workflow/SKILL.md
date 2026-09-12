---
name: dev-workflow
description: "Run a requested development workflow pass or finalize a change through verification and PR preparation."
---

# Dev Workflow

Choose the pass the user requested; the eight-step flow below is an available
end-to-end workflow, not a prerequisite for every edit. Reuse valid verification
for unchanged inputs. Continue authorized work through its completion criteria,
fixing related failures; stop for real blockers or decisions outside scope.
Loading this skill does not authorize commits, pushes, PR publication, or deploys.

The package and skill are named `dev-workflow`; use `/skill:dev-workflow` to load the full workflow context.

## Workflow Overview

```
1. Plan Review      → /workflow:plan       → Challenge the plan before code gains momentum
2. Park Reviewer    → [manual]           → Save implementation details, hold reviewer in reserve
3. Self-Review      → /workflow:self       → Implementor rereads own code with fresh eyes
4. Standards Pass   → /workflow:standards  → Lint, types, conventions, pre-commit hygiene
5. CI Check         → /workflow:ci         → Fetch CI status, analyze failures, distinguish ours vs flakes
6. Verify & Loop    → [manual]           → Verify locally, wake reviewer, iterate 2-6 if needed
7. Documentation    → /workflow:docs       → Explain the why and how for future readers
8. Ship             → /workflow:ship       → Verify CI green, discover PR context, atomic commit, open PR
```

## Choose A Pass

Read the requested pass in [workflow passes](references/workflow-passes.md):
plan, self-review, standards, CI, local verification, docs, or ship. Manual
reviewer orchestration is optional unless the user selected that full flow.
Read the ship section before commit/PR work; do not infer deployment permission.

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

1. /workflow:scout     → scout agent     → Codebase recon before planning
2. /workflow:plan      → [inline]        → Challenge the plan with fresh eyes
3. /workflow:self      → [inline]        → Implementor self-review
4. /workflow:standards → [inline]        → Coding standards pass
5. /workflow:oracle    → oracle agent    → Second opinion, challenge assumptions
6. /workflow:reviewer  → reviewer agent  → Independent review with forked context
7. /workflow:parallel  → 3× reviewer     → Parallel reviews (correctness, tests, complexity)
8. /workflow:docs      → [inline]        → Documentation pass
9. /workflow:ship      → [inline]        → Smart ship (discover PR context, atomic commit, PR)
```

### Subagent Commands

| Command | Agent | What it does |
|---|---|---|
| `/workflow:scout` | `scout` | Fast codebase recon: relevant files, entry points, data flow, risks |
| `/workflow:oracle` | `oracle` | Second opinion, challenges assumptions, no editing — just direction |
| `/workflow:reviewer` | `reviewer` | Independent review with forked context (correctness, edge cases, tests, simplicity) |
| `/workflow:parallel` | 3× `reviewer` | Three parallel reviewers (correctness, tests, complexity) → synthesized fixes |

When Pi is running inside cmux, subagent-style workflow commands default to opening a **seeded split pane** when they are run directly from an **idle** parent session, so the review / recon lane gets its own adjacent surface without the engineer having to remember a separate cmux command.

Mental model:

```text
/workflow:reviewer
  ├─ inside cmux + idle parent session -> open seeded split -> run reviewer prompt there
  └─ otherwise                         -> run inline in current session
```

Queued / follow-up flows keep their normal current-session behavior instead of unexpectedly opening a split later.

The seeded child session carries a small handoff: same cwd, current branch, short git status, a recent parent-session conversation snapshot, and any extra command text.

Inside that child session, the prompt still guides the AI to use the `subagent` tool when available. If `pi-subagents` is not installed, it falls back gracefully to inline analysis / review logic in that lane.

### Reusable Chains

The project includes a pre-built review pipeline chain:

```bash
/run-chain workflow-pipeline -- <task description>
```

This runs: `scout (recon) → reviewer (self-review) → worker (standards) → reviewer (docs) → delegate (ship)`

Each step forks context from the parent session. The package source keeps the chain at `agents/workflow-pipeline.chain.md`; after local install, customize the active copy at `.pi/agents/workflow-pipeline.chain.md` if needed.

## Session Bootstrap & Handoff

### Loading Context from Existing PRs
When starting a new pi session and you need to continue work on an existing PR:

```bash
/workflow:context
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
/workflow:handoff
```

The AI generates a comprehensive handoff including:
- Task overview, current state, remaining work
- Key files, setup commands, test/verify commands
- Decisions made, risks, success criteria

You can refine it with back-and-forth until satisfied. Paste the result into a new pi session or share with an engineer.

### Onboarding Engineers
Generate a message explaining the multi-agent parallel workflow:

```bash
/workflow:onboard
```

Produces a message describing how engineers ("agents") use AI in parallel, readonly-only, with handoff patterns. Ready to share in Slack, email, or docs.

## Crafting Sandboxes

Use `/workflow:crafting <task>` to create, inspect, or update a Crafting
instance. It delegates to the marketplace `crafting-sandboxes` skill (load it
separately or through `skills-bridge`), discovers live templates, verifies
checkout SHAs and frontend DS consumption, and separates endpoint readiness
from authenticated UI proof. Snapshot restores require explicit approval for
the exact source, target, and data replacement. Missing skill/CLI setup is a
blocker, not permission to improvise operations.

## Usage

```bash
# Core workflow (always available)
/workflow:plan              # Step 1 — Review the plan
/workflow:self              # Step 3 — Self-review new/modified code
/workflow:standards         # Step 4 — Coding standards pass
/workflow:ci                # Step 5 — CI check and failure analysis
/workflow:docs              # Step 7 — Documentation pass
/workflow:ship              # Step 8 — Smart ship
/workflow:crafting          # Crafting sandbox creation, inspection, or update

# Session bootstrap & handoff
/workflow:context           # Load context from existing PRs (local or remote)
/workflow:handoff           # Generate handoff for new engineer/subagent
/workflow:onboard           # Generate onboarding message for engineers

# Subagent-enhanced (requires pi-subagents)
/workflow:scout             # Scout codebase before planning
/workflow:oracle            # Second opinion, challenge assumptions
/workflow:reviewer          # Independent review, forked context
/workflow:parallel          # 3 parallel reviewers

# With extra context appended
/workflow:standards also check for missing DB indexes
/workflow:ship target is the staging branch

# See the full flow
/workflow:flow

# Interactive help panel (browse, learn, inject)
/workflow:help

# Run the full pipeline chain (requires pi-subagents)
/run-chain workflow-pipeline -- <task>

# Load this skill for AI context
/skill:dev-workflow
```
