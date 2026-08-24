---
name: test-quality-check
description: >
    Audit test quality: production-path depth, branch coverage, mock realism,
    behavioral value, fixture/setup economy, time-dependent logic,
    transaction-shape claims, and CI-tolerant assertion safety. Rejects tests
    that merely restate framework behavior or wrapper plumbing. Returns findings tagged
    [BLOCKING]/[SHOULD_FIX]/[NIT].
user-invocable: true
allowed-tools: [Bash, Read]
---

# Test Quality Check

Focused sub-skill that verifies tests actually prove the behavior they claim.
Covers monty-v2 blind-spot checks P1, P12, P19, and P20.

## Base Branch Detection

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
```

**This skill is NOT done until you have:**
- Traced the call chain from EVERY new test to its production entry point
- Verified bugfix tests reproduce the REPORTED scenario, not a different variant
- Checked transactional tests for induced-failure rollback; query-level
  SAVEPOINT assertions only when savepoint structure is the application contract
- Audited relaxed assertions for multiplicity preservation on test-owned IDs

---

## Step 1: Test Depth (P1)

For every new test, trace the call chain from the test to the production
entry point:

```bash
# Find new or modified tests in nested test dirs and colocated test modules
git diff --name-only origin/$BASE_BRANCH...HEAD --diff-filter=ACMRT \
  | grep -E '(^|/)(tests?/.*\.py|test_[^/]*\.py)$'
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
- The test mocks every meaningful layer and verifies only argument forwarding

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

When the fix changes transaction behavior, first identify the application
contract. A plain `transaction.atomic()` wrapper should be tested through an
induced later-step failure and observable all-or-nothing state—not by retesting
that Django emits transaction SQL. Assert SAVEPOINT/ROLLBACK query shape only
when nested savepoint boundaries or partial recovery are themselves the feature:

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

# RIGHT for ordinary atomicity: induce a failure after the first write
@pytest.mark.django_db
def test_process_invoice_rolls_back_when_audit_fails(mocker):
    mocker.patch("billing.audit_invoice", side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
        process_invoice(invoice)
    invoice.refresh_from_db()
    assert invoice.status == "pending"

# Only when savepoint structure is an application requirement:
# use django_db(transaction=True) + CaptureQueriesContext and assert the
# expected SAVEPOINT/ROLLBACK boundary.
```

Without transaction-shape assertions, the `atomic()` wrapper can be
removed and the test still passes — the wrapping is unenforceable.

### Flagging

- Atomicity claimed without an induced-failure rollback assertion = `[SHOULD_FIX]`
- Test only proves Django's `atomic()` machinery = `[NIT]` to remove
- Savepoint behavior is an explicit feature but query shape is unobserved = `[SHOULD_FIX]`
- Savepoint-shape test lacks `django_db(transaction=True)` = `[SHOULD_FIX]`

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

## Step 5: Behavioral Value and Test Economy

For every changed test, state the application behavior that would regress if the
test were removed. Flag these recurring low-value forms:

- page renders / HTTP 200 without asserting filtering, permissions, or mutation
- field appears in `list_display`, default/help text matches model metadata, or
  `transaction.atomic()` behaves as Django documents
- one-line wrapper delegates to a mocked function
- mocks replace the exact Titan/API/admin/service chain the regression concerns
- test name claims filtering/rollback/error handling but assertions prove only
  shape, status, or a mocked call

A framework smoke test is justified only when project configuration, templates,
permissions, middleware, or custom hooks make the integration itself the risk.
Otherwise remove it or replace it with behavior-level coverage.

Then inspect economy without weakening coverage:

```bash
# Repeated setup and patch sites in changed tests
rg 'objects\.create|client\.post|admin_client\.post|@patch|with patch' <changed-tests>
rg 'pytest\.mark\.django_db|\bdb\b' <changed-tests>
```

- Repeated model rows/payloads/patches → use an existing or local fixture/factory/helper.
- Symmetric approve/reject or true/false cases → parameterize when assertions are the same.
- Module/class `django_db` marker → remove redundant fixture-level `db` requests.
- Large multi-purpose test → split by behavior; do not hide distinct failures in one flow.
- Bulk setup → use `bulk_create` when signals/default-save behavior is not under test.

Flag behavior-free or misleading tests `[SHOULD_FIX]`; pure Django/framework
retests and test-only production wrappers are `[NIT]` to remove unless they
obscure missing real coverage, then `[SHOULD_FIX]`.

---

## Step 6: Additional Checks

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

## Step 7: Output

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

Behavioral value: <N> behavior tests, <M> plumbing/framework-only tests
Test economy: <N> repeated setup/patch/payload clusters
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
☐ Transaction changes tested via induced failure and observable rollback
☐ SAVEPOINT/ROLLBACK query shape asserted only when it is the application contract
☐ Relaxed assertions (set/>=/subset) checked for Counter() multiplicity
☐ Mocks checked against production return shapes and kept off the behavior path
☐ Every test proves application behavior, not stock framework/wrapper plumbing
☐ Repeated rows/payloads/patches checked for fixture/helper/parameterization reuse
☐ Test names matched against the behavior actually asserted
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
- **Mock only unrelated boundaries** — the production chain that carries the
  changed behavior must stay real.
- **Do not test Django for Django** — prove the project's filtering, permission,
  mutation, integration, or rendering contract instead.
