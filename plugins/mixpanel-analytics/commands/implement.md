---
description: Implement new MixPanel tracking events using the mixpanel-analytics Skill.
---

Run your `mixpanel-analytics` Skill in **implement** mode.

**Flags:**
- `--dry-run` – Preview what would be created without making changes

Focus on:

- Following the 7-step implementation checklist to add new MixPanel events.
- Creating event constants, Pydantic schemas, registry entries, service helpers,
  and tests.
- Enforcing PII protection: no names, emails, or phone numbers in schemas.
- Using correct patterns: keyword-only arguments, try-except fire-and-forget,
  structured logging with UUIDs only.
- Setting `is_cron_job` and `cron_execution_timestamp` only when needed for
  time alignment or event ordering.

After implementation:

- Run post-implementation validations (Ruff, active type gate, Django check,
  pytest). Type gate detection order: `ty` (if configured), then `pyright`,
  then `mypy`.
- Report what was created and any remaining issues.
- Suggest running `/mixpanel-analytics:review` to validate the implementation.
