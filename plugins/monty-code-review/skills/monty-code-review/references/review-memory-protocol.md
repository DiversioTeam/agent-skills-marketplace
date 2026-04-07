# Review Memory Protocol

## Purpose

`monty-code-review` keeps persistent review memory by default so follow-up
reviews can focus on what actually changed instead of re-deriving the same
context every pass.

This is intentionally a **small v1** design:

- one deterministic review target at a time
- one compact current-state file
- one append-only reviews log
- one repo-local `*_review.md` file for humans and for `process-code-review`

## First Principles

Why add review memory at all:

- PR review is iterative. Reviewers come back after new commits, replies, and
  force-pushes.
- Re-reading every old review in full wastes tokens and often repeats the same
  findings.
- Free-form markdown is helpful for humans but expensive and brittle for an LLM
  to re-parse every time.

Why keep the design small:

- Every extra file becomes another source of truth.
- Every extra command becomes another workflow branch to remember.
- Every extra identity mode increases the chance of saving memory to the wrong
  place.

So this implementation deliberately subtracts:

- no multi-repo bundles
- no separate changelog file
- no comment-history persistence yet
- no reset/archive command yet

## Mental Model

Think about the feature as three layers:

1. Review target
   - "What exactly are we reviewing?" Usually one PR or one branch.
2. Memory store
   - "What durable machine-readable state should survive the next review?"
3. Human artifact
   - "What should a reviewer or engineer open in the repo?" This is still the
     repo-local `*_review.md`.

The helper script manages layer 2. The skill itself still owns the actual code
review judgment and the repo-local markdown output.

## Review Flow

```text
resolve target
    |
    v
load compact memory summary
    |
    v
run new review
    |
    +--> write repo-local *_review.md for humans
    |
    +--> append one structured review record for the next pass
```

## Quick Start

Use the helper through `uv run --script` so the inline `click` dependency is
resolved automatically:

```bash
uv run --script plugins/monty-code-review/skills/monty-code-review/scripts/review_memory.py --help

SCOPE_DIR="$(
  uv run --script plugins/monty-code-review/skills/monty-code-review/scripts/review_memory.py \
    resolve-scope \
    --provider github \
    --host github.com \
    --owner DiversioTeam \
    --repo monolith \
    --pull-number 1842 | jq -r '.scope_dir'
)"

uv run --script plugins/monty-code-review/skills/monty-code-review/scripts/review_memory.py \
  summarize-context \
  --scope-dir "$SCOPE_DIR"
```

Typical review-pass flow:

```text
1. resolve-scope
2. summarize-context
3. run review
4. record-review
```

## Default Behavior

1. Resolve a deterministic memory target before reviewing.
2. Load existing memory automatically when the target is unambiguous.
3. Ask one short clarifying question when ambiguity would change the memory
   target or dedupe behavior.
4. Use the helper to summarize memory instead of reading raw history files into
   model context.
5. After the review, write the repo-local markdown review and append one
   structured review record.

## Ask Vs Assume

Ask the user when doubt would change persisted memory state.

Ask before:

- choosing between multiple plausible PRs or branches
- deciding whether branch memory should be treated as the same thing as a later
  PR memory target
- suppressing a prior finding as "the same issue" when the match is uncertain
- reusing incremental history after a force-push or rebase when ancestry is
  broken or unclear

Do not ask for ordinary review judgment calls. In those cases, proceed and
state assumptions in the review when useful.

## Identity Rules

Resolve identity in this order:

1. Explicit user target.
2. Unambiguous current PR target.
3. Unambiguous current branch target when no PR exists.

Canonical target IDs:

- GitHub PR: `github.com/<owner>/<repo>/pull/<number>`
- Git branch: `git/<repo-key>/branch/<branch>@<base-branch-or-merge-base>`

Never use worktree names, absolute local paths, or remote aliases such as
`origin` as part of canonical identity.

Normalize GitHub host, owner, and repo values to lowercase before building the
canonical target ID.

## Timestamps

- Persist canonical timestamps in UTC only.
- Present times to the engineer in local time in chat and repo-local markdown.
- The helper may include both UTC and local-display fields in summary output,
  but UTC remains the source of truth on disk.

## Storage Root

Resolve the storage root in this order:

1. `MONTY_REVIEW_MEMORY_HOME`
2. `${XDG_STATE_HOME}/monty-code-review`
3. `${XDG_CACHE_HOME}/monty-code-review`
4. `~/.cache/monty-code-review`

Directory layout:

```text
<storage-root>/
  targets/<target-slug>--<target-hash>/
    state.json
    reviews.jsonl
```

Use restrictive permissions for new directories and files.

## Canonical On-Disk Files

### `state.json`

`state.json` is the compact current-state file.

It keeps:

- canonical target identity
- current cursor info
- latest reviewed head
- next review number
- still-open findings

Minimal shape:

```json
{
  "schema_version": 1,
  "scope_kind": "target",
  "scope_id": "github.com/diversioteam/monolith/pull/1842",
  "scope_slug": "monolith-pr-1842",
  "created_at_utc": "2026-04-04T21:15:00Z",
  "updated_at_utc": "2026-04-04T21:45:00Z",
  "last_synced_at_utc": "2026-04-04T21:45:00Z",
  "last_reviewed_head_sha": "abc123def456",
  "last_reviewed_merge_base_sha": "111aaa222bbb",
  "history_status": "linear",
  "next_review_number": 3,
  "open_findings": []
}
```

### `reviews.jsonl`

`reviews.jsonl` is the append-only review log.

Each line records one completed review pass:

- UTC timestamp
- review number
- reviewed head / merge-base
- review basis
- recommendation
- touched paths
- commits
- grouped findings: `new`, `carried_forward`, `resolved`
- repo-local markdown review file

## Markdown Compatibility Artifact

The repo-local `*_review.md` file remains required because downstream workflow
currently depends on it.

Treat the JSON-first files as the canonical memory store, then write or update
the repo-local markdown review as the readable compatibility artifact.

In short:

```text
state.json + reviews.jsonl = source of truth
repo-local markdown        = readable projection
```

## Why JSON/JSONL Instead Of Markdown

We intentionally do **not** use markdown as the canonical memory format.

Why:

- JSON objects are cheaper for helper scripts to validate and update.
- JSONL append logs make incremental history straightforward.
- The model can consume one compact summary object instead of many old review
  documents.
- Markdown stays available where humans and downstream skills still need it.

## Rebase And Force-Push Handling

If the previous head is still an ancestor of the current head, review
incrementally as normal.

If ancestry is broken:

- set `history_status` to `rewritten`
- preserve prior open findings
- re-anchor from merge-base or current diff
- ask the user when there is genuine ambiguity about whether the rewritten
  branch should continue the same memory target

## Finding Dedupe

Use stable, boring finding IDs:

```text
<rule-or-risk>|<path-or-area>|<symbol-or-context>
```

Examples:

- `tenant-scope-missing|survey/exports.py|build_rows`
- `n-plus-one|dashboardapp/service.py|get_rows`

Do not use line numbers in stable IDs.

Classify findings as:

- `new`
- `carried_forward`
- `resolved`

If a later review omits an existing open finding, keep it open until it is
explicitly resolved. Do not silently drop unresolved prior findings from
memory.

If the match is uncertain, ask before suppressing it as already known.

## Helper Script Contract

Use `uv run --script ...` so the helper's inline `click` dependency resolves
deterministically.

From the repository root, run:

`uv run --script plugins/monty-code-review/skills/monty-code-review/scripts/review_memory.py ...`

From `plugins/monty-code-review/skills/monty-code-review/`, you can instead
run:

`uv run --script scripts/review_memory.py ...`

Useful commands:

```text
resolve-scope     Create or refresh one deterministic memory scope.
summarize-context Return the compact context the model should read.
record-review     Persist one completed review pass from stdin JSON.
```

Minimal `record-review` example:

```bash
cat <<'EOF' | uv run --script plugins/monty-code-review/skills/monty-code-review/scripts/review_memory.py \
  record-review \
  --scope-dir "$SCOPE_DIR"
{
  "head_sha": "abc123",
  "history_status": "linear",
  "repo_review_file": "docs/code_reviews/pr_1842_review.md",
  "recommendation": "request_changes",
  "findings": {
    "new": [],
    "carried_forward": [],
    "resolved": []
  }
}
EOF
```

Minimum required keys:

- `head_sha`
- `history_status`
- `repo_review_file`
- `recommendation`
- `findings`

If you change the helper:

1. Keep UTC as the only persisted time format.
2. Keep the repo-local markdown review as a compatibility artifact.
3. Keep summaries compact so the feature actually saves tokens.
4. Add new files or commands only when they clearly buy more than they cost.

## Minimal Required Behavior

A valid implementation must be able to:

1. resolve a deterministic scope directory
2. load compact prior context without reading all raw history
3. determine history status (linear vs rewritten) and pass it to the helper
4. append one completed review record
5. keep unresolved findings open until they are explicitly resolved
6. keep UTC persistence and local-time presentation separate
