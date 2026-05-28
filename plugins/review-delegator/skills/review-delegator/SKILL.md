---
name: review-delegator
description: >
    Review delegator. Runs monty-v2's core analysis (intent,
    branch enumeration, adversarial inputs), then delegates specialized
    checks to focused sub-skills in parallel for deep coverage. Compiles
    findings into a single review. Use for PRs that touch 5+ files or
    multiple subsystems where a single-skill review would miss systemic issues.
user-invocable: true
argument-hint: '[--quick] [--deep] [--self-review] [--lanes=auto|on|off]'
allowed-tools: [Bash, Read, Edit, subagent, intercom]
---

# Review Delegator

Delegates a multi-skill code review by running monty-v2's core analysis,
then delegating specialized checks to focused sub-skills. Each sub-skill
handles ONE concern deeply, making it much harder to miss the patterns
that a monolithic review overlooks.

## When to Use

- PR touches **5+ files** or multiple subsystems
- PR involves **contract changes** (new fields, changed signatures)
- PR touches **models, serializers, CSV import/export, management commands,
  admin forms, or config files** — any path where data shape changes
- PR has been through **multiple review rounds** with recurring findings
- Reviewer feedback history shows **lifecycle parity, admin form, merge
  drift, or round-trip issues** were caught late
- **`--deep`** mode: any PR where correctness-critical code is touched
- PR spans **multiple repos** (backend + frontend + DS) — API contract checks

For simple 1-2 file bugfixes with no data shape changes, use
`/monty-v2-code-review:code-review` directly.

## Missed-Pattern Reference (2026 H1 Audit — 15 PRs, ~250 Review Rounds)

These are the highest-recurring patterns reviewers catch that automated checks miss.
Each maps to a Tier 1 or Tier 2 check in the delegation phase.

| Pattern | Frequency | PR Examples | Tier | Sub-Skill |
|---------|-----------|-------------|------|-----------|
| P10 Consumer obligation | ████████ | #3041, #3040, #3079, #3081 | T1 | contract-propagation |
| P17 Lifecycle parity | ████████ | #3041, #3040, #2953, #3035 | T1 | contract-propagation |
| P18 Admin three-layer | ███████  | #3017, #3040, #2953 | T1 | contract-propagation |
| **Import/Export round-trip** | **████████** | **#2974, #2953, #3035, #3034** | **T1** | **import-export-roundtrip** |
| P22 Merge drift | ██████   | #1800, #3081 | T1 | merge-drift |
| **Stale/concurrent races** | **██████** | **#3035, #3017, #3041** | **T1** | **contract-propagation †** |
| **Admin workflow atomicity** | **█████** | **#3017, #3034, #3035** | **T1** | **contract-propagation †** |
| P14 Existing DB bad state | █████    | #2953, #3041 | T2 | historical-data |
| P16 Rollback/reprocess | █████    | #3041, #3035, #2953 | T2 | historical-data |
| P23 Config import legacy | █████    | #2974, #3079 | T2 | historical-data |
| **Empty/edge/boundary** | **████** | **#1015, #1800, #2953** | **T2** | **contract-propagation †** |
| **Multi-tenant safety** | **████** | **#2974, #3041, #3034** | **T2** | **review-delegator inline** |
| **API contract/versioning** | **████** | **#1016, #1800, #2957, #3079** | **T2** | **review-delegator inline** |
| P19 Test gaps | ███      | #2997, #3034 | T2 | test-quality |
| CI gate failures | ██       | #2953, #1800 | T1 | gate-runner |

† Extended contract-propagation-check coverage (concurrency, atomicity, edge states).

## Architecture

```
Review Delegator
├── Phase 1-3: monty-v2 core (understand, enumerate, adversarial)
├── Phase 4 (delegated): Sub-skills in parallel
│   ├── /contract-propagation-check:check ← P10, P17, P18, +concurrency, +atomicity, +edges
│   ├── /import-export-roundtrip-check:check ← P26 (CSV, dict, config, admin I/O) — NEW 2026
│   ├── /merge-drift-check:check        ← P22, P24, P25
│   ├── /historical-data-check:check    ← P14, P16, P23
│   ├── /test-quality-check:check       ← P1, P12, P19, P20
│   └── /gate-runner:run                ← ruff, ty, imports, migrate
├── Phase 4b (delegated inline): Multi-tenant safety + API contract checks
├── Phase 5-6: monty-v2 (bias check, blind-spot sweep)
└── Phase 8: Compile & write review
```

Each sub-skill returns findings tagged with `[BLOCKING]`, `[SHOULD_FIX]`, `[NIT]`.
The delegator compiles all findings into a single review document.

---

## Step 1: Understand the PR

```bash
# Basic PR info
gh pr view --json number,title,url,headRefName,body,baseRefName

# Detect the base branch — defaults to the PR's target branch,
# falling back to the repo's default branch when no PR exists.
# Override by setting BASE_BRANCH before invoking.
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh pr view --json baseRefName --jq '.baseRefName' 2>/dev/null)"
fi
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name')"
fi

# Files changed
git diff --name-only origin/$BASE_BRANCH...HEAD

# Diff size
git diff --stat origin/$BASE_BRANCH...HEAD
```

Classify the PR:
- **Size**: small (1-2 files), medium (3-10 files), large (10+ files)
- **Type**: bugfix, feature, refactor, migration, chore
- **Risk areas**: models, admin, services, API, migrations, config

---

## Step 2: Run monty-v2 Core (Phases 1-3)

Run monty-v2's first three phases to understand intent, enumerate branches,
and check adversarial inputs:

```
/monty-v2-code-review:code-review Phase 1-3 only
```

This gives you:
- What problem is being solved
- Every branch in every changed function
- Input combination gaps
- Test coverage map for each branch

Hold these results — they'll be incorporated into the final review.

---

## Step 3: Delegate Specialized Checks (Parallel)

Determine lane mode first:
- `--lanes=off` → do not spawn delegated lanes; run only inline checks.
- `--lanes=on` → run delegated lanes when possible.
- `--lanes=auto` (default) → optional lanes by risk.

Risk heuristic:
- low-risk: 1-2 files and no model/risk markers
- medium/high-risk: >=3 files, models/admin/service/API changes, migrations,
  or any clear correctness-critical scope.

Transport ladder:
1. Subagent tool present → spawn dedicated review lanes as subagents.
2. Subagent unavailable + cmux/in-session split available + intercom available → spawn cmux fallback lanes and coordinate via intercom.
3. Subagent unavailable + cmux available, no intercom → spawn cmux lanes and coordinate via artifacts.
4. Neither subagent nor cmux available → inline, sequential review.

Build lane prompts from these targets:
- `reviewer-1` (correctness/regressions): contract and lifecycle risks.
- `reviewer-2` (tests/validation): test coverage, assertion strength, regressions.
- `reviewer-3` (maintainability): clarity, duplication, complexity,
  and long-term cost of implementation choices.

Use this transport preference matrix:

- Subagent path:
  - Launch lanes in one async parallel fanout so all reviewers run concurrently:
  ```text
  subagent({
    async: true,
    context: "fresh",
    parallel: [
      { agent: "reviewer", task: "reviewer-1: <correctness lane prompt>", context: "fresh" },
      { agent: "reviewer", task: "reviewer-2: <tests lane prompt>", context: "fresh" },
      { agent: "reviewer", task: "reviewer-3: <maintainability lane prompt>" }
    ]
  })
  ```
  - Use `subagent({ action: "status", id: "<run-id>" })` on the fanout run id; use `subagent({ action: "status" })` to inspect active runs when needed.
  - If a child needs blocking decision handling, the child should use:
    `intercom({ action: "ask", message: "..." })`
    and wait for the parent answer via `intercom({ action: "reply", message: "..." })` (or `reply` with `to` when multiple pending asks).
- cmux fallback path (no subagent):
  - Write lane prompt to `.pi/delegator-runs/<run-id>/reviewer-<n>-prompt.md`.
  - Spawn lane split, have child write findings to the matching `*-findings.md`.
  - Parent reads artifacts after completion.

### Always run (Tier 1 checks — highest-recurring missed patterns)

These sub-skills MUST be invoked for EVERY PR with 3+ files or any
correctness-critical change. Skip only for trivial 1-2 file changes
with no helpers, admin, models, config changes, or I/O format changes.

```
/contract-propagation-check:check
```
Covers: P10 (change propagation), P17 (lifecycle parity), P18 (admin
three-layer surface). **Also covers (2026 extension):** stale/concurrent
data races, admin workflow atomicity (A-then-B failure between steps),
and empty/null/boundary edge states. Greps ALL consumers of every changed
function, model field, and utility. Verifies lifecycle parity at every stage.
For the extension checks:
- **Concurrency**: for every state write (`.save()`, `.update()`), verify
  a concurrent edit can't corrupt data. Trace read-modify-write paths for
  missing row-version or optimistic-lock guards.
- **Admin atomicity**: for every sequential admin action (do-A-then-B),
  verify B can handle A's failure. Check that rows aren't recreated before
  prerequisite checks succeed.
- **Edge states**: for every changed function, trace the null/empty/
  boundary input values. Does the function handle `data=[]`, `None`,
  `index=-1`, or empty strings?

```
/import-export-roundtrip-check:check
```
**NEW 2026 — the #1 newly-identified missed pattern.** Covers: P26
(import/export round-trip safety). Verifies every data structure changed
in the PR can be safely round-tripped through every import/export path:
CSV export→import, dict serialize→deserialize, config export→import,
admin export→import, and management command I/O. Checks field parity,
type coherence, duplicate-row handling, empty-file handling, schema
versioning, and cross-path consistency. **Every PR that touches a model
field, serializer, CSV writer, or management command I/O format runs this.**

```
/merge-drift-check:check
```
Covers: P22 (merge drift), P24 (unrelated file regression), P25 (PR
description drift). Checks pyproject.toml/uv.lock, WhiteLabel assets,
fixture regression, and PR description accuracy. **Also covers (2026
extension):** lockfile/yarn.lock internal consistency, conftest typing
regression, and build artifact integrity.

```
/gate-runner:run
```
Covers: ruff_pr_diff.sh, ty check, local_imports_pr_diff.sh, migration
squash check. Runs the exact CI gate sequence.

### Run when relevant (Tier 2 checks)

```
/historical-data-check:check
```
Run when: migrations, config import/export, data processing, field
constraints, or sentinel values are touched. Covers: P14, P16, P23.

```
/test-quality-check:check
```
Run when: new tests added, test assertions changed, or CI tolerance
adjustments made. Covers: P1, P12, P19, P20.

### Run inline (Tier 2 checks — run by review-delegator directly)

These checks don't have standalone sub-skills; the delegator runs them
inline after sub-skill results return:

**Multi-Tenant Safety Check** — run when:
- Model fields with cross-tenant visibility change (e.g., BespokeQuestion,
  SurveyGroup, free-text)
- Querysets lose `.filter(organization=...)` or `.filter(company=...)`
- Shared resources are touched (S3 keys, tokens, cache keys, notification
  routing)
- Admin actions affect rows across company boundaries

Checklist:
```text
☐ Every new queryset includes tenant scoping (organization/company filter)
☐ Shared resources (S3 paths, tokens, cache keys) include tenant identifier
☐ Admin bulk actions don't silently affect multiple tenants' rows
☐ Cross-tenant data copy paths have explicit allowlisting (not implicit)
☐ Management commands have --organization / --company scoping
```

**API Contract / Version Compatibility Check** — run when:
- Design-system component props change (required/optional, type changes)
- API response shapes change (new/removed/renamed keys)
- Cache keys change without schema version bump
- Multi-repo PRs change contracts between repos
- Management command argument signatures change

Checklist:
```text
☐ No prop/argument became required that was previously optional
☐ No response key was removed that consumers depend on
☐ Cache key includes a schema version marker (ANALYTICS_SCHEMA_VERSION, etc.)
☐ Multi-repo PRs: version bumps sequenced correctly (backend → DS → frontend)
☐ Management commands: --flag renames documented or backward-compatible
☐ Breaking changes in published packages have a migration path or deprecation notice
```

For each lane, collect findings as machine-parseable snippets:

```text
[LANE]/[source] | [SEVERITY] | file:line | issue_class | short_issue_hash | detail | fix
```

### Delegation Completion Gate

Each sub-skill has its own completion gate. Before moving to Step 4, verify:

```text
☐ /contract-propagation-check:check returned with evidence (not "looks fine")
   └── Must include: consumer grep counts, lifecycle stage checklist,
       concurrency race audit, admin atomicity trace, edge input matrix
☐ /import-export-roundtrip-check:check returned with evidence
   └── Must include: round-trip pair matrix, field parity audit,
       type coherence verification, duplicate-row handling check
☐ /merge-drift-check:check returned with evidence (not "no drift found")
☐ /gate-runner:run returned with pass/fail for each gate
☐ /historical-data-check:check returned (if applicable)
☐ /test-quality-check:check returned (if applicable)
☐ Multi-tenant safety checked (if applicable) — tenant scoping verified
☐ API contract compatibility checked (if applicable) — versioning verified
```

**If any sub-skill returned without evidence, re-invoke it.** "No findings"
is only acceptable when accompanied by specific evidence (e.g., line citations,
grep result counts, lifecycle stage checklist).

---

## Step 4: Run monty-v2 Remaining Phases (4-6)

After sub-skills return findings, run monty-v2's per-file analysis and
bias check. **Skip Phase 7 (blind-spot sweep)** — Tier 1 checks are
already handled by the delegated sub-skills. Only run Phase 7 Tier 3
checks inline if any remain unaddressed.

```
/monty-v2-code-review:code-review Phases 4-6 only
```

This covers:
- Phase 4: Per-file analysis (correctness, types, performance, migrations)
- Phase 5: Unchanged code impact (consumer obligation — P10 already covered
  by contract-propagation-check, but Phase 5 adds the centralization
  obligation check: "does every old inline pattern now call the new helper?")
- Phase 6: Bias check (mandatory for self-review)

---

## Step 5: Compile Findings

Merge all findings from all sources using deterministic signatures:
`severity | file | issue_class | anchor_line | short_issue_hash`.
If the same signature reappears, keep one copy with stronger evidence and
clearer fix guidance.

### Deduplication rules
- Same signature, same issue class, same file/anchor → keep richer evidence version.
- Same issue class across different files or the same file/line from multiple lanes
  becomes a **systemic pattern** (stronger signal than isolated findings).

### Systemic patterns
When the same issue class appears in 2+ sub-skills or 2+ files, flag it as a
**systemic pattern** in the review summary:

```
[SYSTEMIC] Lifecycle parity: the new <helper> is applied at <stage1>
and <stage2> but missed at <stage3>, <stage4>, <stage5> across 3 files.
```

Systemic patterns are always `[BLOCKING]` unless there is explicit evidence that each finding is independent and low impact.

---

## Step 6: Write Review

Structure the final review:

1. **Summary** — what changed, review mode used, sub-skills invoked
2. **What's great** — 3-7 bullets with file references
3. **Findings** — grouped by file, then by severity:
   - `[BLOCKING]` file:line — explanation + fix
   - `[SHOULD_FIX]` file:line — explanation + fix
   - `[NIT]` file:line — explanation
   - `[SYSTEMIC]` — pattern found across multiple files/skills
4. **Branch Coverage** — from Phase 2
5. **Sub-Skill Reports** — one section per invoked sub-skill, summarizing findings
6. **Test Gaps** — what's covered, what's missing
7. **Unchanged Code Impact** — affected callers
8. **Verdict** — approve/request changes, quantified

---

## Modes

### Default (medium/large PRs)
Run all of the above. Sub-skills: always contract-propagation + merge-drift +
gate-runner; conditionally historical-data + test-quality.

### --lanes
Optional lane policy for delegated transport:
- `--lanes=auto` (default): small/low-risk PRs may stay inline; medium/high-risk PRs use delegated lanes when available.
- `--lanes=on`: always attempt delegated lanes (subject to env/runtime availability).
- `--lanes=off`: inline-only review, no delegated lanes.

### --quick
For small PRs (1-4 files). Skip sub-skills, run monty-v2 quick-pass directly.
Only invoke sub-skills if monty-v2 quick-pass flags a Tier 1 concern.

```
/monty-v2-code-review:code-review quick-pass
```

### --deep
For security-sensitive, data-migration, or multi-tenant boundary PRs.
Run ALL sub-skills including inline checks + monty-v2 deep-coverage mode
(load per-lens-checklist.md and full blind-spot-patterns.md).

```
/contract-propagation-check:check
/import-export-roundtrip-check:check
/merge-drift-check:check
/historical-data-check:check
/test-quality-check:check
/gate-runner:run
/monty-v2-code-review:code-review deep-coverage
```

Also run the inline Tier 2 checks during `--deep`:
- Multi-tenant safety check
- API contract compatibility check

### --self-review
Same as default but Phase 6 (bias check) is mandatory and runs first.
Bias check findings are listed before all other findings.

---

## Rules

- **No AI signatures** — review must look like a human wrote it.
- **Parallel by default** — sub-skills run in parallel when possible.
- **Deduplicate** — same finding from multiple sources appears once.
- **Flag systemic** — patterns across files/skills are stronger signals.
- **Sub-skills are focused** — each handles ONE concern. Don't ask
  contract-propagation-check to also check formatting.
- **Tier 1 checks are mandatory** — all six Tier 1 patterns (P10, P17, P18,
  P22, P26, CI gates) are the highest-recurring missed patterns. Never skip.
- **Import/export round-trip is the #1 newly-identified gap** — any PR
  touching data shapes runs this check. CSV export→import round-trip bugs
  account for the most review rounds across 2026 H1.
- **Concurrency is checked at contract-propagation level** — not as a
  separate sub-skill, but as an extended dimension of P17 lifecycle parity.
- **Multi-tenant and API contract checks are inline** — the delegator runs
  them directly since they require business-logic judgment that a grep-only
  sub-skill can't fully automate.

---

## Example Prompts

> `/review-delegator`
> Full review of current branch's PR.

> `/review-delegator --quick`
> Fast review for a small PR.

> `/review-delegator --deep`
> Deep review for a security-sensitive or multi-tenant PR.

> `/review-delegator --self-review`
> Self-review before pushing — bias check runs first.
