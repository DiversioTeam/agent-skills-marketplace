This file is referenced from `SKILL.md` to keep the main Skill short and portable.

# Review Mode

## Review Checklist

### 1. PII Protection (CRITICAL - P0)

**MUST CHECK**:
- [ ] No `first_name`, `last_name`, `full_name`, `display_name` in schemas
- [ ] No `email`, `email_address`, `user_email` fields
- [ ] No `phone`, `phone_number`, `phone_e164` fields
- [ ] No `address`, `city`, `country` as free-text fields
- [ ] All identifiers are UUIDs as strings (not UUID objects)
- [ ] `organization_name` is ONLY sent to MixPanel, never logged

### 2. Event Registration Completeness (P1)

**MUST VERIFY**:
- [ ] Event constant exists in `constants.py` under `MixPanelEvent`
- [ ] Schema class exists in `schemas.py`
- [ ] Event is registered in `registry.py` `_EVENT_SCHEMA_REGISTRY`
- [ ] Schema inherits from `MixpanelSuperEventPropertiesSchema`

### 3. Schema Design (P1)

**MUST VERIFY**:
- [ ] All UUID fields are typed as `str`, not `UUID`
- [ ] All required fields have `Field(description="...")`
- [ ] Uses `STRICT_MODEL_CONFIG` or `ALIASED_MODEL_CONFIG` appropriately
- [ ] Enum fields use `SystemRole | None` pattern
- [ ] Docstring describes when the event is tracked
- [ ] Base schema fields from `MixpanelSuperEventPropertiesSchema` are NOT
      redefined as `Optional[str]` - pass empty string `""` for missing values

### 4. Service Method Patterns (P1)

**MUST VERIFY**:
- [ ] Public method is `@classmethod`
- [ ] Uses keyword-only arguments (`*,` after cls)
- [ ] Has try-except wrapper (fire-and-forget)
- [ ] Exception handler logs with structured fields
- [ ] Private implementation is `@staticmethod`

### 5. Test Coverage (P2)

**MUST HAVE**:
- [ ] Schema validation tests
- [ ] Registry registration test
- [ ] Service tracking test with `mock_mixpanel`
- [ ] Non-blocking test (exception doesn't propagate)
- [ ] Uses `pytestmark = [pytest.mark.django_db]`

### 6. Naming Conventions (P2)

**Event names**: `{prefix}.{object}.{action}[.error]`
**Schema names**: `Mxp{Domain}{Action}EventSchema`
**Helper names**: `OptimoMixpanel{Domain}TrackHelper`

### 7. `is_cron_job` Usage (P2)

**NOTE**: Not all background jobs need `is_cron_job=True`. Only use when:
1. API time and tracking time need to align
2. Events with same timestamp need ordering

**IF `is_cron_job=True` is used, MUST VERIFY**:
- [ ] `cron_execution_timestamp` is provided as Unix milliseconds
- [ ] Event name does NOT contain "cron"

### 8. Timestamp Handling (P2)

**MUST VERIFY**:
- [ ] Uses `datetime_to_timestamp_ms()` for MixPanel timestamps
- [ ] Never sends ISO 8601 strings to MixPanel

### 9. distinct_id Selection (P1)

**distinct_id MUST strictly follow this fallback hierarchy**:

1. **Primary**: User's UUID (the authenticated user performing the action)
2. **Fallback 1**: `org_<organization_uuid>` (when no user context exists)
3. **Fallback 2**: Context-specific ID based on the entity being tracked:
   - Slack workspace: `slack_<slack_workspace_id>`
   - API key: `apikey_<api_key_id>`
   - Webhook: `webhook_<webhook_id>`

**NEVER pass organization_id directly as distinct_id** - always prefix with `org_`.

**MUST VERIFY**:

- [ ] distinct_id is user's UUID when user context is available
- [ ] distinct_id uses `org_<uuid>` prefix when falling back to organization
- [ ] distinct_id uses appropriate prefix for context-specific fallbacks
- [ ] distinct_id is NEVER a raw organization_id without prefix

### 10. Export Completeness (P3)

**MUST VERIFY**:
- [ ] New helper classes exported in `service/__init__.py`
- [ ] Added to `__all__` list

## Automated Checks

```bash
# 1. PII Scan
grep -rn "first_name\\|last_name\\|email\\|phone\\|address" optimo_analytics/schemas.py

# 2. UUID Type Check
grep -rn ": UUID" optimo_analytics/schemas.py

# 3. Registration Check
for event in $(grep "^    [A-Z_]* = " optimo_analytics/constants.py | cut -d'=' -f1 | tr -d ' '); do
    grep -q "$event" optimo_analytics/registry.py || echo "UNREGISTERED: $event"
done

# 4. Keyword-only Check
grep -rn "def track_" optimo_analytics/service/*.py | while read line; do
    file=$(echo $line | cut -d: -f1)
    linenum=$(echo $line | cut -d: -f2)
    if ! sed -n "$((linenum+1)),$((linenum+5))p" "$file" | grep -q '\\*,'; then
        echo "MISSING *,: $line"
    fi
done
```

## Review Output Format

```markdown
# MixPanel Implementation Review

**Branch**: {branch}
**Scope**: {scope}
**Date**: {date}

## Summary

| Category | Status | Issues |
|----------|--------|--------|
| PII Protection | PASS/FAIL | {count} |
| Event Registration | PASS/FAIL | {count} |
| Schema Design | PASS/FAIL | {count} |
| Service Patterns | PASS/FAIL | {count} |
| Test Coverage | PASS/FAIL | {count} |

## Issues Found

### [P0] CRITICAL - {title}
**File**: `path:line`
**Issue**: Description
**Fix**: How to fix

### [P1] HIGH - {title}
...

## Recommendations

1. ...
2. ...
```

## Severity Tags

- `[P0]` CRITICAL – PII violations, security issues; must fix before merge
- `[P1]` HIGH – Missing registrations, pattern violations; strongly recommended
- `[P2]` MEDIUM – Test coverage gaps, naming issues; should fix
- `[P3]` LOW – Minor improvements; nice to have

---

## Post-Review Actions

After review, if issues found:
1. Create todo list of fixes
2. Apply fixes using `/mixpanel-analytics:implement`
3. Re-run review to verify

If review passes:
1. Run `/monty-code-review:code-review` for general code quality
2. Run `/backend-atomic-commit:pre-commit` for commit preparation
3. Run tests: `.bin/pytest optimo_analytics/tests/ -v --dc=TestLocalApp`

