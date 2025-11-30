# Claude Code Configuration for `claude-plugins`

This repository is a **Claude Code plugins + marketplace repo** for Diversio. It is
used to host reusable Claude Code plugins (primarily Skills) that can be consumed
from other projects via the plugin system.

## Repository Purpose

- Provide a **local / GitHub marketplace** of Diversio-maintained Claude Code plugins.
- Encapsulate opinionated Skills (for example, the Monty backend code review Skill)
  so they can be reused across multiple repos without copy‑pasting.
- Keep plugin manifests, marketplace definitions, and SKILL docs small, clear, and
  versioned.

Key layout:

- `.claude-plugin/`
  - `marketplace.json` – marketplace definition listing available plugins.
- `plugins/`
  - `monty-code-review/`
    - `.claude-plugin/plugin.json` – plugin manifest for `monty-code-review`.
    - `skills/monty-code-review/SKILL.md` – the Monty backend code review Skill.
  - `backend-pr-workflow/`
    - `.claude-plugin/plugin.json` – plugin manifest for backend PR workflow checks.
    - `skills/backend-pr-workflow/SKILL.md` – backend PR workflow Skill.
  - `code-review-digest-writer/`
    - `.claude-plugin/plugin.json` – plugin manifest for code review digests.
    - `skills/code-review-digest-writer/SKILL.md` – code review digest writer Skill.

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

   - **CLAUDE.md best practice:** Follow Claude Code’s guidance for web-based
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
  - This repo (`claude-plugins`) cloned on your machine.

- Once this repo is hosted at `github.com/DiversioTeam/claude-plugins`, add the
  marketplace to Claude Code from any project:

  ```bash
  /plugin marketplace add DiversioTeam/claude-plugins
  ```

- Install the Monty backend code review plugin:

  ```bash
  /plugin install monty-code-review@diversiotech
  ```

- Install the backend PR workflow plugin:

  ```bash
  /plugin install backend-pr-workflow@diversiotech
  ```

- Install the code review digest writer plugin:

  ```bash
  /plugin install code-review-digest-writer@diversiotech
  ```

## Usage Notes for Humans

- After installation, you can use:
  - `monty-code-review` for hyper‑pedantic Django4Lyfe backend reviews.
  - `backend-pr-workflow` for backend PR workflow checks (ClickUp-linked
    branch/PR naming, migrations, downtime-safe schema changes).
  - `code-review-digest-writer` to generate weekly code review digests for a
    repo based on PR review comments.

## References

- [Claude Code Plugins](https://code.claude.com/docs/en/plugins)
- [Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Agent Skills](https://code.claude.com/docs/en/skills)
