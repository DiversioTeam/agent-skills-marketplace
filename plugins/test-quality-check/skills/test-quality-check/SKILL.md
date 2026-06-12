---
name: test-quality-check
description: >
    Audit test quality: test depth (helper vs production entry point), branch
    coverage gaps, mock realism, time-dependent logic, transaction-shape
    assertions, and CI-tolerant assertion safety. Returns findings tagged
    [BLOCKING]/[SHOULD_FIX]/[NIT].
user-invocable: true
allowed-tools: [Bash, Read]
---

# Test Quality Check

Focused sub-skill that verifies tests actually prove the behavior they claim.
Covers monty-v2 blind-spot checks P1, P12, P19, and P20.

## Base Branch Detection

```bash
# Detect the base branch — defaults to the repo's default branch.
# Override by setting BASE_BRANCH before invoking (e.g., BASE_BRANCH=release).
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name')"
fi
```

**This skill is NOT done until you have:**
- Traced the call chain from EVERY new test to its production entry point
- Verified bugfix tests reproduce the REPORTED scenario, not a different variant
- Checked transactional tests for connection.queries / SAVEPOINT assertions
- Audited relaxed assertions for multiplicity preservation on test-owned IDs

---

## Step 1: Test Depth (P1)

For every new test, trace the call chain from the test to the production
entry point:

```bash
# Find new or modified tests
git diff --name-only origin/$BASE_BRANCH...HEAD -- '*/tests/*.py'
```

For each test:
1. What function does it call directly?
2. Is that function the production entry point, or just an isolated helper?
3. If it's a helper, what is the REAL call chain that the bug travels through?

### The helper-only trap

```
Test → helper_function() → assert    ← only proves helper works
  vs
Test → admin_action() → service() → helper() → assert   ← proves real path
```

Helper-only tests pass even when:
- The helper is never actually called in production
- The production entry point skips the helper for certain states
- The caller passes different arguments than the test assumes

### Flagging

- Test hits only a helper, not the production entry point = `[BLOCKING]`
  if the bug was reported on the production path.
- Test hits the production entry point = OK
- Both helper test AND integration test exist = best practice

---

## Step 2: Wrong Bug Variant (P12)

For bugfix PRs, verify the test reproduces the *reported* scenario, not a
different variant:

1. Read the bug description (PR body, linked issue)
2. Map the reported scenario to concrete test conditions
3. Check if the test sets up those exact conditions

### Common mismatches

| Reported bug | Wrong test variant | Right test variant |
|-------------|-------------------|-------------------|
| "Skipped multiselect crashes" | Unmapped column | Mapped-but-blank multiselect |
| "Empty hired corrupts tenure" | No hired field at all | Hired field present but empty |
| "KPI rollback leaves stale category" | Test only checks hook was called | Test checks category was actually restored |

### Flagging

- Test reproduces a different scenario than reported = `[SHOULD_FIX]`
- Test is ambiguous about which variant = `[SHOULD_FIX]`

---

## Step 3: Transaction-Shape Assertions (P19)

When the fix wraps writes in `atomic()` or splits into savepoints, the
test must prove the transaction shape, not just the final row state:

```bash
# Find tests that claim to test transactional behavior
grep -rn "atomic\|transaction\|savepoint" --include="*.py" \
  $(git diff --name-only origin/$BASE_BRANCH...HEAD -- '*/tests/*.py')
```

### Required assertions

```python
# WRONG: only checks final state
def test_transaction_wraps_writes(db):
    result = process_invoice(invoice)
    assert Invoice.objects.get().status == "processed"

# RIGHT: checks transaction shape
@pytest.mark.django_db(transaction=True)
def test_transaction_wraps_writes(db):
    with CaptureQueriesContext(connection) as ctx:
        process_invoice(invoice)
    # Assert savepoints were created
    queries = [q["sql"] for q in ctx.captured_queries]
    assert any("SAVEPOINT" in q for q in queries)
    assert Invoice.objects.get().status == "processed"
```

Without transaction-shape assertions, the `atomic()` wrapper can be
removed and the test still passes — the wrapping is unenforceable.

### Flagging

- Transaction behavior claimed but not asserted = `[SHOULD_FIX]`
- Test uses `django_db` without `transaction=True` = `[SHOULD_FIX]`

---

## Step 4: CI-Tolerant Assertion Safety (P20)

When tests are relaxed for parallel-CI tolerance (list equality → set/subset),
verify exact-multiplicity is preserved for test-owned data:

```bash
# Find tests with set(), >=, or subset assertions
grep -rn "set(\|>=\|\.issubset\|Counter(" --include="*.py" \
  $(git diff --name-only origin/$BASE_BRANCH...HEAD -- '*/tests/*.py')
```

### The relaxed assertion trap

```python
# BEFORE (fails in parallel CI due to leaked orgs):
assert result_org_ids == [org1.id, org2.id]

# AFTER (tolerates extra orgs but lost exact count):
assert set(result_org_ids) >= {org1.id, org2.id}

# BETTER (tolerates extra orgs + preserves exact count for test-owned):
from collections import Counter
counts = Counter(result_org_ids)
assert counts[org1.id] == 1  # test-owned org processed exactly once
assert counts[org2.id] == 1
assert set(result_org_ids) >= {org1.id, org2.id}  # extra orgs ok
```

### Flagging

- Relaxed from list-equality without multiplicity check = `[SHOULD_FIX]`
- Numeric totals scoped to ALL results, not just test subject = `[SHOULD_FIX]`
- Timestamp assertions relaxed to `>=` instead of strict-greater = `[SHOULD_FIX]`

---

## Step 5: Additional Checks

### Mock realism
```bash
grep -rn "Mock\|patch\|MagicMock" --include="*.py" \
  $(git diff --name-only origin/$BASE_BRANCH...HEAD -- '*/tests/*.py')
```
- Do mocks return shapes that real functions can return?
- `[SHOULD_FIX]` if mock shape diverges from production shape.

### Time-dependent logic
```bash
grep -rn "freeze_time\|now()\|today()\|datetime" --include="*.py" \
  $(git diff --name-only origin/$BASE_BRANCH...HEAD -- '*/tests/*.py')
```
- Time-sensitive logic must use `@freeze_time`.
- `[SHOULD_FIX]` if time-dependent logic has no freeze.

### Both directions of if/else
- For every branch in the production code, verify both directions are
  tested. If running within the review delegator, use the branch map
  from monty-v2 Phase 2. If running standalone, do a brief branch
  enumeration on the changed functions first.
- `[SHOULD_FIX]` if only one direction tested.

---

## Step 6: Output

```text
Test Quality Check
==================
Branch: <branch>
PR: #<number>

Test depth:
  - <N> tests checked, <M> are helper-only
  - Helper-only tests missing production path: <list> [BLOCKING/SHOULD_FIX]

Bug variant accuracy:
  - Reported: <scenario>
  - Tested: <scenario> — [matches/DIFFERS]

Transaction shape:
  - <N> transactional tests, <M> with shape assertions
  - Missing shape assertions: <list> [SHOULD_FIX]

CI-tolerant assertion safety:
  - <N> relaxed assertions, <M> with multiplicity guards
  - Missing multiplicity: <list> [SHOULD_FIX]

Mock realism: [OK/N issues]
Time-dependent: [OK/N issues]
Branch coverage: <X>/<Y> branches tested

Findings:
  [BLOCKING] <file>:<line> — <description>
  [SHOULD_FIX] <file>:<line> — <description>
  [NIT] <file>:<line> — <description>
```

### Completion Gate

```text
☐ Every new/modified test traced to production entry point (not just helper)
☐ For bugfix PRs: reported scenario mapped to test conditions explicitly
☐ Transactional tests checked for connection.queries SAVEPOINT/ROLLBACK
☐ Relaxed assertions (set/>=/subset) checked for Counter() multiplicity
☐ Mocks checked against production function return shapes
☐ Time-sensitive tests checked for @freeze_time
☐ Both directions of every if/else in changed code have test coverage
```

---

## Rules

- **Production entry point** — tests that only hit helpers are NOT
  sufficient for correctness-critical paths.
- **Transaction shape must be asserted** — wrapping is unenforceable
  without query-level assertions.
- **Relaxed ≠ safe** — CI-tolerant assertions still need multiplicity
  guards for test-owned data.
