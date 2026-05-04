# Quality Gates

## Required Commands

Run the checks that match the files you touched:

```bash
bash scripts/validate-skills.sh
bash scripts/validate-skills.sh --all
jq -e . .claude-plugin/marketplace.json >/dev/null
jq -e . plugins/<plugin>/.claude-plugin/plugin.json >/dev/null
jq -e . pi-packages/<package>/package.json >/dev/null
(cd pi-packages/<package> && npm pack --dry-run --json >/tmp/<package>-pack.json)
printf '{"id":"cmds","type":"get_commands"}\n' | PI_OFFLINE=1 pi --mode rpc --no-session --no-context-files --no-extensions -e ./pi-packages/<package> --no-prompt-templates --no-skills
```

`bash scripts/validate-skills.sh` checks changed and untracked `SKILL.md`
files. Use `--all` when auditing the full repo.

## Active Type Gate

This repo does not ship Python application code, so there is no local runtime
type-check job to run here.

The typing policy in this marketplace applies to the repos that code-touching
skills target:

- Read `docs/python-typing-and-ty-best-practices.md`.
- Detect type gates in this order unless the target repo says otherwise:
  `ty`, then `pyright`, then `mypy`.
- If `ty` is configured in the target repo, treat it as mandatory and blocking.

## Common Failures

- Plugin version changed in `plugins/<plugin>/.claude-plugin/plugin.json` but
  not in `.claude-plugin/marketplace.json`.
- Marketplace `source` does not match `./plugins/<plugin>`.
- A skill was added or renamed without a matching command wrapper.
- A changed `SKILL.md` grew beyond 500 lines instead of moving detail into
  `references/` or `scripts/`.
- YAML frontmatter uses unquoted strings with special characters, which breaks
  parsing.
- `CLAUDE.md` accumulates unique behavior instead of remaining a pointer to
  `AGENTS.md`.
- Docs mention install or maintenance behavior that no longer matches the repo.
- Pi package command counts, shortcut names, local install paths, or documented
  TUI keybindings drift from `pi-packages/<package>/README.md`.

## CI Notes

- `Validate Marketplace`
  - Triggered by changes under `.claude-plugin/**`, `plugins/**`, `scripts/**`,
    or the workflow file itself.
  - Validates JSON, unique plugin names, plugin directory coverage, manifest
    name and version sync, skill presence, and changed-skill size budgets.
- `Validate Website`
  - Triggered by changes under `website/**` or the website workflow file.
  - Runs a clean website dependency install and `cd website && npm run build`.
  - This is the build gate for the Astro site that now targets `engineering.diversio.com`.
- `Notify Marketplace Updates`
  - Triggered by pushes to `main` that touch `plugins/**` or `pi-packages/**`.
  - Diffs the full pushed range, groups changes by marketplace item, and posts
    one Slack message with separate `Plugin items` and `Pi items` sections.
- `Deploy Website to Cloudflare Pages`
  - Triggered by website changes and site-doc source changes.
  - Builds the static site in GitHub Actions, then uploads `website/dist` to
    Cloudflare Pages.
  - PR previews run only for same-repo PRs because forked PRs do not receive
    Cloudflare secrets.
  - Pushes to `main` publish production automatically once the required GitHub
    secrets are configured.

Docs-only changes do not currently trigger the marketplace validation workflow,
so run the local checks manually when you touch shared instructions.

Website changes now trigger `Validate Website`, but you should still run the
local build yourself before opening a PR:

```bash
cd website
npm run build
```

## Review Discipline

- After substantive edits, review the changed files plus the adjacent docs or
  metadata they rely on.
- If a workflow changed, update the focused doc that owns it instead of
  expanding `AGENTS.md` or `CLAUDE.md`.
- If the same failure repeats across reviews, add a harness improvement: a doc,
  script, CI check, or clearer wrapper.
