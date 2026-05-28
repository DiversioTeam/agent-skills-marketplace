---
name: review-delegator
description: >
    Review delegator. Runs monty-v2's core analysis (intent,
    branch enumeration, adversarial inputs), then delegates specialized
    checks to focused sub-skills in parallel for deep coverage. Compiles
    findings into a single review. Use for PRs that touch 3+ files or
    multiple subsystems where a single-skill review would miss systemic issues.
user-invocable: true
argument-hint: '[--quick] [--deep] [--self-review] [--lanes=auto|on|off]'
allowed-tools: [Bash, Read, Edit]
---

# Review Delegator

Delegates a multi-skill code review by running monty-v2's core analysis,
then delegating specialized checks to focused sub-skills. Each sub-skill
handles ONE concern deeply, making it much harder to miss the patterns
that a monolithic review overlooks.

## When to Use

- PR touches **3+ files** or multiple subsystems
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
- **Risk level**:
  - `low` = 1-2 files, no high-risk markers, no cross-cutting patterns.
  - `medium` = 3-7 files, or clearly scoped but with one risk marker.
  - `high` = 8+ files, or any security/contract/data/migration/correctness-critical scope.
- **Risk markers** (each adds +1): models/admin, API/serializers/contracts, migrations, auth/rbac/permissions, background jobs, settings/feature flags, raw SQL/reporting queries, financial/stateful workflows.
- **Type**: bugfix, feature, refactor, migration, chore

Optional preflight risk score (>=3 => high):
`risk_score = model_risk_count + critical_path_files + dependency_risk + change_surface`.

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
- `--lanes=off` → do not spawn delegated lanes; run all relevant checks inline.
- `--lanes=on` → always attempt delegated transport.
- `--lanes=auto` (default) → auto-expand by risk.

Lane policy in `auto`:
- `low` risk: keep inline-first; run 1 focused delegated lane if no clear blocker.
- `medium` risk: run 3 baseline lanes.
- `high` risk: run baseline lanes + all applicable specialist lanes.

Build reviewer lane map from PR risk profile:

**Baseline lanes (always enabled when lanes are enabled):**
- `reviewer-1` (correctness/regressions): contract, lifecycle, and data-shape risks.
- `reviewer-2` (tests/validation): test coverage, assertion strength, regressions.
- `reviewer-3` (maintainability): duplication, complexity, API ergonomics, long-term debt.

**Specialist lanes (high-risk only):**
- `reviewer-4` (security & trust): auth, RBAC, boundary checks, secret handling, injection surface.
- `reviewer-5` (data integrity): migrations, backfills, idempotency, historical state cleanup, rollback behavior.

Transport ladder:
1. Subagent tool present: spawn lanes as async parallel fanout (`parallel`).
2. Subagent unavailable + cmux split present + `pi-intercom` available: spawn seeded cmux lanes and coordinate with intercom.
3. Subagent unavailable + cmux split present, no intercom: spawn seeded cmux lanes and coordinate via artifacts.
4. Neither subagent nor cmux available: inline specialist pass in the current session for each active lane in sequence (no silent downgrade).

Transport requirements:
- Feature-detect tools and use only their documented runtime signatures; do not
  assume a specific subagent or messaging schema.
- With native subagents, launch the enabled lanes as one fresh-context,
  read-only parallel fanout and join them through the runtime's documented
  status or wait mechanism.
- Include only lanes justified by the risk profile.
- With cmux, write each prompt to
  `.pi/delegator-runs/<run-id>/reviewer-<n>-prompt.md`, then collect the matching
  `*-findings.md` and `*-done.md` artifacts.
- Route blocking decisions through verified, explicitly addressed child-parent
  messaging. If unavailable, use `*-questions.md` artifacts; never guess.
- The parent is the sole synthesizer and writer under every transport.

### Always run (Tier 1 checks — highest-recurring missed patterns)

Run Tier 1 checks in all delegated modes and for every medium/high-risk or
correctness-critical change. When `--lanes=off`, run the same relevant checks
inline rather than silently reducing review depth.

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

Before moving to Step 4, verify completion with the following minimum evidence:

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

**If any sub-skill returns without evidence, re-invoke it.** Accept "no findings"
only with explicit evidence such as anchor references, grep counts, checklist
output, lifecycle-stage analysis, or a full file sweep.

If delegated transport is unavailable, require at least two inline lane prompts
(`reviewer-1`, `reviewer-2`) plus baseline `monty-v2` phases so review depth is not reduced.

---

## Step 4: Run monty-v2 Remaining Phases (4-6)

After sub-skills return findings, run monty-v2's per-file analysis and
bias check, including a full blind-spot sweep when needed.

Always run:

```
/monty-v2-code-review:code-review Phases 4-6 only
```

Run additional blind-spot coverage when any condition applies:
- high-risk PR
- `--quick` path on a medium/high PR
- only inline transport was possible
- any lane returned ambiguous or low-confidence findings

```
/monty-v2-code-review:code-review Phases 4-7 only
```

This covers:
- Phase 4: Per-file analysis (correctness, types, performance, migrations)
- Phase 5: Unchanged code impact (consumer obligation — P10 already covered
  by contract-propagation-check, but Phase 5 adds centralization verification
  for helper/lifecycle migration)
- Phase 6: Bias check (mandatory for self-review)
- Phase 7: Blind-spot sweep (Tier-3 style systematic gap finder)

---

## Step 5: Compile Findings

Merge all findings from all sources using deterministic signatures:
`severity | file | issue_class | anchor_line | short_issue_hash`.
If the same signature reappears, keep one copy with stronger evidence and
clearer fix guidance.

### Deduplication rules
- Use this dedupe key exactly: `severity | file | issue_class | anchor_line | short_issue_hash`.
- Keep **exact duplicates** only when key, source, and root evidence are the same.
- When sources disagree or add materially different proof, keep both findings and add a short **Evidence Notes** section.
- Keep all findings with same issue class only if they are truly independent (different root cause or affected surfaces).
- Same issue class in multiple files is only escalated to systemic when there is
  shared mechanism evidence (same failing pattern across a shared code path, shared
  migration boundary, or repeated boundary violation).

### Systemic patterns
When the same issue class appears in >=2 files and is traced to a shared mechanism,
mark as systemic in the summary:

```
[SYSTEMIC] Lifecycle parity: the new <helper> is applied at <stage1>
and <stage2> but missed at <stage3>, <stage4>, <stage5> across 3 files.
```

Systemic patterns are `[BLOCKING]` unless evidence explicitly shows each finding is
independent and low impact. If evidence is mixed (systemic + local), keep one
systemic summary plus individual local findings.

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
For low-risk PRs only (typically small PRs: 1-2 files, no high-risk markers).
Run one-pass monty-v2 quick and then run at least one guard-lane baseline check:

```bash
/monty-v2-code-review:code-review quick-pass
/contract-propagation-check:check
/merge-drift-check:check
/gate-runner:run
```

For medium/high-risk PRs, do not use quick as a blind pass; escalate to default mode
with lanes and full minimum gate. Use `--quick` only when the user explicitly wants a
preliminary signal, then call for full mode next.

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
- **Tier 1 checks are mandatory unless explicitly constrained by `--quick` low-risk mode:**
  P10, P17, P18, P22, P23, P24, P25, P26, and CI gates. Never skip them for
  medium/high-risk PRs.
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
