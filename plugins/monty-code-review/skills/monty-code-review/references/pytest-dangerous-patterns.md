# Pytest Dangerous Patterns (Wrong vs Correct)

## Purpose

Use this reference during the `monty-code-review` pytest hardening lane.

This file captures high-signal pytest anti-patterns that can silently pass or
create false confidence. Each pattern includes wrong and corrected snippets so
review feedback can be concrete and immediately actionable.

## Severity Model

- `[BLOCKING]`: silent-pass risk or hidden regression risk.
- `[SHOULD_FIX]`: materially weak or fragile tests that reduce confidence.
- `[NIT]`: clarity/consistency improvements.

## Quick-Detection Preconditions

Before running any detection command in this file, ensure `PYTEST_FILES` is
populated with pytest paths in scope. Example contract:

```bash
# Set PYTEST_FILES first; commands below assume this array is non-empty.
```

## Pattern PTH-001: Defensive Conditionals Around Required Assertions

- Risk: `[BLOCKING]`
- Why this is dangerous:
  - Assertions are hidden inside `if` guards.
  - The test can pass without validating the expected behavior.

Wrong:

```python
assert mock_service.call_count > 0
call_args = mock_service.call_args
if call_args and call_args.kwargs:
    if "months" in call_args.kwargs:
        assert call_args.kwargs["months"] == 12
```

Correct:

```python
assert mock_service.call_count > 0
call_args = mock_service.call_args
assert call_args is not None, "call_args should exist when service is called"
assert call_args.kwargs is not None, "kwargs should exist in call_args"
assert "months" in call_args.kwargs, "months should be passed"
assert call_args.kwargs["months"] == 12, "months should be 12"
```

Alternative (pytest-mock explicit call contract):

```python
mock_service.assert_called_once()
assert mock_service.call_args is not None
assert mock_service.call_args.kwargs["months"] == 12
```

Quick detection:

```bash
ast-grep scan --lang python --pattern 'if call_args:\n    $$$BODY' "${PYTEST_FILES[@]}"
ast-grep scan --lang python --pattern 'if call_args.kwargs:\n    $$$BODY' "${PYTEST_FILES[@]}"
ast-grep scan --lang python --pattern 'if call_args and call_args.kwargs:\n    $$$BODY' "${PYTEST_FILES[@]}"
```

## Pattern PTH-002: `.get(..., default)` Masks Missing Required Fields

- Risk: `[BLOCKING]`
- Why this is dangerous:
  - Defaults can introduce fake values.
  - Missing required fields become invisible.

Wrong:

```python
risk_category = item.get("risk_category", "unknown")
assert data.get("viewer_direct_report_ids", []) == []
```

Correct:

```python
assert "risk_category" in item, "risk_category field is required"
risk_category = item["risk_category"]

assert "viewer_direct_report_ids" in data, "viewer_direct_report_ids should exist"
assert data["viewer_direct_report_ids"] == []
```

Guideline:
- For required fields: assert presence, then use direct indexing.
- Reserve `.get()` for truly optional fields where missing is part of contract.

Quick detection:

```bash
ast-grep scan --lang python --pattern 'assert $OBJ.get($KEY, $DEFAULT) == $EXPECTED' "${PYTEST_FILES[@]}"
ast-grep scan --lang python --pattern '$VAL = $OBJ.get($KEY, $DEFAULT)' "${PYTEST_FILES[@]}"
```

## Pattern PTH-003: Calculated Values Used Only in Error Messages

- Risk: `[SHOULD_FIX]` (can be `[BLOCKING]` when central to test intent)
- Why this is dangerous:
  - The test computes a scenario-quality metric but never validates it.
  - Test name can imply stronger coverage than what is actually verified.

Wrong:

```python
employees_with_multiple_categories = sum(
    1 for cats in employee_risk_categories.values() if len(cats) > 1
)

assert actual_calls == unique_employees, (
    f"... {employees_with_multiple_categories} had multiple categories ..."
)
```

Fallback (warn when scenario is weaker than intended):

```python
employees_with_multiple_categories = sum(
    1 for cats in employee_risk_categories.values() if len(cats) > 1
)

if employees_with_multiple_categories == 0:
    # Example-only local import for snippet brevity.
    # In real test files, keep imports at module top.
    import warnings
    warnings.warn(
        "Fixture has no multi-category employees; caching still validated per employee, "
        "but scenario is less comprehensive.",
        stacklevel=2,
    )

assert actual_calls == unique_employees
```

Preferred default (assert hard precondition when required by test intent):

```python
assert employees_with_multiple_categories > 0, (
    "Expected at least one multi-category employee for this scenario"
)
```

Guideline:
- Prefer hard preconditions when scenario strength is part of test intent.
- Use warning fallback only when fixture variability is expected and non-blocking.

Quick detection:

```bash
# Triage-only heuristics (manual confirmation required before raising findings):
ast-grep scan --lang python --pattern '$METRIC = sum(1 for $ITEM in $VALUES.values() if len($ITEM) > 1)' "${PYTEST_FILES[@]}"
ast-grep scan --lang python --pattern 'assert $COND, f$MSG' "${PYTEST_FILES[@]}"
```

## Reviewer Checklist (Pytest Lane)

- Do required assertions run unconditionally?
- Are required response fields asserted before value checks?
- Are any default values masking missing required keys?
- Are computed scenario metrics validated (asserted or warned) when relevant?
- Does the test fail loudly on contract regressions?

## Suggested Finding Format

Use this table shape in review output:

| Severity | Pattern | File:Line | Detector | Risk | Safe Fix |
|---|---|---|---|---|---|
| `[BLOCKING]` | PTH-001 | `tests/test_x.py:88` | `ast-grep` | Required assertion can be skipped | Replace guard with explicit `assert call_args is not None` chain |
