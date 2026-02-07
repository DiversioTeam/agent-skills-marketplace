# Claude Code Configuration for `agent-skills-marketplace`

This repository is an **Agent Skills marketplace repo** for Diversio. It hosts
reusable Skills packaged in the open Agent Skills standard and includes Claude
Code plugin/marketplace metadata so the same skills can be distributed via
Claude Marketplace or other channels.

## Repository Purpose

- Provide a **local / GitHub marketplace** of Diversio-maintained Agent Skills.
- Encapsulate opinionated Skills (for example, the Monty backend code review Skill)
  so they can be reused across multiple repos without copy‑pasting.
- Keep plugin manifests, marketplace definitions, and SKILL docs small, clear, and
  versioned.

Key layout:

- `.claude-plugin/`
  - `marketplace.json` – Claude Code marketplace definition listing available plugins.
- `plugins/`
  - `monty-code-review/`
    - `.claude-plugin/plugin.json` – plugin manifest for `monty-code-review`.
    - `skills/monty-code-review/SKILL.md` – the Monty backend code review Skill.
  - `backend-atomic-commit/`
    - `.claude-plugin/plugin.json` – plugin manifest for backend pre-commit / atomic commit.
    - `skills/backend-atomic-commit/SKILL.md` – backend atomic commit Skill.
    - `commands/*.md` – Commands for pre-commit, atomic-commit, and commit (run→fix→commit).
  - `backend-pr-workflow/`
    - `.claude-plugin/plugin.json` – plugin manifest for backend PR workflow checks.
    - `skills/backend-pr-workflow/SKILL.md` – backend PR workflow Skill.
  - `bruno-api/`
    - `.claude-plugin/plugin.json` – plugin manifest for Bruno API docs generator.
    - `skills/bruno-api/SKILL.md` – Bruno API documentation Skill.
  - `code-review-digest-writer/`
    - `.claude-plugin/plugin.json` – plugin manifest for code review digests.
    - `skills/code-review-digest-writer/SKILL.md` – code review digest writer Skill.
  - `plan-directory/`
    - `.claude-plugin/plugin.json` – plugin manifest for structured plan directories.
    - `skills/plan-directory/SKILL.md` – plan directory creation and maintenance Skill.
    - `skills/backend-ralph-plan/SKILL.md` – RALPH loop integration for backend Django.
  - `pr-description-writer/`
    - `.claude-plugin/plugin.json` – plugin manifest for PR descriptions.
    - `skills/pr-description-writer/SKILL.md` – PR description generator Skill.
  - `process-code-review/`
    - `.claude-plugin/plugin.json` – plugin manifest for code review processor.
    - `skills/process-code-review/SKILL.md` – process code review findings Skill.
  - `mixpanel-analytics/`
    - `.claude-plugin/plugin.json` – plugin manifest for MixPanel analytics.
    - `skills/mixpanel-analytics/SKILL.md` – MixPanel tracking implementation and review Skill.
  - `clickup-ticket/`
    - `.claude-plugin/plugin.json` – plugin manifest for ClickUp ticket management.
    - `skills/clickup-ticket/SKILL.md` – ClickUp ticket fetching, filtering, and creation Skill.
    - `commands/*.md` – Commands for reading, filtering, creating tickets, subtasks, multi-org.
  - `repo-docs/`
    - `.claude-plugin/plugin.json` – plugin manifest for repository documentation generator.
    - `skills/repo-docs-generator/SKILL.md` – comprehensive AGENTS.md/README.md/CLAUDE.md generator Skill.
    - `commands/generate.md` – Generate new documentation from scratch.
    - `commands/canonicalize.md` – Audit and fix existing docs (make AGENTS.md canonical, normalize CLAUDE.md).
  - `backend-release/`
    - `.claude-plugin/plugin.json` – plugin manifest for Django4Lyfe release workflow.
    - `skills/release-manager/SKILL.md` – full release workflow management Skill.
    - `commands/*.md` – Commands for check, create, and publish releases.
  - `terraform/`
    - `.claude-plugin/plugin.json` – plugin manifest for Terraform/Terragrunt workflows.
    - `skills/terraform-atomic-commit/SKILL.md` – Terraform atomic commit Skill.
    - `skills/terraform-pr-workflow/SKILL.md` – Terraform PR workflow Skill.
    - `commands/*.md` – Commands for pre-commit, atomic-commit, and PR workflow checks.

## How Claude Code Should Behave Here

When working in this repo, Claude Code should:

1. **Treat this as configuration, not application code.**
   - Do **not** scaffold apps, frameworks, or unrelated code here.
   - Limit changes to:
     - `AGENTS.md`, `CLAUDE.md`
     - `.claude-plugin/*.json` (marketplace + repo metadata)
     - `plugins/**/.claude-plugin/plugin.json` (per-plugin manifests)
     - `plugins/**/skills/*/SKILL.md` (Skill docs)
     - `plugins/**/commands/*.md` (plugin slash-command entrypoints that invoke Skills)
     - `README.md` / documentation.

2. **Keep JSON valid and minimal.**
   - Always keep `marketplace.json` and each `plugin.json` valid JSON.
   - Prefer small, targeted edits over whole‑file rewrites.
   - If making non‑trivial changes, mentally (or programmatically) validate JSON.

   - **Versioning:** When you add or change a plugin, always bump its version:
     - Update `plugins/<plugin>/.claude-plugin/plugin.json` with a new version
       (use simple SemVer-style increments, e.g. `0.1.0` → `0.1.1`).
     - Ensure the corresponding entry in `.claude-plugin/marketplace.json` uses
       the **same** version string.
     - For new plugins, start at `0.1.0` (or similar) and add a matching entry
       in `marketplace.json`.

   - **CLAUDE.md best practice:** Follow Claude Code's guidance for web-based
     repos (see
     `https://docs.claude.com/en/docs/claude-code/claude-code-on-the-web#best-practices`):
     - Keep requirements and commands defined in a single source of truth
       (`AGENTS.md` in this repo).
     - In `CLAUDE.md`, **source** this file using `@AGENTS.md` instead of
       duplicating content, and only add minimal extra notes if truly needed.

3. **Keep Skills self‑contained and documented.**
   - Each Skill should live at `plugins/<plugin-name>/skills/<skill-name>/SKILL.md`.
   - SKILL docs should explain:
     - When to use the Skill.
     - Core priorities / taste.
     - Output shape and severity tags.
   - Avoid including secrets or customer‑specific confidential details in SKILL docs.
   - For every Skill, add at least one corresponding **plugin slash command**
     under `plugins/<plugin>/commands/*.md` that invokes the Skill (thin
     wrapper that references the Skill by name). This ensures the plugin
     appears as a `/plugin-name:command` entry in Claude Code's slash command
     palette.

   - **SKILL.md YAML frontmatter:** Always quote string values in the YAML
     frontmatter that contain special characters (colons, brackets, commas,
     quotes). Unquoted strings with colons can cause YAML parsing errors:
     ```yaml
     # CORRECT - strings with special chars are quoted
     ---
     name: my-skill
     description: "Use this when preparing releases, bumping versions, etc."
     allowed-tools: Bash Read Edit Grep Glob
     argument-hint: "[action] (e.g., create, publish)"
     ---

     # WRONG - unquoted strings with colons cause parse errors
     ---
     name: my-skill
     description: Use this when preparing releases, bumping versions, etc.
     argument-hint: [action] (e.g., "create", "publish")
     ---
     ```

4. **Follow existing naming and structure.**
   - New plugins should mirror the structure of `monty-code-review`:
     - `plugins/<plugin>/`
       - `.claude-plugin/plugin.json`
       - `skills/<skill-name>/SKILL.md`
   - Use `kebab-case` for plugin folder names where possible.

5. **Do not modify application behavior here.**
   - This repo should not contain Django/React/Terraform or other app logic.
   - If a plugin needs to describe behavior in another repo, document it here but
     change the actual code in that other repo.

## Requirements & Commands

- Dependencies:
  - Claude Code installed locally.
  - This repo (`agent-skills-marketplace`) cloned on your machine.

- Once this repo is hosted at `github.com/DiversioTeam/agent-skills-marketplace`, add the
  marketplace to Claude Code from any project:

  ```bash
  /plugin marketplace add DiversioTeam/agent-skills-marketplace
  ```

- Install the Monty backend code review plugin:

  ```bash
  /plugin install monty-code-review@diversiotech
  ```

- Install the backend atomic commit plugin:

  ```bash
  /plugin install backend-atomic-commit@diversiotech
  ```

- Install the backend PR workflow plugin:

  ```bash
  /plugin install backend-pr-workflow@diversiotech
  ```

- Install the Bruno API docs plugin:

  ```bash
  /plugin install bruno-api@diversiotech
  ```

- Install the code review digest writer plugin:

  ```bash
  /plugin install code-review-digest-writer@diversiotech
  ```

- Install the plan directory plugin:

  ```bash
  /plugin install plan-directory@diversiotech
  ```

- Install the PR description writer plugin:

  ```bash
  /plugin install pr-description-writer@diversiotech
  ```

- Install the code review processor plugin:

  ```bash
  /plugin install process-code-review@diversiotech
  ```

- Install the MixPanel analytics plugin:

  ```bash
  /plugin install mixpanel-analytics@diversiotech
  ```

- Install the ClickUp ticket plugin:

  ```bash
  /plugin install clickup-ticket@diversiotech
  ```

- Install the repo docs plugin:

  ```bash
  /plugin install repo-docs@diversiotech
  ```

- Install the backend release plugin:

  ```bash
  /plugin install backend-release@diversiotech
  ```

- **Uninstall all Diversio plugins** (Claude Code) to reinstall fresh:

  First check what's installed: `/plugin list` (note `Scope:` field).

  ```bash
  # User scope (default) - run each line
  /plugin uninstall monty-code-review@diversiotech
  /plugin uninstall backend-atomic-commit@diversiotech
  /plugin uninstall backend-pr-workflow@diversiotech
  /plugin uninstall bruno-api@diversiotech
  /plugin uninstall code-review-digest-writer@diversiotech
  /plugin uninstall plan-directory@diversiotech
  /plugin uninstall pr-description-writer@diversiotech
  /plugin uninstall process-code-review@diversiotech
  /plugin uninstall mixpanel-analytics@diversiotech
  /plugin uninstall clickup-ticket@diversiotech
  /plugin uninstall repo-docs@diversiotech
  /plugin uninstall backend-release@diversiotech
  ```

  For project-scoped plugins, add `--scope project`:

  ```bash
  /plugin uninstall <plugin>@diversiotech --scope project
  ```

  **Troubleshooting:** If a plugin shows in list but "not found" on uninstall,
  try the other scope. For stuck/disabled plugins, enable first then uninstall.
  For manual cleanup, delete `.claude/` in project root or check `~/.config/claude/`.

## Codex Skill Installer Notes (For LLMs)

When a user asks how to install these Skills into OpenAI Codex (not Claude's
marketplace), respond with instructions that avoid hardcoded paths:

- Use the Skill Installer script that ships with Codex:
  - `$CODEX_HOME/skills/.system/skill-installer/scripts/install-skill-from-github.py`
  - (with `CODEX_HOME` defaulting to `~/.codex`)
- Prefer `--repo DiversioTeam/agent-skills-marketplace --path plugins/<plugin>/skills/<skill>`.
- Mention `--ref <branch-or-tag>` for pinning and the need to restart Codex.
- Avoid hardcoded absolute user paths like `/Users/<name>/...`.
- If the user wants Codex-console commands, provide `$skill-installer` examples
  that mirror the repo/path usage above.

- **Uninstall all Diversio skills** (Codex) to reinstall fresh:

  ```bash
  # Uninstall all Diversio skills (safe: continues if skill doesn't exist)
  CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
  rm -rf "$CODEX_HOME/skills/monty-code-review" \
         "$CODEX_HOME/skills/backend-atomic-commit" \
         "$CODEX_HOME/skills/backend-pr-workflow" \
         "$CODEX_HOME/skills/bruno-api" \
         "$CODEX_HOME/skills/code-review-digest-writer" \
         "$CODEX_HOME/skills/plan-directory" \
         "$CODEX_HOME/skills/backend-ralph-plan" \
         "$CODEX_HOME/skills/pr-description-writer" \
         "$CODEX_HOME/skills/process-code-review" \
         "$CODEX_HOME/skills/mixpanel-analytics" \
         "$CODEX_HOME/skills/clickup-ticket" \
         "$CODEX_HOME/skills/repo-docs-generator" \
         "$CODEX_HOME/skills/release-manager" \
         "$CODEX_HOME/skills/terraform-atomic-commit" \
         "$CODEX_HOME/skills/terraform-pr-workflow"
  ```

  After removing, restart Codex and reinstall using the Skill Installer.

## Usage Notes for Humans

- After installation, you can use:
  - `monty-code-review` for hyper‑pedantic Django4Lyfe backend reviews.
  - `backend-atomic-commit` for backend pre-commit fixes and strict atomic
     commits that obey local `AGENTS.md`, `.pre-commit-config.yaml`,
     `.security/*` helpers, and Monty's backend taste (no AI commit
     signatures). Includes `/backend-atomic-commit:commit` for full
     run→fix→commit closure with convergence budgets and stuck detection.
  - `backend-pr-workflow` for backend PR workflow checks (ClickUp-linked
    branch/PR naming, migrations, downtime-safe schema changes).
  - `bruno-api` to generate API endpoint documentation from Bruno (`.bru`)
    files by tracing the corresponding Django4Lyfe implementation.
  - `code-review-digest-writer` to generate weekly code review digests for a
    repo based on PR review comments.
  - `plan-directory` to create and maintain structured plan directories with
    a master PLAN.md index and numbered task files (001-*.md) containing
    checklists, tests, and completion criteria.
  - `backend-ralph-plan` to create RALPH loop-integrated plans for backend
    Django projects with iteration-aware prompts, quality gates, and
    automated execution via `/plan-directory:run <slug>`.
  - `pr-description-writer` to generate comprehensive, reviewer-friendly PR
    descriptions with visual diagrams, summary tables, and structured sections.
  - `process-code-review` to interactively process code review findings from
    monty-code-review output - fix or skip issues with status tracking.
  - `mixpanel-analytics` to implement new MixPanel tracking events and review
    implementations for PII protection, schema design, and pattern compliance
    in the Django4Lyfe optimo_analytics module.
  - `clickup-ticket` to fetch, filter, and create ClickUp tickets directly from
    Claude Code or Codex. Supports reading tickets by ID, powerful filtering
    (status, assignee, tags, dates), viewing assigned tickets, multi-org
    workspaces, subtasks, and intelligent caching of workspace data. Commands:
    - `/clickup-ticket:get-ticket <id>` – Fetch full ticket details by ID or URL
    - `/clickup-ticket:list-tickets` – List/filter tickets (status, assignee, tags, dates)
    - `/clickup-ticket:my-tickets` – View your assigned tickets grouped by urgency
    - `/clickup-ticket:create-ticket` – Full interactive ticket creation
    - `/clickup-ticket:quick-ticket` – Fast ticket with defaults
    - `/clickup-ticket:add-to-backlog` – Ultra-fast backlog addition
    - `/clickup-ticket:create-subtask` – Add subtask to existing ticket
    - `/clickup-ticket:switch-org` – Switch between organizations
    - `/clickup-ticket:configure` – Set up defaults and cache
  - `repo-docs` to generate and canonicalize repository documentation. Commands:
    - `/repo-docs:generate [path]` – Generate new AGENTS.md, README.md, CLAUDE.md
      from scratch with ASCII architecture diagrams and tech stack analysis.
    - `/repo-docs:canonicalize [path]` – Audit existing docs across a repo: update
      AGENTS.md to match current tooling (uv, .bin/*), merge CLAUDE.md content
      into AGENTS.md, normalize all CLAUDE.md to minimal `@AGENTS.md` stubs.
  - `backend-release` to manage the full release workflow for Django4Lyfe backend
    (Diversio monolith). Handles release PRs, date-based version bumping
    (YYYY.MM.DD), uv lock updates, and GitHub release publishing. Commands:
    - `/backend-release:check` – Check what commits are pending release
    - `/backend-release:create` – Create release PR with cherry-pick method
    - `/backend-release:publish [PR_NUMBER]` – Publish GitHub release after PR merge
  - `terraform-atomic-commit` for Terraform/Terragrunt pre-commit fixes and strict
    atomic commits (fmt/validate/docs drift; no apply; no AI commit signatures). Commands:
    - `/terraform:pre-commit` – Fix and validate changed IaC files
    - `/terraform:atomic-commit` – Enforce staged atomicity + propose commit message
  - `terraform-pr-workflow` for Terraform/Terragrunt PR workflow checks (naming,
    PR hygiene, read-only CI gates, versioning expectations). Command:
    - `/terraform:check-pr` – Review PR workflow quality

## References

- [Agent Skills Standard](https://agentskills.io/specification)
- [Agent Skills Best Practices](https://agentskills.io/best-practices)
- [OpenAI Codex Skills](https://developers.openai.com/codex/skills)
- [OpenAI Codex Skills (Install new skills)](https://developers.openai.com/codex/skills#install-new-skills)
- [Claude Agent Skills Overview](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)
- [Claude Code Plugins](https://code.claude.com/docs/en/plugins)
- [Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Agent Skills](https://code.claude.com/docs/en/skills)
