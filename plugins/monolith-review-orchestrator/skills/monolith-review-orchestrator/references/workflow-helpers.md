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
prepare or reuse worktree
   |
   v
initialize / update structured state
   |
   v
write markdown review artifact
```

Each step answers one focused question.

## The Four Helpers

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
- optional GitHub auth via `gh auth status`
- sibling directory suitability for deterministic worktrees

Example:

```bash
uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/preflight_review_env.py
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
- maps repo names to monolith submodule paths
- derives a deterministic batch key such as `bk2779-of389`
- derives the worktree path, review artifact path, reassessment path, and state
  file path
- rejects duplicate PR inputs and same-repo linked pairs in v1

Example:

```bash
uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/resolve_review_batch.py \
  --pr-url https://github.com/DiversioTeam/Django4Lyfe/pull/2779 \
  --pr-url https://github.com/DiversioTeam/Optimo-Frontend/pull/389
```

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
  --submodule-path backend \
  --submodule-path optimo-frontend \
  --start-ref HEAD
```

### 4. `review_state.py`

Question it answers:

```text
"What is the durable local identity of this review across multiple passes?"
```

Why it exists:

- Markdown alone is not enough for reassessment.
- Reassessment needs stable fields such as repo, PR number, base branch, head
  SHA, and merge base.
- The model should not hand-edit review-state JSON in chat.

What it does:

- initializes one structured state file for a batch
- records one completed batch-scoped review pass
- rejects review-pass records for PRs outside the batch
- keeps markdown as the human artifact and JSON as the machine identity

Example:

```bash
uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/review_state.py init \
  --state-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/.state/review-bk2779-of389.json" \
  --batch-key bk2779-of389 \
  --worktree-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389" \
  --artifact-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/review-bk2779-of389.md" \
  --pr Django4Lyfe:2779 \
  --pr Optimo-Frontend:389
```

Batch-scoped pass recording example:

```bash
uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/review_state.py record-pass \
  --state-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/.state/review-bk2779-of389.json" \
  --review-target "Django4Lyfe:2779:main:<backend-head-sha>:<backend-merge-base-sha>" \
  --review-target "Optimo-Frontend:389:main:<optimo-head-sha>:<optimo-merge-base-sha>" \
  --artifact-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/review-bk2779-of389.md" \
  --posting-status not_posted
```

## What These Helpers Do Not Solve Yet

The current helpers intentionally do **not** solve:

- GitHub review-thread resolution state
- comment dedupe across flat review-comment APIs
- generic non-backend posting workflows
- monolith-wide branch normalization

That is deliberate. Those areas need dedicated helpers, not more prose.

## Recommended Usage Order

For a normal review run:

```bash
uv run --script .../preflight_review_env.py
uv run --script .../resolve_review_batch.py --pr-url ...
uv run --script .../prepare_review_worktree.py --monolith-root ... --worktree-path ... --submodule-path ...
uv run --script .../review_state.py init ...
```

For reassessment:

```bash
uv run --script .../review_state.py show --state-path ...
```

Then load the stored identity before comparing new commits or writing a new
artifact.
