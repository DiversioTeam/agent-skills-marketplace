# Per-Lens Micro-Checklist (Phase 4)

Run through these lenses for each touched file or logical area.

## 1. API Surface & Naming

- Do names accurately reflect behavior and scope (especially org/company/year/quarter)?
- Are parameters and returns typed and documented where non-trivial?
- Are names specific enough (avoid generic `data`, `obj`, `item`)?
- Are docstrings present for public/non-trivial functions?

## 2. Structure & Responsibilities

- Does each function/class do one coherent thing?
- Are I/O, business logic, formatting, and error handling separated?
- Are large "kitchen-sink" functions candidates for refactoring?

## 3. Correctness & Edge Cases

- Do implementations match requirements for all cases?
- Are edge cases handled (empty inputs, None, boundary values, large values)?
- Are assumptions about external calls explicit and defended?

## 4. Types & Data Structures

- Are types precise (dataclasses/typed dicts over bare tuples)?
- Are invariants (sorted order, uniqueness, non-empty) documented and maintained?
- Are multi-tenant and time-dimension fields always present and correctly scoped?

## 5. Control Flow & Ordering

- Is control flow readable (limited nesting, sensible early returns)?
- Are sorting/selection rules deterministic, including ties?
- Are error paths clear and symmetric with happy paths?

## 6. Performance & Resource Use

- Any N+1 database patterns or repeated queries in loops?
- Any large intermediate structures or per-row external calls to batch?
- Is this on a hot path? Is the algorithmic shape sensible?

## 7. Consistency with Codebase

- Does code follow existing patterns, helpers, abstractions?
- Is it consistent with Django/DRF/Optimo conventions in this repo?
- Are shared concerns (logging, permissions, serialization) going through central mechanisms?

## 8. Tests & Validation

- Tests covering new behavior, edge cases, regressions?
- Factories/fixtures over hand-rolled graphs?
- Multi-tenant and time-dimension scenarios covered?
- **Branch map**: every Phase 2 branch mapped to a test?
- **Input matrix**: all combinations covered?
- **Bidirectional**: both directions of every two-outcome branch tested?
- **Fixture hygiene**: every fixture param used?
- **Mock fidelity**: mocks match real function shapes?
- **Time safety**: time-dependent tests frozen?
- **Exception**: migration files don't need tests; focus on models and business logic.

## 9. Migrations & Schema Changes

- Avoid destructive changes in the same deploy as dependent code. Two-step rollout:
  remove usage first, then drop field/table in follow-up PR.
- For large tables, avoid non-nullable columns with defaults in a single migration:
  1. Add column nullable with no default
  2. Backfill in controlled batches
  3. Then add default for new rows
- Treat volatile defaults (UUIDs, timestamps) similarly.
- If many iterative migrations in one PR: regenerate a minimal, final migration set
  before merge (without touching production migrations).

## 10. Unchanged Code Impact

- Callers of changed functions checked for assumption breakage?
- Serializers/admin/exports checked for changed model fields?
- Import sites updated for extracted/renamed functions?
- Settings/feature-flag consumers traced and tested?
