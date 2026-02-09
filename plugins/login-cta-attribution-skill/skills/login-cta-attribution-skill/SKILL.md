---
name: login-cta-attribution-skill
description: "CTA login attribution implementation skill for Django4Lyfe: guides adding new CTA sources, button/tab attribution, enum registration, and tests."
allowed-tools: Bash Read Edit Write Glob Grep
argument-hint: "[platform] [action] (e.g., slack survey_complete)"
---

# Login CTA Attribution Skill

## When to Use This Skill

Use this Skill in the Django4Lyfe backend when working with the CTA (Call-To-Action)
attribution system that tracks where users log into Optimo from (Slack, Teams, Email):

- `/login-cta-attribution-skill:implement` – to **implement** a new CTA source
  with proper attribution, enum registration, and URL generation.

## Example Prompts

- "Use `/login-cta-attribution-skill:implement` to add a new CTA source for
  Slack team health alerts."
- "Run `/login-cta-attribution-skill:implement slack survey_complete` to add
  survey completion attribution for Slack."
- "Add a new Teams CTA for weekly digest using
  `/login-cta-attribution-skill:implement teams weekly_digest`."
- "I need to track where users click from in our new email campaign —
  `/login-cta-attribution-skill:implement email new_campaign`."

## Architecture Overview

The attribution flow tracks user login sources through the system:

```
Platform (Slack/Teams/Email)
  → User clicks CTA button/link with ?source=... param
    → CTA View endpoint parses source via parse_cta_source()
      → Magic link stores attribution data
        → Auth exchange propagates to Knox token
          → Mixpanel event includes attribution
```

### CTA Source String Pattern

All CTA sources follow: `{platform}_{action}`

Examples: `slack_weekly_digest`, `teams_survey_complete`, `email_weekly_digest`

## Environment & Context Gathering

When this Skill runs, gather context first:

```bash
# Git context
git branch --show-current
git status --porcelain

# Check current attribution state
grep -c "CTA_SOURCE_" optimo_core/models/login_attribution.py 2>/dev/null || echo "0"
grep -c "ALLOWED_CTA_SOURCES" optimo_core/models/login_attribution.py 2>/dev/null || echo "0"
```

Read key reference files:
- `optimo_core/models/login_attribution.py` – core enums, constants, allowlist,
  parser, validation
- `optimo_integrations/slack/cta_choices.py` – Slack button/tab choices
- `optimo_integrations/teams/cta_choices.py` – Teams button choices

Quality checks (on changed files only):

- **`.bin/ruff`:** lint and format only the files you touched
  (`uv run ruff` wrapper). Run as:
  - `.bin/ruff check --fix <changed files>`
  - `.bin/ruff format <changed files>`
- **`.bin/ty`:** type-check only the files you touched
  (`uv run ty` wrapper). Mandatory and blocking. Run as:
  - `.bin/ty check <changed files>`
- **`python manage.py check`:** run Django system checks to catch remaining
  issues.
- Do not accept "baseline acceptable" type-check outcomes on touched files.
- Read local typing policy docs when present (for example
  `docs/python-typing-3.14-best-practices.md`, `TY_MIGRATION_GUIDE.md`).

---

## Implementation Mode

### Step 1: Identify Platform and Action

Determine from the user request:
- **Platform:** `slack`, `teams`, or `email`
- **Action:** What CTA is this? (e.g., `weekly_digest`, `survey_complete`,
  `dashboard_cta`, `team_health_alerts`)

If not clear, ask the user to clarify before proceeding.

### Step 2: Add to LoginSourceDetailChoices (if new action)

**File:** `optimo_core/models/login_attribution.py`

Only needed if the action does not already exist in `LoginSourceDetailChoices`.

```python
class LoginSourceDetailChoices(models.TextChoices):
    # Existing choices...
    NEW_ACTION = "new_action", "New Action CTA"
```

### Step 3: Create CTA Source Constant

**File:** `optimo_core/models/login_attribution.py`

Use the `Final` annotation and compose from enum values:

```python
CTA_SOURCE_{PLATFORM}_{ACTION}: Final[str] = (
    f"{LoginSourceChoices.{PLATFORM}.value}_{LoginSourceDetailChoices.{ACTION}.value}"
)
```

### Step 4: Register in ALLOWED_CTA_SOURCES

**File:** `optimo_core/models/login_attribution.py`

Add the new constant to the allowlist set. If `parse_cta_source()` returns
`None`, this step was missed:

```python
ALLOWED_CTA_SOURCES: Final[set[str]] = {
    # Existing sources...
    CTA_SOURCE_{PLATFORM}_{ACTION},
}
```

### Step 5: Add to VALID_DETAILS_BY_SOURCE

**File:** `optimo_core/models/login_attribution.py`

Register the action under the correct platform:

```python
VALID_DETAILS_BY_SOURCE: Final[dict[...]] = {
    LoginSourceChoices.{PLATFORM}: [
        # Existing details...
        LoginSourceDetailChoices.{ACTION},
    ],
}
```

### Step 6: Add Button Attribution (Slack/Teams Only)

Skip this step for Email — Email has no button/tab concept.

**For Slack:** `optimo_integrations/slack/cta_choices.py`

```python
class SlackButtonChoices(models.TextChoices):
    # Existing choices...
    NEW_BUTTON = "new_button", "New Button Label"  # .label MUST match UI text
```

Slack also has tab choices (`SlackTabChoices.HOME`, `SlackTabChoices.MESSAGES`).

**For Teams:** `optimo_integrations/teams/cta_choices.py`

```python
class TeamsButtonChoices(models.TextChoices):
    # Existing choices...
    NEW_BUTTON = "new_button", "New Button Label"  # .label MUST match UI text
```

Teams has NO tab concept.

### Step 7: Use in URL Generation

```python
from optimo_core.models.login_attribution import CTA_SOURCE_{PLATFORM}_{ACTION}

# For Slack:
from optimo_integrations.slack.cta_choices import (
    SlackButtonChoices,
    SlackTabChoices,
    update_cta_url_with_button_info,
)

base_url = build_stable_slack_cta_url(
    slack_user_uuid=user_uuid,
    source=CTA_SOURCE_{PLATFORM}_{ACTION},
)

final_url = update_cta_url_with_button_info(
    cta_url=base_url,
    slack_button=SlackButtonChoices.NEW_BUTTON,
    slack_tab=SlackTabChoices.HOME,
)

# Use enum label for button text (single source of truth)
button_text = SlackButtonChoices.NEW_BUTTON.label
```

---

## Critical Rules (Do Not Violate)

- **No magic strings:** Always use `CTA_SOURCE_*` constants and enum values.
  Never hardcode source strings like `"slack_weekly_digest"`.
- **Always register:** Every new source MUST be added to `ALLOWED_CTA_SOURCES`
  AND `VALID_DETAILS_BY_SOURCE`. Missing either causes silent failures.
- **Button label = UI text:** The `.label` property of button choice enums MUST
  match the actual button text rendered in the UI.
- **Platform isolation:** Never use `SlackButtonChoices` for Teams or vice versa.
  Each platform has its own choices module.
- **Enum values in tests:** Tests MUST use enum values
  (`LoginSourceChoices.SLACK.value`), not magic strings (`"slack"`).
- **Teams has no tabs:** Do not pass tab parameters for Teams URLs.
- **Email has no buttons/tabs:** Do not add button or tab choices for Email.

---

## Testing Guidelines

### Always Use Enum Values

```python
# WRONG - Magic strings
def test_attribution():
    assert token.login_source == "slack"
    assert token.login_source_detail == "weekly_digest"

# CORRECT - Enum values
from optimo_core.models.login_attribution import (
    LoginSourceChoices,
    LoginSourceDetailChoices,
)

def test_attribution():
    assert token.login_source == LoginSourceChoices.SLACK.value
    assert token.login_source_detail == LoginSourceDetailChoices.WEEKLY_DIGEST.value
```

### Test parse_cta_source()

```python
from optimo_core.models.login_attribution import (
    LoginSourceChoices,
    LoginSourceDetailChoices,
    parse_cta_source,
)

def test_parse_new_cta_source():
    result = parse_cta_source("{platform}_{action}")
    assert result is not None
    assert result.source == LoginSourceChoices.{PLATFORM}
    assert result.detail == LoginSourceDetailChoices.{ACTION}
```

### Test Button Attribution

```python
from optimo_integrations.slack.cta_choices import (
    SlackButtonChoices,
    SlackTabChoices,
    update_cta_url_with_button_info,
)

def test_button_attribution_in_url():
    base_url = "https://example.com/cta?source=slack_{action}"
    result = update_cta_url_with_button_info(
        cta_url=base_url,
        slack_button=SlackButtonChoices.NEW_BUTTON,
        slack_tab=SlackTabChoices.MESSAGES,
    )
    assert f"slack_button={SlackButtonChoices.NEW_BUTTON.value}" in result
    assert f"slack_tab={SlackTabChoices.MESSAGES.value}" in result
```

---

## Validation Checklist

Before marking implementation complete, verify:

- [ ] `LoginSourceDetailChoices` has the action (if new)
- [ ] `CTA_SOURCE_*` constant exists using `Final[str]` + enum composition
- [ ] Source is in `ALLOWED_CTA_SOURCES`
- [ ] Source is in `VALID_DETAILS_BY_SOURCE` for the correct platform
- [ ] Button enum exists (Slack/Teams only, skip for Email)
- [ ] Button `.label` matches actual UI text
- [ ] URL uses `update_cta_url_with_button_info()` (Slack/Teams only)
- [ ] Tests use enum values, not magic strings
- [ ] `parse_cta_source()` returns expected `PlatformAttributionNT` result
- [ ] Type gate passes on all touched files

After implementation:

- **Preferred:** Run `/backend-atomic-commit:pre-commit` to validate all touched
  files. This skill runs the full pre-commit suite (Ruff, ty, Django checks,
  djlint, security helpers) on changed files and auto-fixes what it can. Trust
  its output as the authoritative quality gate.
- **Fallback only** (if `/backend-atomic-commit:pre-commit` is not available):
  manually run on **changed files only**:
  1. `.bin/ruff check --fix <changed files>` and `.bin/ruff format <changed files>`
  2. `.bin/ty check <changed files>`
  3. `python manage.py check`
- Run pytest on attribution tests:
  `pytest optimo_core/tests/test_login_attribution*.py`
- Report what was created and any remaining issues.

---

## Key File Reference

| Purpose | File Path |
|---------|-----------|
| Core attribution enums, constants, allowlist | `optimo_core/models/login_attribution.py` |
| Slack button/tab choices | `optimo_integrations/slack/cta_choices.py` |
| Teams button choices | `optimo_integrations/teams/cta_choices.py` |
| Slack CTA view | `optimo_integrations/slack/views.py` |
| Teams CTA view | `optimo_integrations/teams/views.py` |
| Email CTA view | `optimo_core/dashboard_cta_views.py` |
| Magic link URL builders | `optimo_integrations/utils/platform_magic_links.py` |
| Digest deep links | `optimo_surveys/digest/deep_links.py` |
| Auth token exchange | `optimo_core/services/authentication_service.py` |
| Knox token creation | `optimo_core/auth/knox_auth.py` |
| Attribution tests | `optimo_core/tests/test_login_attribution*.py` |

### Existing Enums Quick Reference

**LoginSourceChoices (Platform):** `slack`, `teams`, `email`

**LoginSourceDetailChoices (Action):** `weekly_digest`, `survey_complete`,
`dashboard_cta`, `team_health_alerts`, `team_health_profile`

**SlackTabChoices:** `messages`, `home`

**SlackButtonChoices:** `go_to_dashboard`, `view_all_alerts`, `open_in_optimo`,
`employee_profile_link`

**TeamsButtonChoices:** `go_to_dashboard`, `open_in_optimo`

## Compatibility Notes

This Skill is designed to work with both Claude Code and OpenAI Codex.

- Claude Code: install the corresponding plugin and use its slash commands
  (see `plugins/login-cta-attribution-skill/commands/`).
- Codex: install the Skill directory and invoke
  `name: login-cta-attribution-skill`.

For installation, see this repo's `README.md`.
