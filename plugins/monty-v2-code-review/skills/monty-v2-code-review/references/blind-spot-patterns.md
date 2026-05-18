# Blind-Spot Patterns (Phase 7)

Twenty-two classes of issues consistently flagged in review. Run each check
mechanically — do not skip on the assumption "this PR doesn't look like that."

P1–P15 emerged from earlier PR cohorts. P16–P22 were added after a fifteen-PR
audit (2026-05) and capture the highest-recurring blind spots that survive
P1–P15 — particularly **lifecycle parity** (P17), **inverse state-clearing on
failure paths** (P16), and the **admin three-layer surface** (P18).

---

## P1 — Test Depth: Helper vs. Production Call Chain

For every new test, trace the call path upward:

- Does the test exercise the actual production entry point (e.g.,
  `get_analyze_inclusion_scores()`, an admin action dispatched via
  `get_actions()`, a CSV export generator)?
- Or does it only exercise an isolated helper that the production path calls?

If a PR adds helper-level tests but leaves the real production-path call chain
uncovered, flag as `[BLOCKING]` for correctness-critical paths,
`[SHOULD_FIX]` otherwise.

Ask: "Which test proves that the production entry point (not just the helper)
behaves correctly end-to-end for this change?"

### Sub-rule: Mutation check — "delete the fix, the test must fail"

Mentally revert the diff line that implements the fix. If the new test still
passes, the test is decoupled from the behavior it claims to cover. Common
causes:

- The test stubs the downstream call so the assertion never depends on the
  new logic (PR 2853 — tests stubbed `build_value_remap_index → {}`, so
  remap-aware code was never exercised).
- The mock's default truthy attributes drive the production path into a
  different branch than the one under test (PR 2853 — `MagicMock()` left
  `job.auto_calculate_disability` truthy, so `transform_row()` always took
  the disability-derivation branch regardless of the comma fix).
- The test asserts a hook was called rather than the state it should have
  produced (PR 2887 — recategorization test asserted the hook fired but not
  that derived KPI weights were restored).

Flag as `[BLOCKING]` for correctness-critical paths, `[SHOULD_FIX]` otherwise.

---

## P2 — Predicate Correctness

### OR Breadth

Spell out each OR clause and ask whether it admits rows the PR does not intend
to expose.

Trap: `display_free_text OR display_responses_without_consent` is broader than
`consent AND len(text) >= FREE_TEXT_DISPLAY_LENGTH_CUTOFF`.

### Truthy-Check Value Collapse

`if not value` treats `Decimal(0)`, `0`, `False`, and `""` as missing. If any
of those are valid, meaningful values for this field, the check is wrong.

Trap: `if not (score := scores.get(kpi))` silently converts a valid
`Decimal(0)` benchmark into `N/A`.

**Fix pattern:** Use `if value is None` or `if value is not None` for nullable
fields where zero/false/empty are valid values.

Flag truthy checks on numeric/Decimal/bool values as `[BLOCKING]`.

---

## P3 — PII / Free-Text Consent Contract

For any code that surfaces, logs, caches, or exports survey response text:

- Does it pass through the `free_text_consent` / `display_free_text` gate?
- Does it respect the permission scoping the rest of the pipeline enforces?
- Are raw write-in values (disability, ethnicity, open-ended responses) written
  to logs? Log a bounded preview or a stable ID instead.

Flag any exposure of raw free-text outside the established consent gate as
`[BLOCKING]`.

---

## P4 — Data Contract Round-Trips

For any code that remaps display values (e.g., raw `Male` → display `Men`,
or any label/code remap):

1. Grep for every reverse lookup that compares against the old raw value.
   Side-panel drilldowns, trainings endpoints, and filter predicates are the
   most common stale sites.
2. If the remap changes a `row.code` or contract key that downstream code
   compares against raw values, the click/drilldown path will silently
   collapse to an empty queryset.
3. Verify the round-trip: remap forward (display), remap backward (filter),
   and confirm both directions are tested with the new values.

### Sub-rule: Dual representation — flat field vs `*_json` mirror

When a model stores the same data in both a flat field and a JSON mirror
(e.g. `role` and `role_json["level_1"]`, `internal_role_name` and a
hierarchical `*_json`), every write path must update **both** representations
and every read path must agree on which is authoritative.

Trap (PR 2911): `apply_value_remap_rules()` rewrote the flat field but left
`*_json["level_1"]` stale; `internal_role_name` recalc read JSON first, so the
stored value depended on which path won. Following fix overcorrected and
rewrote `*_json` even when the source had explicit hierarchy levels.

Mechanical check: list every read of the JSON mirror and every read of the
flat field. If any read prefers JSON, every write must keep JSON in sync (or
delete it). Tests must exercise the case where the two representations would
disagree if the sync were missing.

Flag broken reverse lookups as `[BLOCKING]`. Flag flat/JSON divergence as
`[BLOCKING]` when downstream reads can pick the stale side.

---

## P5 — Feature Flag Guard Completeness

For any feature flag introduced or expanded:

1. List **all** entry points that can reach the flagged behavior: main
   endpoint, side panel, trainings endpoint, exports, background jobs.
2. Verify the guard is re-checked (not assumed inherited) on **every** entry
   point.
3. Verify the guard condition is as tight as the PR description states.

Trap: `max_score == 5` is not equivalent to "five-point scale company" — it
also matches `use_old_style_kpi_score_format=True` companies whose
`get_max_possible_inclusion_cell_score()` returns 5.

Flag any entry point that can reach flagged behavior without the guard as
`[BLOCKING]`.

---

## P6 — Migration State Alignment

For every migration in the diff:

1. **Validator sync** — Do the `validators=[...]` in every `AlterField` /
   `AddField` exactly match the validators on the current model field?
   A mismatch causes `makemigrations --check` drift and a broken CI gate.
2. **Reverse migration safety** — If a migration backfills data, can the
   reverse blank legitimate existing values? A reverse that resets all rows
   to the old default is lossy if any row had a non-default value.
3. **Docstring accuracy** — Does the migration docstring accurately describe
   operations and whether they are safe for live data?

Flag mismatched validators or lossy reverse migrations as `[BLOCKING]`.

---

## P7 — Audit Log / Transaction Ordering

For any log statement inside or adjacent to `transaction.atomic()`:

- Is the log emitted **after** the last fallible operation?
- If a log fires before the final `.save()`, `.bulk_create()`, or other
  fallible step, a rollback produces a misleading audit trail.

Pattern to catch:

```python
with transaction.atomic():
    obj.save()
    logger.info("Updated %s", obj)  # fires before clear_cached_queries()
    clear_cached_queries()           # if this raises, DB rolls back but log fired
```

Flag on security-sensitive operations as `[BLOCKING]`; non-sensitive as
`[SHOULD_FIX]`.

---

## P8 — Shared Constant / Helper Reuse

For any numeric literal, string constant, or logic block in the diff:

1. Search `dashboardapp/`, `survey/`, `utils/`, and `optimo_core/` for an
   existing constant or helper serving the same purpose.
2. Common traps: cutoff lengths (e.g., `2704`), sentinel ordering constants,
   normalization helpers, substring-matching helpers, validator thresholds.
3. If duplicate found, flag as `[SHOULD_FIX]` and point to the canonical
   location.

---

## P9 — CI Green Before Re-Requesting Review

When the review is complete and the PR needs changes:

- Remind the author: confirm all CI checks are green (especially ruff
  format/lint and fast checks) before re-requesting review.
- If a formatter gate is red, the review diff is not final.

---

## P10 — Change Propagation: All Consumers of Modified Contracts

**The #1 most frequent review finding.** When a function, model field,
queryset filter, or utility is changed:

1. `grep -r "function_name\|field_name" --include="*.py"` across the full
   codebase.
2. List every call site. For each, verify it handles the new contract correctly.
3. **Mandatory consumer path checklist** — check ALL of these, not just the
   obvious ones:

| Consumer path | What to verify |
|---------------|----------------|
| Services | Business logic callers handle new signature/return |
| Admin actions | Both row-level AND bulk-level paths updated |
| Serializers / parsers | Field changes reflected in serialization |
| Import / export | CSV generators, workbook builders, report helpers |
| Repair / backfill | Data migration scripts handle new format |
| Management commands | CLI commands using changed code |
| Background tasks | Celery tasks, cron jobs, signals |
| API endpoints | All endpoints sharing the changed query/filter |
| Tests | Fixtures aligned, no stale mocks of old contract |

4. **Centralization obligation:** If the branch extracts inline logic into a
   helper, grep for the OLD pattern. Every site must call the new helper or
   be listed as explicitly exempt with a reason.

Trap (PR #2836): Consent override wired into the API endpoint but missed
`_get_comments_question_descriptors`, `_collect_bespoke_and_engagement_comments_breakdown_families`,
and workbook export families. The UI showed free text exists but exports
behaved as if the flag didn't exist.

Trap (PR #2853): Comma normalization applied to direct fields but not to
remap rule matching — rules created with ASCII commas became unreachable.

### When P10 is not enough: see P17 (Lifecycle Parity)

P10 catches missed callers of one function. P17 generalizes the rule to
**lifecycle stages** — when a normalization, equivalence, or transformation
rule must be applied at every stage in a save/generate/import/export/apply/
revert/consolidate flow, P10's caller-grep alone is insufficient. Use P17's
stage checklist whenever the diff introduces a new equivalence helper, value
transformer, or canonical form.

Flag each missed consumer as `[BLOCKING]`.

---

## P11 — Sentinel State Conflation

`None`, `[]`, `""`, `False`, and `0` are distinct business states. Fixes that
merge two of them break downstream code that branches on the distinction.

Check every `.get(key, default)`, default parameter, and fallback value:

- Does `dict.get(key, [])` collapse "question not asked" (`None`) with
  "question asked but nothing selected" (`[]`)?
- Does a function default of `""` merge "not provided" with "explicitly empty"?
- Does `or []` on a nullable field erase the None signal?

Trap (PR #2855): `dict.get(key, [])` collapsed two states — downstream code
needed to distinguish "not asked" from "asked but blank" to decide whether to
write NULL or an empty array.

### Sub-rule: Six-state explicit enumeration

For every nullable / optional / multi-valued field, explicitly name which of
these six states the new contract distinguishes and which it merges:

| State | Concrete meaning |
|-------|------------------|
| `None` | Field absent / question never asked |
| `[]` | Asked, user selected nothing |
| `""` | Asked, user typed an empty string |
| `False` / `0` | Asked, user gave the falsy answer |
| Missing key | Pipeline did not produce a value |
| Sentinel string (e.g. `"N/A"`, `"PNTA"`) | Explicit user-selected pass |

Trap (PR 2887): writing `details["role_json"] = 0` to mark "no hierarchy"
downgraded surveys with real hierarchy data because downstream consumers
treated `0` as "no levels" but truthy as "levels present" — with `1` as a
valid level count.

Flag as `[BLOCKING]` when downstream code branches on a distinction the new
contract collapses; `[SHOULD_FIX]` if the collapse is harmless today but the
contract makes the meaning ambiguous.

---

## P12 — Test Targets the Wrong Bug Variant

The test must reproduce the *exact reported scenario*, not a different variant
that happens to pass through similar code.

Ask: "If the bug report says X crashes, does my test have X in its fixture,
or does it have Y which exercises the same function but not the same input?"

Trap (PR #2855): Bug was "skipped multiselect responses crash." Test used an
unmapped column (different code path) instead of a mapped-but-blank multiselect
(the actual bug).

Trap (PR #2836): Tests used rows where both `free_text` and `free_text_en` are
populated, missing the raw-text-only edge case that actually triggered the issue.

Flag as `[SHOULD_FIX]` — the test provides false confidence.

---

## P13 — Row vs Bulk Path Divergence

When admin features have separate row-level and bulk-level code paths, both
must implement the same business logic:

1. Identify both paths (e.g., single-row admin action vs queryset bulk action).
2. Compare: grouping keys, filter predicates, side effects, validation.
3. If one path has logic the other doesn't, the feature is inconsistent.

Trap (PR #2851): Row path derived `multiselect_group_key` across the whole
job, but bulk path counted only unapproved siblings — different scoping for
the same operation.

Flag path divergence as `[BLOCKING]`.

---

## P14 — Historical Data Not Addressed

A forward-only fix prevents new bad data but leaves existing broken rows:

1. Does the fix create a new data format? Are old-format rows still readable?
2. Are there existing rows with the old sentinel/NULL/wrong value?
3. Do existing remap rules, cached values, or denormalized fields need updating?

If yes, the PR needs either:
- A data migration to backfill
- A documented follow-up ticket for the backfill
- An explicit note that historical data is intentionally left as-is (with reason)

Trap (PR #2855): Fix prevented new NULL array writes but didn't repair
historical rows that already stored NULL.

Trap (PR #2853): Existing remap rules with ASCII commas remained unreachable.

### Sub-rule: Simulate the legacy row in the test fixture

The single biggest cause of "fix shipped, then we filed a follow-up bug" is
tests that only build greenfield data. Before merging, the test must include
a row that *only the legacy/buggy code path could have written* and prove
the fix handles it. Concretely:

- If the new contract distinguishes `None` from `[]`, the test must construct
  a row with the legacy NULL value and prove the fix reads it correctly.
- If the new contract introduces a normalization, the test must seed at least
  one row in the un-normalized form and prove the read path canonicalizes.
- If a JSON mirror is added, the test must include a row whose flat field is
  populated but JSON mirror is missing, and prove the read path reconciles.

Trap (PR 2886): older exported configs may carry `"NA"` rather than `"N/A"`
— legacy-row test missing on import.

Flag as `[SHOULD_FIX]` with a concrete recommendation (migrate, ticket, or
justify leaving it). Flag as `[BLOCKING]` if the fix actively breaks legacy
rows (e.g. crashes on read) rather than merely leaving them stale.

---

## P15 — Feature Flag Interaction Matrix

When a feature is gated on a flag, the guard must check the **actual
precondition**, not a correlated flag that usually agrees but can diverge:

1. List all flags that affect this feature area.
2. Enumerate the combinations where the flags disagree.
3. Verify the guard is tight — does it pass for ONLY the intended configs?

Trap (PR #2850): Guard checked `use_five_point_inclusion_scale` but the score
contract depended on `use_old_style_kpi_score_format` — a separate flag that
can be True independently, producing scores on a different scale.

Trap (PR #2836): `display_responses_without_consent=True` was OR'd with
`display_free_text=True`, bypassing the length cutoff gate for a broader set
of companies than intended.

Flag as `[BLOCKING]` when a valid flag combination bypasses the guard.

---

## P16 — Inverse State-Clearing on Failure Paths

**Severity: BLOCKING.** When a PR adds a forward-write to a state field
(timestamp, status, audit log, derived flag), the **inverse paths** (failure,
reset, reprocess-fail, validation-error, exception) almost always get missed.

The pattern: forward path writes `obj.processed_at = now()` on success; later
the row is reset, reprocessed, or hits a validation error — and the stale
"processed" timestamp is still there. Or `_mark_failed()` on a reprocess
attempt clobbers the original successful `COMPLETED` state, stranding the
job in a non-rollbackable state.

### Mechanical check

1. Grep for every place the new field is assigned (`field = ...`,
   `update_fields=["field"]`, `bulk_update(..., ["field"])`).
2. For each, list every state transition that *could land on the row again*:
   `FAILED`, `DRAFT`, `reset_to_draft`, validation-error early-return,
   `except` clauses, retry handlers.
3. Verify each one writes the documented inverse (`field = None`, restore
   previous value, or explicit "do not touch") under `update_fields`.
4. Require a regression test for each inverse path that asserts the row's
   final state.

### Reproductions

- PR 2902 (`response_creator.py:987`): added `processed_at` write on success
  but failure paths and `reset_to_draft` left stale "Processed" timestamps.
- PR 2887 (`enrichment_processor.py:2279`): `_mark_failed()` on a reprocess
  attempt clobbered the original successful `COMPLETED` state, stranding
  the job.
- PR 2895: `process()` had no equivalent of the `reprocess()` freshness
  guard, leaving the inverse path of "swap CSV before *first* completion"
  unguarded.

Flag as `[BLOCKING]`. This is a sub-class of P10/P13 specifically about
**inverse state transitions on the same column** — and it recurs strongly
enough to deserve its own check.

---

## P17 — Lifecycle Parity Across All Stages

**Severity: BLOCKING. The most frequent recurring class in the audit.**

When a normalization, equivalence, or transformation rule is introduced, it
must be applied at **every lifecycle stage**, not just the read path or one
write path. The stages reviewers expect parity across:

| Stage | Verify |
|-------|--------|
| Save / `pre_save` signal | Field is canonicalized before persistence |
| Generate / build | Generation routines emit canonical form |
| Import (CSV, config, fixtures) | Imported values are canonicalized on entry |
| Export (CSV, config, fixtures) | Exported values match the canonical form |
| Apply / migrate | One-shot apply scripts canonicalize |
| Revert / rollback | Revert routines compare against canonical form |
| Consolidate / dedupe | Equivalence collisions detect canonical match |
| Admin enum / `TextChoices` | The choice surface admits the canonical value |
| Collision / IntegrityError surface | Raises business exception, not raw `IntegrityError` |

### Mechanical check

For every new equivalence/normalization helper:

1. Enumerate every model method and service function whose logic depends on
   the same equivalence and confirm they all share **one** helper (not
   parallel ad-hoc copies). Grep for the pre-helper inline pattern.
2. For each stage in the table above, point to the line that applies the
   helper — or document why the stage is exempt.
3. Verify the admin `TextChoices` enum admits every value the helper
   produces. Consolidation routines must not skip blank-`to_value` rows that
   export/import would later reject.
4. Verify the test suite covers a "legacy row" (P14) at each lifecycle stage.

### Reproduction (PR #2853 — 10 review rounds with the same theme)

- Round 1: lookup canonicalization missed because `_apply_value_remap()` ran
  *before* `clean_comma()`.
- Round 2: hierarchy-derived path didn't apply the base-field remap.
- Round 3: rule lifecycle (`save`/`generate`/`import`/`apply`) still
  raw-keyed.
- Round 4: `revert_value_remap_rules()` collision detector keyed on raw
  `to_value`.
- Round 5: legacy ASCII-key sibling not reused on import.
- Round 6: stale ASCII sibling left active after canonical sibling won.
- Round 7: `revert` fail-closed on duplicate inactive siblings.
- Round 8: import deletes inactive siblings, erasing revert history.
- Round 9: target-side cross-partition collision raised `IntegrityError`
  instead of `ValueError`.
- Round 10: `company_name` declared comma-sensitive but missing from
  `SurveyGroupValueRemapRule.TargetField` admin enum; consolidation skipped
  blank `to_value` rows that export/import reject.

Each round was a missed lifecycle stage that the previous round did not
audit. P10 (caller grep) is necessary but not sufficient — lifecycle parity
is a stronger commitment.

Flag every missed stage as `[BLOCKING]`.

---

## P18 — Admin Three-Layer Surface (ModelAdmin / Inline / ModelForm)

**Severity: BLOCKING.** Locking parent model fields after a state transition
without locking the **related InlineModelAdmin and ModelForm rebuilds**
leaves the same contract reachable from the same UI.

### Mechanical check

For every change to `get_readonly_fields()`, `has_change_permission()`, or
state-gated edit logic in a `ModelAdmin`:

1. Grep for every `InlineModelAdmin` subclass attached to the parent.
   Verify each inline applies the equivalent gate (or has its own).
2. Grep for every `ModelForm.__init__` for the parent (and its inlines)
   that sets `self.fields[...]`, mutates `required`, or rebuilds choices.
   A form that *unconditionally* re-adds a field as required defeats the
   admin's readonly declaration: the POST will validation-fail before any
   service-layer guard runs.
3. Add a regression test that POSTs the parent admin under the readonly
   state and asserts the locked fields are not required and not persisted.

### Reproduction (PR #2895)

- `survey/admin/survey_processing.py:7355` — parent fields locked after
  DRAFT, but `EnrichmentColumnMappingInline` still allowed editing
  `mapping_type / target_field / is_approved` — same contract break, different
  surface.
- `SupplementaryEnrichmentJobForm.__init__` at `:7059` — re-added
  `match_source_column` as a required form field even when the admin
  rendered it readonly. POST with replacement CSV failed validation before
  the service guard could run.

Flag each missed surface as `[BLOCKING]`.

---

## P19 — Transaction-Shape Test Assertions

**Severity: SHOULD_FIX.** When a fix's stated goal is "wrap N writes in a
single outer `transaction.atomic()`" or "split one transaction into N
savepoints," happy-path tests still pass if you remove the wrapping. The
test must prove the SQL transaction shape, not just the final row state.

### Mechanical check

For any PR whose stated fix is a transaction-scope change:

1. Require a test using `@pytest.mark.django_db(transaction=True)` (so
   savepoints can be observed) that:
   - asserts `not connection.in_atomic_block` before the call,
   - captures `connection.queries` (or `CaptureQueriesContext`) and asserts
     the count of `SAVEPOINT` / `RELEASE SAVEPOINT` / `ROLLBACK TO SAVEPOINT`
     statements matches the intended shape,
   - induces a failure inside one inner unit and asserts only that unit
     rolled back (or all units, if the fix is a single outer atomic).
2. If the fix is "early-return inside loop after partial commits," the test
   must exercise the loop with a row that fails *after* an earlier row
   succeeded, and assert the earlier row was reverted.

### Reproductions

- PR 2896 (`survey/admin/survey_processing.py:2430`): 504-fix wraps mapping
  loop in outer transaction, but tests only check rule output — outer atomic
  could be removed without test failure.
- PR 2883: `_populate_bespoke_responses_helper()` returns early on first
  failed `rule.save()` but earlier rules in the inheritance loop already
  committed — needs an atomic-rollback regression covering "later rule
  fails, earlier rule reverted."

Flag as `[SHOULD_FIX]`.

---

## P20 — Multiplicity Preservation in CI-Tolerant Assertions

**Severity: SHOULD_FIX.** When a parallel-CI test is made "tolerant of
leaked rows" by switching from `assertEqual(list, expected)` to a `set`,
`>=`, or `subset` assertion, the original "exactly once" contract silently
disappears. A regression that double-processes the test's own rows still
passes the relaxed assertion.

### Mechanical check

Any time a test changes from list-equality to a set or `>=` assertion:

1. Require a `Counter(...)` of expected IDs and an `== 1` (or expected
   multiplicity) assertion **for the IDs the test owns**. Leaked-org
   tolerance and exact-once enforcement are not mutually exclusive.
2. Require numeric totals to be scoped to the test-owned subject
   (`employee_results`, `company_results`) rather than to a global
   "process-all" aggregate.
3. Timestamp regressions: `>= original_timestamp` is a weaker contract than
   `> original_timestamp`. If the fix is "rewrite the timestamp on
   reprocess," the assertion must be strict-greater.

### Reproductions

- PR 2902 (`test_map_automation_service.py:963, :950, :888`): subset
  tolerance hid duplicate processing; reviewer asked for
  `Counter(seen_org_ids)` exact-multiplicity in three separate places.
- PR 2902: `test_completed_job_can_be_reprocessed` used `>=` against the
  first run's timestamp — a regression that leaves timestamps untouched
  would still pass.

Flag as `[SHOULD_FIX]`.

---

## P21 — Classifier-vs-Parser Range Parity

**Severity: BLOCKING.** When a heuristic auto-classifier names a downstream
type (`nps_1_to_5`, `multi_select`, `numeric_int`), the parser/populator
that *reads* that type must accept every input the classifier admits. A
permissive classifier feeding a clamping parser silently collapses
distributions.

### Mechanical check

For every new auto-classification heuristic that emits a `question_data_type`
or equivalent tag:

1. Find the parser/populator that reads that tag (grep for the constant or
   enum value).
2. Compare the value range the classifier accepts to the range the parser
   preserves. If the parser clamps or buckets, narrow the classifier or
   document the lossy mapping with a stored-value test.
3. If the classifier admits adjacent types (e.g. `multiple_choice` *and*
   `multi_select`), confirm the downstream population code does not hard-code
   one specific tag.

### Reproductions (PR #2904)

- `_is_nps_1_to_5()` accepted 0..4 / 0..6 but `parse_nps_weight(highest=5)`
  clamps — collapsed `0,1 → 1`.
- Including `multiple_choice` in the scoring branch let checkbox groups
  become NPS, conflicting with grouped-rule `multi_select` requirement and
  population code that hard-codes `question_data_type = "multi_select"`.

Flag as `[BLOCKING]`.

---

## P22 — Merge Resolution Drift on Unrelated Files

**Severity: BLOCKING.** Long-running feature branches that merge from older
bases regress `pyproject.toml` / `uv.lock` versions, and revert independent
improvements (white-label asset URL, typed test fixtures, `ty` cleanups)
when the merge was resolved naively. CI green (P9) does not catch this — a
downgraded version still passes tests.

### Mechanical check

Before requesting review on any branch that merged from `release` more than
once:

```bash
# Version files must move forward, never backward
git diff origin/release -- pyproject.toml uv.lock

# Anything in unrelated areas that the branch reverted
git diff origin/release --stat -- ':!<your-feature-area>'
```

For each non-zero diff outside the stated feature area, justify the change
or restore the `release` version.

### Reproductions (all PR #2896)

- `pyproject.toml` / `uv.lock` rolled back from `2026.04.29-2` to
  `2026.04.28`.
- `dashboardapp/utility/white_label.py` reverted `_dashboard_asset_url()`
  helper to a hard-coded prod CA S3 URL.
- `dashboardapp/tests/test_models.py:779` reverted typed `_event_uuid()`
  helper, breaking `ty`.

Flag as `[BLOCKING]` — these regressions land silently and ship the next
release.
