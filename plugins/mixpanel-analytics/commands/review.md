---
description: Review MixPanel tracking implementations using the mixpanel-analytics Skill.
---

Run your `mixpanel-analytics` Skill in **review** mode.

Scope options (pass as argument):
- `staged` - Review only staged changes (default)
- `branch` - Review all changes on current branch vs release
- `all` - Full audit of optimo_analytics module
- `file:path` - Review specific file

Focus on:

- **PII Protection (P0)**: No names, emails, phone numbers in schemas.
- **Event Registration (P1)**: Constants, schemas, and registry entries aligned.
- **Schema Design (P1)**: UUIDs as strings, proper Field descriptions, correct
  model configs.
- **Service Patterns (P1)**: Keyword-only args, try-except wrappers, structured
  logging.
- **Test Coverage (P2)**: Schema validation, registry, tracking, and non-blocking
  tests.
- **Naming Conventions (P2)**: Event, schema, and helper naming patterns.

Generate a structured review report with:

- Summary table showing pass/fail status per category.
- Issues found with severity tags (`[P0]`, `[P1]`, `[P2]`, `[P3]`).
- Specific file:line references and recommended fixes.
- Quality gate status (Ruff, active type gate, Django check, tests). Type gate
  detection order: `ty` (if configured), then `pyright`, then `mypy`.

If issues found, suggest using `/mixpanel-analytics:implement` to fix them.
