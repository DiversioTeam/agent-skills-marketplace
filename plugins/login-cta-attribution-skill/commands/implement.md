---
description: Implement new CTA login attribution sources using the login-cta-attribution-skill Skill.
---

Run your `login-cta-attribution-skill` Skill in **implement** mode.

**Arguments:**
- `[platform]` – Target platform: `slack`, `teams`, or `email`
- `[action]` – CTA action name (e.g., `survey_complete`, `weekly_digest`)

Focus on:

- Following the 7-step implementation checklist to add new CTA sources.
- Adding `LoginSourceDetailChoices` enum values (if new action).
- Creating `CTA_SOURCE_*` constants using `Final[str]` and enum composition.
- Registering in both `ALLOWED_CTA_SOURCES` and `VALID_DETAILS_BY_SOURCE`.
- Adding platform-specific button/tab choices (Slack/Teams only, not Email).
- Using `update_cta_url_with_button_info()` for URL generation.
- Ensuring button `.label` matches actual UI button text.
- Writing tests that use enum values, never magic strings.

After implementation:

- **Preferred:** Run `/backend-atomic-commit:pre-commit` to validate changed files
  (full pre-commit suite with auto-fixes).
- **Fallback only** (if not available): manually run on **changed files only**:
  `.bin/ruff check --fix` + `.bin/ruff format`, `.bin/ty check`,
  `python manage.py check`.
- Run pytest on attribution tests.
- Verify `parse_cta_source()` returns expected result for new source.
- Report what was created and run the validation checklist.
