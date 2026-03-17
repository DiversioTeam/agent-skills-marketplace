# Visual Explainer Netlify Review

This change adds optional Netlify preview publishing to the `visual-explainer`
skill, including local config bootstrap, publish receipts, and a deterministic
helper script. I focused the review on publish correctness, runtime-env
behavior, output contracts, documentation accuracy, and stale harness guidance.

## What's great

- `plugins/visual-explainer/skills/visual-explainer/SKILL.md` keeps the main
  skill under the size budget while moving deeper publish guidance into
  references and a helper script.
- `plugins/visual-explainer/skills/visual-explainer/scripts/publish_netlify_preview.py`
  uses only stdlib modules, which keeps installation friction low.
- `plugins/visual-explainer/skills/visual-explainer/references/config-layout.md`
  clearly enforces the "env-var names only" secret model rather than storing
  literal tokens.
- `plugins/visual-explainer/commands/explain.md` keeps the wrapper thin and
  surfaces the new publish behavior without duplicating the full workflow.
- The plugin metadata in `plugins/visual-explainer/.claude-plugin/plugin.json`
  and `.claude-plugin/marketplace.json` is version-synced.

## What could be improved

- `[SHOULD_FIX]` `plugins/visual-explainer/skills/visual-explainer/scripts/publish_netlify_preview.py`
  – initial URL selection preferred deploy permalinks, which can produce
  hostnames with DNS labels longer than 63 characters for long site names. This
  has been fixed by preferring the canonical site alias URL and filtering for
  DNS-safe hostnames.
- `[SHOULD_FIX]` `plugins/visual-explainer/skills/visual-explainer/scripts/publish_netlify_preview.py`
  – initial deploy ZIP omitted a Netlify `_headers` file, so some published
  explainers were served as `text/plain` and displayed raw HTML. This has been
  fixed by packaging `_headers` with explicit `text/html; charset=UTF-8`
  overrides for `/` and `/index.html`.
- `[SHOULD_FIX]` `plugins/visual-explainer/skills/visual-explainer/SKILL.md`,
  `plugins/visual-explainer/commands/explain.md`,
  `plugins/visual-explainer/skills/visual-explainer/references/*.md`
  – the first draft did not make it explicit enough that the helper reads from
  the current process environment, not directly from `~/.zshrc`. This has been
  fixed by adding runtime-env checks and restart guidance.
- `[NIT]` `plugins/visual-explainer/skills/visual-explainer/references/netlify-publishing.md`
  – the first draft listed env-var names but not where to obtain the Netlify
  token or account slug. This has been fixed with a short setup section.
- `[NIT]` `plugins/visual-explainer/skills/visual-explainer/scripts/__pycache__/`
  – a local `__pycache__` artifact appeared during testing. It has been
  removed and should stay out of the PR.

## Tests

- Covered well:
  - local syntax check for the publish helper
  - `SKILL.md` size validation
  - JSON validation for plugin and marketplace manifests
  - live Netlify publish smoke tests from the repo copy, including URL and
    `Content-Type` verification
- Missing:
  - no automated unit tests for the helper script yet
  - no automated regression checks for URL selection or `_headers` packaging in
    CI

## Verdict

Approve after the applied fixes. I do not see any remaining blocking issues in
the reviewed change set, but the lack of automated tests for the helper script
is still a residual risk to note in the PR.
