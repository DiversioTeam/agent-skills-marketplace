---
description: Validate gh auth and set github-ticket defaults for planning, execution repos, project hydration, labels, and backlog behavior.
---

Use your `github-ticket` Skill in **configure** mode.

This command should:
1. Run `gh auth status`.
2. Create or update local config in `${XDG_CONFIG_HOME:-$HOME/.config}/github-ticket/config.json` (by default, `~/.config/github-ticket/config.json`).
3. Confirm planning repo, preferred execution repos, default labels, and project settings including field defaults.

See the `SKILL.md` for the full config model and routing rules.
