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

## Review Quality Standard

For substantive reviews, establish the intended behavior from the request and
current code, then trace the changed path through its real callers, shared
helpers, storage, and external boundaries. Inspect only the dependencies needed
to test those claims, not the whole repository by ritual. Verify fixes at the
shared root cause rather than only at the reported caller.

Prioritize correctness, security, tenant isolation, data integrity, side effects,
and actual performance regressions before naming or structure. Inspect failure,
retry, transaction, concurrency, and compatibility behavior when that path can
exercise them. Identify the concrete regression case a test should catch; do
not demand generic coverage or tests that merely duplicate implementation.
Run checks only within the authorized review scope and environment. Distinguish
executed results from code inspection and unverified hypotheses.

### Simplicity Test

For each material design change, ask what requirement each new layer serves:

- Can existing code, the standard library, or the framework express the same
  contract with fewer moving parts?
- Can unused options, duplicate rules, unnecessary state, or speculative
  fallback paths be removed instead of creating another abstraction?
- Does a helper improve its caller or remove real repetition, rather than move
  a few lines elsewhere? Does a small business change still require edits in
  many unrelated files?
- Do names expose their current values, side effects, and ordering? Are types
  and constants in a shared low-level home without importing service behavior?
- Does a proposed simplification preserve validation, tenant scope, privacy,
  transaction boundaries, error visibility, and measured performance?

Prefer deletion, reuse, or a direct implementation over new dependencies,
interfaces with one implementation, factories, or generic configuration without
a current need. Do not confuse fewer lines with simpler behavior, or remove
required recovery paths, compatibility layers, or safety checks. Read the real
callers and product requirements before calling a path unnecessary.

### Python Clarity Source And Precedence

The bundled [guide](code-clarity-best-practices.md) is a verbatim snapshot of
`DiversioTeam/Django4Lyfe:docs/code-clarity-best-practices.md` at commit
`a6badef47370f66d6c94acad61a1e28415c62b9e`:
[permanent source](https://github.com/DiversioTeam/Django4Lyfe/blob/a6badef47370f66d6c94acad61a1e28415c62b9e/docs/code-clarity-best-practices.md).
SHA-256: `cd44cfc1da956cc1ac7cd3ddc3eda373484fae31588c819f199ff400db24e775`.
It requires no sibling checkout or developer-specific absolute path.

Prefer the target repository's current guide or documented replacement. Record
its path and reviewed revision (or disclose local modifications); otherwise
identify the bundled snapshot, not an assumed latest upstream version. Refresh
this copy and provenance together when the source changes; do not silently
rewrite the snapshot while reviewing a consumer PR.

Target-repo AGENTS.md, explicit policy, and required gates remain authoritative.
The selected clarity guide takes precedence over generic review-taste defaults;
surface material policy conflicts rather than silently choosing a rule. Pass
that precedence to Monty and any delegated reviewer. In particular, do not turn
its justified exceptions for casts, forward references, or local imports into
blanket bans. Smells trigger inspection, not automatic refactors. Preserve the
guide's Must / Should / Consider distinctions and its limits on speculative
exception handling. Configured Python type gates remain blocking: detect `ty`,
then `pyright`, then `mypy`, and require configured `ty`.

### Finding Acceptance

Before accepting a finding into the final review, verify:

- It names the current location and a reachable behavior, violated rule, or
  concrete reading/maintenance burden; earlier comments alone are not proof.
- It explains the impact and gives the smallest safe correction, with relevant
  caller or regression-test evidence. No speculative architecture prescriptions.
- Severity follows impact: Must maps to blocking when violated; Should to an
  evidence-backed improvement; Consider stays optional unless real risk warrants
  escalation. A smell or personal preference alone never blocks approval.
- It belongs to the requested change or exposes a regression caused by it.
  Unrelated cleanup is a separate optional follow-up, not scope creep.
- It does not duplicate another root-cause finding or reopen a resolved nit
  without evidence of regression. A clean review needs no invented praise or nits.

Finish once the requested scope, material claims, prior findings, and applicable
contracts have been checked and real gaps addressed or explicitly reported.
Missing evidence limits the verdict; a green test suite alone does not establish
correctness. Reuse valid unchanged-input evidence instead of forcing extra passes.
Persist useful source/rationale in existing scope summaries, finding summaries,
teaching points, and Markdown artifacts; do not add a new review-state schema.

## Comment-History Workflow

For each PR:

1. Read the PR metadata, description, and changed files.
2. Read all review comments and replies.
3. When resolution or outdated-state fidelity matters, prefer a thread-aware
   source such as `gh api graphql` or the GitHub plugin workflow that exposes
   `reviewThreads`, `isResolved`, and `isOutdated`.
4. Build three buckets:
   - still legitimate
   - moot / no longer applicable
   - resolved but still useful context
5. Validate author claims against the current code instead of repeating them.

If you only have flat comments, say thread state is provisional. Still read the
comments and reuse the context.

Default acquisition path:

```bash
uv run --script plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/fetch_review_threads.py \
  --pr-url <github-pr-url> [...]
```

Use that helper whenever GitHub auth is available. Fall back to flat comments
only when the helper cannot be used, and mark thread state provisional in that
case.

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
3. `record-review` after every substantive pass.

`record-review` should persist:

- mode
- recommendation
- scope summary
- entries with repo, PR number, base branch, head SHA, and merge base for the
  full batch
- author claims checked
- comment context, including structured review-thread records when available
- findings with repo-scoped stable IDs
- teaching points
- inline comment targets

Thread-record note:

- `status` is the normalized review assessment for the thread (`open`,
  `resolved`, `moot`)
- `is_resolved` is the raw GitHub resolution state when known
- the helper should reject obviously contradictory combinations such as
  `status=open` with `is_resolved=true`

Guardrails:

- do not record half of a linked PR pair as if it were a full reassessment pass
- persisted linked-batch passes that only cover one side of the batch should be
  rejected during normalization rather than silently upgraded
- every inline comment target must include a `finding_id`, and that ID should
  exist in the active `new` or `carried_forward` findings for the pass
- omitting comment context or teaching points in a later pass should not erase
  them from `summarize-context`; the helper merges persistent context across
  passes
- `summarize-context` should stay compact by prioritizing recent-pass context
  instead of replaying every historical thread record or teaching point forever
- capped `open_findings` output should prefer the most recent surviving active
  findings, not the oldest ones still left in memory

Keep the markdown artifact for humans, but treat the JSON state as canonical for
follow-up passes.

## Inline Comment Target Shape

Persist `inline_comment_targets` only when the point has a stable current-diff
anchor and the finding is still active.

Why this shape exists:

```text
finding_id
  -> explains why the comment exists

path + line + side
  -> names one concrete diff anchor

expected_line_text
  -> helps the worker notice drift before publish
```

This is intentionally small. The state file should capture only the parts a
later pass or worker can check reliably, not a blob of prose that needs to be
reinterpreted each time.

Required shape for each target:

- `finding_id`
- `path`
- `line`
- `side`
- optional `start_line`
- optional `start_side`
- optional `expected_line_text`

Scope fields for persisted batch state:

- include `repo` and `pr_number` when the batch contains more than one PR
- those scope fields are batch identity, not part of the worker's diff-anchor
  contract itself

Rules:

- `finding_id` must reference an active `new` or `carried_forward` finding in
  the same recorded pass.
- `side` should be `RIGHT` or `LEFT`; prefer single-line `RIGHT`-side anchors
  when possible.
- `expected_line_text` should capture the visible diff text when you know it,
  so the worker can fail closed if the anchor drifts before publish.
- If you cannot name a stable diff anchor, do not persist an inline target for
  that point. Fold it into the top-level review body instead.
- Do not rely on prose-only location hints instead of anchor fields.

Practical writing rule:

```text
if you can point to one exact diff line
  -> persist an inline target

if you cannot point to one exact diff line
  -> keep the point in the top-level review body
```

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
      "merge_base": "def456"
    },
    {
      "repo": "Optimo-Frontend",
      "pr_number": 389,
      "base_branch": "main",
      "head_sha": "ghi789",
      "merge_base": "jkl012"
    }
  ],
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
      "line": 77,
      "side": "RIGHT",
      "expected_line_text": "return <RiskCardBody body={body} />;"
    }
  ]
}
EOF
```

## Author-Guiding Review Output

When posting or drafting the final review:

- keep one authoritative top-level review
- keep one inline anchor per root-cause cluster only when the diff anchor is
  genuinely stable
- avoid duplicating already-open reviewer threads
- tie each serious comment to risk or broken behavior
- give the author the smallest safe next step, not a speculative redesign
- apply the finding-acceptance rules above to delegated and main-agent findings

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
- prefer single-line `RIGHT`-side anchors and fold uncertain anchors into the
  top-level review

If a prior resolved comment still matters, mention that briefly so the author
can see the continuity without having to reconstruct the whole history.
