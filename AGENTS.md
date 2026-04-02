# AGENTS.md

## What This Repo Is

This repo is Diversio's configuration-only marketplace for reusable Agent
Skills and Claude Code plugins. The source of truth is the marketplace
metadata, per-plugin manifests, skill docs, slash-command wrappers, and the
repo-local docs that explain how they fit together.

Do not add application behavior here. Keep changes scoped to docs, manifests,
skills, commands, and supporting validation scripts.

## Branch And PR Hygiene

- Prefer issue-linked branches such as `gh-45-workflow-skill-branch-pr-conventions`
  for tracked marketplace work.
- Default PR target: `main`.
- Default PR state: ready-for-review. Use draft only for explicit WIP or when
  the workflow docs for a specific change say draft-first.
- Prefer issue links in the PR body such as `Closes #45`.

## How To Navigate This Repo

- Start here for repo-wide rules, verified commands, and doc routing.
- Read `docs/architecture/overview.md` for the marketplace layout, boundaries,
  and change flow.
- Read `docs/quality/gates.md` for CI checks, manifest-sync rules, and the
  `SKILL.md` size guardrail.
- Read `docs/runbooks/distribution.md` for Claude Code and Codex install,
  uninstall, and reinstall workflows.
- Read `docs/plugins/catalog.md` for the plugin inventory, skill paths, and
  slash commands.
- Read `docs/python-typing-and-ty-best-practices.md` when editing a
  code-touching Python skill.
- Read `CONTRIBUTING.md` when adding a plugin or reshaping a skill.

## Commands

```bash
bash scripts/validate-skills.sh
bash scripts/validate-skills.sh --all
jq -e . .claude-plugin/marketplace.json >/dev/null
jq -e . plugins/<plugin>/.claude-plugin/plugin.json >/dev/null
git diff -- AGENTS.md CLAUDE.md README.md CONTRIBUTING.md docs .claude-plugin plugins
```

## Non-Negotiable Rules

- Treat this as configuration, not application code.
- Keep JSON valid and minimal. When a plugin changes, bump the version in both
  `plugins/<plugin>/.claude-plugin/plugin.json` and the matching entry in
  `.claude-plugin/marketplace.json`.
- Every skill must live under `plugins/<plugin>/skills/<skill>/SKILL.md` and
  have at least one thin wrapper in `plugins/<plugin>/commands/*.md`.
- Keep each changed `SKILL.md` at or below 500 lines. Move deep guidance to
  `references/` and reusable logic to `scripts/`.
- Quote YAML frontmatter strings that contain special characters such as
  colons, commas, brackets, or quotes.
- `CLAUDE.md` is a minimal `@AGENTS.md` pointer only. Put durable rules here or
  in repo-local docs, not in `CLAUDE.md`.
- `README.md` is still a maintained engineer-facing document. When plugin
  inventory, install flows, slash-command examples, or the top-level repo shape
  change, update `README.md` as well as the focused docs.
- For Python code-touching skills, document type-gate detection in this order:
  `ty`, then `pyright`, then `mypy`. If `ty` is configured in the target repo,
  treat it as mandatory and blocking.
- When documenting Codex installation, use the `$CODEX_HOME`-based installer
  pattern from `docs/runbooks/distribution.md`; avoid hardcoded user paths and
  mention `--ref`, restart requirements, and the `visual-explainer`
  replacement caveat.
- After substantive skill, command, manifest, or doc changes, do a fresh-eyes
  pass across adjacent docs and metadata before stopping.

## Repo Shape

- `.claude-plugin/marketplace.json` - top-level marketplace definition
- `plugins/<plugin>/.claude-plugin/plugin.json` - per-plugin manifest
- `plugins/<plugin>/skills/<skill>/SKILL.md` - skill definition
- `plugins/<plugin>/commands/*.md` - slash-command wrappers
- `scripts/validate-skills.sh` - local and CI `SKILL.md` size budget check
- `.github/workflows/validate-marketplace.yml` - JSON, version, and structure CI
- `.github/workflows/notify-plugin-updates.yml` - Slack notification on plugin
  changes pushed to `main`

## Docs Index

- `README.md` - human-first quickstart and entrypoint
- `docs/architecture/overview.md` - structure, ownership boundaries, and flows
- `docs/quality/gates.md` - validation, CI coverage, and recurring failure modes
- `docs/runbooks/distribution.md` - Claude Code and Codex install workflows
- `docs/plugins/catalog.md` - plugin inventory, commands, and skill paths
- `docs/python-typing-and-ty-best-practices.md` - policy for code-touching
  Python skills
- `CONTRIBUTING.md` - how to add or update plugins safely

## Keep The Harness Fresh

- If a failure repeats, encode it in docs, scripts, or CI instead of letting it
  remain tribal knowledge.
- If install or distribution behavior changes, update
  `docs/runbooks/distribution.md` and any top-level pointers that reference it.
- If the plugin inventory or command surface changes, update both
  `docs/plugins/catalog.md` and `README.md`. Keep the catalog as the structured
  inventory and keep `README.md` accurate for engineers who use it as the main
  handbook.
- Add focused docs under `docs/` instead of turning this file back into a
  handbook.
