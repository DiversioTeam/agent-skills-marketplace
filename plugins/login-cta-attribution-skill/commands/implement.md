---
description: Implement new CTA login attribution sources using the login-cta-attribution-skill Skill.
---

Run your `login-cta-attribution-skill` Skill in **implement** mode.

**Arguments:**
- `[platform]` – Target platform: `slack`, `teams`, or `email`
- `[action]` – CTA action name (e.g., `survey_complete`, `weekly_digest`)

Focus on:

- Following the 8-step implementation checklist to add new CTA sources.
- Adding `LoginSourceDetailChoices` enum values (if new action) WITH `from_raw_to_enum()`.
- Creating `CTA_SOURCE_*` constants using `Final[str]` and enum composition.
- Registering in both `ALLOWED_CTA_SOURCES` and `VALID_DETAILS_BY_SOURCE`.
- Adding platform-specific button/tab choices (Slack/Teams only, not Email).
- **Choosing the correct layer for button attribution:**
  - **Layer 1:** Use `build_stable_slack_cta_url()` / `build_stable_teams_cta_url()`
    with button params baked in (for single-button CTAs like Home Tab).
  - **Layer 2:** Use `update_slack_cta_url_with_button_info()` /
    `update_teams_cta_url_with_button_info()` to append button params
    to a base URL (for multi-button contexts like Digests).
- Using correct function signatures:
  - `build_login_magic_link_for_user()` takes **enum types** for
    `login_cta_source` and `login_cta_source_detail`, not strings.
  - `build_stable_slack_cta_url()` takes `SlackTabChoices` and `SlackButtonChoices`
    enum types directly.
- Ensuring `build_source_attribution_metadata()` is called in magic link creation.
- Ensuring button `.label` matches actual UI button text.
- Writing tests that use enum values, never magic strings.
- Updating platform AGENTS.md files with new CTA rules.
- Applying type-gate detection precedence (unless repo docs/CI override):
  `ty` -> `pyright` -> `mypy`.

After implementation:

- **Preferred:** Run `/backend-atomic-commit:pre-commit` to validate changed files
  (full pre-commit suite with auto-fixes).
- **Fallback only** (if not available): manually run on **changed files only**:
  `.bin/ruff check --fix` + `.bin/ruff format`, then active type gate:
  `.bin/ty check` (or `.bin/pyright` or `.bin/mypy`), then
  `.bin/django check` (or `python manage.py check`).
- Run pytest on attribution tests:
  ```bash
  pytest optimo_core/tests/test_login_attribution*.py
  pytest optimo_core/tests/test_login_attribution_integration.py
  pytest optimo_integrations/tests/slack/test_home_cta.py
  pytest optimo_integrations/tests/test_magic_links_helpers.py
  ```
- Verify `parse_cta_source()` returns expected result for new source.
- Report what was created and run the validation checklist.
