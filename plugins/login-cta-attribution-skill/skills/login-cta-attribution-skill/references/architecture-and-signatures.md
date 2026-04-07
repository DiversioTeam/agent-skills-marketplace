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

## Token Propagation Flow (Simplified)

High-level summary; see the 9-point chain under Mixpanel Integration Notes
for the authoritative step-by-step path.

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

The `SourceAttributionMetadataTD` TypedDict, builder
(`build_source_attribution_metadata`), and serializer
(`serialize_source_attribution_metadata`) live in:

- `optimo_core/utils/source_attribution.py`

Builder-layer fields (used during CTA → magic-link construction):

- `login_cta_source` — enum-typed platform source
- `login_cta_source_detail` — enum-typed action detail
- `redirect_path`
- `magic_link_action`
- `slack_button`
- `slack_tab`
- `teams_button`
- `teams_tab`
- `cta_parse_failed`

**Field rename at analytics boundary**: the builder stores
`login_cta_source` / `login_cta_source_detail`, but model parsers
(`magic_link.py`, `auth.py`) and `MixpanelSessionContextSchema` expose these
as `login_source` / `login_source_detail`. This rename happens in the model
parser layer (chain points 6-7). If you add a new attribution field whose
builder-layer name differs from its analytics-layer name, both names must be
handled in the model parsers.

## Parser Behavior

`parse_cta_source(cta_source, expected_source)` is the sole CTA parser:

- Returns `PlatformAttributionNT` on valid input, `None` on invalid input.
- Validates against `ALLOWED_CTA_SOURCES` allowlist.
- Enforces channel consistency: the parsed source must match
  `expected_source` (e.g., a Slack endpoint cannot persist Teams attribution).

CTA views should handle `None` returns with resilient defaults per platform.

## Mixpanel Integration Notes

Attribution fields flow through a 9-point chain. When adding a new attribution
dimension (e.g., `teams_tab`), ALL points must be updated or the field is
silently dropped:

1. **URL builder** (`optimo_integrations/utils/platform_magic_links.py: build_stable_teams_cta_url`) — adds query param to CTA URL
2. **CTA view** (`optimo_integrations/teams/views.py` or `optimo_integrations/slack/views.py`) — reads query param from `request.GET`
3. **Magic link builder** (`optimo_integrations/utils/platform_magic_links.py: build_login_magic_link_for_user`) — accepts param and passes to metadata builder
4. **Attribution metadata builder** (`optimo_core/utils/source_attribution.py: build_source_attribution_metadata`) — converts raw string to enum via `from_raw_to_enum()`, stores in `SourceAttributionMetadataTD`
5. **Attribution metadata serializer** (`optimo_core/utils/source_attribution.py: serialize_source_attribution_metadata`) — converts enum back to string for JSON storage. Must extract and serialize the new field or it is dropped during DB persistence
6. **Model parser — magic link** (`optimo_core/models/magic_link.py: parsed_source_attribution_metadata`) — reads field from stored JSON via `raw.get("field_name")` and passes to builder
7. **Model parser — auth token** (`optimo_core/models/auth.py: parsed_source_attribution_metadata`) — same as above for auth tokens
8. **Analytics service** (`optimo_analytics/service/core.py: get_session_contexts_batch`) — reads from `parsed_attribution["field_name"]` into `MixpanelSessionContextSchema`
9. **Event flattening** (`optimo_analytics/schemas.py`) — the field must be listed in the `include_from_session` default set on **both** `MixpanelLoginEventPropertiesSchema.from_session_context()` and `MixpanelLogoutEventPropertiesSchema.from_session_context()`, otherwise it is stored on the session context but excluded from the actual Mixpanel event payload

**Parity rule**: Slack and Teams must have matching attribution chains. If Slack
has `slack_tab`, Teams must have `teams_tab` at all 9 points. Missing any point
causes silent data loss in Mixpanel events.

**Current attribution fields** that must be in all `include_from_session` sets:

```python
"login_source",
"login_source_detail",
"slack_button",
"slack_tab",
"teams_button",
"teams_tab",
"cta_parse_failed",
```

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
| Metadata TypedDict, builder, and serializer | `optimo_core/utils/source_attribution.py` |
| Stable URL builders + magic link builder | `optimo_integrations/utils/platform_magic_links.py` |
| Slack CTA view | `optimo_integrations/slack/views.py` |
| Teams CTA view | `optimo_integrations/teams/views.py` |
| Email CTA view | `optimo_core/dashboard_cta_views.py` |
| Magic link model (parsed attribution) | `optimo_core/models/magic_link.py` |
| Auth token model (parsed attribution) | `optimo_core/models/auth.py` |
| Analytics session context schema | `optimo_analytics/schemas.py` |
| Analytics session context builder | `optimo_analytics/service/core.py` |
| Login/logout event flattening | `optimo_analytics/schemas.py` (include_from_session sets) |
| Digest base links | `optimo_surveys/digest/deep_links.py` |
| Digest Slack formatter | `optimo_surveys/digest/slack_formatter.py` |
| Digest Teams formatter | `optimo_surveys/digest/teams_formatter.py` |
| Auth exchange | `optimo_core/services/authentication_service.py` |
| Knox token creation | `optimo_core/auth/knox_auth.py` |
| Attribution-focused tests | `optimo_core/tests/test_login_attribution*.py` |

## Common Enum Values (Typical)

Platform source values (`LoginSourceChoices`):

- `slack`
- `teams`
- `email`

Common detail values (`LoginSourceDetailChoices`):

- `weekly_digest`
- `survey_complete`
- `dashboard_cta`
- `team_health_alerts`
- `team_health_profile`

Magic-link action values (`MagicLinkActionChoices`):

- `login`
- `invite`
- `signup`
- `verify_email`

Slack tab values (`SlackTabChoices`):

- `messages`
- `home`

Teams tab values (`TeamsTabChoices`):

- `optimo_pulse`
- `how_it_works`
