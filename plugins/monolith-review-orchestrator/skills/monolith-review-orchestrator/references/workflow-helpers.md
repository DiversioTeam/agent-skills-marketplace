# Workflow Helpers

This reference explains the new helper scripts for
`monolith-review-orchestrator` from first principles.

## Why These Helpers Exist

The first version of the skill relied too much on prose.

That caused three problems:

1. The model had to re-derive deterministic names and file paths each time.
2. Reassessment identity was too fuzzy and could drift after force-pushes or
   rebases.
3. Review prep could accidentally call monolith-wide mutation helpers that were
   not safe for narrow review work.

The scripts in `scripts/` solve those problems by moving the fragile,
machineable parts out of chat instructions and into deterministic helpers.

## Mental Model

Think of the helpers as a small pipeline:

```text
preflight
   |
   v
resolve review batch
   |
   v
fetch live PR context
   |
   v
prepare or reuse worktree
   |
   v
initialize / update structured state
   |
   v
write markdown review artifact
```

Each step answers one focused question.

## The Helpers

### 1. `preflight_review_env.py`

Question it answers:

```text
"Can this machine and this checkout safely run the review harness at all?"
```

Why it exists:

- The skill is monolith-local, not repo-agnostic.
- Failing late is expensive and confusing.
- Review runs should stop early if the monolith markers or basic tools are
  missing.

What it checks:

- monolith markers such as `.gitmodules` and the monolith scripts/docs
- `git`, `uv`, and `git worktree`
- GitHub auth via `gh auth status` whenever a mode or PR URL is provided
- sibling directory suitability for deterministic worktrees

Example:

```bash
uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/preflight_review_env.py \
  --mode review \
  --pr-url https://github.com/DiversioTeam/Django4Lyfe/pull/2779
```

### 2. `resolve_review_batch.py`

Question it answers:

```text
"What is the stable identity of this review run?"
```

Why it exists:

- Batch keys, worktree names, and artifact paths should not be re-invented by
  the model every time.
- Linked PR pairs need one stable name.
- In v1, linked PR pairs are intentionally cross-repo only.
- V1 needs explicit scope limits.

What it does:

- parses GitHub PR URLs
- maps `(owner, repo)` pairs to monolith submodule paths
- carries the selected mode into the resolved batch payload
- derives a deterministic batch key such as `bk2779-of389`
- derives the worktree path, review artifact path, reassessment path, and state
  file path
- rejects duplicate PR inputs and same-repo linked pairs in v1
- requires linked-pair metadata for linked cross-repo review batches
- fails clearly when it cannot discover a real monolith root

Example:

```bash
uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/resolve_review_batch.py \
  --mode review \
  --pr-url https://github.com/DiversioTeam/Django4Lyfe/pull/2779 \
  --pr-url https://github.com/DiversioTeam/Optimo-Frontend/pull/389 \
  --linked-pair-reason "Backend and frontend must ship together for the end-to-end behavior to work." \
  --authoritative-pr Django4Lyfe:2779
```

This helper now mirrors preflight's sibling-worktree root discovery instead of
requiring the caller to stand in the monolith root specifically.

### 3. `prepare_review_worktree.py`

Question it answers:

```text
"Can we safely create or reuse the exact review worktree we intend to use?"
```

Why it exists:

- `scripts/create_worktree.py` is interactive and great for humans, but not for
  deterministic automation.
- Review prep must not silently mutate unrelated repos.
- Dirty reuse needs an explicit safety gate.

What it does:

- creates one detached worktree, or reuses an existing registered one
- initializes only the explicitly listed review-batch submodules in that
  worktree
- blocks dirty reuse unless explicitly allowed
- fetches and detaches each review submodule at the exact expected PR head SHA
- fails closed if a submodule cannot be matched to the requested PR head
- rejects duplicate `--review-target` values for the same submodule path

Important non-goal:

- it does **not** run `scripts/update_submodules.py`

Why that omission matters:

- `update_submodules.py` is a monolith branch-policy updater
- review prep should stay narrow and only touch the batch it is reviewing

Example:

```bash
uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/prepare_review_worktree.py \
  --monolith-root "$MONOLITH_ROOT" \
  --worktree-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389" \
  --review-target "backend:2779:<backend-head-sha>:<backend-head-ref-name>" \
  --review-target "optimo-frontend:389:<optimo-head-sha>:<optimo-head-ref-name>" \
  --start-ref HEAD
```

If the helper must fall back to the pull-ref fetch path, it now infers the
remote from the preferred ref or the configured remotes instead of hardcoding
`origin`.

### 4. `fetch_review_threads.py`

Question it answers:

```text
"What exactly happened in GitHub review threads, including resolved and outdated ones?"
```

Why it exists:

- Flat PR comment surfaces do not preserve thread resolution state.
- Deep reassessment depends on reading resolved and outdated inline threads, not
  just top-level comments.
- The orchestrator needs a deterministic acquisition path for thread-aware
  review data instead of ad hoc `gh api graphql` commands in chat.

What it does:

- fetches PR metadata, conversation comments, review submissions, and
  `reviewThreads` through `gh api graphql`
- paginates PR comments, review submissions, and review threads
- follows up for extra thread-comment pages when a thread has more than the
  first page of comments
- enforces the same v1 scope as the batch resolver: one PR or one linked
  cross-repo pair under the known Diversio repos
- emits normalized thread-aware JSON keyed by repo and PR number

Why the helper owns this instead of leaving it to prompts:

```text
GitHub review data is not one flat list.

conversation comments
review submissions
inline review threads
thread comments
```

Those surfaces paginate independently and carry different kinds of meaning. The
helper exists so the model does not have to rediscover those details every time
it wants a trustworthy picture of the PR discussion.

Example:

```bash
uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/fetch_review_threads.py \
  --pr-url https://github.com/DiversioTeam/Django4Lyfe/pull/2779 \
  --pr-url https://github.com/DiversioTeam/Optimo-Frontend/pull/389
```

### 5. `review_state.py`

Question it answers:

```text
"What is the durable local identity of this review across multiple passes?"
```

Why it exists:

- Markdown alone is not enough for reassessment.
- Reassessment needs stable fields such as repo, PR number, base branch, head
  SHA, and merge base.
- The model should not hand-edit review-state JSON in chat.
- High-quality follow-up review also needs compact cached context about prior
  findings, comment legitimacy, structured thread records, and teaching points.

What it does:

- initializes one structured state file for a batch
- enforces the same v1 batch scope as `resolve_review_batch.py`
- summarizes the latest reusable review context for reassessment/posting
- validates live GitHub PR metadata against the latest recorded substantive
  batch identity by re-reading GitHub from the supplied `fetch_review_threads.py`
  artifact
- emits a one-time validation token that `mode=post` must consume
- records one completed batch-scoped review pass
- records one completed review pass plus compact review context from stdin JSON
- rejects review-pass records for PRs outside the batch
- keeps markdown as the human artifact and JSON as the machine identity
- refuses to overwrite existing state unless `--force` is explicit

Example:

```bash
uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/review_state.py init \
  --state-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/.state/review-bk2779-of389.json" \
  --batch-key bk2779-of389 \
  --worktree-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389" \
  --artifact-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/review-bk2779-of389.md" \
  --pr Django4Lyfe:2779 \
  --pr Optimo-Frontend:389 \
  --link-type explicit_cross_repo_pair \
  --linked-pair-reason "Backend and frontend must ship together for the end-to-end behavior to work." \
  --authoritative-pr Django4Lyfe:2779
```

If the state file already exists and you intentionally want to replace it:

```bash
uv run --script .../review_state.py init --force ...
```

Compact context read example:

```bash
uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/review_state.py \
  summarize-context \
  --state-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/.state/review-bk2779-of389.json"
```

Live-state validation example:

```bash
uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/review_state.py \
  validate-live-state \
  --state-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/.state/review-bk2779-of389.json" \
  --pr-context-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/pr-context-bk2779-of389.json"
```

For posting, take the returned `token` and include it as
`validation_token` in the `record-review` payload for `mode=post`. That proof is
time-limited and must still be fresh when posting occurs. It is now sourced from
structured live GitHub metadata, not caller-typed entries. The current
live-validation proof covers base branch, head SHA, PR state, and draft state.

Rich review-context write example:

```bash
cat <<EOF | uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/review_state.py \
  record-review \
  --state-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/.state/review-bk2779-of389.json"
{
  "mode": "review",
  "artifact_path": "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/review-bk2779-of389.md",
  "posting_status": "not_posted",
  "recommendation": "request_changes",
  "scope_summary": "Completed an initial deep review of the linked backend and Optimo frontend PRs.",
  "entries": [
    {
      "repo": "Django4Lyfe",
      "pr_number": 2779,
      "base_branch": "main",
      "head_sha": "<backend-head-sha>",
      "merge_base": "<backend-merge-base>",
      "pr_state": "OPEN",
      "is_draft": false
    },
    {
      "repo": "Optimo-Frontend",
      "pr_number": 389,
      "base_branch": "main",
      "head_sha": "<optimo-head-sha>",
      "merge_base": "<optimo-merge-base>",
      "pr_state": "OPEN",
      "is_draft": false
    }
  ],
  "backend_handoff": {
    "repo": "Django4Lyfe",
    "pr_number": 2779,
    "worktree_path": "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389",
    "pr_url": "https://github.com/DiversioTeam/Django4Lyfe/pull/2779",
    "head_sha": "<backend-head-sha>",
    "prior_open_finding_ids": [],
    "thread_context_summary": "Fetched full GitHub thread history before invoking monty."
  },
  "no_author_claims": true,
  "no_findings_after_full_review": true,
  "comment_context": {
    "thread_source": "gh_graphql",
    "summary": "Read all GitHub review threads, including resolved ones, before concluding the pass.",
    "resolved_for_context": [
      "A resolved earlier thread still explains why the helper now owns the PR ref validation."
    ]
  },
  "findings": {
    "new": [],
    "carried_forward": [],
    "resolved": [],
    "moot": []
  }
}
EOF
```

Guardrails:

- `entries` must cover the full batch, not just one side of a linked PR pair
- `inline_comment_targets[].finding_id` must point at an active `new` or
  `carried_forward` finding ID
- `summarize-context` merges durable context across all passes and only trims at
  the item level for compact output
- incomplete persisted linked-batch passes should fail normalization instead of
  being silently upgraded
- `mode=post` must reuse the latest validated recommendation and active finding
  set instead of inventing a new verdict at write time
- `backend_handoff` must match the backend batch entry's PR, SHA, recommendation,
  and recorded worktree path
- `record-pass` is disabled for normal review runs and only available behind
  `--compatibility-only --justification`

## What These Helpers Do Not Solve Yet

The current helpers intentionally do **not** solve:

- comment dedupe across flat review-comment APIs
- generic non-backend posting workflows
- monolith-wide branch normalization

They now do fetch thread-aware GitHub review state, but they still do **not**
solve the downstream problems of generic dedupe/posting or non-backend review
automation.

That is deliberate. Those areas need dedicated helpers, not more prose.

## Recommended Usage Order

For a normal review run:

```bash
uv run --script .../preflight_review_env.py
uv run --script .../resolve_review_batch.py --mode review --pr-url ...
uv run --script .../fetch_review_threads.py --pr-url ...
uv run --script .../prepare_review_worktree.py --monolith-root ... --worktree-path ... --review-target ...
uv run --script .../review_state.py init ...
```

For reassessment:

```bash
uv run --script .../review_state.py summarize-context --state-path ...
uv run --script .../review_state.py validate-live-state --state-path ... --pr-context-path ...
```

Then load the stored identity before comparing new commits or writing a new
artifact.
