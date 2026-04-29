# Contributing to `agent-skills-marketplace`

This repo is a configuration marketplace for Diversio-maintained Agent Skills
and Claude Code plugins. Treat it as manifests, docs, commands, and validation
scripts, not application code.

Start with `AGENTS.md` for repo-wide rules, then use the focused docs in
`docs/` for deeper guidance:

- `docs/architecture/overview.md`
- `docs/quality/gates.md`
- `docs/runbooks/distribution.md`
- `docs/plugins/catalog.md`

## What You Can Change

Contributions should generally be limited to:

- `AGENTS.md`, `CLAUDE.md`, `README.md`, `CONTRIBUTING.md`
- `.claude-plugin/marketplace.json`
- `plugins/**/.claude-plugin/plugin.json`
- `plugins/**/skills/*/SKILL.md`
- `plugins/**/commands/*.md`
- `pi-packages/**` for pi-native packages
- `docs/**`
- `scripts/**`

Do not add Diversio product application logic here. Pi extension code is allowed
only inside `pi-packages/**` and should stay harness-focused.

## Adding Or Updating A Plugin

1. Create or update the plugin shape

   ```text
   plugins/<plugin-name>/
     .claude-plugin/plugin.json
     skills/<skill-name>/SKILL.md
     commands/<command-name>.md
   ```

2. Keep manifests minimal and synchronized

   - `plugins/<plugin-name>/.claude-plugin/plugin.json` must stay valid JSON.
   - `.claude-plugin/marketplace.json` must contain a matching entry with the
     same `name`, `version`, and `source`.
   - Any plugin change requires a version bump in both files.

3. Keep skills small and portable

   - `SKILL.md` should focus on activation workflow, priorities, and output
     shape.
   - Keep each changed `SKILL.md` at or below 500 lines.
   - Move long procedures into `references/` and reusable logic into `scripts/`.
   - Quote YAML frontmatter strings when they contain special characters.

4. Keep slash commands thin

   - Every skill needs at least one command under `plugins/<plugin>/commands/`.
   - Command files should invoke the skill and add only command-specific
     context; they should not duplicate the full skill body.

5. Preserve repo-local policy docs

   - Update `docs/plugins/catalog.md` when plugin inventory or slash commands
     change.
   - Update `README.md` when plugin inventory, install commands, slash command
     examples, or the repository structure summary change.
   - Keep the engineer-facing README sections current:
     - repository tree diagram
     - available plugins table
     - install examples
     - slash command examples
   - Update `docs/runbooks/distribution.md` when install, uninstall, or Codex
     distribution guidance changes.
   - Update `AGENTS.md` when repo-wide navigation, commands, or agent-facing
     rules change.
   - If the plugin touches code-oriented Python workflows, reflect the typing
     policy in `docs/python-typing-and-ty-best-practices.md`.

## Adding Or Updating A Pi Package

Pi-native packages live under `pi-packages/<package>/` when the workflow needs a
pi extension, TUI component, or pi-local skill that does not fit the Claude Code
marketplace plugin shape.

Keep the package `README.md`, `package.json`, `docs/runbooks/distribution.md`,
`docs/plugins/catalog.md`, and the top-level `README.md` in sync when commands,
shortcuts, install paths, or packaged resources change. If a package exposes an
interactive TUI, document its keybindings in terms of Pi keybinding ids when
possible (for example, `app.message.followUp`) so custom user bindings still
make sense. Bump the package version when publishing an update rather than only
editing source files.

For local extension smoke tests, prefer `pi -e ./pi-packages/<package>` so the
package loads for the current run without mutating user or project settings.
Use `pi install -l` only when testing project-local install, `/reload`, or
settings persistence behavior.

## Validation

Run the guardrails that match your change:

```bash
bash scripts/validate-skills.sh
bash scripts/validate-skills.sh --all
jq -e . .claude-plugin/marketplace.json >/dev/null
jq -e . plugins/<plugin>/.claude-plugin/plugin.json >/dev/null
jq -e . pi-packages/<package>/package.json >/dev/null
(cd pi-packages/<package> && npm pack --dry-run --json >/tmp/<package>-pack.json)
printf '{"id":"cmds","type":"get_commands"}\n' | PI_OFFLINE=1 pi --mode rpc --no-session --no-context-files --no-extensions -e ./pi-packages/<package> --no-prompt-templates --no-skills
```

The `Validate Marketplace` GitHub workflow also checks:

- JSON parses cleanly
- marketplace plugin names are unique
- every marketplace entry has a matching `plugins/<name>` directory
- every plugin manifest name and version matches the marketplace entry
- each plugin has at least one `SKILL.md`

## Review Checklist

Before opening a PR or pushing directly:

- [ ] Plugin manifest and marketplace entry are in sync.
- [ ] Every changed skill still has at least one command wrapper.
- [ ] Changed `SKILL.md` files stay within the 500-line budget.
- [ ] `docs/plugins/catalog.md` reflects any added, removed, or renamed plugins
      and commands.
- [ ] `README.md` reflects any changed plugin inventory, install flows,
      repository structure summaries, or slash command examples.
- [ ] `docs/runbooks/distribution.md` still matches the supported Claude Code
      and Codex installation flows.
- [ ] `README.md` and `AGENTS.md` still point to the right docs.
- [ ] No application code or secrets were added.
