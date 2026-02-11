---
name: login-cta-attribution-skill
description: "CTA login attribution implementation skill for Django4Lyfe: guides adding new CTA sources, button/tab attribution, enum registration, and tests."
allowed-tools: Bash Read Edit Write Glob Grep
argument-hint: "[platform] [action] (e.g., slack survey_complete)"
---

# Login CTA Attribution Skill

## When to Use This Skill

Use this Skill in Django4Lyfe backend repos when implementing or updating login
CTA attribution for Slack, Teams, or Email.

Primary command:

- `/login-cta-attribution-skill:implement` - add or update a CTA source with
  correct enum registration, attribution plumbing, and tests.

## Example Prompts

- "Run `/login-cta-attribution-skill:implement slack survey_complete`."
- "Add a new Teams CTA source for weekly digest."
- "Implement email CTA attribution for our new campaign."

## Architecture Overview

High-level flow:

```text
CTA URL (?source=...) ->
CTA view parses source ->
magic link stores attribution metadata ->
auth exchange copies attribution to token ->
Mixpanel receives attribution fields
```

Button attribution has two valid layers:

1. Layer 1 (URL generation time): use stable URL builders with button/tab params.
2. Layer 2 (render time): append button/tab params to a base URL in formatters.

Use exactly one layer per CTA path to avoid double-attribution.

For concrete signatures and deeper architecture notes, read:
- `references/architecture-and-signatures.md`

## Environment & Context Gathering

Before coding:

```bash
git branch --show-current
git status --porcelain
```

Read these files first:

- `optimo_core/models/login_attribution.py`
- `optimo_core/auth/magic_link.py`
- `optimo_integrations/slack/cta_choices.py`
- `optimo_integrations/teams/cta_choices.py`
- `optimo_integrations/utils/platform_magic_links.py`

Also read local policy docs when present:

- `AGENTS.md`
- `docs/python-typing-3.14-best-practices.md`
- `TY_MIGRATION_GUIDE.md`

## Type Gate Detection (Mandatory)

This is a Python code-touching skill. Use this precedence unless target repo
docs/CI define a different order:

1. `ty`
2. `pyright`
3. `mypy`

Detect active checker:

- `ty` is active if any of:
  - `[tool.ty]` in `pyproject.toml`
  - `ty.toml`
  - `.bin/ty`
  - CI or pre-commit runs `ty`
- `pyright` is active if any of:
  - `pyrightconfig.json`
  - `[tool.pyright]` in `pyproject.toml`
  - CI or pre-commit runs `pyright`
- `mypy` is active if any of:
  - `mypy.ini` or `.mypy.ini`
  - `[tool.mypy]` in `pyproject.toml`
  - CI or pre-commit runs `mypy`

Command resolution order:

1. `.bin/<tool>`
2. `uv run <tool>`
3. `<tool>`

Examples:

```bash
# ty
.bin/ty check <changed python files>
uv run ty check <changed python files>

# pyright
.bin/pyright <changed python files>
uv run pyright <changed python files>

# mypy
.bin/mypy <changed python files>
uv run mypy <changed python files>
```

Strictness:

- Touched files must pass the active type gate with zero diagnostics.
- Do not accept "baseline acceptable" on touched files.
- Do not use blanket suppressions as default behavior.

## Quality Checks

Run on changed files (or stricter if repo policy requires):

- `.bin/ruff check --fix <changed files>`
- `.bin/ruff format <changed files>`
- Active type gate (`ty` or `pyright` or `mypy`)
- Django checks (`.bin/django check` if available, else `python manage.py check`)
- Targeted pytest for attribution paths

## Implementation Workflow

### Step 1: Identify Platform and Action

From user request, resolve:

- platform: `slack`, `teams`, or `email`
- action: e.g. `weekly_digest`, `survey_complete`, `dashboard_cta`

Ask for clarification if either is ambiguous.

### Step 2: Add Action Enum (if needed)

File: `optimo_core/models/login_attribution.py`

If action is new, add it to `LoginSourceDetailChoices` and keep the project's
existing enum conversion pattern consistent.

### Step 3: Add CTA Source Constant

File: `optimo_core/models/login_attribution.py`

Use enum composition and `Final[str]`:

```python
CTA_SOURCE_{PLATFORM}_{ACTION}: Final[str] = (
    f"{LoginSourceChoices.{PLATFORM}.value}_{LoginSourceDetailChoices.{ACTION}.value}"
)
```

### Step 4: Register the Source

File: `optimo_core/models/login_attribution.py`

Register in both:

- `ALLOWED_CTA_SOURCES`
- `VALID_DETAILS_BY_SOURCE`

Missing either commonly causes `parse_cta_source()` fallbacks.

### Step 5: Add Platform-Specific Button Choices (if applicable)

- Slack/Teams: add or reuse platform button enum choices.
- Email: no button/tab attribution enums.
- Teams: no tab concept.

Enum labels must match actual UI button text.

### Step 6: Choose Attribution Layer Correctly

- Layer 1 (single-button contexts): pass button/tab directly into stable URL
  builders.
- Layer 2 (multi-button contexts like digests): append button/tab at render
  time with `update_cta_url_with_button_info()`.

Never apply both layers on the same CTA path.

### Step 7: Wire URL + Magic Link Usage

Use typed enums for source and detail where required, and keep button/tab value
types aligned with the function signature you are calling.

Example (Slack, Layer 1):

```python
from optimo_core.models.login_attribution import CTA_SOURCE_{PLATFORM}_{ACTION}
from optimo_integrations.slack.cta_choices import SlackButtonChoices, SlackTabChoices
from optimo_integrations.utils.platform_magic_links import build_stable_slack_cta_url

url = build_stable_slack_cta_url(
    slack_user_uuid=user_uuid,
    source=CTA_SOURCE_{PLATFORM}_{ACTION},
    slack_tab=SlackTabChoices.HOME,
    slack_button=SlackButtonChoices.VIEW_ALL_ALERTS,
)
```

Example (Teams, Layer 1):

```python
from optimo_core.models.login_attribution import CTA_SOURCE_{PLATFORM}_{ACTION}
from optimo_integrations.teams.cta_choices import TeamsButtonChoices
from optimo_integrations.utils.platform_magic_links import build_stable_teams_cta_url

url = build_stable_teams_cta_url(
    teams_user_uuid=user_uuid,
    source=CTA_SOURCE_{PLATFORM}_{ACTION},
    teams_button=TeamsButtonChoices.GO_TO_DASHBOARD,
)
```

Example (direct magic-link builder):

```python
from optimo_core.models.login_attribution import (
    LoginSourceChoices,
    LoginSourceDetailChoices,
)
from optimo_integrations.slack.cta_choices import SlackButtonChoices, SlackTabChoices
from optimo_integrations.utils.platform_magic_links import build_login_magic_link_for_user

url = build_login_magic_link_for_user(
    user=user,
    login_cta_source=LoginSourceChoices.SLACK,
    login_cta_source_detail=LoginSourceDetailChoices.WEEKLY_DIGEST,
    slack_button=str(SlackButtonChoices.OPEN_IN_OPTIMO.value),
    slack_tab=str(SlackTabChoices.HOME.value),
)
```

### Step 8: Update Tests and Supporting Docs

Add or update tests to cover:

- parser behavior (`parse_cta_source`)
- allowlist/detail registration
- button/tab propagation in URL + token metadata
- platform-specific behavior (Slack/Teams/Email differences)

Use enum values in tests, not raw magic strings.

Update local docs/guides in the target repo if new attribution behavior was
introduced.

## Critical Rules (Do Not Violate)

- No hardcoded source strings where constants/enums exist.
- Always register new sources in both allowlist and valid-details mapping.
- Keep Slack and Teams button enums isolated by platform.
- Do not add tab semantics to Teams or Email.
- Respect the selected attribution layer (Layer 1 or Layer 2, not both).
- Touched files must pass the active type gate.

## Validation Checklist

Before completion:

- [ ] Action enum exists (if new action).
- [ ] `CTA_SOURCE_*` constant added with enum composition.
- [ ] Source is in `ALLOWED_CTA_SOURCES`.
- [ ] Source detail is in `VALID_DETAILS_BY_SOURCE` for the right platform.
- [ ] Platform button/tab handling is correct (Slack/Teams/Email rules).
- [ ] Correct attribution layer chosen and applied once.
- [ ] Magic-link attribution metadata path is preserved.
- [ ] Tests use enum values and cover parser + attribution flow.
- [ ] Ruff, active type gate, Django checks, and relevant tests pass.

## Output Format

When reporting work, include:

1. What changed:
   - files touched
   - enums/constants/registrations added or modified
2. Validation executed:
   - lint, type checker used, Django checks, tests
3. Risk notes:
   - any fallback behavior or edge case not yet covered

If blocked, explicitly report the blocker with file-level context and exact
failing command output summary.

## References

For detailed signatures, metadata schema notes, parser behavior, and extended
file map:

- `references/architecture-and-signatures.md`

## Compatibility Notes

This Skill is designed to work with both Claude Code and OpenAI Codex.

- Claude Code: install plugin and invoke `/login-cta-attribution-skill:implement`.
- Codex: install skill directory and invoke `name: login-cta-attribution-skill`.
