# Contributing to `agent-skills-marketplace`

This repo is an **Agent Skills marketplace** for Diversio. It is mostly
configuration, Skills, and commands – not application code. The goal is to make
it easy to add and evolve Skills and plugin metadata using LLMs while keeping
things consistent and safe.

If in doubt, treat `AGENTS.md` as the source of truth and follow it first.

## What You Can Change

In this repo, contributions should generally be limited to:

- `AGENTS.md`, `CLAUDE.md`
- `.claude-plugin/marketplace.json`
- `plugins/**/.claude-plugin/plugin.json` (per-plugin manifests)
- `plugins/**/skills/*/SKILL.md` (Skill definitions)
- `plugins/**/commands/*.md` (slash command entrypoints)
- `README.md` / `CONTRIBUTING.md` / other small docs

Do **not** add application logic (Django, React, Terraform, etc.) here.

## Adding a New Plugin

Follow the existing structure (e.g. `monty-code-review`, `backend-atomic-commit`):

1. **Create the plugin folder**

   ```text
   plugins/<plugin-name>/
     .claude-plugin/plugin.json
     skills/<skill-name>/SKILL.md
     commands/<command-name>.md (one or more)
   ```

   - Use `kebab-case` for `<plugin-name>` where possible.
   - `<skill-name>` is usually the same as the plugin name, but doesn’t have to be.

2. **Plugin manifest**

   `plugins/<plugin-name>/.claude-plugin/plugin.json`:

   - Keep it minimal and valid JSON.
   - Fields:
     - `name` – plugin name (kebab-case).
     - `version` – SemVer-like string.
     - `description` – short, human-readable.
     - `author` – e.g. `{ "name": "Diversio Devs" }`.

   **Versioning rules:**

   - New plugins start at `0.1.0` (or similar).
   - On any behavior or docs change to the plugin, bump the version:
     - e.g. `0.1.0` → `0.1.1`.

3. **Marketplace entry**

   Add an entry to `.claude-plugin/marketplace.json`:

   - `name` – must match plugin manifest.
   - `version` – must match plugin manifest version.
   - `source` – `./plugins/<plugin-name>`.
   - `category`, `keywords` – keep them short and accurate.

4. **Skill definition**

   `plugins/<plugin-name>/skills/<skill-name>/SKILL.md` should:

   - Start with YAML frontmatter:

     ```yaml
     ---
     name: <skill-name>
     description: "Short, single-line summary of what this Skill does."
     allowed-tools: Bash Read Edit Glob Grep
     ---
     ```

   - For portability across both Codex + Claude Code:
     - Keep `description` single-line and reasonably short (Codex validates this at startup).
     - Avoid `anthropic`/`claude` in Skill names and don’t include XML tags in `name`/`description` (Claude).

   - Include sections such as:
     - `When to Use This Skill`
     - `Example Prompts`
     - Core priorities / taste (what the Skill optimizes for)
     - Any severity tags and required output structure
     - High-level workflow / checklist

   - Keep it self-contained and repo-agnostic where possible:
     - If it depends on a particular repo’s `AGENTS.md`, say so explicitly.
     - Avoid hard-coding customer-specific or secret information.

5. **Commands**

   Add one or more command files under:

   ```text
   plugins/<plugin-name>/commands/<command-name>.md
   ```

   Each should:

   - Have a short frontmatter block:

     ```yaml
     ---
     description: Short description of what this command does.
     ---
     ```

   - Instruct Claude to “use your `<skill-name>` Skill” with:
     - Clear mode (e.g. “pre-commit mode”, “atomic-commit mode”, “PR review mode”).
     - High-level focus areas.
     - Any special flags/arguments to interpret.

   Commands should be **thin wrappers** over the Skill – avoid duplicating full
   Skill logic in the command file.

6. **Docs & references**

   - Update `README.md`:
     - Add the plugin to the tree diagram.
     - Add a row to the “Available Plugins” table.
     - Add an install example and slash command examples.
   - Update `AGENTS.md`:
     - Add an install command for the new plugin.
     - Add a short bullet under “Usage Notes for Humans”.

## Using LLMs to Create Skills & Commands

We expect most Skills and commands here to be written with LLM help. That’s OK
and encouraged – a few guidelines:

- It’s fine to **reuse prompt patterns** across Skills:
  - Example: Monty’s backend taste, severity tags, output shapes.
  - Example: “When to Use This Skill” + “Example Prompts” sections.
- Anchor new Skills in existing ones:
  - If you’re adding a backend tool, read:
    - `plugins/monty-code-review/skills/monty-code-review/SKILL.md`
    - `plugins/backend-pr-workflow/skills/backend-pr-workflow/SKILL.md`
    - `plugins/backend-atomic-commit/skills/backend-atomic-commit/SKILL.md`
  - Reuse structure and wording where it saves review time, then customize the
    behavior and context.
- Keep prompts **explicit and pedantic**:
  - Spell out checklists and severity tags.
  - Define the expected output shape (sections, tags, summaries).
  - When behavior involves repositories with `AGENTS.md`, tell the Skill to
    treat those as the source of truth.
- Always review LLM output before committing:
  - Remove or rephrase anything that sounds generic or misaligned with Diversio.
  - Make sure no secrets, tokens, or internal-only URLs are included.

## JSON & Validation

- Always keep JSON valid:
  - You can use `python -m json.tool` or any editor tooling locally to validate
    `.claude-plugin/marketplace.json` and `plugin.json` files.
- Optionally validate Skills against the Agent Skills spec using `skills-ref validate <path>` (if you have `skills-ref` installed).
- Prefer small, focused edits over wholesale rewrites:
  - This makes diffs easier to review.

## Review Checklist for PRs

Before opening a PR (or pushing directly, if that’s your workflow), quickly
check:

- [ ] New plugin has:
  - [ ] `plugins/<plugin-name>/.claude-plugin/plugin.json`
  - [ ] `plugins/<plugin-name>/skills/<skill-name>/SKILL.md`
  - [ ] `plugins/<plugin-name>/commands/*.md`
- [ ] Plugin `version` matches in `plugin.json` and `marketplace.json`.
- [ ] `marketplace.json` JSON parses cleanly.
- [ ] `README.md` and `AGENTS.md` mention the new plugin where appropriate.
- [ ] SKILL docs:
  - [ ] Explain when to use the Skill.
  - [ ] Include example prompts.
  - [ ] Define severity tags / output shape if the Skill reports findings.
- [ ] No application code or secrets added to this repo.

Following these guidelines should keep new plugins easy to add, easy to review,
and consistent with the rest of the marketplace. Feel free to evolve this
document as we learn what patterns work best.
