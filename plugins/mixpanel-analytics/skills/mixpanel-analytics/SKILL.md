---
name: mixpanel-analytics
description: "Mixpanel analytics tracking implementation + review skill for Django optimo_analytics: add events and audit for PII safety, schema design, and code quality."
allowed-tools: Bash Read Edit Write Glob Grep
---

# MixPanel Analytics Skill

## When to Use This Skill

Use this Skill in the Django4Lyfe backend when working with MixPanel analytics
tracking in the `optimo_analytics` module:

- `/mixpanel-analytics:implement` – to **implement** new MixPanel tracking events
  or update existing ones following established patterns (7-step checklist).
- `/mixpanel-analytics:review` – to **review** MixPanel implementations for
  correctness, PII protection, and adherence to Django4Lyfe standards.

## Example Prompts

### Implement Mode

- "Use `/mixpanel-analytics:implement` to add a new event for tracking when a
  user completes their profile setup."
- "Run `/mixpanel-analytics:implement svc.surveys.reminder_sent` to add tracking
  for survey reminder notifications."
- "Implement MixPanel tracking for the new HRIS CSV validation feature using
  `/mixpanel-analytics:implement`."

### Review Mode

- "Run `/mixpanel-analytics:review staged` to check my staged MixPanel changes
  for PII violations and pattern compliance."
- "Use `/mixpanel-analytics:review branch` to audit all analytics changes on
  this feature branch."
- "Review the entire optimo_analytics module with `/mixpanel-analytics:review all`."

## Modes

This Skill behaves differently based on how it is invoked:

- `implement` mode – invoked via `/mixpanel-analytics:implement`:
  - Guides implementation of new MixPanel events through 7 steps.
  - Creates constants, schemas, registry entries, service methods, and tests.
  - Enforces PII protection and code patterns.
- `review` mode – invoked via `/mixpanel-analytics:review`:
  - Audits existing implementations for compliance.
  - Checks PII protection, schema design, service patterns, and test coverage.
  - Generates structured review reports with severity tags.

## Environment & Context Gathering

When this Skill runs, gather context first:

```bash
# Git context
git branch --show-current
git status --porcelain
git diff --cached --name-only | grep -E "optimo_analytics|mixpanel"

# Analytics module stats
grep -c "^    [A-Z_]* = " optimo_analytics/constants.py 2>/dev/null || echo "0"
grep -c "^class Mxp" optimo_analytics/schemas.py 2>/dev/null || echo "0"
grep -c "MixPanelEvent\." optimo_analytics/registry.py 2>/dev/null || echo "0"
ls -1 optimo_analytics/service/*.py 2>/dev/null | xargs -I{} basename {} .py
```

Read key reference files:
- `optimo_analytics/AGENTS.md` – module-level rules and PII guidelines
- `optimo_analytics/schemas.py` – existing schema patterns
- `optimo_analytics/service/AGENTS.md` – service layer patterns
- `optimo_analytics/tests/AGENTS.md` – test patterns

---

# Implementation Mode

For the full templates and step-by-step implementation checklist, use:
- [references/implementation.md](references/implementation.md)

Checklist (summary):
1. Add event constant (`optimo_analytics/constants.py`)
2. Create schema (`optimo_analytics/schemas.py`)
3. Register schema (`optimo_analytics/registry.py`)
4. Add tracking helper (`optimo_analytics/service/{domain}.py`)
5. Export helper (`optimo_analytics/service/__init__.py`)
6. Add tests (`optimo_analytics/tests/`)
7. Integrate call site in business logic

## Critical Rules (Do Not Violate)

- **PII**: never send names/emails/phones/addresses; identifiers are UUID strings; `organization_name` is allowed but never logged.
- **Fire-and-forget**: keyword-only args + try/except wrapper; never let tracking break business logic.
- **Event names**: `{prefix}.{object}.{action}[.error]`; do not encode execution context (e.g., "cron") in the event name.
- **distinct_id**: user UUID → `org_<org_uuid>` → `slack_`/`apikey_`/`webhook_`; never a raw org UUID.
- **Timestamps**: Unix ms (`datetime_to_timestamp_ms()`), not ISO strings.
- **`is_cron_job`**: only when tracking-time must align with the original action; include `cron_execution_timestamp` when set.

---

# Review Mode

For the full checklist, automated checks, and report template, use:
- [references/review.md](references/review.md)

Summary checklist:
- [P0] PII protection
- [P1] Event registration completeness
- [P1] Schema design + types
- [P1] Service method patterns
- [P2] Test coverage
- [P2] Naming, timestamps, `is_cron_job`, distinct_id, exports

## References

- Implementation templates: [references/implementation.md](references/implementation.md)
- Review checklist + report template: [references/review.md](references/review.md)

## Compatibility Notes

This Skill is designed to work with both Claude Code and OpenAI Codex.

- Claude Code: install the corresponding plugin and use its slash commands (see `plugins/mixpanel-analytics/commands/`).
- Codex: install the Skill directory and invoke `name: mixpanel-analytics`.

For installation, see this repo's `README.md`.
