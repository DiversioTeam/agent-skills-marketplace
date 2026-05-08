---
name: codebase-reuse-finder
description: >
    Scan current changes for hardcoded values, magic numbers, and reimplemented
    patterns. Search the codebase for existing constants, utilities, and
    abstractions that could replace them. Reports findings with import paths.
    Respects the Diversio/Optimo product boundary.
user-invocable: true
argument-hint: '[file-or-directory] [--apply]'
allowed-tools: [Bash, Read, Glob, Grep, Edit]
---

# Codebase Reuse Finder Skill

Scan code for hardcoded values, magic numbers, and reimplemented patterns.
Search the codebase for existing constants, utilities, and abstractions that
could replace them. Standalone skill — use anytime, not tied to the PR workflow.

**Reference documentation:**

- `AGENTS.md` — product boundaries and global rules
- `docs/architecture/overview.md` — system architecture and module relationships

---

## Step 1: Determine Scope

Three ways to determine what code to scan:

### A: Explicit file or directory (argument)

If a file or directory is provided as argument, scan that directly.

### B: Staged and unstaged changes (default)

If no argument is provided, scan current changes:

```bash
# Staged changes
git diff --cached --name-only | grep -E '\.py$'

# Unstaged changes
git diff --name-only | grep -E '\.py$'
```

### C: Combined

If both argument and changes exist, scan only the argument.

If no argument and no changes, tell the user:

> "No changes detected and no file/directory specified. Please provide a target
> or make some changes first."

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
- Manual string normalization that exists as utility functions
- Manual permission checks that exist as policy functions

### Repeated patterns

- Same literal appearing 2+ times in the scanned files
- Copy-pasted logic blocks that could be a shared function

---

## Step 4: Search for Existing Replacements

For each candidate, search in this order (respecting product boundary from
Step 2):

### 1. Constants files

```bash
# Common constant locations
Grep for the literal value or a semantically similar constant name in:
  utils/constants.py
  optimo_core/services/constants.py
  optimo_surveys/constants.py
  <app>/constants.py  (for the current app)
  settings/*.py
```

### 2. Utility modules

```bash
# Common utility locations
Grep for similar function names or patterns in:
  utils/*.py
  optimo_core/utils/*.py
  <app>/utils.py or <app>/utils/*.py
```

### 3. Model choices (TextChoices / IntegerChoices)

```bash
# Search for Django choice enums
Grep for "TextChoices\|IntegerChoices" in models.py and choices.py files
  within the search scope
```

### 4. Service methods

```bash
# Search for existing service classes with similar logic
Grep in:
  <app>/services/*.py
  optimo_core/services/*.py
```

### 5. Django and DRF built-ins

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

Hardcoded secrets, API keys, passwords, database connection strings, or tokens.
These must be fixed immediately — they should use `settings` or environment
variables.

### `[SHOULD_FIX]`

The hardcoded value **matches an existing constant** or the pattern
**reimplements an existing utility**. Include the exact import path:

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

Top reuse opportunities:
  1. <constant/utility> — used in <N> places, could replace <N> hardcoded values
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
- **Don't create new constants** — this skill finds existing reuse opportunities,
  it does not create new abstractions.
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
