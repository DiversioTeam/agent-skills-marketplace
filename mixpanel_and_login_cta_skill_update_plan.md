# Plan: Update `login-cta-attribution-skill` and `mixpanel-analytics` Skills

## Context

PR #2623 (GH-4376) moved CTA choice enums from `optimo_integrations/*/cta_choices.py` into `optimo_core/models/login_attribution.py` and renamed the URL helper functions for disambiguation. The two Claude Code skills that reference these files are now stale:

- **`login-cta-attribution-skill` (v0.1.0)**: References deleted `cta_choices.py` files and old function names throughout SKILL.md, references/architecture-and-signatures.md, and commands/implement.md.
- **`mixpanel-analytics` (v0.1.3)**: Has no awareness of CTA attribution enums, session context fields, or the testing guides created in this PR.

Dev repo: `~/DiversioMonolith/claude-plugins/plugins/`

---

## Part A: `login-cta-attribution-skill` — Fix Stale References

### A1. `skills/login-cta-attribution-skill/SKILL.md`

**Environment & Context Gathering (lines 58-64)**: Remove deleted files, keep canonical path.

| Current (stale) | New |
|---|---|
| `optimo_integrations/slack/cta_choices.py` | *(delete line)* |
| `optimo_integrations/teams/cta_choices.py` | *(delete line)* |

Keep `optimo_core/models/login_attribution.py` (already listed).

**Step 6 (line 188)**: Rename function reference.

| Current | New |
|---|---|
| `update_cta_url_with_button_info()` | `update_slack_cta_url_with_button_info()` / `update_teams_cta_url_with_button_info()` |

**Step 7 code examples (lines 197-243)**: Update import paths.

| Current import | New import |
|---|---|
| `from optimo_integrations.slack.cta_choices import SlackButtonChoices, SlackTabChoices` | `from optimo_core.models import SlackButtonChoices, SlackTabChoices` |
| `from optimo_integrations.teams.cta_choices import TeamsButtonChoices` | `from optimo_core.models import TeamsButtonChoices` |

All three code examples (Slack Layer 1, Teams Layer 1, direct magic-link builder) need this update.

### A2. `skills/login-cta-attribution-skill/references/architecture-and-signatures.md`

**Layer 2 description (line 22)**: Rename function.

| Current | New |
|---|---|
| `update_cta_url_with_button_info(cta_url, ...)` | `update_slack_cta_url_with_button_info(cta_url, ...)` / `update_teams_cta_url_with_button_info(cta_url, ...)` |

**Key Files table (lines 155-171)**: Remove deleted file rows, add canonical row.

| Current rows to remove | Replacement |
|---|---|
| `Slack choices and helpers \| optimo_integrations/slack/cta_choices.py` | `Slack/Teams CTA enums + helpers \| optimo_core/models/login_attribution.py` |
| `Teams choices and helpers \| optimo_integrations/teams/cta_choices.py` | *(merged into row above)* |

### A3. `commands/implement.md`

**Line 22**: Rename Layer 2 function reference.

| Current | New |
|---|---|
| `update_cta_url_with_button_info()` | `update_slack_cta_url_with_button_info()` / `update_teams_cta_url_with_button_info()` |

### A4. `.claude-plugin/plugin.json`

Bump version `0.1.0` → `0.2.0`.

---

## Part B: `mixpanel-analytics` — Add CTA Attribution Awareness

### B1. `skills/mixpanel-analytics/SKILL.md`

**Environment & Context Gathering section** — add to the "Read key reference files" list:

```
- `optimo_core/models/login_attribution.py` – CTA attribution enums (SlackButtonChoices, SlackTabChoices, TeamsButtonChoices) and URL helpers
- `optimo_analytics/docs/LoginCTA_AttributionTestingGuide.md` – CTA attribution testing scenarios
- `optimo_analytics/docs/BackendMixpanelTestingGuideV2.md` – Survey lifecycle & MAP event testing scenarios
```

### B2. `skills/mixpanel-analytics/references/implementation.md`

**After Step 7** — add a new section:

```markdown
## CTA Attribution Context (Login Events)

Login/session events include CTA attribution fields in `MixpanelSessionContextSchema`:

| Field | Source | Values |
|---|---|---|
| `login_source` | `LoginSourceChoices` | `slack`, `teams`, `email`, `direct` |
| `login_source_detail` | `LoginSourceDetailChoices` | `weekly_digest`, `survey_complete`, etc. |
| `magic_link_action` | `MagicLinkActionChoices` | `login`, `invite`, `signup`, `verify_email` |
| `slack_button` | `SlackButtonChoices` | Button label from Slack CTA |
| `slack_tab` | `SlackTabChoices` | `messages`, `home` |
| `teams_button` | `TeamsButtonChoices` | Button label from Teams CTA |
| `cta_parse_failed` | `bool` | `True` if source param parsing failed |

All enums live in `optimo_core/models/login_attribution.py`.

When implementing events that extend `MixpanelSessionContextSchema`, these fields
are auto-populated from the auth token's session context — no manual wiring needed.

Testing guides:
- `optimo_analytics/docs/LoginCTA_AttributionTestingGuide.md`
- `optimo_analytics/docs/BackendMixpanelTestingGuideV2.md`
```

### B3. `skills/mixpanel-analytics/references/review.md`

**After section 10 (Export Completeness)** — add:

```markdown
### 11. CTA Attribution Fields (P2)

For events extending `MixpanelSessionContextSchema`:

**MUST VERIFY**:
- [ ] Attribution fields are NOT manually set (they flow from session context)
- [ ] `login_source` uses `LoginSourceChoices` enum, not raw strings
- [ ] `slack_button`/`teams_button` use their respective enum labels
- [ ] Test scenarios cover attributed and non-attributed login paths
```

### B4. `.claude-plugin/plugin.json`

Bump version `0.1.3` → `0.1.4`.

---

## Files Modified (Summary)

| Plugin | File | Change |
|---|---|---|
| `login-cta-attribution-skill` | `SKILL.md` | Remove deleted file refs, update imports + function names |
| `login-cta-attribution-skill` | `references/architecture-and-signatures.md` | Update Key Files table, rename Layer 2 function |
| `login-cta-attribution-skill` | `commands/implement.md` | Rename Layer 2 function reference |
| `login-cta-attribution-skill` | `.claude-plugin/plugin.json` | Bump `0.1.0` → `0.2.0` |
| `mixpanel-analytics` | `SKILL.md` | Add CTA attribution to context gathering |
| `mixpanel-analytics` | `references/implementation.md` | Add CTA Attribution Context section |
| `mixpanel-analytics` | `references/review.md` | Add CTA Attribution Fields review check |
| `mixpanel-analytics` | `.claude-plugin/plugin.json` | Bump `0.1.3` → `0.1.4` |

---

## What We're NOT Changing

- No changes to the `commands/implement.md` or `commands/review.md` for `mixpanel-analytics` (they delegate to SKILL.md which delegates to references).
- No structural reorganization of either skill — just content updates.

---

## Verification

1. Grep both skills for any remaining references to `cta_choices.py`:
   ```bash
   grep -r "cta_choices" ~/DiversioMonolith/claude-plugins/plugins/login-cta-attribution-skill/
   grep -r "cta_choices" ~/DiversioMonolith/claude-plugins/plugins/mixpanel-analytics/
   ```

2. Grep for old function name:
   ```bash
   grep -r "update_cta_url_with_button_info" ~/DiversioMonolith/claude-plugins/plugins/login-cta-attribution-skill/
   ```

3. Verify JSON validity of both `plugin.json` files:
   ```bash
   python3 -m json.tool ~/DiversioMonolith/claude-plugins/plugins/login-cta-attribution-skill/.claude-plugin/plugin.json
   python3 -m json.tool ~/DiversioMonolith/claude-plugins/plugins/mixpanel-analytics/.claude-plugin/plugin.json
   ```

4. After publishing updated plugins, invoke each skill once to verify it loads without errors.
