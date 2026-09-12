---
name: monolith-review-orchestrator
description: "Review or reassess Diversio PRs in monolith worktrees with persistent thread context and controlled publication."
allowed-tools: Bash Read Edit Glob Grep TodoWrite
---

# Monolith Review Orchestrator

## V1 Scope

Treat this as a narrow v1 harness workflow, not a universal review brain.

Supported v1 scope:

- single PR, or one explicitly linked cross-repo PR pair
- monolith-local execution only
- `status`, `review`, `reassess`, and worker-owned `post` mode
- deterministic worktree reuse/bootstrap
- persistent JSON-first review context plus markdown artifacts
- worker-owned final review publishing: Codex drafts, the worker revalidates,
  and the worker publishes one top-level review plus zero or more inline
  comments atomically when the anchors validate cleanly

Explicitly out of scope for v1:

- generic multi-PR batch posting
- generic unresolved-thread automation without a dedicated helper
- replies to existing review threads or partial inline publication
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
- `scripts/fetch_review_threads.py`
- `scripts/review_state.py`

For the simple "what is each helper for?" explanation, load:
- `references/workflow-helpers.md`

For the deep-understanding, comment-history, and author-guidance protocol, load:
- `references/review-context-protocol.md`

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
   - Draft the latest validated review for worker-owned GitHub publication,
     including inline comments only when the diff anchor is stable enough for
     the worker to validate safely.

If the prompt implies more than one mode, use this order:

`status/review -> reassess if needed -> post`

## Deep Understanding First

This skill is not allowed to jump straight from diff reading to verdict writing.

Before you synthesize status, findings, or posting copy:

- read the PR description, changed files, and material author claims
- read all review comments and replies, including resolved ones when available
- prefer thread-aware GitHub reads when resolution/outdated state matters
- treat resolved threads as context, not noise, and separate thread state from
  legitimacy
- validate what prior reviewers and the author claimed against the current code

## Review Quality And Simplicity

For `review` and `reassess`, follow the
[quality standard](references/review-context-protocol.md#review-quality-standard):
trace changed behavior through real callers, check failure and tenant boundaries,
and prefer the smallest design that preserves the contract. Review depth means
strong evidence, not more findings, abstractions, or mandatory review passes.

For **any Python under review**, including scripts, tests, and non-backend repos,
load the target repo's `docs/code-clarity-best-practices.md` (or its documented
replacement). If absent, use the bundled
[Code Clarity Best Practices](references/code-clarity-best-practices.md).
Apply Python/general rules everywhere relevant; Django and Optimo rules only
where those frameworks apply. Follow the reference's source/precedence rules,
include the selected guide in reviewer handoffs, and verify compliance before
accepting delegated findings. If no local guide exists and the bundled fallback
is missing, report a setup blocker rather than claiming clarity compliance.

`status` uses these rules when checking an existing claim; it still does not
start a new full review. Review does not authorize application-code edits.

## Intake Rules

Ask only for missing information that materially changes execution. Keep the
question block short and grouped in one message when possible.

Gather this data:

- PR set: one PR URL, or one explicitly linked cross-repo PR pair.
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

## Execute The Selected Mode

Read [execution protocol](references/execution-protocol.md) for batch identity,
worktree preparation, full comment context, and structured review artifacts.
Use its deep-code-review section for `review`/`reassess`, delegation only when
authorized, and publication only for `post`. `status` does not require a new
full code review. Preserve the worker-owned atomic publication contract.

## Output Contract

While running:

- give short progress updates for long work, blockers, or material state changes;
  do not narrate every routine step
- surface material assumptions before they matter

Final response should include:

- mode executed
- worktree path used or reused
- PRs reviewed
- final status per PR
- substantive review scope, clarity-guide source for Python, observed checks,
  unverified risks, and any evidence-backed simplification recommendations
- remaining legitimate unresolved comments
- how resolved-comment history affected the current verdict when it mattered
- whether a GitHub review was posted, and if so whether it was approval or
  changes requested

## Reassessment Rules

When the user says the author pushed changes and wants another pass:

- reuse the existing review worktree if possible
- fetch latest refs and verify the tracked review refs are current
- load the structured review state first with `summarize-context`
- compare against the prior structured state and linked artifact
- identify commits since the prior review
- re-check every previously material finding
- do not assume a comment is resolved just because code moved
- do not drop prior open findings unless you explicitly record them as resolved
  or moot
- keep resolved-thread context in view when it explains the author’s fix
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
- Never ignore resolved review threads when they explain current code or prior fixes.
- Never drop a prior open finding from memory unless you mark it resolved or moot.
- Never post vague review comments that fail to explain risk and the next step.
- Never let one PR's finding or inline target overwrite another PR's context in a
  linked cross-repo batch.
- Never use `uv run scripts/update_submodules.py` as a default review refresh.
