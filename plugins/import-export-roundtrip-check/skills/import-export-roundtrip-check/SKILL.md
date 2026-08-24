---
name: import-export-roundtrip-check
description: >
    Verify every data structure changed in the PR can be safely round-tripped
    through every import/export path it touches: CSV, dict/serialized, config,
    workbook, management command import/export, and admin import/export.
    The #1 newly-identified missed pattern across 15+ PR audits (2026 H1).
    Returns findings tagged [BLOCKING]/[SHOULD_FIX]/[NIT].
user-invocable: true
allowed-tools: [Bash, Read, Glob]
---

# Import/Export Round-Trip Check

Focused sub-skill that verifies data written through ONE path can be
safely read back through EVERY other import/export path. The highest-
frequency missed pattern in 2026 H1 PR audits: CSV export fields not
matching import expectations, dict shapes breaking between serialize/
deserialize, admin export/import losing fields.

**This skill is NOT done until you have:**
- Enumerated EVERY import and export path touching changed data structures
- Traced a full round-trip through every import→export pair
- Verified field parity: export writes it, import reads it, round-trip preserves it
- Checked edge cases: empty exports, legacy format compatibility, version skew

---

## Step 1: Identify Changed Data Structures

From the branch diff, list every data structure whose shape or content changed:

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

For each changed file, identify:
- **Model fields** added, removed, or type-changed
- **Serializer/dict shapes** modified (keys added, removed, renamed)
- **CSV column mappings** altered (`writer.writerow(...)`, `csv.DictReader(...)`)
- **Export functions** changed (`to_dict()`, `as_json()`, `generate_export()`)
- **Import functions** changed (`from_dict()`, `from_csv()`, `parse_import()`)
- **Management command args** that change input/output formats

---

## Step 2: Map Every Import/Export Path

For each changed data structure, enumerate ALL import and export paths:

```bash
# Find export paths
grep -rn "export\|to_csv\|to_dict\|to_json\|generate.*export\|write.*csv\|writerow" --include="*.py" | grep -v tests/

# Find import paths
grep -rn "import.*csv\|from_csv\|from_dict\|from_json\|parse.*import\|read.*csv\|DictReader" --include="*.py" | grep -v tests/

# Find management command I/O
grep -rn "add_argument.*csv\|add_argument.*file\|add_argument.*output\|add_argument.*input" --include="*.py" | grep -v tests/

# Find admin import/export
grep -rn "ImportMixin\|ExportMixin\|import_export\|ExportActionMixin" --include="*.py" | grep -v tests/
```

Build a matrix of import→export pairs that are expected to be round-trippable:

| Data Structure | Export Path | Import Path | Round-Trip Safe? |
|----------------|-------------|-------------|------------------|
| `BespokeResponse` | `handle_bespoke_fields()` CSV export | `import_bespoke_fields()` CSV import | ? |
| `ConfigDict` | `export_config_json()` | `import_config_json()` | ? |

---

## Step 3: Field-Level Parity Audit

For each import→export pair, verify field-level parity:

```bash
# For CSV paths: compare column headers written vs column headers read
# Export side - find what columns are written
grep -A 20 "def.*export\|writer.writerow\|to_csv" <file> | grep -E "\[.*\]|columns|headers"

# Import side - find what columns are expected
grep -A 20 "def.*import\|from_csv\|DictReader" <file> | grep -E "\[.*\]|columns|headers|row\["
```

### Parity checklist per round-trip pair

| Check | Detail |
|-------|--------|
| **Field count parity** | Export writes N fields, import reads N fields? |
| **Field name parity** | Export column names match import column name lookups? |
| **Field type parity** | Export writes strings but import expects ints? |
| **Null handling** | Export writes `""` vs `None`, import handles both? |
| **Encoding parity** | Export uses latin-1, import reads UTF-8? |
| **Legacy format support** | Import can read pre-change export format? |
| **Schema versioning** | Export includes version marker, import checks it? |

### Flagging

- Export field missing from import = `[BLOCKING]` (data silently lost)
- Import field not present in export = `[BLOCKING]` (import will crash or use defaults)
- Field type mismatch = `[BLOCKING]` (data corruption on round-trip)
- Legacy format not handled = `[SHOULD_FIX]` (existing exports become unreadable)
- No schema version marker = `[SHOULD_FIX]` (silent breakage on format change)

---

## Step 4: Cross-Path Consistency

Data written through one path must be consumable through ALL paths:

```bash
# Find all places that write to the same storage medium
grep -rn "\.save()\|\.update()\|\.create()\|bulk_create\|bulk_update" <changed_models>.py

# For each write path, find all read paths
grep -rn "\.get()\|\.filter()\|\.all()\|\.values()" <changed_models>.py
```

### The cross-path attack vector

```
Model.save() writes field X as integer
    → CSV export reads field X → writes as string "123"
    → CSV import reads string "123" → writes back as string "123"
    → Model field X now has type string instead of integer
    → Next .filter(X__gt=100) silently fails
```

### Checks

1. **Type coherence**: does every write path produce the same type for the same field?
2. **Serialization coherence**: does the dict-based serialization match the CSV serialization?
3. **Admin vs command parity**: does admin export produce the same shape as management command export?

### Flagging

- Two write paths produce different types for the same field = `[BLOCKING]`
- Admin export shape differs from command export = `[SHOULD_FIX]`
- Dict serialization missing fields present in CSV export = `[BLOCKING]`

---

## Step 5: Edge Cases

### Empty/null data

```bash
# Check if export handles empty querysets
grep -A 10 "def.*export" <file> | grep -E "if not|if len|\.count|\.exists"

# Check if import handles empty files
grep -A 10 "def.*import" <file> | grep -E "if not|\.strip|\.read"
```

### Large datasets

- Does the export stream or load everything into memory?
- Does the import use batched processing or one-by-one?

### Duplicate rows

- CSV contains duplicate rows for the same entity: does import deduplicate or create duplicates?
- Real example from PR#3041: "When the CSV contains duplicate rows for the same respondent... newly created rows..."
- Flag: `[BLOCKING]` if duplicates can corrupt data.

### Round-trip identity

- Export → Import → Export: does the second export match the first?
- Changing field A but export only writes field B: can field A round-trip?

---

## Step 6: Output

```text
Import/Export Round-Trip Check
==============================
Branch: <branch>
PR: #<number>

Changed data structures:
  - <Model> in <file>
  - <Serializer/dict> in <file>
  - <CSV format> in <file>

Import/export paths found:
  - Export: <N> paths — <list with file:line>
  - Import: <M> paths — <list with file:line>
  - Round-trip pairs: <P> pairs

Field parity audit:
  - <pair>: <N> fields exported, <M> fields imported — [MATCH/MISMATCH]
  - Type coherence: [ALL MATCH/MISMATCH at <file:line>]
  - Schema versioning: [PRESENT/MISSING]

Cross-path consistency:
  - Write path 1 (<file:line>) vs Write path 2 (<file:line>): [COHERENT/DIVERGENT]
  - Admin export vs command export: [MATCH/MISMATCH]

Edge cases:
  - Empty/null handling: [COVERED/GAP at <file:line>]
  - Duplicate row handling: [COVERED/GAP at <file:line>]
  - Round-trip identity: [PRESERVED/BROKEN]

Findings:
  [BLOCKING] <file>:<line> — <description>
  [SHOULD_FIX] <file>:<line> — <description>
  [NIT] <file>:<line> — <description>
```

### Completion Gate

```text
☐ Every changed data structure identified (models, serializers, CSV formats)
☐ Every import path enumerated and traced to changed structures
☐ Every export path enumerated and traced to changed structures
☐ Field-level parity checked for every import→export round-trip pair
☐ Type coherence verified across all write paths
☐ Empty/null edge cases checked for every import/export handler
☐ Duplicate row handling verified for every import path
☐ Schema versioning assessed: can old exports survive new import code?
☐ Cross-path consistency verified: admin export vs command export vs API export
```

---

## Rules

- **Round-trip first** — if you can't export→import→export and get the same result, something is broken.
- **Every export must have a matching import** — if a management command exports CSV but no import reads that format, document it explicitly.
- **Schema versioning is not optional** — any format change without a version marker is a future bug.
- **Duplicate rows are the #1 CSV import bug** — always check deduplication logic.
- **Type coherence across write paths** — if two writers produce different types for the same field, one of them is wrong.
