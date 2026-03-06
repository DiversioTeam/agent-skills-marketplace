# Architecture Overview

## Main Components

- `.claude-plugin/marketplace.json`
  - The top-level Claude Code marketplace definition.
  - Owns the published plugin list, versions, descriptions, categories, and
    source paths.
- `plugins/<plugin>/`
  - Each plugin directory owns one plugin manifest, one or more skills, and
    one or more slash-command wrappers.
- `plugins/<plugin>/skills/<skill>/SKILL.md`
  - The canonical instructions for a skill.
  - Deep procedures should live one level deeper in `references/` or `scripts/`.
- `plugins/<plugin>/commands/*.md`
  - Thin wrappers that surface skills as `/plugin:command` entries in Claude
    Code.
- `scripts/validate-skills.sh`
  - Local and CI guardrail for the `SKILL.md` line-count budget.
- `.github/workflows/validate-marketplace.yml`
  - Structure and consistency checks for marketplace metadata and changed
    skills.
- `.github/workflows/notify-plugin-updates.yml`
  - Post-merge notification flow for plugin changes pushed to `main`.

## Boundaries

- This repo stores configuration and documentation for skills. It should not
  contain application behavior from the target repos those skills operate on.
- The marketplace manifest and per-plugin manifests must agree on plugin name,
  version, and source path.
- Slash-command files should stay thin. The real behavior belongs in
  `SKILL.md`, `references/`, and helper scripts.
- `README.md` stays human-first, `AGENTS.md` stays as the agent routing map,
  and detailed guidance lives under `docs/`.

## Main Flows

1. Add or change a plugin
   - Update the skill, command wrapper, and plugin manifest under
     `plugins/<plugin>/`.
   - Sync the matching `.claude-plugin/marketplace.json` entry.
   - Update the catalog or distribution docs if the user-facing inventory
     changed.
2. Validate locally
   - Run `bash scripts/validate-skills.sh` for changed skills.
   - Validate edited JSON with `jq -e .`.
3. CI verification
   - `Validate Marketplace` checks JSON validity, unique plugin names,
     directory/manifest consistency, version sync, presence of skills, and the
     `SKILL.md` size budget.
4. Post-merge notification
   - Pushes to `main` that touch `plugins/**` trigger Slack update messages with
     plugin names, versions, and changelog snippets.

## Useful References

- `AGENTS.md` - repo-wide rules and navigation
- `docs/quality/gates.md` - validation details and recurring failure modes
- `docs/runbooks/distribution.md` - install, uninstall, and reinstall commands
- `docs/plugins/catalog.md` - plugin inventory and slash commands
