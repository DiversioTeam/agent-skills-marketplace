---
name: monolith-review-orchestrator
description: "Monolith-local Diversio PR review harness for deep PR understanding, deterministic worktree reuse/bootstrap, persistent review context across passes, resolved-comment-aware reassessment, backend monty-review handoff, and author-guiding review output."
allowed-tools: Bash Read Edit Glob Grep TodoWrite
---

# Monolith Review Orchestrator

## V1 Scope

Treat this as a narrow v1 harness workflow, not a universal review brain.

Supported v1 scope:

- single PR, or one explicitly linked cross-repo PR pair
- monolith-local execution only
- read-only `status`, `review`, and `reassess`
- deterministic worktree reuse/bootstrap
- persistent JSON-first review context plus markdown artifacts
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
   - Publish the latest validated review to GitHub, including inline comments
     when warranted and approval only if clean.

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
- read all review comments, replies, and resolved threads when available
- use `scripts/fetch_review_threads.py` as the default thread-aware acquisition
  path when GitHub auth is available
- identify unresolved threads only when you have a reliable thread-resolution
  source
- cross-check whether each still-open claim is actually legitimate against the
  current code
- note author claims that must be validated against the implementation

Resolved comments are not blockers by default, but they remain part of the
review history and often explain why the current code looks the way it does.
Do not discard that context during review or reassessment.

Do not claim reliable unresolved-thread state from flat comment lists alone.
If `fetch_review_threads.py` cannot be used, call the result provisional.

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
- what prior reviewers already identified, what changed since then, and whether
  the fix actually addressed the root cause

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

Minimum identity fields:

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

Minimum cached context fields for substantive passes:

- latest mode, recommendation, scope summary, repo-scoped stable finding IDs,
  claim checks, structured thread/comment context, teaching points, and inline
  comment targets

Use `scripts/review_state.py` for:

- `init` once per batch
- `summarize-context` before reassessment or posting
- `record-review` after each substantive status/review/reassess/post pass
- `record-pass` only as a compatibility fallback

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
- resolved prior-review comments that still matter for context
- what we learned from earlier review rounds and how the current code supports
  or contradicts that history
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
- explain when a resolved comment shaped the current assessment or fix
- top-level review should teach, not just label, by explaining the issue, why
  it matters, and the concrete next step
- inline comments should anchor one root-cause cluster each and include risk and
  actionable guidance
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
