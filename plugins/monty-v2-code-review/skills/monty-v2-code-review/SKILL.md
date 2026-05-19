---
name: monty-v2-code-review
description: "Deep-coverage code review with mechanical branch enumeration, adversarial inputs, and self-review bias mitigation."
user-invocable: true
allowed-tools: [Bash, Read, Edit, Glob, Grep]
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
| New/changed helper or normalization function | Run `/contract-propagation-check:contract-propagation-check` (P10, P17) |
| Model field changes or new constraints | Run `/historical-data-check:historical-data-check` (P14, P16, P23) |
| Admin changes (get_readonly_fields, forms, inlines) | Run `/contract-propagation-check:contract-propagation-check` (P18) |
| pyproject.toml or uv.lock changed | Run `/merge-drift-check:merge-drift-check` (P22, P24, P25) |
| Bugfix PR | Run `/test-quality-check:test-quality-check` (P1, P12) |

**Why**: The Tier 1 blind-spot checks (P17, P23, P22, P18, P10) are the
highest-recurring missed patterns because they require deep, systematic
investigation — grepping ALL consumers, checking ALL lifecycle stages,
auditing ALL admin surfaces. A single skill with 25 checks cannot do
all of these deeply. Delegating each Tier 1 check to a focused sub-skill
forces the AI to complete the investigation before producing a verdict.

## Diff Scope: Full Branch, Not Latest Commit

**Always review the full branch diff against the base branch.**

```bash
# Detect the base branch — defaults to the repo's default branch.
# Override by setting BASE_BRANCH before invoking (e.g., BASE_BRANCH=release).
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name')"
fi

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
2. **Wrong type**: list where dict expected, int where string expected
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
- **Types**: Precise types or `dict[str, Any]`? Invariants documented?
- **Performance**: N+1 patterns? Per-row external calls? Hot-path complexity?
- **Tests** (for test files):
  - Every fixture param in signature actually used? (`[NIT]` if not)
  - Mocks return shapes that real functions can return? (`[SHOULD_FIX]` if not)
  - Both directions of if/else tested? (`[SHOULD_FIX]` if not)
  - Time-dependent logic frozen with `@freeze_time`? (`[SHOULD_FIX]` if not)
  - Assertions check behavior, not just structure?
  - Tests hit production entry point, not just isolated helper? (→P1)
- **Tooling**: Would ruff, type checker flag anything? New `# noqa` suppressions?
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

The 25 historically missed patterns. **Tier 1 checks (P17, P23, P22, P18, P10,
P1) CANNOT be done inline — they require deep, systematic investigation.
You MUST delegate them to the focused sub-skills.**

**Tier 1 — Must delegate (highest recurrence, missed in 4-6+ PRs each):**

| Check | Delegate to | Why delegation is mandatory |
|-------|-----------|---------------------------|
| P17: Lifecycle parity | `/contract-propagation-check:contract-propagation-check` Step 3 | Must check 9 lifecycle stages per helper — cannot be skimmed |
| P23: Historical config reuse | `/historical-data-check:historical-data-check` Step 2 | Must trace import code paths for legacy config injection |
| P22: Merge resolution drift | `/merge-drift-check:merge-drift-check` Steps 1-4 | Must audit pyproject, uv.lock, WhiteLabel, fixtures, config |
| P18: Admin three-layer surface | `/contract-propagation-check:contract-propagation-check` Step 4 | Must read admin + inline + form classes in full |
| P10: Change propagation | `/contract-propagation-check:contract-propagation-check` Step 2 | Must grep every consumer across 9 consumer paths |
| P1: Test depth | `/test-quality-check:test-quality-check` Step 1 | Must trace call chain from test to production entry point |
| P14: Historical data | `/historical-data-check:historical-data-check` Step 1 | Must assess existing DB rows for constraint violations |

**You are NOT done with Phase 7 until each delegated sub-skill returns its
findings.** A sub-skill finding of "clean — all stages covered" is valid
if it cites evidence. A sub-skill finding of "not checked" is NOT valid —
you must run the sub-skill.

**Tier 2 — Can do inline, but delegate for deep coverage:**
- P16: Inverse state-clearing → `/historical-data-check:historical-data-check` Step 3
- P19: Transaction-shape assertions → `/test-quality-check:test-quality-check` Step 3
- P20: CI-tolerant assertion safety → `/test-quality-check:test-quality-check` Step 4
- P12: Wrong bug variant → `/test-quality-check:test-quality-check` Step 2

**Tier 3 — Do inline (contextual only):**
- All remaining checks (P2-P9, P11, P13, P15, P21, P24, P25)

### Phase 7 Completion Gate

Before writing findings (Phase 8), verify:

```text
☐ P17: /contract-propagation-check:contract-propagation-check returned lifecycle parity results
☐ P23: /historical-data-check:historical-data-check returned legacy config audit results
☐ P22: /merge-drift-check:merge-drift-check returned merge drift audit results
☐ P18: /contract-propagation-check:contract-propagation-check returned admin surface results
☐ P10: /contract-propagation-check:contract-propagation-check returned consumer obligation results
☐ P1:  /test-quality-check:test-quality-check returned test depth results
☐ P14: /historical-data-check:historical-data-check returned existing data results (if applicable)
```

**If any Tier 1 check is missing from the review, the review is incomplete.
Do not produce a verdict.**

**From first 20 PR analysis:**
1. **Test depth** — does the test hit the production entry point, or just a helper?
   `[BLOCKING]` if the real call chain is uncovered.
2. **Predicate correctness** — do OR conditions admit unintended rows? Does
   `if not value` collapse `Decimal(0)` / `False` / `0` into the wrong branch?
   `[BLOCKING]` on numeric/Decimal/bool values.
3. **PII / free-text consent** — any survey text surfaced must pass through the
   established consent gate. `[BLOCKING]` if bypassed.
4. **Remap round-trips** — if a value is remapped (e.g. `Male→Men`), do all
   reverse lookups (side panel, drilldowns, trainings) use the new value?
   `[BLOCKING]` if broken.
5. **Feature flag completeness** — is the guard checked on ALL entry points
   that reach the flagged behavior? `[BLOCKING]` if any path skips the check.
6. **Migration alignment** — do `AlterField` validators match the model?
   Can the reverse migration blank live data? `[BLOCKING]` if mismatched.
7. **Audit log ordering** — inside `transaction.atomic()`, logs must fire AFTER
   the last fallible step. `[BLOCKING]` on security-sensitive ops.
8. **Constant/helper reuse** — search for existing constants before introducing
   new literals. `[SHOULD_FIX]` if duplicate found.
9. **CI green** — remind author to confirm CI passes before re-requesting review.

**From latest 10 PR analysis:**
10. **Change propagation** — grep ALL consumers of any changed function, model
    field, queryset filter, or utility. If the fix touches 1 call site, find
    every other site that shares the same contract. `[BLOCKING]` per missed site.
11. **Sentinel state conflation** — `None` vs `[]` vs `""` vs `False` are
    distinct business states. Does `dict.get(key, [])` collapse "not asked"
    (None) with "asked but empty" ([])?  Does a default parameter merge two
    meaningful states? `[BLOCKING]` if downstream code branches on the
    distinction.
12. **Test targets the wrong bug variant** — does the test reproduce the
    *reported* scenario, or a different one? If the bug is "skipped multiselect
    crashes," the test must have a mapped-but-blank multiselect, not an unmapped
    column. `[SHOULD_FIX]`.
13. **Row vs bulk path divergence** — when admin features have separate row-level
    and bulk-level code paths, do both implement the same logic? Check for
    grouping keys, filter predicates, and side effects that exist in one path
    but not the other. `[BLOCKING]` if they diverge.
14. **Historical data not addressed** — does the fix prevent new bad data but
    leave existing stale/broken rows? Existing remap rules, NULL arrays, or
    wrong sentinel values may need a backfill or data migration. `[SHOULD_FIX]`.
15. **Feature flag interaction matrix** — is the guard checking the actual
    precondition or a correlated flag? Enumerate all flag combinations and
    verify the gate is tight. `[BLOCKING]` if a valid configuration bypasses
    the guard.

**From latest 15 PR analysis (2026-05):**
16. **Inverse state-clearing on failure paths** — every forward write of a
    state field (timestamp, status, audit flag) must have a documented
    inverse path on FAILED / reset / reprocess-fail / exception with a
    regression test. `[BLOCKING]` per missed inverse.
17. **Lifecycle parity across all stages** — when an equivalence or
    normalization helper is introduced, it must be applied at save,
    generate, import, export, apply, revert, consolidate, and the admin
    `TextChoices` enum. P10 (caller grep) is necessary but not sufficient;
    cite the line at every stage or document why the stage is exempt.
    `[BLOCKING]` per missed stage. **Highest-recurring class in the audit.**
18. **Admin three-layer surface** — `get_readonly_fields()` changes must be
    mirrored on every `InlineModelAdmin` for the parent and any
    `ModelForm.__init__` that re-adds fields as required. POST-the-locked-
    state regression test required. `[BLOCKING]` per missed surface.
19. **Transaction-shape test assertions** — when the fix is "wrap N writes
    in atomic" or "split into savepoints," the test must use
    `django_db(transaction=True)`, observe `connection.queries`, and prove
    the SAVEPOINT/ROLLBACK shape — not just the final row state.
    `[SHOULD_FIX]`.
20. **Multiplicity preservation in CI-tolerant assertions** — when a test
    is relaxed from list-equality to set/`>=`/subset for parallel-CI
    tolerance, add `Counter(...)` exact-multiplicity for test-owned IDs
    and scope numeric totals to the test subject. Strict-greater on
    timestamp regressions. `[SHOULD_FIX]`.
21. **Classifier-vs-parser range parity** — auto-classification heuristics
    that emit a downstream type (`nps_1_to_5`, `multi_select`, etc.) must
    accept only inputs the parser preserves. Permissive classifier feeding
    a clamping parser collapses distributions. `[BLOCKING]`.
22. **Merge resolution drift on unrelated files** — `pyproject.toml`,
    `uv.lock`, and unrelated areas must move forward only.
    `git diff origin/$BASE_BRANCH -- pyproject.toml uv.lock` and a stat-diff of
    files outside the feature area. CI green does not catch this.
    `[BLOCKING]` per silent regression.

**From latest 15 PR analysis — high-recurrence additions (2026-05):**
23. **Historical config reuse bypass** — when a fix prevents new bad data,
    test importing a LEGACY config (pre-fix export) through the new code
    path. Config export/import can preserve old sentinel values, wrong
    enum entries, and stale overrides that re-introduce the exact bug the
    fix is meant to prevent. `[BLOCKING]` if a legacy import recreates
    the bad state. **Second-highest-recurring class.**
24. **Merge drift on unrelated files** — beyond pyproject.toml/uv.lock,
    also check for: WhiteLabel asset regression, fixture type cleanup
    regression, config constant regression, test utility regression.
    `git diff origin/$BASE_BRANCH --stat` and audit any file outside the
    feature area that differs. `[BLOCKING]` per silent regression.
25. **PR description / migration numbering drift** — the PR body references
    a migration name/number that no longer matches the branch. Check the
    PR description's migration references against the actual migration
    files on the branch. `[SHOULD_FIX]` if mismatched — it confuses
    operators during deployment.

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
P10, P1, P14) was not completed with specific evidence.**

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
