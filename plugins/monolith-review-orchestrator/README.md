# Monolith Review Orchestrator

Monolith-local PR review workflow for deep understanding, thread-aware GitHub
review history, persistent review context, deterministic worktree reuse, and
reviewer-friendly final output.

Use this plugin when the goal is not just to skim a diff, but to:

- deeply understand the PR and the back-and-forth review history
- treat resolved comments as important context, not noise
- reassess incrementally after new commits
- post clearer, more instructive GitHub reviews through the worker-owned
  publish path, with inline comments when anchors are stable

## What It Figures Out For You

The normal path should not require the user to think about worktree names,
cursor pagination, or local repo layout.

```text
you provide:
  - PR URL(s)
  - review intent
  - whether posting is allowed

the plugin figures out:
  - review batch identity
  - linked-pair metadata when two PRs must be reviewed together
  - live PR head SHAs before local checkout
  - worktree reuse or preparation
  - thread-aware GitHub review history
  - durable local review context
  - what changed since the last pass
```

That is why the example prompts below focus on the review ask, not the setup
mechanics.

## First Principles

The plugin intentionally splits review work into two different jobs:

```text
Codex / agent
  -> understand the PR
  -> draft the review

worker
  -> re-check live GitHub state
  -> validate inline anchors
  -> publish atomically through local `gh` / `gh api`
```

That split exists because analysis and publication fail in different ways. A
good review draft can still become stale before publish. Keeping the worker in
charge of the final mutation makes that last safety check explicit.

## Best Inputs

The workflow is strongest when your prompt includes:

- the PR URL
- linked PR URLs when the change spans repos
- whether this is `status`, `review`, `reassess`, or `post`
- for linked PRs: why they are linked and which PR is authoritative if the
  verdicts diverge
- whether GitHub posting is allowed in this run

Only mention a local worktree or submodule path when you explicitly want the
plugin to reuse a specific local setup instead of resolving or preparing one
itself.

## Example Prompts

### 1. Deep PR Understanding

```text
Please deeply understand https://github.com/DiversioTeam/Django4Lyfe/pull/2779.

Read the PR thoroughly, including all review comments and replies. Treat resolved comments as context too. Tell me the real current status: what is fixed, what is still legitimate, and what earlier feedback is now moot.
```

### 2. Linked Cross-Repo Review

```text
Please deeply understand these linked PRs and review them together:

https://github.com/DiversioTeam/Django4Lyfe/pull/2779
https://github.com/DiversioTeam/Optimo-Frontend/pull/389

Read all comments and resolved threads, verify the author's claims against the current code, and review the end-to-end behavior with no compromises.
```

### 3. Thorough Review Pass

```text
Use monolith-review-orchestrator in review mode for https://github.com/DiversioTeam/Django4Lyfe/pull/2779.

Do a very thorough review. Reuse prior review context if it exists. I want business-logic issues, contract issues, tests, reuse opportunities, and any real edge cases, not just style feedback.
```

### 4. Reassessment After New Commits

```text
The author pushed updates to https://github.com/DiversioTeam/Django4Lyfe/pull/2779.

Please reassess it using the existing review context. Focus on deltas, re-check prior findings, and tell me exactly what is newly resolved, still open, newly introduced, or now moot.
```

### 5. Post Final Review

```text
Now post the final GitHub review for https://github.com/DiversioTeam/Django4Lyfe/pull/2779.

Keep one authoritative top-level review. Use inline comments only when the
exact diff anchor is genuinely stable; otherwise fold the point into the
top-level review. When inline comments are present, let the worker publish
them together with the top-level review through the worker-owned path. Approve
only if there are no legitimate blocking issues left.
```

### 6. Status-Only Read

```text
Use monolith-review-orchestrator in status mode for https://github.com/DiversioTeam/Optimo-Frontend/pull/389.

I do not want a fresh full review yet. I want the final status based on the current code plus the entire review history, including resolved threads.
```

## Slash Commands

If you prefer slash commands:

```text
/monolith-review-orchestrator:review-prs
/monolith-review-orchestrator:reassess-prs
/monolith-review-orchestrator:post-review
```

Then provide the same concrete PR URLs and review intent in the prompt that
follows.

## Prerequisites

This is a harness-local workflow plugin. It assumes:

- a Diversio monolith checkout or sibling monolith review worktree
- the monolith `scripts/` helpers and docs are present
- `uv`, `git`, and `git worktree` are installed
- GitHub auth is available if PR metadata or posting is required
- local permission to create sibling worktrees

## Helper Workflow

Use this when you want the deterministic local workflow without re-reading the
full skill docs.

The helper flow is:

```text
preflight -> resolve batch -> prepare worktree -> fetch review threads -> persist review context -> write review artifact
```

### 1. Preflight The Machine And Checkout

Why:
- fail early if this is not a real monolith checkout
- avoid discovering missing tools after worktree or review state steps
- allow an explicit `--monolith-root` override when invoking the helper from
  outside the monolith checkout

```bash
export MONOLITH_ROOT="/path/to/monolith"
cd "$MONOLITH_ROOT"

uv run --script agent-skills-marketplace/plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/preflight_review_env.py
```

### 2. Resolve One Stable Review Batch Identity

Why:
- one PR or one linked cross-repo PR pair should always map to the same batch
  key, worktree path, markdown artifact path, and state path

```bash
cd "$MONOLITH_ROOT"

uv run --script agent-skills-marketplace/plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/resolve_review_batch.py \
  --pr-url https://github.com/DiversioTeam/Django4Lyfe/pull/2779 \
  --pr-url https://github.com/DiversioTeam/Optimo-Frontend/pull/389
```

Expected shape:

```json
{
  "batch_key": "bk2779-of389",
  "worktree_path": "/path/to/monolith-review-bk2779-of389",
  "artifact_path": "/path/to/monolith-review-bk2779-of389/reviews/review-bk2779-of389.md",
  "state_path": "/path/to/monolith-review-bk2779-of389/reviews/.state/review-bk2779-of389.json"
}
```

The actual command also includes keys such as `monolith_root`, `review_dir`,
`reassess_artifact_path`, and `prs`.

### 3. Create Or Reuse The Detached Review Worktree

Why:
- keep the review run isolated
- avoid attached-branch worktree lock pain
- initialize only this worktree instead of broad monolith mutation

```bash
cd "$MONOLITH_ROOT"

uv run --script agent-skills-marketplace/plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/prepare_review_worktree.py \
  --monolith-root "$MONOLITH_ROOT" \
  --worktree-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389" \
  --submodule-path backend \
  --submodule-path optimo-frontend \
  --start-ref HEAD
```

Important:
- this helper intentionally does **not** run `scripts/update_submodules.py`
- review prep should stay narrow and not normalize unrelated submodules

### 4. Fetch Thread-Aware GitHub Review History

Why:
- resolved and outdated threads carry important review context
- the orchestrator owns a first-class GraphQL acquisition path for thread state
  and thread comments

```bash
cd "$MONOLITH_ROOT"

uv run --script agent-skills-marketplace/plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/fetch_review_threads.py \
  --pr-url https://github.com/DiversioTeam/Django4Lyfe/pull/2779 \
  --pr-url https://github.com/DiversioTeam/Optimo-Frontend/pull/389
```

### 5. Initialize Structured Review State

Why:
- markdown is for humans
- JSON state is for reassessment identity and compact review context
- follow-up passes should update the same batch state, not invent a new one

```bash
cd "$MONOLITH_ROOT"

uv run --script agent-skills-marketplace/plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/review_state.py init \
  --state-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/.state/review-bk2779-of389.json" \
  --batch-key bk2779-of389 \
  --worktree-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389" \
  --artifact-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/review-bk2779-of389.md" \
  --pr Django4Lyfe:2779 \
  --pr Optimo-Frontend:389
```

If the state file already exists and you intentionally want to replace it, add
`--force`. The default behavior refuses overwrites so reassessment history is
not destroyed accidentally.

### 6. Reassessment And Context Reuse

Why:
- load the durable local identity first
- reuse prior findings, comment-history notes, and teaching points before
  comparing deltas
- preserve repo-scoped findings and thread context across passes instead of
  replacing them with the latest pass only
- prefer recent active findings in the compact summary instead of surfacing the
  oldest still-open issues first
- compare deltas against stored state instead of guessing from the latest
  markdown file alone

```bash
cd "$MONOLITH_ROOT"

uv run --script agent-skills-marketplace/plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/review_state.py summarize-context \
  --state-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/.state/review-bk2779-of389.json"
```

Then record the new pass after reviewing:

```bash
cd "$MONOLITH_ROOT"

cat <<EOF | uv run --script agent-skills-marketplace/plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/review_state.py \
  record-review \
  --state-path "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/.state/review-bk2779-of389.json"
{
  "mode": "reassess",
  "artifact_path": "${MONOLITH_ROOT%/*}/monolith-review-bk2779-of389/reviews/review-bk2779-of389.md",
  "posting_status": "not_posted",
  "recommendation": "request_changes",
  "scope_summary": "Reassessed the linked backend and Optimo frontend PRs after follow-up commits.",
  "entries": [
    {
      "repo": "Django4Lyfe",
      "pr_number": 2779,
      "base_branch": "main",
      "head_sha": "<backend-head-sha>",
      "merge_base": "<backend-merge-base-sha>"
    },
    {
      "repo": "Optimo-Frontend",
      "pr_number": 389,
      "base_branch": "main",
      "head_sha": "<optimo-head-sha>",
      "merge_base": "<optimo-merge-base-sha>"
    }
  ],
  "comment_context": {
    "thread_source": "gh_graphql",
    "summary": "Read existing review threads, including resolved ones, before reassessing."
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

Important:
- `entries` must include every PR in the batch
- findings and inline targets should stay repo-scoped inside linked PR batches
- inline comment targets should reference active findings, not free-form IDs
- `summarize-context` is intentionally compact and should prioritize recent-pass
  context instead of replaying every historical note forever

### Visual Summary

There is also a presentation-style explainer at:

```text
~/.agent/diagrams/monolith-review-orchestrator-visual-explainer.html
```

## Notes

- The plugin uses a thread-aware GitHub acquisition helper when GitHub auth is
  available, and that deterministic path currently uses `gh`.
- The cache is strongest when you reuse the same deterministic review worktree
  and batch state across passes.
- Worktree prep should fail closed unless each review submodule is detached at
  the exact PR head SHA being reviewed.
- `post` should only run after current-head validation plus a prior substantive
  pass on the same heads, and it should consume the live-state validation token
  from that check while it is still fresh. That validation now re-reads GitHub
  from the thread-helper artifact instead of trusting caller-typed state.
- When posting is enabled, the worker revalidates the live PR and publishes the
  top-level review plus any validated inline comments atomically through local
  `gh` / `gh api`.
- This plugin is still intentionally narrow on multi-PR publish automation and
  replies to existing review threads.

## Why These Pieces Exist

```text
fetch_review_threads.py
  reads the real review discussion, including resolved/outdated threads

review_state.py
  keeps the reusable memory of what we learned

SKILL.md + references/
  explain when to use the workflow and how to interpret its output
```

Without the fetch helper, the review cache would be downstream of an incomplete
read path. Without the review-state helper, every reassessment would have to
reconstruct prior context from scratch.

## Related Files

- Skill: `skills/monolith-review-orchestrator/SKILL.md`
- Review context protocol:
  `skills/monolith-review-orchestrator/references/review-context-protocol.md`
- Workflow helpers:
  `skills/monolith-review-orchestrator/references/workflow-helpers.md`
