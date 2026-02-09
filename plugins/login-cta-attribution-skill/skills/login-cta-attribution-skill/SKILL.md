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
      → Magic link stores attribution data in source_attribution_metadata
        → Auth exchange propagates to Knox token
          → Mixpanel event includes all attribution fields
```

### CTA Source String Pattern

All CTA sources follow: `{platform}_{action}`

Examples: `slack_weekly_digest`, `teams_survey_complete`, `email_weekly_digest`

### Two-Layer Button Attribution Architecture

The system has **two distinct layers** for adding button/tab attribution:

```
+------------------------------------------------------------------+
|                 TWO-LAYER BUTTON ATTRIBUTION                      |
+------------------------------------------------------------------+
|                                                                   |
|  LAYER 1: At URL Generation Time                                  |
|  ================================                                  |
|  Use when: One CTA URL = one button (e.g., Slack Home Tab)        |
|                                                                   |
|  Functions:                                                       |
|  - build_stable_slack_cta_url(..., slack_tab=, slack_button=)     |
|  - build_stable_teams_cta_url(..., teams_button=)                 |
|                                                                   |
|  Button params are BAKED INTO the URL at creation time.           |
|                                                                   |
+------------------------------------------------------------------+
|                                                                   |
|  LAYER 2: At Render Time                                          |
|  =======================                                          |
|  Use when: One base URL shared by multiple buttons (e.g., Digests)|
|                                                                   |
|  Function:                                                        |
|  - update_cta_url_with_button_info(cta_url, slack_button=, ...)   |
|                                                                   |
|  Button params are APPENDED to pre-built URL during rendering.    |
|  DigestDeepLinkGenerator returns BASE URLs without attribution.   |
|  Formatters (slack_formatter.py, teams_formatter.py) add buttons. |
|                                                                   |
+------------------------------------------------------------------+

CHOOSE THE RIGHT LAYER:
- Home Tab / single-button CTAs → Layer 1
- Digest formatters / multi-button contexts → Layer 2
- Using both = double-attribution bug!
```

### Token Propagation Flow

```
+---------------------------+
| User clicks CTA link      |
+------------+--------------+
             |
             v
+---------------------------+
| CTA View parses source    |
| via parse_cta_source()    |
+------------+--------------+
             |
             v
+---------------------------+
| build_login_magic_link_   |
| for_user() creates link   |
| with attribution metadata |
+------------+--------------+
             |
             v
+---------------------------+
| OptimoMagicLink stores    |
| source_attribution_       |
| metadata (JSONField)      |
+------------+--------------+
             |
             v
+---------------------------+
| AuthenticationService     |
| .exchange_token_for_auth()|
| extracts attribution      |
+------------+--------------+
             |
             v
+---------------------------+
| OptimoAuthToken stores:   |
| - login_source            |
| - login_source_detail     |
| - source_attribution_     |
|   metadata (JSONField)    |
+---------------------------+
```

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
- `optimo_core/auth/magic_link.py` – `SourceAttributionMetadataTD` TypedDict
  and `build_source_attribution_metadata()` function
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
# First, add the Literal-typed constant (for type safety)
NEW_ACTION_DETAIL: Literal["new_action"] = "new_action"

class LoginSourceDetailChoices(models.TextChoices):
    # Existing choices...
    NEW_ACTION = NEW_ACTION_DETAIL, "New Action CTA"

    @classmethod
    def from_raw_to_enum(cls, raw: str | None) -> LoginSourceDetailChoices | None:
        """Convert raw string to enum, returning None for invalid values."""
        if not raw:
            return None
        try:
            return cls(raw)
        except ValueError:
            return None
```

**CRITICAL:** Every enum MUST include the `from_raw_to_enum()` classmethod. This
is the standard conversion pattern used everywhere in the attribution system.

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

    @classmethod
    def from_raw_to_enum(cls, raw: str | None) -> SlackButtonChoices | None:
        """Convert raw string to enum, returning None for invalid values."""
        if not raw:
            return None
        try:
            return cls(raw)
        except ValueError:
            return None
```

Slack also has tab choices (`SlackTabChoices.HOME`, `SlackTabChoices.MESSAGES`).

**For Teams:** `optimo_integrations/teams/cta_choices.py`

```python
class TeamsButtonChoices(models.TextChoices):
    # Existing choices...
    NEW_BUTTON = "new_button", "New Button Label"  # .label MUST match UI text

    @classmethod
    def from_raw_to_enum(cls, raw: str | None) -> TeamsButtonChoices | None:
        """Convert raw string to enum, returning None for invalid values."""
        if not raw:
            return None
        try:
            return cls(raw)
        except ValueError:
            return None
```

Teams has NO tab concept.

**MIGRATION NOTE:** Old button label constants like `SLACK_DASHBOARD_CTA_BUTTON_LABEL`
and `TEAMS_DASHBOARD_CTA_BUTTON_LABEL` in `constants.py` were REMOVED. Button
labels now live on the enum `.label` property. Use `SlackButtonChoices.GO_TO_DASHBOARD.label`.

### Step 7: Use in URL Generation

**Choose the appropriate layer based on your use case:**

#### Layer 1: Single Button CTAs (Home Tab, etc.)

Use `build_stable_slack_cta_url()` or `build_stable_teams_cta_url()` with
button/tab params baked in:

```python
from optimo_core.models.login_attribution import CTA_SOURCE_{PLATFORM}_{ACTION}
from optimo_integrations.slack.cta_choices import SlackButtonChoices, SlackTabChoices

# Slack - button/tab baked into URL at generation time
url = build_stable_slack_cta_url(
    slack_user_uuid=user_uuid,
    source=CTA_SOURCE_{PLATFORM}_{ACTION},
    redirect_path="/alerts",  # Optional deep link
    slack_tab=SlackTabChoices.HOME,  # NEW: baked into URL
    slack_button=SlackButtonChoices.VIEW_ALL_ALERTS,  # NEW: baked into URL
)

# Teams - teams_button baked into URL
url = build_stable_teams_cta_url(
    teams_user_uuid=user_uuid,
    source=CTA_SOURCE_{PLATFORM}_{ACTION},
    teams_button=TeamsButtonChoices.GO_TO_DASHBOARD,  # NEW: baked into URL
)
```

**Actual function signatures (post-PR):**

```python
def build_stable_slack_cta_url(
    slack_user_uuid: UUID | str,
    *,
    source: str = CTA_SOURCE_SLACK_SURVEY_COMPLETE,
    session_uuid: str | None = None,
    redirect_path: str | None = None,
    slack_tab: SlackTabChoices | None = None,       # ENUM type
    slack_button: SlackButtonChoices | None = None,  # ENUM type
) -> str | None:

def build_stable_teams_cta_url(
    teams_user_uuid: UUID | str,
    *,
    source: str = CTA_SOURCE_TEAMS_SURVEY_COMPLETE,
    session_uuid: str | None = None,
    redirect_path: str | None = None,
    slack_tab: SlackTabChoices | None = None,       # IGNORED for Teams (noqa: ARG001)
    slack_button: SlackButtonChoices | None = None,  # IGNORED for Teams (noqa: ARG001)
    teams_button: TeamsButtonChoices | None = None,  # ENUM type
) -> str | None:
```

#### Layer 2: Multi-Button Contexts (Digests)

Use `update_cta_url_with_button_info()` to append button attribution to a
pre-built base URL:

```python
from optimo_integrations.slack.cta_choices import (
    SlackButtonChoices,
    SlackTabChoices,
    update_cta_url_with_button_info,
)

# DigestDeepLinkGenerator returns BASE URL without button attribution
base_url = deep_link_generator.generate_slack_link()

# Formatter adds button attribution at render time
final_url = update_cta_url_with_button_info(
    cta_url=base_url,
    slack_button=SlackButtonChoices.NEW_BUTTON,
    slack_tab=SlackTabChoices.MESSAGES,
)

# Use enum label for button text (single source of truth)
button_text = SlackButtonChoices.NEW_BUTTON.label
```

### Step 8: Update Magic Link Creation (if creating direct links)

When creating magic links directly (not via stable CTA endpoints), use
`build_login_magic_link_for_user()` with the correct enum parameters:

```python
from optimo_core.models.login_attribution import (
    LoginSourceChoices,
    LoginSourceDetailChoices,
)
from optimo_integrations.utils.platform_magic_links import (
    build_login_magic_link_for_user,
)

# CORRECT: Use enum types for source params, string for button/tab
url = build_login_magic_link_for_user(
    user=user,
    login_cta_source=LoginSourceChoices.SLACK,          # ENUM, not string!
    login_cta_source_detail=LoginSourceDetailChoices.WEEKLY_DIGEST,  # ENUM!
    session_uuid=session_uuid,
    expires_minutes=15,
    ip_address=request.META.get("REMOTE_ADDR"),
    redirect_path="/alerts",
    slack_button=str(SlackButtonChoices.OPEN_IN_OPTIMO.value),  # String
    slack_tab=str(SlackTabChoices.HOME.value),  # String
)
```

**Actual function signature:**

```python
def build_login_magic_link_for_user(
    user: OptimoUser,
    *,
    login_cta_source: LoginSourceChoices,         # ENUM, NOT string!
    login_cta_source_detail: LoginSourceDetailChoices,  # ENUM, NOT string!
    session_uuid: str | None = None,
    expires_minutes: int = 15,
    ip_address: str | None = None,
    redirect_path: str | None = None,
    slack_button: str | None = None,   # String (raw value)
    slack_tab: str | None = None,      # String (raw value)
    teams_button: str | None = None,   # String (raw value)
) -> str | None:
```

---

## SourceAttributionMetadataTD and Builder Function

All attribution flows through the `SourceAttributionMetadataTD` TypedDict,
built via `build_source_attribution_metadata()`.

**File:** `optimo_core/auth/magic_link.py`

```python
class SourceAttributionMetadataTD(TypedDict):
    """Typed structure for magic link source attribution metadata."""
    login_cta_source: LoginSourceChoices | None
    login_cta_source_detail: LoginSourceDetailChoices | None
    redirect_path: str | None
    magic_link_action: MagicLinkActionChoices | None
    slack_button: SlackButtonChoices | None
    slack_tab: SlackTabChoices | None
    teams_button: TeamsButtonChoices | None


def build_source_attribution_metadata(
    *,
    login_cta_source: str | None,        # Accepts RAW STRINGS
    login_cta_source_detail: str | None,
    redirect_path: str | None = None,
    magic_link_action: str | None = None,
    slack_button: str | None = None,
    slack_tab: str | None = None,
    teams_button: str | None = None,
) -> SourceAttributionMetadataTD:
    """Build attribution metadata with automatic string-to-enum conversion.

    Uses from_raw_to_enum() on each field. Invalid values become None.
    """
```

**When to use:** All magic link creation must call this function to properly
structure attribution metadata. Without it, no attribution flows through to
the Knox token.

---

## MagicLinkActionChoices Enum

**File:** `optimo_core/models/login_attribution.py`

This enum defines the purpose of a magic link (stored in attribution metadata):

```python
class MagicLinkActionChoices(models.TextChoices):
    LOGIN = "login", "Login"
    INVITE = "invite", "Invite"
    SIGNUP = "signup", "Signup"
    VERIFY_EMAIL = "verify_email", "Verify Email"

    @classmethod
    def from_raw_to_enum(cls, raw: str | None) -> MagicLinkActionChoices | None:
        """Convert raw string to enum, returning None for invalid values."""
```

**Note:** For CTA flows, `magic_link_action` is **automatically set to `"login"`** inside
`build_login_magic_link_for_user()`. You do NOT need to pass it manually — the function
handles it internally. The Mixpanel event will show `"magic_link_action": "login"` for
all CTA-initiated logins.

---

## Django Model Fields

**OptimoAuthToken** has these attribution fields:
- `login_source` — CharField(max_length=20, choices=LoginSourceChoices.choices)
- `login_source_detail` — CharField(max_length=50)
- `source_attribution_metadata` — JSONField (stores full `SourceAttributionMetadataTD`)

**OptimoMagicLink** has:
- `source_attribution_metadata` — JSONField (stores full `SourceAttributionMetadataTD`)

If adding a new platform or attribution dimension, you may need migrations.

---

## Token Refresh Preserves Attribution

When tokens are refreshed via `AuthenticationService.refresh_token()`, the old
token's attribution data is extracted and passed to the new token. This includes:
- `login_source`
- `login_source_detail`
- Full `source_attribution_metadata` JSON (including `slack_button`, `slack_tab`,
  `teams_button`, `redirect_path`, `magic_link_action`)

**If adding new attribution fields, update the refresh preservation logic.**

---

## Mixpanel Schema Integration

**Files:** `optimo_analytics/schemas.py`, `optimo_analytics/service.py`

Six attribution fields are added to both `MixpanelSessionContextSchema` and
`MixpanelLoginEventPropertiesSchema`:
- `login_source`
- `login_source_detail`
- `magic_link_action`
- `slack_button`
- `slack_tab`
- `teams_button`

These are flattened from session context into login events via `from_session_context()`.

**If adding new attribution dimensions, update the Mixpanel schemas.**

---

## URL Query Parameters

CTA URLs include these query parameters:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `source` | Combined CTA source string | `slack_weekly_digest` |
| `slack_button` | Slack button attribution | `open_in_optimo` |
| `slack_tab` | Slack surface (HOME or MESSAGES) | `home` |
| `teams_button` | Teams button attribution | `go_to_dashboard` |
| `redirect` | Frontend path after login | `/alerts` |
| `session_uuid` | Survey session for debugging | UUID string |

---

## Parser Functions: parse_cta_source() vs validate_strict_attribution()

Two parser functions exist with different error handling:

| Function | Behavior | Use Case |
|----------|----------|----------|
| `parse_cta_source()` | **Lenient** - returns `None` on failure | CTA views (never crash on bad params) |
| `validate_strict_attribution()` | **Strict** - raises `ValueError` on failure | Programmatic validation |

**CTA View Fallback Behavior:**
When `parse_cta_source()` returns `None`, views fall back to defaults:
- **Slack view:** Falls back to `SLACK` + `WEEKLY_DIGEST`
- **Teams view:** Falls back to `TEAMS` + `WEEKLY_DIGEST`
- **Email view:** Falls back to `EMAIL` + `WEEKLY_DIGEST`

Views are resilient and never crash on bad source parameters.

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
- **Include from_raw_to_enum():** Every new enum MUST include this classmethod.
- **Choose correct layer:** Layer 1 for single-button CTAs, Layer 2 for
  multi-button contexts. Using both = double-attribution bug.

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
- [ ] New enum has `from_raw_to_enum()` classmethod
- [ ] `CTA_SOURCE_*` constant exists using `Final[str]` + enum composition
- [ ] Source is in `ALLOWED_CTA_SOURCES`
- [ ] Source is in `VALID_DETAILS_BY_SOURCE` for the correct platform
- [ ] Button enum exists (Slack/Teams only, skip for Email)
- [ ] Button `.label` matches actual UI text
- [ ] Correct layer chosen (Layer 1 vs Layer 2 for button attribution)
- [ ] `build_source_attribution_metadata()` called in magic link creation
- [ ] `SourceAttributionMetadataTD` fields populated for new attribution dimensions
- [ ] Tests use enum values, not magic strings
- [ ] `parse_cta_source()` returns expected `PlatformAttributionNT` result
- [ ] CTA view has fallback when `parse_cta_source()` returns None
- [ ] Type gate passes on all touched files
- [ ] Mixpanel schemas updated if new attribution fields added
- [ ] Token refresh logic preserves new attribution fields
- [ ] Platform AGENTS.md updated with new button/CTA rules
- [ ] Manual testing guide updated with new CTA scenario

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
  ```bash
  pytest optimo_core/tests/test_login_attribution*.py
  pytest optimo_core/tests/test_login_attribution_integration.py
  pytest optimo_integrations/tests/slack/test_home_cta.py
  pytest optimo_integrations/tests/test_magic_links_helpers.py
  pytest optimo_surveys/tests/digest/test_slack_formatter.py
  pytest optimo_surveys/tests/digest/test_teams_formatter.py
  ```
- Report what was created and any remaining issues.

---

## Key File Reference

| Purpose | File Path |
|---------|-----------|
| Core attribution enums, constants, allowlist | `optimo_core/models/login_attribution.py` |
| Attribution metadata TypedDict + builder | `optimo_core/auth/magic_link.py` |
| Slack button/tab choices | `optimo_integrations/slack/cta_choices.py` |
| Teams button choices | `optimo_integrations/teams/cta_choices.py` |
| Slack CTA view | `optimo_integrations/slack/views.py` |
| Teams CTA view | `optimo_integrations/teams/views.py` |
| Email CTA view | `optimo_core/dashboard_cta_views.py` |
| Magic link URL builders | `optimo_integrations/utils/platform_magic_links.py` |
| Digest deep links (base URLs) | `optimo_surveys/digest/deep_links.py` |
| Slack formatter (adds button attribution) | `optimo_surveys/digest/slack_formatter.py` |
| Teams formatter (adds button attribution) | `optimo_surveys/digest/teams_formatter.py` |
| Slack survey bot | `optimo_integrations/slack/survey_bot.py` |
| Teams survey bot | `optimo_integrations/teams/survey_bot.py` |
| Slack home tab events | `optimo_integrations/slack/events.py` |
| Teams cards | `optimo_integrations/teams/cards.py` |
| Auth token exchange | `optimo_core/services/authentication_service.py` |
| Knox token creation | `optimo_core/auth/knox_auth.py` |
| Mixpanel session/login schemas | `optimo_analytics/schemas.py` |
| Mixpanel service (reads token attribution) | `optimo_analytics/service.py` |
| Attribution tests | `optimo_core/tests/test_login_attribution*.py` |
| Integration tests | `optimo_core/tests/test_login_attribution_integration.py` |
| Manual testing guide | `optimo_analytics/docs/LoginCTA_AttributionTestingGuide.md` |
| Slack AGENTS.md (CTA rules) | `optimo_integrations/slack/AGENTS.md` |
| Teams AGENTS.md (CTA rules) | `optimo_integrations/teams/AGENTS.md` |

### Existing Enums Quick Reference

**LoginSourceChoices (Platform):** `slack`, `teams`, `email`

**LoginSourceDetailChoices (Action):** `weekly_digest`, `survey_complete`,
`dashboard_cta`, `team_health_alerts`, `team_health_profile`

**MagicLinkActionChoices:** `login`, `invite`, `signup`, `verify_email`

**SlackTabChoices:** `messages`, `home`

**SlackButtonChoices:** `go_to_dashboard`, `view_all_alerts`, `open_in_optimo`,
`employee_profile_link`

**TeamsButtonChoices:** `go_to_dashboard`, `open_in_optimo`

---

## Admin Panel

`OptimoMagicLinkAdmin` displays `source_attribution_metadata` summary in the
list view (showing "source -> detail"). Useful for debugging attribution issues.

---

## Compatibility Notes

This Skill is designed to work with both Claude Code and OpenAI Codex.

- Claude Code: install the corresponding plugin and use its slash commands
  (see `plugins/login-cta-attribution-skill/commands/`).
- Codex: install the Skill directory and invoke
  `name: login-cta-attribution-skill`.

For installation, see this repo's `README.md`.
