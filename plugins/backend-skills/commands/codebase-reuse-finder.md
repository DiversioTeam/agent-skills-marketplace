---
description: Scan code for hardcoded values and find existing constants/utilities
---

Use your `codebase-reuse-finder` Skill to scan current changes or a specified
file/directory for hardcoded values, magic numbers, and reimplemented patterns,
following the workflow and product boundary rules defined in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:

1. Determine scope (argument, staged changes, or unstaged changes).
2. Auto-detect product boundary (Optimo vs Diversio vs Shared).
3. Extract candidates (string literals, magic numbers, reimplemented patterns).
4. Search for existing replacements (constants, utilities, model choices, DRF built-ins).
5. Tag findings by severity (BLOCKING, SHOULD_FIX, NIT).
6. Present findings grouped by file with import paths.

If `--apply` is provided, implement BLOCKING and SHOULD_FIX replacements,
run ruff and ty, and stage modified files.
