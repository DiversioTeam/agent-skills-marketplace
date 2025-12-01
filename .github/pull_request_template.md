## Summary

<!-- Short description of what this PR changes and why. -->

## Plugins / Skills Touched

<!-- List the plugins/skills/commands you added or modified. -->

- Plugin(s):
  - [ ] New plugin
  - [ ] Existing plugin(s) updated
- Skills:
  - `plugins/.../skills/.../SKILL.md`:
  - Commands:
  - Manifests / marketplace:

## Checklist (from CONTRIBUTING.md)

Please confirm that you have:

- [ ] Limited changes to configuration / docs:
      `.claude-plugin/marketplace.json`, plugin manifests, `SKILL.md`,
      `commands/*.md`, `AGENTS.md`, `README.md`, `CONTRIBUTING.md`.
- [ ] **Not** added any application logic (Django, React, Terraform, etc.) to
      this repo.
- [ ] For each plugin you touched:
  - [ ] `plugins/<plugin>/.claude-plugin/plugin.json` exists and is valid JSON.
  - [ ] Version in `plugin.json` was bumped appropriately
        (e.g. `0.1.0` → `0.1.1`).
  - [ ] Matching entry exists in `.claude-plugin/marketplace.json` with the
        same `name` and `version`.
- [ ] SKILL docs include:
  - [ ] A clear “When to Use This Skill” section.
  - [ ] One or more “Example Prompts”.
  - [ ] Any severity tags / output shape expectations the Skill relies on.
- [ ] Command files under `plugins/<plugin>/commands/*.md`:
  - [ ] Are thin wrappers that tell Claude to use the correct Skill.
  - [ ] Clearly describe the mode or behavior (e.g. pre-commit vs atomic-commit).
- [ ] `README.md` is updated (tree diagram, Available Plugins table, install and
      usage examples) when introducing or renaming plugins.
- [ ] `AGENTS.md` is updated with install instructions and a short usage note
      when adding new plugins meant for general use.
- [ ] No secrets, tokens, or customer-specific confidential details have been
      added (including example data or URLs).
- [ ] Any LLM-generated content (SKILL docs, commands, etc.) has been reviewed
      and edited to match Diversio’s tone and practices.

## Testing / Validation

<!--
For this repo, “testing” usually means:
- JSON validation for manifests / marketplace.
- Basic sanity check that SKILL docs and commands reference the right paths/names.
Describe anything you did here (or write “N/A” if not applicable).
-->

