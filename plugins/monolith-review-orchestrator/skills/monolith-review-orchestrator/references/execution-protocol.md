# Execution Protocol

Bundled helper paths such as `scripts/review_state.py` are relative to the
parent skill directory, not this `references/` directory. Commands for monolith
`scripts/update_submodules.py` remain target-repository paths.

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
- `agent-skills-marketplace` -> `agent-skills-marketplace`
- `terraform-modules` -> `terraform-modules`

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

Apply the [quality standard](review-context-protocol.md#review-quality-standard),
including the simplicity test and finding acceptance. For any Python slice,
select and read the clarity guide as specified there before reviewing code.

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
- Give Monty the selected clarity-guide path/revision, its precedence over
  generic taste defaults, the affected callers, and the authorized check scope.
  Verify returned findings against the guide before accepting them.
- Reuse its review memory protocol when doing a follow-up pass.
- Reuse Monty's backend review taste and memory context when it helps, but keep
  the final GitHub publish step on this orchestrator's worker-owned path.

Non-backend rule:

- Keep v1 to code reading, repo-local pattern checks, and synthesis.
- Do not manufacture Monty-specific Django findings for frontend-only work.
- If a stable repo-specific review adapter does not exist, say so explicitly.
- Python scripts/tests in these repos still receive the Python clarity review;
  Django/Optimo-only rules do not apply to unrelated frameworks.

### 5. Use Parallel Agents Carefully

This skill may use multiple agents when the user allows it.

Default to no parallel agents unless the user explicitly asked for parallelism,
delegation, or multiple agents.

Ownership model:

- main agent owns intake, local state management, final synthesis, and the
  final drafted review bundle
- sidecar agents own bounded analysis tasks only; include the selected clarity
  guide and quality standard in each relevant handoff
- the main agent checks their evidence and smallest-safe-fix recommendations;
  agreement among agents is not independent proof

Good parallel splits:

- one PR per agent when multiple PRs are independent
- one agent for backend code/comment analysis and one for frontend code/comment
  analysis in a linked cross-repo change
- one agent for existing review-thread triage while the main agent inspects code

Bad parallel splits:

- two agents preparing competing final review drafts for the same PR
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

Phase 2a posting contract:

- Codex drafts one authoritative top-level review body and zero or more inline
  comments.
- Codex does not post the final review to GitHub directly.
- The worker re-checks the live PR summary, unresolved-thread state, and
  top-level review/comment activity immediately before publish.
- The worker validates inline anchors against the current diff.
- The worker publishes one atomic review through local `gh` / `gh api`, or
  publishes nothing if the stale-input or anchor checks fail.
- Replies to existing review threads and partial inline publication are still
  out of scope.

Drafting rules for `post` mode:

- one authoritative top-level review per PR
- inline comments only for distinct root-cause findings with genuinely stable
  diff anchors
- prefer single-line `RIGHT`-side anchors when possible
- use multi-line anchors only when the diff location is unambiguous
- if an anchor is uncertain or likely to drift, fold that point into the
  top-level review body instead
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
