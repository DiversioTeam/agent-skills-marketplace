---
name: codebase-reuse-finder
description: >
    Scan current changes for hardcoded values, duplicated setup/query logic,
    weakened stable types, and reimplemented framework or repository patterns.
    Search for existing constants, enums, TypedDicts, clients, decorators,
    utilities, and test helpers before inventing replacements. Reports concrete
    reuse evidence while respecting the Diversio/Optimo product boundary.
user-invocable: true
argument-hint: '[file-or-directory] [--apply]'
allowed-tools: [Bash, Read, Edit]
---

# Codebase Reuse Finder Skill

Scan code for hardcoded values, magic numbers, duplicated setup/query logic,
weakened stable types, and reimplemented patterns. Search the codebase before
inventing a replacement. Standalone skill — use anytime, not tied to the PR
workflow.

**Reference documentation:**

- `AGENTS.md` — product boundaries and global rules
- `docs/architecture/overview.md` — system architecture and module relationships

---

## Step 1: Determine Scope

Three ways to determine what code to scan:

### A: Explicit file or directory (argument)

If a file or directory is provided as argument, scan that directly.

### B: Full branch plus local changes (default)

If no argument is provided, scan the full PR/branch diff, then union staged,
unstaged, and untracked files. A clean worktree does **not** mean there is no
review scope.

```bash
BASE_BRANCH="$(gh pr view --json baseRefName --jq '.baseRefName' 2>/dev/null)"
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name')"
fi
git fetch origin "$BASE_BRANCH"
{
  git diff --name-only "origin/$BASE_BRANCH...HEAD" --diff-filter=ACMRT
  git diff --cached --name-only --diff-filter=ACMRT
  git diff --name-only --diff-filter=ACMRT
  git ls-files --others --exclude-standard
} | sort -u | grep -E '\.(py|ts|tsx|js|jsx)$'
```

### C: Explicit scope wins

If an argument and changes both exist, scan only the argument.

If no argument and the full branch/local union is empty, tell the user there is
no scope and ask for a target.

---

## Step 2: Auto-Detect Product Boundary

Determine which product the scanned files belong to, which controls the search
scope for replacements:

| Scanned file path starts with | Product    | Search scope                                                             |
| ------------------------------ | ---------- | ------------------------------------------------------------------------ |
| `optimo_*`                     | Optimo     | `optimo_core/`, `optimo_surveys/`, `optimo_integrations/`, `optimo_hris_csv_processing/`, `utils/` |
| `dashboardapp/`                | Diversio   | `dashboardapp/`, `survey/`, `pulse_iq/`, `titan/`, `utils/`             |
| `survey/`                      | Diversio   | `dashboardapp/`, `survey/`, `pulse_iq/`, `titan/`, `utils/`             |
| `pulse_iq/`                    | Diversio   | `dashboardapp/`, `survey/`, `pulse_iq/`, `titan/`, `utils/`             |
| `titan/`                       | Diversio   | `dashboardapp/`, `survey/`, `pulse_iq/`, `titan/`, `utils/`             |
| `utils/`                       | Shared     | Everything (shared code can reference any module)                        |
| Other                          | Contextual | Infer from imports in the file                                           |

**Hard boundary:**

- Optimo code must **never** suggest imports from Diversio apps
- Diversio code must **never** suggest imports from `optimo_*` apps
- `utils/` is always fair game for both products

---

## Step 3: Extract Candidates

Read each file in scope and identify:

### String literals

- Hardcoded URLs, API paths, email addresses
- Hardcoded status strings (`"active"`, `"pending"`, `"completed"`)
- Hardcoded error messages that might exist as constants elsewhere
- Hardcoded feature flags or config keys

### Magic numbers

- Numeric literals other than `0`, `1`, `-1` (these are generally acceptable)
- HTTP status codes used as raw integers (`404`, `200`, `403`)
- Timeout values, retry counts, page sizes
- Percentage thresholds, scoring weights

### Reimplemented patterns

- Manual date/time formatting (vs `timezone.now()`, `timedelta`, etc.)
- Manual decimal rounding (vs `Decimal` utilities)
- Manual queryset filtering patterns that exist as manager methods
- Re-evaluating the same queryset for count/IDs/rows instead of materializing once
- Manual string normalization that exists as a utility
- Manual permission checks that exist as policy functions
- Manual task dispatch, HTTP method checks, resource clients, or response parsing
  where the framework/repository already provides `.delay()`, decorators, or a
  typed resource abstraction
- `dict[str, Any]` or `Any` for a stable known shape when a `TypedDict`, dataclass,
  protocol, or precise mapping already exists

### Repeated patterns

- Same literal appearing 2+ times in the scanned files
- Copy-pasted production logic blocks that could use an existing helper
- Repeated test factories, POST payloads, patch setup, or row creation where the
  test suite already has a fixture/factory/helper
- Added flags, helpers, or branches used only by tests and no production caller

---

## Step 4: Search for Existing Replacements

For each candidate, search in this order (respecting product boundary from
Step 2). Record the query and all credible matches; a claim that no replacement
exists without search evidence is incomplete.

### 1. Symbol and caller discovery

```bash
# Search the candidate name, semantic synonyms, imports, and old inline shape
rg "<candidate|synonym|literal>" <product-scope>
rg "<new_helper_or_flag>" --glob '*.py'
```

Use caller discovery to detect test-only APIs, duplicate implementations, and
nearby canonical abstractions. Read the candidate replacement before recommending
it: verify return shape, query/network behavior, caching, permissions, and error
semantics. Reuse that adds an API call or weakens a shared contract is not reuse.

### 2. Constants, enums, and stable types

```bash
# Common constant locations
Grep for the literal value or a semantically similar constant name in:
  utils/constants.py
  optimo_core/services/constants.py
  optimo_surveys/constants.py
  <app>/constants.py  (for the current app)
  settings/*.py
```

Also search for `TypedDict`, dataclasses, protocols, `TextChoices`, and
`IntegerChoices` that describe any newly added stable dictionaries or literals.

### 3. Utility and resource modules

```bash
# Common utility locations
Grep for similar function names or patterns in:
  utils/*.py
  optimo_core/utils/*.py
  <app>/utils.py or <app>/utils/*.py
```

Include shared API/resource clients and framework-native facilities (Django
view decorators, task `.delay()`, admin permission hooks) rather than limiting
the search to small utility functions.

### 4. Model choices (TextChoices / IntegerChoices)

```bash
# Search for Django choice enums
Grep for "TextChoices\|IntegerChoices" in models.py and choices.py files
  within the search scope
```

### 5. Service methods and test support

```bash
# Search for existing service classes with similar logic
Grep in:
  <app>/services/*.py
  optimo_core/services/*.py
```

Search current-app services, managers, tests/conftest files, factories, and
fixture modules for established setup and behavior.

### 6. Django, task-runner, and DRF built-ins

Check if the hardcoded value maps to a well-known constant:

| Hardcoded value | Replacement                            |
| --------------- | -------------------------------------- |
| `200`           | `rest_framework.status.HTTP_200_OK`    |
| `201`           | `rest_framework.status.HTTP_201_CREATED` |
| `400`           | `rest_framework.status.HTTP_400_BAD_REQUEST` |
| `403`           | `rest_framework.status.HTTP_403_FORBIDDEN` |
| `404`           | `rest_framework.status.HTTP_404_NOT_FOUND` |
| `"utf-8"`       | Usually fine as-is                     |
| Raw `datetime.now()` | `django.utils.timezone.now()`     |
| Raw `json.dumps()` on response | `JsonResponse` or DRF serializer |

---

## Step 5: Tag Findings by Severity

### `[BLOCKING]`

- Hardcoded secrets, API keys, passwords, database connection strings, or tokens.
- Reimplementing a canonical abstraction when the copy creates a correctness,
  permission, tenant, or unbounded query/network regression.

These must be fixed immediately.

### `[SHOULD_FIX]`

The value matches an existing constant/type, the pattern reimplements an
existing utility/framework facility, or repeated branch code should reuse an
existing fixture/helper/query result. Include the exact import path or local
symbol path:

```
[SHOULD_FIX] optimo_surveys/views/response.py:42
  Current:  status_code = 400
  Replace:  from rest_framework import status; status_code = status.HTTP_400_BAD_REQUEST
```

### `[NIT]`

The value could benefit from being a constant, but no existing constant was
found. This is a suggestion for future improvement, not a required change.

---

## Step 6: Present Findings

For each finding, show:

```
[SEVERITY] file_path:line_number
  Current code:   <the line with the hardcoded value>
  Existing replacement: <constant/utility name>
  Import path:    <from X import Y>
  Reason:         <why this replacement is better>
```

Group findings by file, then by severity within each file.

---

## Step 7: Apply Fixes (if `--apply`)

When `--apply` is passed:

1. For each `[BLOCKING]` and `[SHOULD_FIX]` finding:
   - Add the necessary import (respecting existing import style)
   - Replace the hardcoded value with the constant/utility
   - Do **not** fix `[NIT]` findings automatically

2. After all replacements, run quality gates:

```bash
.bin/ruff check --fix <modified-files>
.bin/ruff format <modified-files>
.bin/ty check <modified-files>
```

3. Stage modified files:

```bash
git add <modified-files>
```

---

## Step 8: Output Summary

```
Codebase Reuse Finder Summary
==============================
Scope: <files/directory scanned>
Product boundary: <Optimo | Diversio | Shared>

Files analyzed: <N>

Findings:
  [BLOCKING]:   <N>
  [SHOULD_FIX]: <N>
  [NIT]:        <N>

Search evidence:
  - <query> → <credible matches inspected>
Top reuse opportunities:
  1. <constant/utility/type/helper> — used in <N> places, could replace <N> occurrences
  2. <constant/utility> — ...
  3. <constant/utility> — ...

<if --apply>
Applied fixes: <N> ([BLOCKING] + [SHOULD_FIX] only)
Quality gates: passed
Files staged: <list>
</if>
```

---

## Rules

- **Respect the Diversio/Optimo product boundary** — never suggest cross-product
  imports.
- **`utils/` is shared** — always search `utils/` regardless of product.
- **Don't flag `0`, `1`, `-1`** — these are generally acceptable magic numbers.
- **Include import paths** — every `[SHOULD_FIX]` must include a working import
  statement.
- **Search before abstraction** — prefer existing symbols. If no canonical symbol
  exists, report repeated newly introduced code as `[NIT]` with a local extraction
  option; do not invent a cross-module abstraction without evidence.
- **Verify replacement semantics** — compare return shape, I/O/query count,
  caching, permissions, and exceptions before recommending reuse.
- **Stable shapes deserve stable types** — added `Any` is not acceptable merely
  because the type checker permits it; find/reuse the precise schema when known.
- **`--apply` only fixes `[BLOCKING]` and `[SHOULD_FIX]`** — `[NIT]` findings
  are informational only.

---

## Example Prompts

> `/codebase-reuse-finder`
>
> Scans all staged and unstaged changes for reuse opportunities.

> `/codebase-reuse-finder optimo_surveys/views/`
>
> Scans all files in the optimo_surveys views directory.

> `/codebase-reuse-finder optimo_core/services/onboarding.py --apply`
>
> Scans the file and automatically applies fixes for BLOCKING and SHOULD_FIX
> findings.

---

## Example Finding Output

```
[SHOULD_FIX] optimo_surveys/views/response.py:42
  Current code:   if response.status_code == 400:
  Existing replacement: HTTP_400_BAD_REQUEST
  Import path:    from rest_framework.status import HTTP_400_BAD_REQUEST
  Reason:         DRF provides named constants for all HTTP status codes

[SHOULD_FIX] optimo_core/services/invitation.py:87
  Current code:   expires_in = 72 * 60 * 60  # 72 hours
  Existing replacement: INVITATION_EXPIRY_SECONDS
  Import path:    from optimo_core.services.constants import INVITATION_EXPIRY_SECONDS
  Reason:         This exact value is already defined as a named constant

[BLOCKING] dashboardapp/views/export.py:15
  Current code:   api_key = "sk-prod-abc123..."
  Existing replacement: settings.EXPORT_API_KEY
  Import path:    from django.conf import settings
  Reason:         Hardcoded API key — must use settings/environment variable

[NIT] survey/tasks.py:203
  Current code:   batch_size = 500
  Existing replacement: (none found)
  Reason:         Consider extracting to a constant if used in multiple places
```
