# claude-plugins

Claude Code plugins marketplace for Diversio.

## Overview

This repository is a Claude Code marketplace that hosts reusable plugins (primarily Skills) maintained by the Diversio team.

## Repository Structure

```
claude-plugins/
├── .claude-plugin/
│   └── marketplace.json               # Marketplace definition
├── plugins/
│   ├── monty-code-review/             # Monty backend code review plugin
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json            # Plugin manifest
│   │   ├── skills/
│   │   │   └── monty-code-review/
│   │   │       └── SKILL.md           # Skill definition
│   │   └── commands/
│   │       └── code-review.md         # Slash command entrypoint
│   ├── backend-pr-workflow/           # Backend PR workflow plugin
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json
│   │   ├── skills/
│   │   │   └── backend-pr-workflow/
│   │   │       └── SKILL.md
│   │   └── commands/
│   │       └── check-pr.md            # Slash command entrypoint
│   ├── backend-atomic-commit/         # Backend pre-commit & atomic-commit plugin
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json
│   │   ├── skills/
│   │   │   └── backend-atomic-commit/
│   │   │       └── SKILL.md
│   │   └── commands/
│   │       ├── pre-commit.md
│   │       └── atomic-commit.md
│   └── code-review-digest-writer/     # Code review digest generator
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── skills/
│       │   └── code-review-digest-writer/
│       │       └── SKILL.md
│       └── commands/
│           └── review-digest.md       # Slash command entrypoint
├── README.md
└── LICENSE
```

## Available Plugins

| Plugin | Description |
|--------|-------------|
| `monty-code-review` | Hyper-pedantic Django4Lyfe backend code review Skill |
| `backend-atomic-commit` | Backend pre-commit / atomic-commit Skill that enforces AGENTS.md, pre-commit hooks, .security helpers, and Monty’s backend taste (no AI commit signatures) |
| `backend-pr-workflow` | Backend PR workflow Skill that enforces ClickUp-linked branch/PR naming, safe migrations, and downtime-safe schema changes |
| `code-review-digest-writer` | Weekly code-review digest writer Skill (repo-agnostic) |

## Installation

1. Add the marketplace to Claude Code:

   ```bash
   /plugin marketplace add DiversioTeam/claude-plugins
   ```

2. Install a plugin from the marketplace:

   ```bash
   # Monty backend code review
   /plugin install monty-code-review@diversiotech

   # Backend pre-commit / atomic commit helper
   /plugin install backend-atomic-commit@diversiotech

   # Backend PR workflow (ClickUp + migrations/downtime)
   /plugin install backend-pr-workflow@diversiotech

   # Code review digest writer
   /plugin install code-review-digest-writer@diversiotech
   ```

3. Use plugin-provided slash commands (once plugins are installed):

   ```text
   /monty-code-review:code-review          # Hyper-pedantic backend code review
   /backend-atomic-commit:pre-commit       # Actively fix backend files to meet AGENTS/pre-commit/.security standards
   /backend-atomic-commit:atomic-commit    # Strict atomic commit helper (all gates green, no AI signature)
   /backend-pr-workflow:check-pr           # Backend PR workflow & migrations check
   /code-review-digest-writer:review-digest  # Generate a code review digest
   ```

## Documentation

- [Claude Code Plugins](https://code.claude.com/docs/en/plugins)
- [Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Agent Skills](https://code.claude.com/docs/en/skills)

## License

MIT License - see [LICENSE](LICENSE) for details.
