---
name: historical-data-check
description: >
    Audit for historical data gaps: existing DB rows in bad state, legacy
    config import reintroducing bugs, rollback/reprocess safety for old data,
    and inverse state-clearing on failure paths. Returns findings tagged
    [BLOCKING]/[SHOULD_FIX].
user-invocable: true
allowed-tools: [Bash, Read, Glob, Grep]
---

# Historical Data Check

Focused sub-skill that verifies fixes don't just prevent new bad data but
also handle existing stale/broken data. Covers monty-v2 blind-spot checks
P14, P16, and P23.

**This skill is NOT done until you have:**
- Identified EVERY model field the fix constrains or changes
- Assessed whether existing DB rows can violate the new constraint
- Traced the config import path for legacy config injection (P23 — #2 most-missed)
- Audited EVERY state write for inverse/rollback safety (P16)
- Checked whether reprocess/rollback paths are still safe for old data

---

## Step 1: Existing DB Rows in Bad State (P14)

When a fix constrains or changes field behavior, check if existing rows
already have the bad values:

```bash
# Find model fields the fix constrains
grep -rn "<field_name>" --include="*.py" | grep -v tests/ | grep -v migrations/ | head -20

# Check for the old/bad pattern that the fix prevents
grep -rn "<old_value_pattern>" --include="*.py" | grep -v tests/
```

### Questions to ask

1. **Does the fix add a new constraint?** (unique, not-null, choices)
   → Existing rows may violate it → needs data migration or backfill.

2. **Does the fix change how a field is interpreted?**
   → Existing rows were written with the old interpretation.

3. **Does the fix add a new non-nullable field with a default?**
   → Large-table migration risk: Django adds the column with default
   on every row, which can lock the table.

4. **Does the fix change an enum/sentinel value?**
   → Existing rows still have the old value.

### Flagging

- Existing rows can hit the new constraint = `[BLOCKING]`
- Large-table non-nullable with default = `[SHOULD_FIX]` (needs batched migration)
- Old enum values not migrated = `[SHOULD_FIX]`

---

## Step 2: Legacy Config Import Reuse (P23)

**Second-highest-recurring missed pattern.** When config export/import,
mapping persistence, or field serialization is touched, test importing
a pre-fix config:

```bash
# Find import paths
grep -rn "import.*config\|from.*import\|load.*config" --include="*.py" | grep -v tests/

# Find export paths
grep -rn "export.*config\|to.*dict\|serialize" --include="*.py" | grep -v tests/
```

### The legacy config attack vector

```
Pre-fix export (bad values persisted)
    → Stored in config export file
    → Re-imported through NEW import code path
    → Bad values survive the fix because import "preserves" them
    → Bug is still live through historical config reuse
```

### Checks

1. **Does import sanitize or validate legacy values?**
   If not, a pre-fix config can re-introduce sentinel overrides, wrong
   enums, or stale mappings.

2. **Does import have a schema version check?**
   If not, v1 configs may lack fields that v2 code requires, causing
   silent defaults or crashes.

3. **Does import clean up known-bad values?**
   For example: disability sentinel overrides (`I_DO_NOT`, `PNTA`, `NA`)
   should be dropped on import, not preserved.

### Flagging

- Legacy config can reintroduce the exact bug = `[BLOCKING]`
- Import doesn't validate schema version = `[SHOULD_FIX]`
- Known-bad sentinel values not cleaned on import = `[BLOCKING]`

---

## Step 3: Rollback / Reprocess Safety (P16)

Every forward write of a state field (timestamp, status, audit flag)
must have a documented inverse path:

```bash
# Find state writes
grep -rn "\.status\s*=\|\.save()\|\.update(" --include="*.py" | grep -v tests/
```

### State transition audit

For every new state write, enumerate every transition that could land
on that row again:

| Forward write | Inverse needed | Regression test? |
|---------------|---------------|-----------------|
| status = COMPLETED | rollback → DRAFT | |
| analyzed_at = now() | reprocess → clear? | |
| validation_errors = [...] | successful reprocess → clear | |
| audit_log = snapshot | rollback → restore from audit | |

### Rollback parity

If the fix changes forward processing behavior, verify rollback can
restore pre-fix state correctly:

1. Does rollback use the same field set as forward processing?
   (e.g., if forward expanded from demographic to KPI fields, does rollback?)

2. Does rollback trigger recategorization/recomputation with the same
   trigger set as forward processing?

3. Can a failed reprocess be rolled back safely, or does the failure
   state prevent rollback?

### Flagging

- State write with no inverse path = `[BLOCKING]`
- Rollback uses narrower trigger set than forward = `[BLOCKING]`
- Failed reprocess prevents rollback = `[BLOCKING]`
- Inverse not tested = `[BLOCKING]`

---

## Step 4: Output

```text
Historical Data Check
=====================
Branch: <branch>
PR: #<number>

Existing DB rows:
  - <field>: <N> rows may have old values — [OK/NEEDS MIGRATION]
  - <constraint>: existing violations possible — [OK/NEEDS BACKFILL]

Legacy config import:
  - Import path: <file>:<line> — [safe/EXPOSED]
  - Schema versioning: [present/MISSING]
  - Sentinel cleanup: [present/MISSING]
  - Legacy config can reintroduce bug: [NO/YES — BLOCKING]

Rollback/reprocess:
  - State transition: <from> → <to> — inverse: [present/MISSING]
  - Rollback parity: [matches forward/NARROWER]
  - Failed reprocess safety: [safe/BLOCKS ROLLBACK]

Findings:
  [BLOCKING] <file>:<line> — <description>
  [SHOULD_FIX] <file>:<line> — <description>
```

### Completion Gate

```text
☐ Every constrained model field checked for existing row violations
☐ Config import path traced end-to-end for legacy value injection
☐ Import schema versioning assessed — can v1 configs survive v2 code?
☐ Known-bad sentinel values checked: are they cleaned on import or re-persisted?
☐ Every state-field write has an inverse path documented
☐ Rollback trigger set compared against forward processing trigger set
☐ Failed reprocess path checked: does it strand the job in a non-rollbackable state?
```

---

## Rules

- **Historical config reuse is the #2 missed pattern** — always check
  import paths when data processing or config code changes.
- **Every state write needs an inverse** — timestamp, status, and audit
  writes must be reversible or explicitly documented as irreversible.
- **Testing new code is not enough** — old data running through new code
  is where the bugs hide.
