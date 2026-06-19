---
name: contract-propagation-check
description: >
    Grep ALL consumers of every changed function, model field, queryset filter,
    and utility. Verify lifecycle parity at every stage (save, generate, import,
    export, apply, revert, consolidate). Check admin three-layer surface
    (get_readonly_fields, InlineModelAdmin, ModelForm.__init__). Audit
    concurrency safety (stale reads, race windows, missing row-version guards),
    admin workflow atomicity (A-then-B failure between steps), and empty/edge
    state handling (null, empty, boundary inputs). Returns findings tagged
    [BLOCKING]/[SHOULD_FIX]/[NIT].
user-invocable: true
allowed-tools: [Bash, Read]
---

# Contract Propagation Check

Focused sub-skill that verifies every changed contract propagates correctly
to ALL consumers. Covers monty-v2 blind-spot checks P10, P17, and P18.

**This skill is NOT done until you have:**
- Grep'd EVERY changed function/model field across the entire codebase
- Checked EVERY consumer path (services, admin, serializers, import/export,
  repair, commands, tasks, API, tests) — not just the ones you think matter
- Audited EVERY lifecycle stage (save, generate, import, export, apply,
  revert, consolidate, admin enum, collision) — cite the line at each
- Read EVERY admin class, inline, and ModelForm touched — in full, not diff-only

**Evidence rule**: "Looks fine" is not a finding. Every check must produce
either a line citation or an explicit exemption with reason.

---

## Step 1: Identify Changed Contracts

From the branch diff, list every changed function, model field, utility,
helper, queryset filter, and serializer:

```bash
# Detect the base branch — defaults to the PR's target branch when a PR exists.
# Override by setting BASE_BRANCH before invoking if needed.
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh pr view --json baseRefName --jq '.baseRefName' 2>/dev/null)"
fi
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name')"
fi

# List all changed Python files
git diff --name-only origin/$BASE_BRANCH...HEAD --diff-filter=ACMRT | grep '\.py$'
```

For each changed file, extract:
- **New/modified functions**: `def <name>(`
- **New/modified model fields**: `class <Model>` blocks
- **New/modified helpers**: any extracted or centralized function
- **New state fields**: timestamps, status columns, audit flags

---

## Step 2: Consumer Obligation (P10)

For every changed function/helper/model field, grep ALL consumers:

```bash
# Example: function was added or signature changed
grep -rn "<function_name>(" --include="*.py" | grep -v tests/ | grep -v migrations/

# Example: model field was added or type changed
grep -rn "<field_name>" --include="*.py" | grep -v tests/ | grep -v migrations/

# Example: queryset filter logic changed
grep -rn "<filter_pattern>" --include="*.py" | grep -v tests/
```

### Consumer surface checklist

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

### Centralization obligation

If the branch extracts logic into a helper, grep for the OLD inline pattern:

```bash
grep -rn "<old_inline_pattern>" --include="*.py" | grep -v tests/
```

Every old site must call the new helper or be listed as explicitly exempt.

### Flagging

- Missed consumer in code path = `[BLOCKING]`
- Missed consumer in test-only path = `[SHOULD_FIX]`
- Stale mock of old contract in tests = `[SHOULD_FIX]`

---

## Step 3: Lifecycle Parity (P17)

When an equivalence, normalization, or canonicalization helper is introduced,
verify it's applied at EVERY lifecycle stage:

```bash
# Find the helper
grep -rn "<helper_name>" --include="*.py" | grep -v tests/
```

For each stage, cite the line where the helper is applied, or document why
the stage is exempt:

| Stage | Found? | Line |
|-------|--------|------|
| Save / `pre_save` signal | | |
| Generate / build | | |
| Import (CSV / config) | | |
| Export (CSV / config) | | |
| Apply / migrate | | |
| Revert / rollback | | |
| Consolidate / dedupe | | |
| Admin `TextChoices` enum | | |
| Collision surface | | |

### Flagging

- Missed lifecycle stage = `[BLOCKING]` (highest-recurring class in PR audit)
- Stage exempt with documentation = OK, cite the reason
- Stage exempt without documentation = `[BLOCKING]`

---

## Step 4: Admin Three-Layer Surface (P18)

If admin `get_readonly_fields()`, `InlineModelAdmin`, or `ModelForm` is
touched:

```bash
# Find the admin class
grep -rn "class.*Admin" --include="*.py" <app>/admin/

# Find all InlineModelAdmin classes for the parent model
grep -rn "class.*Inline" --include="*.py" <app>/admin/

# Find all ModelForm.__init__ that reference changed fields
grep -rn "def __init__" --include="*.py" <app>/admin/
```

For each, verify:

1. **If `get_readonly_fields()` excludes a field for state X**, then:
   - Every `InlineModelAdmin` for the parent must also exclude it for state X
   - No `ModelForm.__init__()` re-adds it as required for state X
   - A POST of a state-X record without the field must succeed

2. **If an inline is made conditionally readonly**, verify:
   - All inline actions (add, change, delete) respect the state gate
   - The inline's own `get_readonly_fields()` mirrors the parent

3. **If a `ModelForm.__init__()` dynamically builds fields**, verify:
   - It checks the instance state before re-adding fields
   - It doesn't override super().__init__() readonly decisions

### Flagging

- Inline or form re-adds a locked field = `[BLOCKING]`
- POST-the-locked-state not tested = `[BLOCKING]`
- Inline missing the state gate = `[BLOCKING]`

---

## Step 5: Concurrency & Stale-Data Race Audit (2026 Extension)

When state is read, modified, and written back by a changed code path,
verify that a concurrent edit can't corrupt the data.

### Read-modify-write patterns

```bash
# Find places where data is read then saved back
grep -rn "\.get(\|\.filter(" --include="*.py" <changed_files> | head -20
grep -rn "\.save()\|\.update()\|bulk_update\|bulk_create" --include="*.py" <changed_files> | head -20

# Find places missing row-version or optimistic-lock guards
grep -rn "version\|modified_at\|updated_at\|row_version" --include="*.py" <changed_files>
```

### Race audit checklist

For every state write path found in Step 3 (lifecycle parity):

| Check | Detail |
|-------|--------|
| **Stale-read window** | Does the code read data, compute something async, then write back? Between read and write, can another process change the data? |
| **Background-task races** | Does a Celery task / Lambda function read data that can be modified by admin actions while the task runs? (PR#3035: categorize_pain_points reads stale text) |
| **Admin edit races** | Can two admin users edit the same row simultaneously? Is there a row-version check or optimistic lock? |
| **Bulk-action races** | Does a bulk action read a queryset, then iterate and save individually? Between queryset execution and individual saves, can rows change? |
| **Recreate-before-check** | Does the code create/delete rows before validating prerequisites? (PR#3017: recreates SurveyResponses before checking if bespoke can succeed) |
| **Hidden-state overwrite** | Can a concurrent operation overwrite a field that was hidden/inactive during the original read? (PR#3035: queued recategorization undoes operator hide decisions) |

### Flagging

- Read-modify-write without version guard = `[BLOCKING]`
- Background task reads data that admin actions can modify = `[BLOCKING]`
- Create/delete before prerequisite validation = `[BLOCKING]`
- Bulk action iterates and saves individually without re-fetching = `[SHOULD_FIX]`
- Hidden-state fields can be silently overwritten = `[BLOCKING]`

---

## Step 6: Admin Workflow Atomicity (2026 Extension)

Beyond the three-layer surface check (Step 4), verify that sequential
admin actions (A-then-B) are safe when A succeeds but B fails.

### Sequential action patterns

```bash
# Find admin actions that do multiple things in sequence
grep -rn "def.*admin.*action\|def process_\|def handle_\|def run_" --include="*.py" <admin_files>
```

### Atomicity checklist

For every sequential admin action path:

| Check | Detail |
|-------|--------|
| **A-then-B failure** | If step A succeeds and step B fails, is the partial state safe? Does A get rolled back? |
| **No-op/misleading logging** | If an action produces a success message for rows it didn't actually change, is the log misleading? (PR#3034: deactivate_tokens logs unchanged rows) |
| **Mixed-selection handling** | If a bulk selection contains both valid and invalid rows, does the action handle the mixed case correctly or silently skip invalid rows? |
| **Permission gates on all endpoints** | Does ImportMixin expose /import/ and /process_import/ without model-level permission checks? (PR#3034: InspirationalQuoteAdmin import) |
| **Post-commit side effects** | Does the action trigger side effects (Slack, audit, email) that can't be rolled back if a later step fails? |

### Flagging

- A-then-B without rollback on B failure = `[BLOCKING]`
- Success message logged for no-op rows = `[SHOULD_FIX]`
- Mixed valid/invalid bulk selection silently skips invalids = `[SHOULD_FIX]`
- Import/export endpoints without permission gates = `[BLOCKING]`
- Post-commit side effects not isolated from later-step failures = `[BLOCKING]`

---

## Step 7: Empty/Edge/Boundary Input Matrix (2026 Extension)

For every changed function, helper, or data-processing path, trace the
null, empty, and boundary input values to verify they don't crash or
produce broken state.

### Edge input enumeration

```bash
# Find function signatures in changed files
grep -rn "^def " --include="*.py" <changed_files> | grep -v tests/
```

For each function, build the edge input matrix:

| Input | Expected Behavior | Actual Behavior | Safe? |
|-------|-------------------|-----------------|-------|
| `None` / `null` | Fails closed or skips | ? | |
| Empty `[]` / `{}` / `""` | Graceful skip or default | ? | |
| `data.length = 0` | No-op, no crash | ? | |
| `index = -1` (empty-first mount) | Guarded against | ? | |
| `index = 0` (valid boundary) | Treated correctly (not as falsy!) | ? | |
| Max boundary (`len-1`, `MAX_INT`) | Handled without overflow | ? | |
| Unset/undefined optional field | Default applied, no crash | ? | |
| Legacy row missing new field | Fails closed or migrated | ? | |
| Malformed payload (partial rollout) | Fails closed, no render | ? | |

### Common edge-state bugs (from PR audit)

- `||` fallback treating valid `0` as falsy (PR#1015: `endIndex=0` becomes `data.length-1`)
- `data.length - 1` producing `-1` on empty data (PR#1015: Brush boundary `-1`)
- Stale selections persisting during fetch transitions (PR#1800: filter revalidation during survey change)
- Legacy rows without new fields hitting `AttributeError` or silent `None` (PR#2953: grouped rows without `raw_value`)
- Overlapping spans producing duplicate/replaced text (PR#2974: spaCy PERSON spans overlap)
- `formatAmount()` global string replace corrupting currency prefixes (PR#1800: `BHD 2.7M` → `BillionHD 2.7 Million`)

### Flagging

- Empty/null input crashes or corrupts state = `[BLOCKING]`
- Valid boundary value (`0`, `false`, `""`) treated as falsy = `[BLOCKING]`
- Legacy rows hitting `AttributeError` or silent data loss = `[BLOCKING]`
- Malformed/partial payload renders broken UI = `[BLOCKING]`
- Global string replacements corrupting other text = `[BLOCKING]`
- No guard against `-1` index from empty data = `[SHOULD_FIX]`

---

## Step 8: Output

```text
Contract Propagation Check
===========================
Branch: <branch>
PR: #<number>

Changed contracts:
  - <function> in <file>:<line>
  - <model>.<field> in <file>:<line>
  - <helper> (extracted from <old_pattern>)

Consumer audit:
  - <N> consumers found, <M> verified
  - Missed: <consumer> in <file>:<line> [BLOCKING/SHOULD_FIX]

Lifecycle parity:
  - <helper> applied at <N>/9 stages
  - Missed: <stage> [BLOCKING] / <stage> (exempt: <reason>)

Admin surface:
  - get_readonly_fields: <N> exclusions verified
  - Inlines: <N> checked, <M> gaps found
  - ModelForm: <N> checked, <M> conflicts found
  - Missed: <surface> in <file>:<line> [BLOCKING]

Concurrency audit (2026 extension):
  - Stale-read windows: <N> identified, <M> unguarded
  - Background-task races: <N> paths, <M> vulnerable
  - Recreate-before-check: <N> instances
  - Missed: <race> in <file>:<line> [BLOCKING/SHOULD_FIX]

Admin atomicity (2026 extension):
  - A-then-B paths: <N> identified, <M> without rollback on B failure
  - Permission-gated endpoints: <N> endpoints, <M> exposed without gates
  - No-op logging: <N> instances of misleading success messages
  - Missed: <gap> in <file>:<line> [BLOCKING/SHOULD_FIX]

Edge input matrix (2026 extension):
  - Functions audited: <N>
  - Empty/null gaps: <M>
  - Boundary-value gaps: <M>
  - Legacy-row gaps: <M>
  - Missed: <edge> in <file>:<line> [BLOCKING/SHOULD_FIX]

Findings:
  [BLOCKING] <file>:<line> — <description>
  [SHOULD_FIX] <file>:<line> — <description>
  [NIT] <file>:<line> — <description>
```

### Completion Gate

Before returning results, verify:

```text
☐ Every changed function grepped across entire codebase (not just diff)
☐ Every consumer path checked: services, admin, serializers, import/export,
   repair, commands, tasks, API, tests
☐ Every lifecycle stage cited with line number or exemption reason
☐ Every admin class read in full (not diff-only)
☐ Every inline ModelAdmin checked for state gate consistency
☐ Every ModelForm.__init__() checked for field re-add conflicts
☐ [2026] Every read-modify-write path checked for version guard or stale-read window
☐ [2026] Every background task read path checked for concurrent admin edit safety
☐ [2026] Every sequential admin action (A-then-B) checked for rollback on B failure
☐ [2026] Every ImportMixin/ExportMixin endpoint checked for permission gates
☐ [2026] Every changed function traced for null/empty/boundary input behavior
☐ [2026] Every legacy-row-compatibility path checked (old rows missing new fields)
```

If any box is unchecked, you are NOT done. Continue investigation.

---

## Rules

- **Grep, don't guess** — every consumer must be found via grep, not assumed.
- **Cite the line** — every finding must have a file:line reference.
- **Exemptions must be documented** — if a stage is skipped, state why.
- **P17 is the #1 missed pattern** — lifecycle parity gets extra scrutiny.
