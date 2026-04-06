---
name: monolith-review-orchestrator
description: "Monolith-local Diversio PR review harness for structured intake, deterministic worktree reuse/bootstrap, cautious comment/status analysis, stateful reassessment, backend monty-review handoff, and narrow v1 posting boundaries."
allowed-tools: Bash Read Edit Glob Grep TodoWrite
---

# Monolith Review Orchestrator

## V1 Scope

Treat this as a narrow v1 harness workflow, not a universal review brain.

Supported v1 scope:

- single PR, or one explicitly linked PR pair
- monolith-local execution only
- read-only `status`, `review`, and `reassess`
- deterministic worktree reuse/bootstrap
- structured local review state plus markdown artifacts
- backend GitHub posting only when reusing `monty-code-review` memory/posting
  machinery

Explicitly out of scope for v1:

- generic multi-PR batch posting
- generic unresolved-thread automation without a dedicated helper
- repo-agnostic marketplace-style usage outside the Diversio monolith
- broad submodule branch normalization during review prep
- claiming reliable "final status" from comment lists alone

## When To Use This Skill

- The user wants an end-to-end PR review workflow instead of manually driving
  worktrees, submodules, PR context reads, reassessment passes, and GitHub
  posting step by step.
- The review spans one or more monolith submodules such as `backend/`,
  `frontend/`, `optimo-frontend/`, `design-system/`, or `infrastructure/`.
- The user says things like "deeply understand this PR", "check all comments and
  unresolved threads", "reassess after the author pushed updates", or "post the
  final review to GitHub".
- The user wants the agent to manage deterministic review worktrees and keep the
  local monolith state fresh.

This skill is an orchestrator. It does not replace repo-specific review taste.

- For Django4Lyfe/backend slices, invoke `monty-code-review`.
- For GitHub issue/PR metadata and comments, prefer the GitHub plugin/app when
  available; fall back to `gh` only when needed.
- For frontend or other non-backend slices, keep v1 narrower: do deep repo
  reading and synthesis, but do not pretend there is a stable repo-specific
  review adapter unless one actually exists.

## Prerequisites

This skill is monolith-local and should fail fast if these prerequisites are
not met:

- running inside a Diversio monolith checkout or sibling review worktree
- monolith scripts and docs are present
- `uv`, `git`, and `git worktree` are available
- GitHub auth is available if PR metadata or posting is requested
- the agent has permission to create sibling worktrees if bootstrap is needed

If preflight fails, stop and report the missing prerequisite instead of
continuing heuristically.

Deterministic helpers for this skill now live under `scripts/`:

- `scripts/preflight_review_env.py`
- `scripts/resolve_review_batch.py`
- `scripts/prepare_review_worktree.py`
- `scripts/review_state.py`

For the simple "what is each helper for?" explanation, load:

- `references/workflow-helpers.md`

## Modes

Choose one mode early and state it explicitly to the user:

1. `status`
   - Understand the PRs, read discussion history, audit unresolved comments,
     and report current status without doing a fresh full review.
2. `review`
   - Do a full deep review, create/update local review artifacts, and stop
     before posting unless the user asked to post.
3. `reassess`
   - Re-review after new commits, focusing on deltas, prior findings, and still
     open concerns.
4. `post`
   - Publish the latest validated review to GitHub, including inline comments
     when warranted and approval only if clean.

If the prompt implies more than one mode, use this order:

`status/review -> reassess if needed -> post`

## Intake Rules

Ask only for missing information that materially changes execution. Keep the
question block short and grouped in one message when possible.

Gather this data:

- PR set: one or more PR URLs.
- Local execution context for each PR:
  - monolith path or existing worktree path
  - submodule path
  - branch name if already checked out
- desired mode: `status`, `review`, `reassess`, or `post`
- whether the run is read-only or local mutation is allowed
- whether an existing dirty worktree may be reused
- whether tests/builds should run or this is code-reading only
- which PR is authoritative if linked PR verdicts diverge
- whether parallel sub-agents are allowed
- whether GitHub posting is allowed in this run
- if posting is allowed, whether this run is eligible for `COMMENT`,
  `REQUEST_CHANGES`, or `APPROVE`

Default assumptions when the user did not say:

- local mutation: no
- dirty worktree reuse: no
- tests/builds: code-reading only
- GitHub posting: no
- parallel sub-agents: no

Do not ask for information already present in the prompt. Infer obvious things
from the PR URL, local paths, and the monolith repo layout first.

If the user already gave local paths and branch names, prefer reusing them over
creating a new worktree.

## Deterministic Worktree Policy

Load `references/intake-and-worktree-protocol.md` for the exact naming and
reuse rules.

Use the deterministic helpers instead of reconstructing this logic manually
when possible.

Core rules:

- Prefer reusing an existing deterministic review worktree over creating a new
  one.
- `uv run scripts/create_worktree.py` is interactive/TTY-driven, so do not rely
  on it for unattended automation.
- For automated runs, use `git worktree` directly and bootstrap only the review
  batch repos.
- In automated review worktrees, prefer detached refs/commits for the monolith
  and relevant submodules so the workflow does not fight Git branch locks across
  multiple active worktrees.
- If a deterministic worktree path already exists:
  - verify whether Git still knows it as a worktree
  - refresh it safely instead of replacing it
  - never delete or force-reset it unless the user explicitly asks
- If the user points you at an already-prepared worktree, treat that as the
  source of truth and do not silently switch to a different one.

## Execution Workflow

### 1. Normalize The Review Batch

Resolve the batch with `scripts/resolve_review_batch.py` first, then mirror the
result in your notes:

- repo name
- PR number
- local submodule path
- target branch / checked-out branch
- mode
- review artifact path

Map common Diversio repos to monolith paths:

- `Django4Lyfe` -> `backend`
- `Diversio-Frontend` -> `frontend`
- `Optimo-Frontend` -> `optimo-frontend`
- `diversio-ds` -> `design-system`
- `infrastructure` -> `infrastructure`
- `diversio-serverless` -> `diversio-serverless`

If a repo cannot be mapped confidently, ask once.

### 2. Prepare Or Reuse Local State

Run preflight first with `scripts/preflight_review_env.py`.

In the selected monolith root or review worktree:

- confirm current path and git status
- if the worktree is dirty and reuse was not explicitly allowed, stop and ask
- fetch remotes needed for the monolith and relevant submodules
- initialize submodules if needed
- for each relevant submodule:
  - verify the requested branch/ref exists locally or fetch it
  - prefer detached checkout of the remote ref or exact commit under review
    rather than attaching a local branch
  - only attach a local branch if the user explicitly asked for that behavior
  - avoid adjusting repos outside the review batch

Do not use `uv run scripts/update_submodules.py` as routine review prep. That
script enforces monolith branch policy and can mutate unrelated submodules.
Refreshing utility repos is opt-in only.

Use `scripts/prepare_review_worktree.py` for deterministic worktree
create/reuse and safe submodule initialization.

State clearly what you updated and what you intentionally left untouched.

### 3. Gather PR And Comment Context

For each PR:

- read the PR metadata, description, and changed files
- read all review comments and replies
- identify unresolved threads only when you have a reliable thread-resolution
  source
- cross-check whether each still-open claim is actually legitimate against the
  current code
- note author claims that must be validated against the implementation

Do not claim reliable unresolved-thread state from flat comment lists alone.
Without a dedicated helper that exposes thread resolution/outdated state, call
the result provisional.

When the user asked for "final status", explicitly separate:

- what appears fixed
- what is still unresolved
- what looks misunderstood or no longer applicable

### 4. Review Code Deeply

For each PR, inspect:

- business logic and product behavior
- correctness and data/contract invariants
- reuse of existing utilities/helpers/patterns
- tests and regression coverage
- docs or harness gaps that make the change harder to reason about

Backend rule:

- If a PR touches `backend/`, invoke `monty-code-review` for that slice.
- Reuse its review memory protocol when doing a follow-up pass.
- When posting to GitHub for backend findings, follow the monty GitHub posting
  protocol instead of improvising.

Non-backend rule:

- Keep v1 to code reading, repo-local pattern checks, and synthesis.
- Do not manufacture Monty-specific Django findings for frontend-only work.
- If a stable repo-specific review adapter does not exist, say so explicitly.

### 5. Use Parallel Agents Carefully

This skill may use multiple agents when the user allows it.

Default to no parallel agents unless the user explicitly asked for parallelism,
delegation, or multiple agents.

Ownership model:

- main agent owns intake, local state management, final synthesis, and GitHub
  posting
- sidecar agents own bounded analysis tasks only

Good parallel splits:

- one PR per agent when multiple PRs are independent
- one agent for backend code/comment analysis and one for frontend code/comment
  analysis in a linked cross-repo change
- one agent for existing review-thread triage while the main agent inspects code

Bad parallel splits:

- two agents posting to the same PR
- two agents editing the same review artifact
- delegating the immediate blocker when the main agent needs the answer next

Before spawning, tell the user you are parallelizing and what each agent owns.

### 6. Persist Review Artifacts

Persist structured state first, then render markdown artifacts.

The structured state is the canonical local reassessment identity for this
skill. Markdown is the human-facing artifact.

Minimum state fields:

- review batch key
- repo
- PR number
- base branch
- head SHA
- merge base
- worktree path
- artifact path
- review pass number
- posting status

Use `scripts/review_state.py` for state initialization, lookup, and pass
recording instead of hand-rolling JSON updates in chat.

Create or update deterministic markdown artifacts under a `reviews/` directory
at the monolith root of the chosen worktree unless the user specified another
path.

Use filenames derived from the review batch key, for example:

- `reviews/review-bk2779.md`
- `reviews/review-bk2779-of389.md`
- `reviews/review-bk2779-reassess.md`

Each combined artifact should include:

- review scope and mode
- worktree path used
- PRs reviewed
- current branch per relevant submodule
- current status / final verdict
- open findings grouped by repo
- unresolved prior-review comments that still look legitimate
- prior-review comments that no longer look legitimate
- explicit next step: `reassess`, `post`, `approve`, or `request changes`

If `monty-code-review` produced a backend-specific artifact, link or reference
it from the combined artifact instead of duplicating it line for line.

### 7. Posting To GitHub

Only post when the user asked or explicitly confirmed posting.

V1 posting boundary:

- backend posting may proceed only through `monty-code-review` posting/memory
  machinery
- generic multi-PR or non-backend posting should be treated as not yet
  productized unless dedicated helpers exist

Posting rules:

- one authoritative top-level review per PR
- inline comments only for distinct root-cause findings
- avoid duplicate comments against already-open reviewer threads
- explain why a prior unresolved comment is still valid, or why it is now moot
- approve only when there are no legitimate blocking issues remaining
- if not approving, provide clear options and next steps

For linked PRs, keep the reviews coordinated:

- mention cross-repo dependencies
- do not approve one side if the other side blocks the behavior end to end

## Output Contract

While running:

- narrate the workflow in short step updates
- tell the invoker when you are doing intake, local-state prep, comment audit,
  deep review, reassessment, or posting
- surface material assumptions before they matter

Final response should include:

- mode executed
- worktree path used or reused
- PRs reviewed
- final status per PR
- remaining legitimate unresolved comments
- whether a GitHub review was posted, and if so whether it was approval or
  changes requested

## Reassessment Rules

When the user says the author pushed changes and wants another pass:

- reuse the existing review worktree if possible
- fetch latest refs and verify the tracked review refs are current
- load the structured review state first
- compare against the prior structured state and linked artifact
- identify commits since the prior review
- re-check every previously material finding
- do not assume a comment is resolved just because code moved
- do not repeat already-resolved nits unless the regression reappeared

The reassessment summary must distinguish:

- newly resolved
- still open
- newly introduced

## Non-Negotiables

- Never hard-reset, delete, or recreate a user worktree without explicit approval.
- Never post GitHub comments from sidecar agents.
- Never approve a PR while simultaneously documenting legitimate blocking issues.
- Never treat an unresolved thread as valid without checking the current code.
- Never treat a resolved thread as safe without checking whether the underlying
  issue was actually fixed.
- Never use `uv run scripts/update_submodules.py` as a default review refresh.
