---
name: monty-v2-code-review
description: "Deep-coverage code review with mechanical branch enumeration, adversarial inputs, and self-review bias mitigation."
user-invocable: true
allowed-tools: [Bash, Read, Edit]
---

# Monty V2 Code Review

A methodology-driven code review skill. V2's value comes from mechanical
analysis (branch enumeration, input matrices, caller tracing) rather than
intuitive scanning. Works on any Python/Django codebase.

**Before starting:** Read the repo's `AGENTS.md` or `CLAUDE.md` for
project-specific rules (multi-tenant boundaries, product areas, coding
conventions). Apply those rules alongside this methodology.

## Core Priorities

1. Correctness & invariants (data integrity, idempotency, boundary conditions)
2. Security & permissions (tenant scoping, auth, PII exposure)
3. API & contracts (backwards compat, error shapes, migrations)
4. Performance (N+1s, batch vs per-row, hot-path complexity)
5. Testing (branch coverage, realistic fixtures, regressions)
6. Unchanged code impact (callers broken by new contracts)
7. Maintainability (naming, structure, reuse)
8. Style (only after everything above is addressed)

## When to Use This Skill Directly vs Delegate

**Use monty-v2 directly ONLY for PRs with 1-2 files and no correctness-critical changes.**

For any PR that meets ANY of these criteria, you MUST use the master
orchestrator or invoke the specialized sub-skills directly:

| PR characteristic | Required action |
|-------------------|----------------|
| 3+ files changed | Use master orchestrator or run sub-skills alongside monty-v2 |
| New/changed helper or normalization function | Run `/contract-propagation-check:check` (P10, P17) |
| Model field changes or new constraints | Run `/historical-data-check:check` (P14, P16, P23) |
| CSV/config/admin import-export or management-command I/O shape changes | Run `/import-export-roundtrip-check:check` (P26) |
| Admin changes (get_readonly_fields, forms, inlines) | Run `/contract-propagation-check:check` (P18) |
| pyproject.toml or uv.lock changed | Run `/merge-drift-check:check` (P22, P24, P25) |
| Bugfix or production behavior change (even with no test diff) | Run `/test-quality-check:check` (P1, P12) |
| New literals/enums/stable dicts/resources or duplicated setup | Run `/moe-skills:codebase-reuse-finder` (P8, P27, P29) |

**Why**: The Tier 1 blind-spot checks (P17, P23, P22, P18, P10, P26) are the
highest-recurring missed patterns because they require deep, systematic
investigation — grepping ALL consumers, checking ALL lifecycle stages,
auditing ALL admin surfaces, and proving round-trip integrity. A single skill
with 29 checks cannot do all of these deeply. Delegating each Tier 1 check to a
focused sub-skill forces the AI to complete the investigation before producing a
verdict.

## Diff Scope: Full Branch, Not Latest Commit

**Always review the full branch diff against the base branch.**

```bash
# Detect the actual PR target, then fall back to the repo default.
# Override by setting BASE_BRANCH before invoking.
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh pr view --json baseRefName --jq '.baseRefName' 2>/dev/null)"
fi
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name')"
fi
git fetch origin "$BASE_BRANCH"

# Full branch diff — this is your review surface
git diff origin/$BASE_BRANCH...HEAD

# List all files changed on this branch
git diff --name-only origin/$BASE_BRANCH...HEAD
```

Never use `git diff` (unstaged only) or `git diff HEAD~1` (latest commit).
Even after fixing reviewer comments, review the **entire branch's changes**.
Incremental reviews of individual commits miss systemic issues — a fix in
commit 3 can break an assumption from commit 1 that no single-commit diff
would reveal.

### Reading tactics

- **Start from the full branch diff** — all phases operate on the complete
  change set, not individual commits.
- **Targeted reads only** — when you need the full function for branch
  enumeration, read just that function (line ranges), not the whole file.
- **Targeted grep for callers** — don't speculatively read files.
- **Large PRs (10+ files)** — prioritize correctness-critical code.
  Diff-only is fine for tests, docstrings, config.

## 8-Phase Review

### Phase 1: Understand Intent

From the diff and PR description:

- What problem is being solved? Restate it.
- Which areas are touched (models, APIs, jobs, admin, tests)?
- What are the key constraints (types, nullability, scoping)?
- Classify: new feature, bugfix, refactor, migration, chore.

### Phase 2: Branch Enumeration

**The highest-value phase.** For each added/modified function in the diff:

1. **List every branch**: if/elif/else, early return, try/except,
   loop-with-break, guard clause, ternary. Number them (B1, B2, B3...).
   Do a targeted read of the full function if the diff only shows part.

2. **Name both outcomes** for two-outcome branches:
   - B3a: `if confirmation != "yes"` → cancel
   - B3b: else → dispatch

3. **Input combination matrix** for functions with optional/nullable params.
   Boolean pairs = 2^N combinations. Flag untested combinations.

4. **Map each branch to a test by name.** No test = `[SHOULD_FIX]`.
   Correctness-critical branch with no test = `[BLOCKING]`.

Output format:

```
process_invoice():
  B1: invoice is None          → test_none_invoice_raises
  B2: amount <= 0              → test_zero_amount_rejected
  B3: currency not supported   → *** NO TEST *** [SHOULD_FIX]
  B4: happy path               → test_valid_invoice_processed
  B5: duplicate invoice        → *** NO TEST *** [BLOCKING]
```

### Phase 3: Adversarial Inputs

For each public entry point (API, command, task, signal, admin action),
**consider** all 7 — only flag where code would actually break:

1. **Empty**: None, empty string, empty list, empty queryset
2. **Wrong type at an untrusted boundary**: list where dict expected, int where
   string expected. Do not demand speculative wrong-type guards inside a stable,
   precisely typed internal contract.
3. **Duplicates**: same record twice, same ID in two places
4. **Boundaries**: first/last item, page boundary, midnight UTC, max int
5. **External failure**: slow DB, cache miss, unexpected API response
6. **Idempotency**: called twice with same inputs
7. **Concurrency**: two workers run simultaneously

### Phase 4: Per-File Analysis

One pass per touched file. For each, check:

- **Correctness**: Does implementation match intent for all cases? Edge cases
  handled? Assumptions about external calls defended? Check OR predicate
  breadth (→P2) and truthy-check value collapse on Decimal/bool (→P2).
- **Types**: inventory every added `Any`, `dict[str, Any]`, cast, untyped public
  parameter, and `getattr()` on a known result. Stable shapes require an existing
  or new `TypedDict`/dataclass/protocol/precise mapping; explicit `Any` does not
  pass merely because the type gate is green. Check positional `zip`/tuple-index
  identity for silent reorder or truncation.
- **Performance**: N+1 patterns? Per-row external calls? Hot-path complexity?
- **Tests** (for test files):
  - Every fixture param in signature actually used? (`[NIT]` if not)
  - Mocks return shapes that real functions can return? (`[SHOULD_FIX]` if not)
  - Both directions of if/else tested? (`[SHOULD_FIX]` if not)
  - Time-dependent logic frozen with `@freeze_time`? (`[SHOULD_FIX]` if not)
  - Assertions check behavior, not just structure?
  - Tests hit production entry point, not just isolated helper? (→P1)
- **Tooling**: Would ruff/type gates fail? New suppressions? Also inspect added
  explicit `Any`, which static gates often permit:
  ```bash
  git diff -U0 "origin/$BASE_BRANCH...HEAD" -- '*.py' \
    | grep '^+' | grep -E '\bAny\b|dict\[str, Any\]|getattr\('
  ```
- **Necessity/simplicity**: For every new fallback, broad catch, compatibility
  flag, wrapper, or branch, cite a production caller or real failure source.
  Internal typed code should not defend against impossible states. Catch exact
  exceptions narrowly; flag test-only APIs and unused parameters.
- **Reuse**: Search for existing enums, TypedDicts, clients/resources,
  decorators/task dispatch, permission hooks, constants, query helpers, and
  test fixtures before accepting new equivalents. Verify reuse semantics and
  I/O count, not just the symbol name.
- **Migrations**: Destructive + dependent code in same deploy? Large-table
  non-nullable column with default? Multiple new migrations for the same app
  that should be squashed into one? (`[SHOULD_FIX]` — regenerate a single
  final migration before merge)
- **Transaction shape** (→P19): If the fix wraps writes in `atomic()` or
  splits into savepoints, the test must observe `connection.queries` and
  assert the SAVEPOINT/ROLLBACK shape. Otherwise the wrapping is removable
  with no test failure.
- **Admin readonly changes** (→P18): If `get_readonly_fields()` is gated on
  state, audit every `InlineModelAdmin` and `ModelForm.__init__` for the
  parent. POST-the-locked-state regression test required.
- **State-field writes** (→P16): For every new write of a state column,
  list every state transition that could land on the row again (FAILED,
  reset, retry) and verify each path writes the documented inverse.

Load `references/per-lens-checklist.md` for the expanded 10-lens version
when doing a thorough review.

### Phase 5: Unchanged Code Impact — Consumer Obligation Checklist

**For every changed function, helper, model field, or utility**, grep ALL
consumers across these paths. This is a proof of obligation — every
consumer must either handle the new contract or be explicitly exempt.

| Consumer path | What to verify |
|---------------|----------------|
| **Services** | Business logic callers handle new signature/return |
| **Admin actions** | Both row-level AND bulk-level paths updated |
| **Serializers / parsers** | Field changes reflected in serialization |
| **Import / export** | CSV generators, workbook builders, report helpers |
| **Repair / backfill** | Data migration scripts handle new format |
| **Management commands** | CLI commands using changed code |
| **Background tasks** | Celery tasks, cron jobs, signals |
| **API endpoints** | All endpoints sharing the changed query/filter |
| **Tests** | Fixtures aligned, no stale mocks of old contract |

**Centralization obligation:** If the branch extracts logic into a helper,
grep for the OLD inline pattern. Every site must call the new helper or be
listed as explicitly exempt with a reason.

**Lifecycle parity** (→P17): When the helper encodes an equivalence /
normalization / canonical form, also enumerate these lifecycle stages and
cite the line that applies the helper at each one — or document why the
stage is exempt:

| Stage | Apply helper at |
|-------|-----------------|
| Save / `pre_save` signal | Field canonicalized before persistence |
| Generate / build | Generation routines emit canonical form |
| Import (CSV / config) | Imported values canonicalized on entry |
| Export (CSV / config) | Exported values match canonical form |
| Apply / migrate | One-shot apply scripts canonicalize |
| Revert / rollback | Revert routines compare against canonical form |
| Consolidate / dedupe | Equivalence collisions detect canonical match |
| Admin `TextChoices` enum | The choice surface admits the canonical value |
| Collision surface | Raises business exception, not raw `IntegrityError` |

```bash
# Example: function was renamed or extracted
grep -rn "old_function_name\|old_inline_pattern" --include="*.py"
```

Trigger conditions:
1. **Changed signature** → grep callers, verify they handle new contract
2. **Changed model field** → grep serializers, admin, exports
3. **New setting/flag** → grep consumers, check fallbacks exist
4. **Extracted/renamed** → grep old name, verify no stale references
5. **Centralized helper** → grep old inline pattern, verify all sites migrated
6. **None of the above** → state "no impact — new code with no prior callers"

Flag each missed consumer as `[BLOCKING]`.

### Phase 6: Bias Check

**Critical when you authored the code.** Before writing findings, answer:

- What input combination did I NOT test?
- Which branch has only one direction tested?
- What assumption isn't proven by a test?

Don't write "I re-examined and found nothing." Either find something or cite
the specific evidence: "B1-B5 all mapped to tests, both directions of B3
covered, all 4 input combinations tested."

### Phase 7: Blind-Spot Sweep

The 29 historically missed patterns. **Applicable Tier 1 checks (P17, P23,
P22, P18, P10, P1, P26) cannot be skimmed inline — delegate them to focused
sub-skills.** First record applicability with evidence. P14/P23 apply when the
change touches persistence, migrations, config/import, state interpretation, or
legacy-compatible paths; P26 applies when the PR changes any CSV/config/admin/
command I/O shape or a model/serializer field that those paths serialize. Do not
silently skip them and do not force a DB audit on a docs-only change.

**Tier 1 — Must delegate (highest recurrence, missed in 4-6+ PRs each):**

| Check | Delegate to | Why delegation is mandatory |
|-------|-----------|---------------------------|
| P17: Lifecycle parity | `/contract-propagation-check:check` Step 3 | Must check 9 lifecycle stages per helper — cannot be skimmed |
| P23: Historical config reuse | `/historical-data-check:check` Step 2 | Must trace import code paths for legacy config injection |
| P22: Merge resolution drift | `/merge-drift-check:check` Steps 1-4 | Must audit pyproject, uv.lock, WhiteLabel, fixtures, config |
| P18: Admin three-layer surface | `/contract-propagation-check:check` Step 4 | Must read admin + inline + form classes in full |
| P10: Change propagation | `/contract-propagation-check:check` Step 2 | Must grep every consumer across 9 consumer paths |
| P1: Test depth | `/test-quality-check:check` Step 1 | Must trace call chain from test to production entry point |
| P26: Import/export round-trip | `/import-export-roundtrip-check:check` | Must prove changed data shapes survive every supported round-trip path |
| P14: Historical data | `/historical-data-check:check` Step 1 | Must assess existing DB rows for constraint violations |

**You are NOT done with Phase 7 until each delegated sub-skill returns its
findings.** A sub-skill finding of "clean — all stages covered" is valid
if it cites evidence. A sub-skill finding of "not checked" is NOT valid —
you must run the sub-skill.

**Tier 2 — Can do inline, but delegate for deep coverage:**
- P16: Inverse state-clearing → `/historical-data-check:check` Step 3
- P19: Transaction-shape assertions → `/test-quality-check:check` Step 3
- P20: CI-tolerant assertion safety → `/test-quality-check:check` Step 4
- P12: Wrong bug variant → `/test-quality-check:check` Step 2

**Tier 3 — Do inline (contextual only):**
- All remaining checks (P2-P9, P11, P13, P15, P21, P24, P25)

### Phase 7 Completion Gate

Before writing findings (Phase 8), verify:

```text
☐ P17: /contract-propagation-check:check returned lifecycle parity results
☐ P23: /historical-data-check:check returned legacy config results (if applicable; otherwise evidence-backed exemption)
☐ P22: /merge-drift-check:check returned merge drift audit results
☐ P18: /contract-propagation-check:check returned admin surface results
☐ P10: /contract-propagation-check:check returned consumer obligation results
☐ P1:  /test-quality-check:check returned test depth results
☐ P26: /import-export-roundtrip-check:check returned round-trip results (if applicable; otherwise evidence-backed exemption)
☐ P14: /historical-data-check:check returned existing data results (if applicable)
```

**If any applicable Tier 1 check or its evidence-backed exemption is missing,
the review is incomplete.
Do not produce a verdict.**

Load `references/blind-spot-patterns.md` and run P1–P29 mechanically. The
reference is canonical; do not maintain a second abbreviated pattern list here.
The post-cutoff additions P27–P29 are mandatory on self-review:

- precise stable shapes (`Any`, casts, positional identity)
- evidence-based defensive code and narrow exception boundaries
- repository/framework reuse with behavioral and I/O-contract verification

### Phase 8: Write Findings

Structure your review as a Markdown file:

1. **Summary** — one paragraph: what changed, what you focused on
2. **What's great** — 3–7 bullets with file references
3. **Findings** — severity-tagged, grouped by file:
   - `[BLOCKING]` file:line — explanation + fix
   - `[SHOULD_FIX]` file:line — explanation + fix
   - `[NIT]` file:line — explanation
4. **Branch Coverage** — branch map from Phase 2 with gap indicators
5. **Test Gaps** — what's covered (with counts), what's missing
6. **Unchanged Code Impact** — affected callers, or "none" with reason
7. **Verdict** — approve/request changes, quantified:
   "X branches mapped, Y tested, Z gaps"

## Severity Tags

**`[BLOCKING]`** — must fix:
- Data integrity violations (wrong scoping, wrong joins)
- Security flaws (missing auth, PII exposure)
- Contract-breaking changes without intent
- Missing tests for correctness-critical branches

**`[SHOULD_FIX]`** — important:
- Performance issues on hot paths
- Missing tests for non-critical branches
- Mock/prod shape divergence
- Time-sensitive tests without frozen time
- Untested input combinations

**`[NIT]`** — minor:
- Style, naming, docstrings
- Unused fixture parameters
- Non-critical duplication

Any `[BLOCKING]` → verdict is "request changes."

## Strictness

- Missing tests for new behavior = `[SHOULD_FIX]` minimum, often `[BLOCKING]`.
- Justify clean areas with evidence: "7/7 branches tested, 4/4 input
  combinations covered." Never just "tests look good."

### Review Completeness Rule

**A review is incomplete if ANY Tier 1 blind-spot check (P17, P23, P22, P18,
P10, P1, P26, P14) was not completed with specific evidence.**

Incomplete review indicators:
- "Lifecycle parity looks fine" ← NO. Cite each stage with line numbers.
- "No historical data issues" ← NO. Show grep results.
- "Merge drift: none" ← NO. Show `git diff --stat` against release.
- "Admin surface: OK" ← NO. List each admin/inline/form checked.
- "Tests cover it" ← NO. Show the call chain from test to production entry point.

If you cannot produce the evidence, you have not completed the check. Delegate
to the sub-skill — it will force you to produce the evidence.

### Review Modes

- **Full review (DEFAULT for 3+ file PRs)**: monty-v2 Phases 1-4 + delegate
  Tier 1 checks to sub-skills + compile. This is the ONLY mode that produces
  complete reviews for non-trivial PRs.
- **Quick-pass mode (1-2 file PRs only)**: Phases 2 (branch enumeration),
  3 (adversarial inputs). Skip `[NIT]`. Do NOT use for PRs touching helpers,
  admin, models, or config.
- **Self-review mode**: Full review + Phase 6 (bias check) is mandatory.
- **Deep-coverage mode**: Full review + load `references/per-lens-checklist.md`
  for Phase 4 + ALL sub-skills + full blind-spot-patterns.md. For security-
  sensitive, data-migration, or multi-tenant boundary PRs.

## References

- `references/per-lens-checklist.md` — expanded 10-lens checklist for Phase 4
- `references/blind-spot-patterns.md` — detailed Phase 7 blind-spot patterns with examples
- `references/style-guidelines.md` — project-specific style rules

## Example Prompts

> "Review this PR with full branch enumeration."

> "Quick review — only blocking and should-fix, skip nits."

> "Self-review my changes before I push."
