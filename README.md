# agent-skills-marketplace

Agent Skills marketplace for Diversio.

## Agent Skills Standard

This repo follows the [Agent Skills standard](https://agentskills.io/specification): an
open, tool-agnostic format for packaging capabilities and workflows for agents.
A skill is a directory with a required `SKILL.md` that contains YAML frontmatter
(`name`, `description`) and Markdown instructions, plus optional `scripts/`,
`references/`, and `assets/`.

Key points from the standard:
- `SKILL.md` is required and starts with YAML frontmatter.
- `name` must match the skill directory and use lowercase letters, numbers, and hyphens.
- `description` should explain what the skill does and when to use it.
- Optional frontmatter fields include `license`, `compatibility`, `metadata`, and experimental `allowed-tools` (space-delimited string).
- Keep `SKILL.md` focused; link to longer guidance in `references/` or helpers in `scripts/`.

Skills are designed for progressive disclosure: agents read metadata first,
load the full `SKILL.md` when invoked, and open `references/` or `scripts/`
only if needed.

### Compatibility (Codex + Claude Code)

To keep Skills portable across both OpenAI Codex and Claude Code:
- Prefer only `name` + `description` in YAML frontmatter; treat other fields as optional/ignored by many runtimes.
- Keep `description` single-line and ≤500 chars (Codex validates this at startup).
- Avoid `anthropic`/`claude` in Skill names and don’t include XML tags in `name`/`description` (Claude).
- Keep `SKILL.md` reasonably small (≈<500 lines); move deep docs into `references/`.

## Working on Skills (LLM checklist)

- Start with `AGENTS.md` (source of truth); `CLAUDE.md` only includes it.
- Required structure: `plugins/<plugin>/skills/<skill-name>/SKILL.md` with YAML frontmatter (`name`, `description`).
- Ensure the skill directory name matches `name` and stays in kebab-case.
- Add or update a corresponding `plugins/<plugin>/commands/*.md` entrypoint.
- Keep `SKILL.md` focused; put deep docs in `references/` and helpers in `scripts/`.
- If you change a plugin, bump its version in `plugins/<plugin>/.claude-plugin/plugin.json`
  and keep `.claude-plugin/marketplace.json` in sync.

## Overview

This repository hosts Diversio-maintained Agent Skills and plugin manifests so
the same skills can be distributed via the Claude Code marketplace or other
channels.

## Repository Structure

```
agent-skills-marketplace/
├── .claude-plugin/
│   └── marketplace.json               # Marketplace definition
├── plugins/
│   ├── monty-code-review/             # Monty backend code review plugin
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/monty-code-review/SKILL.md
│   │   └── commands/code-review.md
│   ├── backend-atomic-commit/         # Backend pre-commit & atomic-commit plugin
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/backend-atomic-commit/SKILL.md
│   │   └── commands/
│   │       ├── pre-commit.md
│   │       └── atomic-commit.md
│   ├── backend-pr-workflow/           # Backend PR workflow plugin
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/backend-pr-workflow/SKILL.md
│   │   └── commands/check-pr.md
│   ├── bruno-api/                     # Bruno API docs generator
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/bruno-api/SKILL.md
│   │   └── commands/docs.md
│   ├── code-review-digest-writer/     # Code review digest generator
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/code-review-digest-writer/SKILL.md
│   │   └── commands/review-digest.md
│   ├── plan-directory/                # Structured plan directories + RALPH loop
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/
│   │   │   ├── plan-directory/
│   │   │   │   ├── SKILL.md
│   │   │   │   └── references/        # Extended guidance
│   │   │   └── backend-ralph-plan/    # RALPH loop integration
│   │   │       ├── SKILL.md
│   │   │       ├── references/
│   │   │       └── examples/
│   │   └── commands/
│   │       ├── plan.md
│   │       ├── backend-ralph-plan.md
│   │       └── run.md                 # Execute RALPH plans
│   ├── pr-description-writer/         # PR description generator
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/pr-description-writer/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   └── commands/write-pr.md
│   ├── process-code-review/           # Code review processor (fix/skip issues)
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/process-code-review/SKILL.md
│   │   └── commands/process-review.md
│   └── mixpanel-analytics/            # MixPanel tracking implementation & review
│       ├── .claude-plugin/plugin.json
│       ├── skills/mixpanel-analytics/
│       │   ├── SKILL.md
│       │   └── references/
│       └── commands/
│           ├── implement.md
│           └── review.md
├── AGENTS.md                          # Source of truth for Claude Code behavior
├── CLAUDE.md                          # Sources AGENTS.md
├── README.md
├── CONTRIBUTING.md
└── LICENSE
```

## Available Plugins

| Plugin | Description |
|--------|-------------|
| `monty-code-review` | Hyper-pedantic Django4Lyfe backend code review Skill |
| `backend-atomic-commit` | Backend pre-commit / atomic-commit Skill that enforces AGENTS.md, pre-commit hooks, .security helpers, and Monty's backend taste (no AI commit signatures) |
| `backend-pr-workflow` | Backend PR workflow Skill that enforces ClickUp-linked branch/PR naming, safe migrations, and downtime-safe schema changes |
| `bruno-api` | API endpoint documentation generator from Bruno (`.bru`) files that traces Django4Lyfe implementations (DRF/Django Ninja) |
| `code-review-digest-writer` | Weekly code-review digest writer Skill (repo-agnostic) |
| `plan-directory` | Structured plan directories with PLAN.md index, numbered task files, and RALPH loop integration for iterative execution |
| `pr-description-writer` | Generates comprehensive, reviewer-friendly PR descriptions with visual diagrams, summary tables, and structured sections |
| `process-code-review` | Process code review findings - interactively fix or skip issues from monty-code-review output with status tracking |
| `mixpanel-analytics` | MixPanel tracking implementation and review Skill for Django4Lyfe optimo_analytics module with PII protection and pattern enforcement |

## Installation

1. Add the marketplace to Claude Code:

   ```bash
   /plugin marketplace add DiversioTeam/agent-skills-marketplace
   ```

2. Install a plugin from the marketplace:

   ```bash
   # Monty backend code review
   /plugin install monty-code-review@diversiotech

   # Backend pre-commit / atomic commit helper
   /plugin install backend-atomic-commit@diversiotech

   # Backend PR workflow (ClickUp + migrations/downtime)
   /plugin install backend-pr-workflow@diversiotech

   # Bruno API docs generator (.bru -> Django endpoint docs)
   /plugin install bruno-api@diversiotech

   # Code review digest writer
   /plugin install code-review-digest-writer@diversiotech

   # Plan directory with RALPH loop integration
   /plugin install plan-directory@diversiotech

   # PR description writer
   /plugin install pr-description-writer@diversiotech

   # Code review processor (fix/skip issues from monty-code-review)
   /plugin install process-code-review@diversiotech

   # MixPanel analytics (implement and review tracking events)
   /plugin install mixpanel-analytics@diversiotech
   ```

3. Use plugin-provided slash commands (once plugins are installed):

   ```text
   /monty-code-review:code-review            # Hyper-pedantic backend code review
   /backend-atomic-commit:pre-commit         # Fix backend files to meet AGENTS/pre-commit/.security standards
   /backend-atomic-commit:atomic-commit      # Strict atomic commit helper (all gates green, no AI signature)
   /backend-pr-workflow:check-pr             # Backend PR workflow & migrations check
   /bruno-api:docs                           # Generate endpoint docs from Bruno (.bru) files
   /code-review-digest-writer:review-digest  # Generate a code review digest
   /plan-directory:plan                      # Create structured plan directory with PLAN.md
   /plan-directory:backend-ralph-plan        # Create RALPH loop-integrated plan for backend
   /plan-directory:run <slug>                # Execute a RALPH plan via ralph-wiggum loop
   /pr-description-writer:write-pr           # Generate a comprehensive PR description
   /process-code-review:process-review       # Process code review findings (fix/skip issues)
   /mixpanel-analytics:implement             # Implement new MixPanel tracking events
   /mixpanel-analytics:review                # Review MixPanel implementations for compliance
   ```

## Install As Codex Skills

Codex can install these Skills directly from GitHub (separate from Claude's
marketplace) using the Skill Installer and avoid hardcoded user paths:

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

python3 "$CODEX_HOME/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo DiversioTeam/agent-skills-marketplace \
  --path plugins/monty-code-review/skills/monty-code-review
```

You can also invoke the installer from the Codex console:

```text
$skill-installer install from github repo=DiversioTeam/agent-skills-marketplace path=plugins/monty-code-review/skills/monty-code-review
```

Install multiple Skills in one run:

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

python3 "$CODEX_HOME/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo DiversioTeam/agent-skills-marketplace \
  --ref main \
  --path \
    plugins/monty-code-review/skills/monty-code-review \
    plugins/backend-atomic-commit/skills/backend-atomic-commit \
    plugins/backend-pr-workflow/skills/backend-pr-workflow \
    plugins/bruno-api/skills/bruno-api \
    plugins/code-review-digest-writer/skills/code-review-digest-writer \
    plugins/plan-directory/skills/plan-directory \
    plugins/plan-directory/skills/backend-ralph-plan \
    plugins/pr-description-writer/skills/pr-description-writer \
    plugins/process-code-review/skills/process-code-review \
    plugins/mixpanel-analytics/skills/mixpanel-analytics
```

Codex console multi-install example:

```text
$skill-installer install from github repo=DiversioTeam/agent-skills-marketplace \
  path=plugins/monty-code-review/skills/monty-code-review \
  path=plugins/backend-atomic-commit/skills/backend-atomic-commit \
  path=plugins/backend-pr-workflow/skills/backend-pr-workflow \
  path=plugins/bruno-api/skills/bruno-api \
  path=plugins/code-review-digest-writer/skills/code-review-digest-writer \
  path=plugins/plan-directory/skills/plan-directory \
  path=plugins/plan-directory/skills/backend-ralph-plan \
  path=plugins/pr-description-writer/skills/pr-description-writer \
  path=plugins/process-code-review/skills/process-code-review \
  path=plugins/mixpanel-analytics/skills/mixpanel-analytics
```

Notes:
- Add `--ref <branch-or-tag>` to pin a version.
- `install-skill-from-github.py` does not overwrite existing Skills; to update, delete the existing `$CODEX_HOME/skills/<skill-name>` directory and reinstall.
- Codex installs Skills into `~/.codex/skills` by default, and also loads repo-local Skills from `.codex/skills`.
- Restart Codex after installing Skills.

## Documentation

- [Agent Skills Standard](https://agentskills.io/specification)
- [Agent Skills Best Practices](https://agentskills.io/best-practices)
- [OpenAI Codex Skills](https://developers.openai.com/codex/skills)
- [OpenAI Codex Skills (Install new skills)](https://developers.openai.com/codex/skills#install-new-skills)
- [Claude Agent Skills Overview](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)
- [Claude Code Plugins](https://code.claude.com/docs/en/plugins)
- [Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Agent Skills](https://code.claude.com/docs/en/skills)

## License

MIT License - see [LICENSE](LICENSE) for details.
