# Login CTA Attribution: Architecture and Signatures

This file holds deep implementation details referenced by the main
`SKILL.md` for progressive disclosure.

## Two-Layer Button Attribution Model

Use one layer per CTA path.

### Layer 1: URL Generation Time

Use for one-CTA-per-button contexts (for example, Home tab links):

- `build_stable_slack_cta_url(..., slack_tab=..., slack_button=...)`
- `build_stable_teams_cta_url(..., teams_button=..., teams_tab=...)`

### Layer 2: Render Time

Use for multi-button contexts sharing a base link (for example, digest
formatters):

- `update_slack_cta_url_with_button_info(cta_url, ...)` (Slack)
- `update_teams_cta_url_with_button_info(cta_url, ...)` (Teams)

Applying both layers on the same path can cause double-attribution.

## Token Propagation Flow

```text
CTA URL click ->
CTA view parses source ->
magic link stores source_attribution_metadata ->
AuthenticationService exchanges token ->
OptimoAuthToken stores attribution ->
Mixpanel login event includes attribution fields
```

## CTA Source Pattern

Canonical source format:

```text
{platform}_{action}
```

Examples:

- `slack_weekly_digest`
- `teams_survey_complete`
- `email_weekly_digest`

## Function Signature Notes

Signatures evolve over time. Verify in-code before implementation.

### Stable URL Builders

```python
def build_stable_slack_cta_url(
    slack_user_uuid: UUID | str,
    *,
    source: str = CTA_SOURCE_SLACK_SURVEY_COMPLETE,
    session_uuid: str | None = None,
    redirect_path: str | None = None,
    slack_tab: SlackTabChoices | None = None,
    slack_button: SlackButtonChoices | None = None,
) -> str | None: ...

def build_stable_teams_cta_url(
    teams_user_uuid: UUID | str,
    *,
    source: str = CTA_SOURCE_TEAMS_SURVEY_COMPLETE,
    session_uuid: str | None = None,
    redirect_path: str | None = None,
    teams_button: TeamsButtonChoices | None = None,
    teams_tab: TeamsTabChoices | None = None,
) -> str | None: ...
```

### Direct Magic-Link Builder

```python
def build_login_magic_link_for_user(
    user: OptimoUser,
    *,
    login_cta_source: LoginSourceChoices,
    login_cta_source_detail: LoginSourceDetailChoices,
    session_uuid: str | None = None,
    expires_minutes: int = 15,
    ip_address: str | None = None,
    redirect_path: str | None = None,
    slack_button: SlackButtonChoices | None = None,
    slack_tab: SlackTabChoices | None = None,
    teams_button: TeamsButtonChoices | None = None,
    teams_tab: TeamsTabChoices | None = None,
    cta_parse_failed: bool | None = None,
) -> str | None: ...
```

## Source Attribution Metadata

Primary metadata structure lives in:

- `optimo_core/auth/magic_link.py`

Typical fields include:

- `login_cta_source`
- `login_cta_source_detail`
- `redirect_path`
- `magic_link_action`
- `slack_button`
- `slack_tab`
- `teams_button`
- `teams_tab`

Builder helper:

- `build_source_attribution_metadata(...)`

Use helper-based parsing/conversion conventions from the target codebase.

## Parser Behavior

Two parser modes often exist:

- `parse_cta_source()`:
  - lenient
  - returns `None` on invalid input
- `validate_strict_attribution()`:
  - strict
  - raises `ValueError` on invalid input

CTA views should handle parse failures with resilient defaults per platform.

## Mixpanel Integration Notes

Attribution fields flow through a 6-point chain. When adding a new attribution
dimension (e.g., `teams_tab`), ALL points must be updated or the field is
silently dropped:

1. **URL builder** (`platform_magic_links.py`) — adds query param to CTA URL
2. **CTA view** (`teams/views.py` or `slack/views.py`) — reads query param from request
3. **Magic link builder** (`platform_magic_links.py: build_login_magic_link_for_user`) — accepts and passes param
4. **Attribution metadata builder** (`source_attribution.py: build_source_attribution_metadata`) — converts to enum, stores in TypedDict
5. **Analytics schema** (`optimo_analytics/schemas.py: MixpanelSessionContextSchema`) — Pydantic field
6. **Analytics service** (`optimo_analytics/service/core.py: get_session_contexts_batch`) — reads from parsed attribution into schema

**Parity rule**: Slack and Teams must have matching attribution chains. If Slack
has `slack_tab`, Teams must have `teams_tab` at all 6 points. Missing any point
causes silent data loss in Mixpanel events.

## Token Refresh Notes

When token refresh re-issues auth tokens, attribution should be preserved:

- source
- source detail
- metadata payload fields (button/tab/action/redirect)

If new attribution keys are introduced, confirm refresh path copies them.

## Key Files

| Purpose | Path |
| --- | --- |
| Core attribution enums/constants/parser | `optimo_core/models/login_attribution.py` |
| Slack/Teams CTA enums + URL helpers | `optimo_core/models/login_attribution.py` |
| Metadata TypedDict and builder | `optimo_core/utils/source_attribution.py` |
| Stable URL builders | `optimo_integrations/utils/platform_magic_links.py` |
| Slack CTA view | `optimo_integrations/slack/views.py` |
| Teams CTA view | `optimo_integrations/teams/views.py` |
| Email CTA view | `optimo_core/dashboard_cta_views.py` |
| Digest base links | `optimo_surveys/digest/deep_links.py` |
| Digest Slack formatter | `optimo_surveys/digest/slack_formatter.py` |
| Digest Teams formatter | `optimo_surveys/digest/teams_formatter.py` |
| Auth exchange | `optimo_core/services/authentication_service.py` |
| Knox token creation | `optimo_core/auth/knox_auth.py` |
| Attribution-focused tests | `optimo_core/tests/test_login_attribution*.py` |

## Common Enum Values (Typical)

Platform source values:

- `slack`
- `teams`
- `email`

Common detail values:

- `weekly_digest`
- `survey_complete`
- `dashboard_cta`
- `team_health_alerts`
- `team_health_profile`

Magic-link action values may include:

- `login`
- `invite`
- `signup`
- `verify_email`

Slack tab values:

- `messages`
- `home`
