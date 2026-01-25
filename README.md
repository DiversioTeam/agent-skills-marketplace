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
│   ├── session-review-notes/          # PR-ready AI session review notes
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/session-review-notes/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   └── commands/
│   │       ├── generate.md
│   │       └── list-sessions.md
│   ├── process-code-review/           # Code review processor (fix/skip issues)
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/process-code-review/SKILL.md
│   │   └── commands/process-review.md
│   ├── mixpanel-analytics/            # MixPanel tracking implementation & review
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/mixpanel-analytics/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   └── commands/
│   │       ├── implement.md
│   │       └── review.md
│   ├── clickup-ticket/                # ClickUp ticket management
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/clickup-ticket/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   └── commands/
│   │       ├── configure.md
│   │       ├── create-ticket.md
│   │       ├── quick-ticket.md
│   │       ├── create-subtask.md
│   │       ├── add-to-backlog.md
│   │       ├── list-spaces.md
│   │       ├── switch-org.md
│   │       ├── add-org.md
│   │       └── refresh-cache.md
│   ├── repo-docs/                     # Repository documentation generator
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/repo-docs-generator/SKILL.md
│   │   └── commands/
│   │       ├── generate.md
│   │       └── canonicalize.md
│   └── backend-release/               # Django4Lyfe release workflow
│       ├── .claude-plugin/plugin.json
│       ├── skills/release-manager/SKILL.md
│       └── commands/
│           ├── check.md
│           ├── create.md
│           └── publish.md
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
| `session-review-notes` | Upsert a single PR comment that serves as an AI session ledger (human steering, deltas, tests) across Codex + Claude Code (not a PR description) |
| `process-code-review` | Process code review findings - interactively fix or skip issues from monty-code-review output with status tracking |
| `mixpanel-analytics` | MixPanel tracking implementation and review Skill for Django4Lyfe optimo_analytics module with PII protection and pattern enforcement |
| `clickup-ticket` | Create and manage ClickUp tickets directly from Claude Code or Codex with multi-org support, interactive ticket creation, subtasks, and backlog management |
| `repo-docs` | Generate and canonicalize repository documentation (AGENTS.md, README.md, CLAUDE.md) with ASCII architecture diagrams and single-source-of-truth pattern |
| `backend-release` | Django4Lyfe backend release workflow - create release PRs, date-based version bumping (YYYY.MM.DD), and GitHub release publishing |

## Installation

### 1. Add the marketplace

From your terminal (outside Claude Code):

```bash
claude plugin marketplace add DiversioTeam/agent-skills-marketplace
```

Or from within a Claude Code session:

```
/plugin marketplace add DiversioTeam/agent-skills-marketplace
```

### 2. Install plugins

**Recommended:** Install at user scope (default) for compatibility with git worktrees.
Project-scope plugins don't persist across worktrees.

<details>
<summary><strong>Install All Plugins (CLI commands)</strong></summary>

Copy-paste these commands in your terminal:

```bash
claude plugin install monty-code-review@diversiotech
claude plugin install backend-atomic-commit@diversiotech
claude plugin install backend-pr-workflow@diversiotech
claude plugin install bruno-api@diversiotech
claude plugin install code-review-digest-writer@diversiotech
claude plugin install plan-directory@diversiotech
claude plugin install pr-description-writer@diversiotech
claude plugin install session-review-notes@diversiotech
claude plugin install process-code-review@diversiotech
claude plugin install mixpanel-analytics@diversiotech
claude plugin install clickup-ticket@diversiotech
claude plugin install repo-docs@diversiotech
claude plugin install backend-release@diversiotech
```

For project-scoped installation (shared with collaborators via `.claude/settings.json`):

```bash
claude plugin install monty-code-review@diversiotech --scope project
# ... repeat for each plugin
```

</details>

<details>
<summary><strong>Install Individual Plugins</strong></summary>

| Plugin | CLI Command |
|--------|-------------|
| Monty backend code review | `claude plugin install monty-code-review@diversiotech` |
| Backend pre-commit / atomic commit | `claude plugin install backend-atomic-commit@diversiotech` |
| Backend PR workflow | `claude plugin install backend-pr-workflow@diversiotech` |
| Bruno API docs generator | `claude plugin install bruno-api@diversiotech` |
| Code review digest writer | `claude plugin install code-review-digest-writer@diversiotech` |
| Plan directory + RALPH loop | `claude plugin install plan-directory@diversiotech` |
| PR description writer | `claude plugin install pr-description-writer@diversiotech` |
| Session review notes | `claude plugin install session-review-notes@diversiotech` |
| Code review processor | `claude plugin install process-code-review@diversiotech` |
| MixPanel analytics | `claude plugin install mixpanel-analytics@diversiotech` |
| ClickUp ticket management | `claude plugin install clickup-ticket@diversiotech` |
| Repository docs generator | `claude plugin install repo-docs@diversiotech` |
| Backend release workflow | `claude plugin install backend-release@diversiotech` |

</details>

### 3. Use slash commands

Once plugins are installed:

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
   /session-review-notes:generate            # Generate PR-ready AI session review notes
   /session-review-notes:list-sessions       # List recent Codex + Claude sessions (human-readable picker)
   /process-code-review:process-review       # Process code review findings (fix/skip issues)
   /mixpanel-analytics:implement             # Implement new MixPanel tracking events
   /mixpanel-analytics:review                # Review MixPanel implementations for compliance
   /clickup-ticket:configure                 # Initial setup and org configuration
   /clickup-ticket:create-ticket             # Full interactive ticket creation
   /clickup-ticket:quick-ticket              # Fast ticket with minimal prompts
   /clickup-ticket:create-subtask            # Add subtask to existing ticket
   /clickup-ticket:add-to-backlog            # Quick add to configured backlog list
   /clickup-ticket:list-spaces               # Browse workspace hierarchy
   /clickup-ticket:switch-org                # Switch between organizations
   /clickup-ticket:add-org                   # Add a new organization
   /clickup-ticket:refresh-cache             # Force refresh cached data
   /repo-docs:generate                       # Generate new AGENTS.md, README.md, CLAUDE.md
   /repo-docs:canonicalize                   # Audit and fix existing docs (make AGENTS.md canonical)
   /backend-release:check                    # Check what commits are pending release
   /backend-release:create                   # Create release PR with cherry-pick method
   /backend-release:publish                  # Publish GitHub release after PR merge
   ```

### Uninstall Plugins (Claude Code)

<details>
<summary><strong>Uninstall All Diversio Plugins</strong></summary>

**Step 1: Check what's installed**

```bash
claude plugin list
```

Or inside Claude Code: `/plugin list`

Look for plugins with `@diversiotech` - note the `Scope:` field (user or project).

**Step 2: Uninstall user-scoped plugins**

Copy-paste these commands in your terminal:

```bash
claude plugin uninstall monty-code-review@diversiotech
claude plugin uninstall backend-atomic-commit@diversiotech
claude plugin uninstall backend-pr-workflow@diversiotech
claude plugin uninstall bruno-api@diversiotech
claude plugin uninstall code-review-digest-writer@diversiotech
claude plugin uninstall plan-directory@diversiotech
claude plugin uninstall pr-description-writer@diversiotech
claude plugin uninstall session-review-notes@diversiotech
claude plugin uninstall process-code-review@diversiotech
claude plugin uninstall mixpanel-analytics@diversiotech
claude plugin uninstall clickup-ticket@diversiotech
claude plugin uninstall repo-docs@diversiotech
claude plugin uninstall backend-release@diversiotech
```

**Step 3: Uninstall project-scoped plugins (if any)**

If `claude plugin list` shows plugins at `Scope: project`:

```bash
claude plugin uninstall monty-code-review@diversiotech --scope project
claude plugin uninstall backend-atomic-commit@diversiotech --scope project
claude plugin uninstall backend-pr-workflow@diversiotech --scope project
claude plugin uninstall bruno-api@diversiotech --scope project
claude plugin uninstall code-review-digest-writer@diversiotech --scope project
claude plugin uninstall plan-directory@diversiotech --scope project
claude plugin uninstall pr-description-writer@diversiotech --scope project
claude plugin uninstall session-review-notes@diversiotech --scope project
claude plugin uninstall process-code-review@diversiotech --scope project
claude plugin uninstall mixpanel-analytics@diversiotech --scope project
claude plugin uninstall clickup-ticket@diversiotech --scope project
claude plugin uninstall repo-docs@diversiotech --scope project
claude plugin uninstall backend-release@diversiotech --scope project
```

</details>

<details>
<summary><strong>Troubleshooting</strong></summary>

| Problem | Solution |
|---------|----------|
| Plugin shows in list but "not found" on uninstall | Try the other scope: `--scope project` or `--scope user` |
| Plugin stuck in disabled state | Enable first (`claude plugin enable ...`), then uninstall |
| Project-scoped plugins don't persist in git worktrees | Uninstall with `--scope project`, reinstall at user scope |
| Manual cleanup needed | Delete `.claude/` directory in project root, or check `~/.claude/` for user config |

</details>

After uninstalling, reinstall using the install commands above.

## Install As Codex Skills

Codex can install these Skills directly from GitHub (separate from Claude's
marketplace) using the Skill Installer.

<details>
<summary><strong>Install All Skills (Codex)</strong></summary>

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
    plugins/session-review-notes/skills/session-review-notes \
    plugins/process-code-review/skills/process-code-review \
    plugins/mixpanel-analytics/skills/mixpanel-analytics \
    plugins/clickup-ticket/skills/clickup-ticket \
    plugins/repo-docs/skills/repo-docs-generator \
    plugins/backend-release/skills/release-manager
```

**Codex console alternative:**

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
  path=plugins/session-review-notes/skills/session-review-notes \
  path=plugins/process-code-review/skills/process-code-review \
  path=plugins/mixpanel-analytics/skills/mixpanel-analytics \
  path=plugins/clickup-ticket/skills/clickup-ticket \
  path=plugins/repo-docs/skills/repo-docs-generator \
  path=plugins/backend-release/skills/release-manager
```

</details>

<details>
<summary><strong>Install Individual Skills (Codex)</strong></summary>

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

python3 "$CODEX_HOME/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo DiversioTeam/agent-skills-marketplace \
  --path plugins/monty-code-review/skills/monty-code-review
```

Or from the Codex console:

```text
$skill-installer install from github repo=DiversioTeam/agent-skills-marketplace path=plugins/monty-code-review/skills/monty-code-review
```

</details>

<details>
<summary><strong>Uninstall All Skills (Codex)</strong></summary>

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
rm -rf "$CODEX_HOME/skills/monty-code-review" \
       "$CODEX_HOME/skills/backend-atomic-commit" \
       "$CODEX_HOME/skills/backend-pr-workflow" \
       "$CODEX_HOME/skills/bruno-api" \
       "$CODEX_HOME/skills/code-review-digest-writer" \
       "$CODEX_HOME/skills/plan-directory" \
       "$CODEX_HOME/skills/backend-ralph-plan" \
       "$CODEX_HOME/skills/pr-description-writer" \
       "$CODEX_HOME/skills/session-review-notes" \
       "$CODEX_HOME/skills/process-code-review" \
       "$CODEX_HOME/skills/mixpanel-analytics" \
       "$CODEX_HOME/skills/clickup-ticket" \
       "$CODEX_HOME/skills/repo-docs-generator" \
       "$CODEX_HOME/skills/release-manager"
echo "Done. Restart Codex and reinstall skills."
```

</details>

**Notes:**
- Add `--ref <branch-or-tag>` to pin a version.
- The installer does not overwrite existing Skills; delete `$CODEX_HOME/skills/<skill-name>` first to update.
- Codex installs Skills into `~/.codex/skills` by default.
- Restart Codex after installing Skills.

## Documentation

- [Agent Skills Standard](https://agentskills.io/specification)
- [Agent Skills Best Practices](https://agentskills.io/best-practices)
- [OpenAI Codex Skills](https://developers.openai.com/codex/skills)
- [OpenAI Codex Skills (Install new skills)](https://developers.openai.com/codex/skills#install-new-skills)
- [Claude Agent Skills Overview](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)
- [Claude Code Plugins](https://code.claude.com/docs/en/plugins)
- [Discover and Install Plugins](https://code.claude.com/docs/en/discover-plugins)
- [Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Agent Skills](https://code.claude.com/docs/en/skills)

## License

MIT License - see [LICENSE](LICENSE) for details.
