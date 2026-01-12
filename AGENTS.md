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
    - `.claude-plugin/plugin.json` – plugin manifest for ClickUp ticket creation.
    - `skills/clickup-ticket/SKILL.md` – ClickUp ticket creation and management Skill.
    - `commands/*.md` – Commands for ticket creation, subtasks, backlog, multi-org.

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

## Usage Notes for Humans

- After installation, you can use:
  - `monty-code-review` for hyper‑pedantic Django4Lyfe backend reviews.
  - `backend-atomic-commit` for backend pre-commit fixes and strict atomic
     commits that obey local `AGENTS.md`, `.pre-commit-config.yaml`,
     `.security/*` helpers, and Monty's backend taste (no AI commit
     signatures).
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
  - `clickup-ticket` to create and manage ClickUp tickets directly from Claude
    Code or Codex. Supports multi-org workspaces, interactive ticket creation,
    subtasks, backlog management, and intelligent caching of your ClickUp
    workspace data. Commands include:
    - `/clickup-ticket:create-ticket` – Full interactive ticket creation
    - `/clickup-ticket:quick-ticket` – Fast ticket with defaults
    - `/clickup-ticket:add-to-backlog` – Ultra-fast backlog addition
    - `/clickup-ticket:create-subtask` – Add subtask to existing ticket
    - `/clickup-ticket:switch-org` – Switch between organizations
    - `/clickup-ticket:configure` – Set up defaults and cache

## References

- [Agent Skills Standard](https://agentskills.io/specification)
- [Agent Skills Best Practices](https://agentskills.io/best-practices)
- [OpenAI Codex Skills](https://developers.openai.com/codex/skills)
- [OpenAI Codex Skills (Install new skills)](https://developers.openai.com/codex/skills#install-new-skills)
- [Claude Agent Skills Overview](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)
- [Claude Code Plugins](https://code.claude.com/docs/en/plugins)
- [Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Agent Skills](https://code.claude.com/docs/en/skills)
