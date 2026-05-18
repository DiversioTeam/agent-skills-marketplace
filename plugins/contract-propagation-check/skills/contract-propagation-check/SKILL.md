---
name: contract-propagation-check
description: >
    Grep ALL consumers of every changed function, model field, queryset filter,
    and utility. Verify lifecycle parity at every stage (save, generate, import,
    export, apply, revert, consolidate). Check admin three-layer surface
    (get_readonly_fields, InlineModelAdmin, ModelForm.__init__). Returns
    findings tagged [BLOCKING]/[SHOULD_FIX]/[NIT].
user-invocable: true
allowed-tools: [Bash, Read, Glob, Grep]
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
# List all changed Python files
git diff --name-only origin/release...HEAD --diff-filter=ACMRT | grep '\.py$'
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

## Step 5: Output

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
```

If any box is unchecked, you are NOT done. Continue investigation.

---

## Rules

- **Grep, don't guess** — every consumer must be found via grep, not assumed.
- **Cite the line** — every finding must have a file:line reference.
- **Exemptions must be documented** — if a stage is skipped, state why.
- **P17 is the #1 missed pattern** — lifecycle parity gets extra scrutiny.
