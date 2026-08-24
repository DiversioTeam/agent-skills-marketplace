---
description: Find existing types, constants, helpers, clients, and framework patterns to reuse
---

Use your `codebase-reuse-finder` Skill to scan current changes or a specified
file/directory or full branch for hardcoded values, weakened stable types,
duplicated setup/queries, and reimplemented repository/framework patterns,
following the workflow and product boundary rules defined in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:

1. Determine scope (explicit argument, otherwise full PR/branch diff plus staged, unstaged, and untracked local changes).
2. Auto-detect product boundary (Optimo vs Diversio vs Shared).
3. Extract candidates (literals, `Any`, repeated setup/queries, wrappers).
4. Search for existing replacements (types, enums, clients, helpers, fixtures,
   decorators/task APIs) and verify their behavioral/I/O contract.
5. Tag findings by severity (BLOCKING, SHOULD_FIX, NIT).
6. Present findings grouped by file with import paths.

If `--apply` is provided, implement BLOCKING and SHOULD_FIX replacements,
run ruff and ty, and stage modified files.
