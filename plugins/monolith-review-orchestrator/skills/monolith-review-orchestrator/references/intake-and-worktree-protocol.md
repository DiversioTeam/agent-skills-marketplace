# Intake And Worktree Protocol

Use this reference when the user wants the review workflow automated rather than
manually driven.

Prefer these helpers over ad-hoc reconstruction:

- `scripts/preflight_review_env.py`
- `scripts/resolve_review_batch.py`
- `scripts/prepare_review_worktree.py`
- `scripts/fetch_review_threads.py`
- `scripts/review_state.py`

If you need the "why" behind those helpers, also read:

- `references/workflow-helpers.md`

## Essential Intake Fields

Collect only what is missing:

- review mode: `status`, `review`, `reassess`, `post`
- PR URLs
- local worktree path if one already exists
- local submodule path and branch per PR if already checked out
- whether the run is read-only or local mutation is allowed
- whether an existing dirty worktree may be reused
- whether tests/builds should run or this is code-reading only
- which PR is authoritative if linked PR verdicts diverge
- whether GitHub posting is allowed now
- if posting is allowed, whether this run is `COMMENT`, `REQUEST_CHANGES`, or
  `APPROVE` eligible
- whether parallel sub-agents are allowed

If the user says "it's already checked out", prefer asking for the local path
only if it was omitted and you cannot infer it.

Safe defaults when omitted:

- local mutation: no
- dirty worktree reuse: no
- tests/builds: code-reading only
- GitHub posting: no
- parallel sub-agents: no

## Deterministic Batch Key

Build a stable batch key from the sorted PR set:

1. Map repo to a short alias.
2. Sort by alias, then PR number.
3. Concatenate as `<alias><pr>`.
4. Join multiple entries with `-`.

Suggested aliases:

- `monolith` -> `mono`
- `backend` -> `bk`
- `frontend` -> `fe`
- `optimo-frontend` -> `of`
- `design-system` -> `ds`
- `infrastructure` -> `infra`
- `diversio-serverless` -> `sls`
- `monolith` -> `mono`

Examples:

- monolith PR 123 -> `mono123`
- backend PR 2779 -> `bk2779`
- backend PR 2779 + optimo-frontend PR 389 -> `bk2779-of389`

In v1, a linked PR pair is intentionally cross-repo only.

Use `scripts/resolve_review_batch.py` so the model does not re-implement this
logic inconsistently.

## Deterministic Worktree Name

Default worktree path:

- sibling to the monolith root
- `../monolith-review-<batch-key>`

Examples:

- `../monolith-review-bk2779`
- `../monolith-review-bk2779-of389`

This is deterministic, short enough to scan in tabs, and stable across
reassessment passes.

## Reuse vs Create

### Reuse

Reuse an existing deterministic worktree when:

- the path exists and is registered in `git worktree list --porcelain`, or
- the user explicitly points to it

On reuse:

- inspect `git status --short`
- do not discard local changes silently
- if dirty and reuse was not explicitly allowed, stop
- fetch and refresh only what is needed

### Create

Create the deterministic worktree when:

- no reusable worktree exists, and
- the user did not point you at a prepared path

Preferred bootstrap sequence:

```bash
git worktree add --detach ../monolith-review-<batch-key> <monolith-start-ref>
git submodule update --init -- <review-batch-submodule>...
```

Choose `<monolith-start-ref>` conservatively:

- default to the current monolith `HEAD` unless the user asked for a different
  monolith branch
- the monolith repo is usually just the harness container here; the important
  review refs live in the relevant submodules

Why direct `git worktree`:

- `scripts/create_worktree.py` is interactive and expects a TTY
- deterministic automation should not depend on prompt-driven selection

Use `scripts/prepare_review_worktree.py` to encapsulate this flow.

## Safe Refresh Pattern

Inside the chosen worktree:

```bash
git fetch --all --prune
git submodule update --init -- <review-batch-submodule>...
```

Then, for each relevant submodule:

```bash
git fetch --all --prune
git status --short
```

For the actual review ref:

- prefer `git switch --detach <remote-ref-or-sha>` over attaching a local branch
- use an attached local branch only when the user explicitly asked for that
  behavior or the local path is already intentionally configured that way

Do not use `uv run scripts/update_submodules.py` as routine refresh here. It is
a mutating branch-policy updater for the monolith, not a safe read-only review
prep helper.

Only adjust refs that belong to the review batch.

## Structured State

Do not rely on markdown artifacts alone for reassessment identity.

Do not treat resolved review threads as disposable either. Persist the compact
context that explains what prior comments said, which ones are still
legitimate, which became moot, and which resolved comments still matter for
understanding the current code.

Persist a structured local state file keyed by the batch key. Minimum fields:

- repo
- PR number
- base branch
- head SHA
- merge base
- worktree path
- artifact path
- review pass number
- posting status

For substantive passes, also persist:

- stable finding IDs with `new`, `carried_forward`, and `resolved` buckets
- author claims checked
- comment-context buckets:
  - still legitimate
  - moot / no longer applicable
  - resolved but still useful context
- teaching points and inline comment targets

Reassessment should load this state before comparing deltas.

Use `scripts/review_state.py` for initialization, compact context lookup, and
review recording.

## Combined Review Artifact Path

Default combined artifact path:

- `reviews/review-<batch-key>.md`

Reassessment default:

- `reviews/review-<batch-key>-reassess.md`

If the user wants one rolling file instead, update the existing artifact rather
than creating a second one.
