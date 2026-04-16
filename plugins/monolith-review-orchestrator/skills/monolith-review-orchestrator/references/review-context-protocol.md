# Review Context Protocol

Use this reference when the quality of the review depends on understanding the
whole PR history, not just the latest diff.

## Core Rule

Resolved comments are not active blockers by default, but they are still part
of the review context.

Read them because they often tell you:

- what previous reviewers already caught
- how the author said they fixed it
- which invariants or business assumptions were debated
- whether the current diff really addressed the underlying issue

Do not treat "resolved" as "irrelevant".

## Comment-History Workflow

For each PR:

1. Read the PR metadata, description, and changed files.
2. Read all review comments and replies.
3. When resolution or outdated-state fidelity matters, use the orchestrator's
   deterministic `fetch_review_threads.py` helper so the acquisition path is
   explicit and repeatable.
4. Build three buckets:
   - still legitimate
   - moot / no longer applicable
   - resolved but still useful context
5. Validate author claims against the current code instead of repeating them.

If `fetch_review_threads.py` is unavailable and thread-resolution fidelity
materially affects the result, stop and report that the run is blocked. Only
fall back to flat comments when the user explicitly accepts a provisional
context-only read that does not depend on reliable resolved/open thread state.

Default acquisition path:

```bash
uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/fetch_review_threads.py \
  --pr-url <github-pr-url> [...]
```

Use that helper whenever GitHub auth is available. If it cannot be used and the
request still depends on reliable thread state, fail closed instead of guessing.

Mental model:

```text
acquisition answers:
  "what happened in GitHub?"

persistence answers:
  "what should we remember for the next pass?"
```

The two jobs are separate on purpose. Keeping them separate makes both the
read path and the memory model easier to reason about.

## Persistent Review Context

Use `scripts/review_state.py` as the local cache for the review's durable
understanding.

Recommended flow:

1. `init` once per batch.
2. `summarize-context` before reassessment or posting.
3. `validate-live-state` before reassessment or posting. It now uses the
   `fetch_review_threads.py` artifact as a PR-url input and then performs a
   fresh live GitHub read before minting a token. For `post`, consume the
   returned `validation_token` in the posting payload.
4. `record-review` after every substantive pass.

`record-review` should persist:

- mode
- recommendation
- scope summary
- entries with repo, PR number, base branch, head SHA, and merge base for the
  full batch
- author claims checked, or `no_author_claims=true`
- comment context, including structured review-thread records when available
- findings with repo-scoped stable IDs, or `no_findings_after_full_review=true`
- teaching points
- inline comment targets
- `backend_handoff` when the batch includes Django4Lyfe

Thread-record note:

- `status` is the normalized review assessment for the thread (`open`,
  `resolved`, `moot`)
- `is_resolved` is the raw GitHub resolution state when known
- the helper should reject obviously contradictory combinations such as
  `status=open` with `is_resolved=true` or `status=resolved` with
  `is_resolved=false`

Guardrails:

- do not record half of a linked PR pair as if it were a full reassessment pass
- persisted linked-batch passes that only cover one side of the batch should be
  rejected during normalization rather than silently upgraded
- every inline comment target must include a `finding_id`, and that ID should
  exist in the active `new` or `carried_forward` findings for the pass
- `record-pass` is compatibility-only and should not be used for normal review
  runs
- omitting comment context or teaching points in a later pass should not erase
  them from `summarize-context`; the helper merges persistent context across
  all passes, then trims at the item level for compact output
- `summarize-context` should stay compact by prioritizing recent-pass context
  instead of replaying every historical thread record or teaching point forever
- capped `open_findings` output should prefer the most recent surviving active
  findings, not the oldest ones still left in memory

Keep the markdown artifact for humans, but treat the JSON state as canonical for
follow-up passes.

## Stable Finding IDs

Use a repo-scoped finding identity:

```text
(repo, pr_number, id)
```

Keep `id` itself stable and boring so findings can survive rebases and moved
lines:

```text
<repo-alias><pr>|<risk-or-rule>|<path-or-area>|<symbol-or-context>
```

Examples:

- `of389|empty-state-contract|src/cards/RiskCard.tsx|render_body`
- `bk2779|tenant-scope-missing|optimo_core/services/foo.py|get_queryset`

Do not use line numbers in stable IDs.

Classify findings as:

- `new`
- `carried_forward`
- `resolved`
- `moot`

If a finding stays open, keep carrying it forward until you can honestly mark
it `resolved` or `moot`.

## Minimal `record-review` Example

```bash
cat <<'EOF' | uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/review_state.py \
  record-review \
  --state-path "$STATE_PATH"
{
  "mode": "reassess",
  "artifact_path": "/path/to/reviews/review-bk2779-of389.md",
  "posting_status": "not_posted",
  "recommendation": "request_changes",
  "scope_summary": "Reassessed backend PR 2779 and Optimo frontend PR 389 after two follow-up commits.",
  "entries": [
    {
      "repo": "Django4Lyfe",
      "pr_number": 2779,
      "base_branch": "main",
      "head_sha": "abc123",
      "merge_base": "def456",
      "pr_state": "OPEN",
      "is_draft": false
    },
    {
      "repo": "Optimo-Frontend",
      "pr_number": 389,
      "base_branch": "main",
      "head_sha": "ghi789",
      "merge_base": "jkl012",
      "pr_state": "OPEN",
      "is_draft": false
    }
  ],
  "author_claims_checked": [
    {
      "repo": "Django4Lyfe",
      "pr_number": 2779,
      "claim": "This now scopes the queryset by tenant.",
      "status": "verified",
      "evidence": "Confirmed the service now passes the tenant-bound queryset into the reused helper."
    }
  ],
  "backend_handoff": {
    "repo": "Django4Lyfe",
    "pr_number": 2779,
    "worktree_path": "/path/to/monolith-review-bk2779-of389",
    "pr_url": "https://github.com/DiversioTeam/Django4Lyfe/pull/2779",
    "head_sha": "abc123",
    "prior_open_finding_ids": [],
    "thread_context_summary": "Fetched full GitHub thread history before invoking monty.",
    "allowed_posting_action": "request_changes"
  },
  "comment_context": {
    "thread_source": "gh_graphql",
    "summary": "Read all review threads, including resolved ones, before reassessing.",
    "threads": [
      {
        "repo": "Optimo-Frontend",
        "pr_number": 389,
        "thread_id": "PRRT_kwXYZ",
        "comment_ids": [101, 102],
        "path": "src/cards/RiskCard.tsx",
        "line": 77,
        "is_resolved": true,
        "is_outdated": false,
        "linked_finding_id": "of389|empty-state-contract|src/cards/RiskCard.tsx|render_body",
        "status": "resolved",
        "last_seen_head_sha": "ghi789",
        "summary": "Previous thread about empty body behavior; still relevant context."
      }
    ],
    "still_legit": [
      "Frontend still renders an empty body when backend returns an empty string."
    ],
    "moot_or_no_longer_applicable": [
      "An earlier thread about a missing import is no longer applicable after the component split."
    ],
    "resolved_for_context": [
      "Previous spacing/thread cleanup is resolved but explains the current component split."
    ]
  },
  "findings": {
    "new": [],
    "carried_forward": [
      {
        "repo": "Optimo-Frontend",
        "pr_number": 389,
        "id": "of389|empty-state-contract|src/cards/RiskCard.tsx|render_body",
        "severity": "blocking",
        "summary": "The empty-body case is still not handled end-to-end."
      }
    ],
    "resolved": [],
    "moot": []
  },
  "teaching_points": [
    "This flow needs one explicit empty-state contract across backend and frontend."
  ],
  "inline_comment_targets": [
    {
      "repo": "Optimo-Frontend",
      "pr_number": 389,
      "finding_id": "of389|empty-state-contract|src/cards/RiskCard.tsx|render_body",
      "path": "src/cards/RiskCard.tsx",
      "summary": "Anchor the empty-body root cause here."
    }
  ]
}
EOF
```

If a reassessment or posting run depends on current PR heads still matching the
stored batch identity, validate that from the live `fetch_review_threads.py`
artifact:

```bash
uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/review_state.py \
  validate-live-state \
  --state-path "$STATE_PATH" \
  --pr-context-path /path/to/fetch-review-threads.json
```

That command now writes a one-time live-state proof into the state file and
returns a `token`. `mode=post` must consume that token before it can record the
posting pass. The proof is intentionally short-lived; stale proofs must be
rejected and revalidated immediately before posting. The supplied artifact must
come from `fetch_review_threads.py`, and the helper re-reads GitHub before
minting the token.

## Author-Guiding Review Output

When posting or drafting the final review:

- keep one authoritative top-level review
- keep one inline anchor per root-cause cluster
- avoid duplicating already-open reviewer threads
- tie each serious comment to risk or broken behavior
- give the author a concrete next step

Top-level review shape:

1. `What's great`
2. `Findings`
3. `Prior discussion context`
4. `Validation`
5. `Next steps`

Inline comments should be compact but complete:

- what is wrong
- why it matters
- what change would fix it

If a prior resolved comment still matters, mention that briefly so the author
can see the continuity without having to reconstruct the whole history.
