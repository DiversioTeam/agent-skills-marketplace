# Distribution Runbook

Use this file for installation, uninstallation, and reinstall workflows across
Claude Code and Codex.

## Claude Code Marketplace

### Add the marketplace

Terminal:

```bash
claude plugin marketplace add DiversioTeam/agent-skills-marketplace
```

Inside Claude Code:

```text
/plugin marketplace add DiversioTeam/agent-skills-marketplace
```

### Install a plugin

```bash
claude plugin install repo-docs@diversiotech
```

Project scope is supported, but user scope is the safest default when you work
across multiple git worktrees:

```bash
claude plugin install repo-docs@diversiotech --scope project
```

If you are replacing the upstream `visual-explainer` plugin, uninstall that
version first:

```bash
claude plugin uninstall visual-explainer@visual-explainer-marketplace
```

### Install all marketplace plugins

```bash
PLUGINS=(
  monty-code-review
  backend-atomic-commit
  backend-pr-workflow
  bruno-api
  code-review-digest-writer
  plan-directory
  pr-description-writer
  process-code-review
  mixpanel-analytics
  clickup-ticket
  github-ticket
  repo-docs
  visual-explainer
  backend-release
  dependabot-remediation
  terraform
  login-cta-attribution-skill
  frontend
)

for plugin in "${PLUGINS[@]}"; do
  claude plugin install "${plugin}@diversiotech"
done
```

Use `--scope project` inside the loop if you intentionally want project-scoped
installs.

### Uninstall all Diversio plugins

Check what is installed first:

```bash
claude plugin list
```

Then uninstall the user-scoped copies:

```bash
PLUGINS=(
  monty-code-review
  backend-atomic-commit
  backend-pr-workflow
  bruno-api
  code-review-digest-writer
  plan-directory
  pr-description-writer
  process-code-review
  mixpanel-analytics
  clickup-ticket
  github-ticket
  repo-docs
  visual-explainer
  backend-release
  dependabot-remediation
  terraform
  login-cta-attribution-skill
  frontend
)

for plugin in "${PLUGINS[@]}"; do
  claude plugin uninstall "${plugin}@diversiotech"
done
```

If you also installed project-scoped copies:

```bash
for plugin in "${PLUGINS[@]}"; do
  claude plugin uninstall "${plugin}@diversiotech" --scope project
done
```

Troubleshooting:

- If uninstall says the plugin is not found, try the other scope.
- If a plugin is disabled, re-enable it before uninstalling.
- If cleanup is still required, inspect the repo-local `.claude/` directory and
  your user-level Claude Code config location before deleting anything.

## Pi Package Installation

Pi-native packages live under `pi-packages/` and are installed with the pi CLI,
not the Claude Code marketplace.

### Git-based install (recommended)

The root `package.json` at the top of this repo declares every sub-package so pi
can discover all five from a single clone. One command replaces five:

```bash
pi install git:github.com/DiversioTeam/agent-skills-marketplace
```

If your environment is not already configured for other `@diversioteam`
GitHub Packages, export `NPM_TOKEN` with GitHub Packages read access before the
first install. `dev-workflow` and `oh-my-pi` install the shared
`@diversioteam/pi-cmux` dependency from `npm.pkg.github.com`.

Run `/reload` in pi after installation. To pull the latest updates later:

```bash
pi update --extensions
```

This does a `git pull` on the cloned repo and reloads all extensions and
skills. Versions are not pinned, so `pi update --extensions` always fetches
the latest `main`. If you want to freeze at a known version, pin the install
with a tag:

```bash
pi install git:github.com/DiversioTeam/agent-skills-marketplace@v0.0.1
```

Pinned refs are skipped by `pi update --extensions`.

**How it works.** When you `pi install` a git URL, pi clones the repo to
`~/.pi/agent/git/github.com/DiversioTeam/agent-skills-marketplace`, runs
`npm install` if a `package.json` exists, and then reads the `pi` manifest to
discover extensions, skills, prompts, and themes. The root manifest points into
the `pi-packages/` subdirectories so pi finds `ci-status`, `dev-workflow`,
`image-router`, `oh-my-pi`, and `skills-bridge` without any extra
configuration.

**Migrating from local-path installs.** If you previously installed packages
via local paths (e.g. `pi install "$PWD/pi-packages/ci-status"`), remove those
entries from `~/.pi/agent/settings.json` before switching to the git install.
Otherwise pi loads both copies and you get duplicate extensions.

### Local-path install (legacy / local dev)

From a checkout of this repo:

```bash
pi install "$PWD/pi-packages/ci-status"
pi install "$PWD/pi-packages/dev-workflow"
pi install "$PWD/pi-packages/image-router"
pi install "$PWD/pi-packages/oh-my-pi"
pi install "$PWD/pi-packages/skills-bridge"
```

From the Diversio monolith root, include the submodule path:

```bash
pi install "$PWD/agent-skills-marketplace/pi-packages/ci-status"
pi install "$PWD/agent-skills-marketplace/pi-packages/dev-workflow"
pi install "$PWD/agent-skills-marketplace/pi-packages/image-router"
pi install "$PWD/agent-skills-marketplace/pi-packages/oh-my-pi"
pi install "$PWD/agent-skills-marketplace/pi-packages/skills-bridge"
```

Before local-path installs or `-e` smoke tests of `dev-workflow` or `oh-my-pi`,
make sure your environment is already configured for `@diversioteam` GitHub
Packages, then run `npm install` either at the repo root or inside the target
package directory so `@diversioteam/pi-cmux` is available.

Plain `pi install` writes to global user settings (`~/.pi/agent/settings.json`).
For one-off extension testing from the repo root, prefer `--no-extensions -e`
so Pi loads only the target package and does not also load the same package a
second time from the root marketplace manifest:

```bash
pi --no-extensions -e ./pi-packages/ci-status
pi --no-extensions -e ./pi-packages/dev-workflow
pi --no-extensions -e ./pi-packages/image-router
pi --no-extensions -e ./pi-packages/oh-my-pi
pi --no-extensions -e ./pi-packages/skills-bridge
```

Use `-l` only when you need to test project-local install, reload, or
persistence behavior that writes to `.pi/settings.json`:

```bash
pi install -l ./pi-packages/ci-status
pi install -l ./pi-packages/dev-workflow
pi install -l ./pi-packages/image-router
pi install -l ./pi-packages/oh-my-pi
pi install -l ./pi-packages/skills-bridge
```

Install a pi package in one scope at a time. Pi deduplicates the same package
identity across user and project settings, but different local paths can still
resolve as different packages. For `ci-status`, duplicate loads can produce
tool registration conflicts for `get_ci_status` and `ci_fetch_job_logs`. Remove
the duplicate project package entry or uninstall the global copy before
restarting or running `/reload`.

After install, restart pi or run `/reload`.

Quick mental model:

```text
ci-status    -> CI visibility and job logs

dev-workflow -> workflow prompts, review passes, shipping, and
                automatic seeded cmux splits for subagent-style prompts
                when Pi is inside cmux and the parent session is idle

oh-my-pi     -> explicit cmux notifications, split-pane commands,
                and workspace-tab commands

skills-bridge -> exposes marketplace plugin skills inside Pi
```

The `ci-status` package provides `/ci`, `/ci-detail`, `/ci-logs`, CI auto-watch,
UI widgets, notifications, and LLM tools (`get_ci_status`,
`ci_fetch_job_logs`).

The `dev-workflow` package provides `/workflow:*` commands,
`/workflow:help`, `/workflow:run`, `/workflow:prompts`, `/workflow:flow`, the
`dev-workflow` and `ci` skills, XDG/project prompt config, and a bundled
`agents/workflow-pipeline.chain.md` file for pi-subagents. If your
pi-subagents setup only scans `.pi/agents/`, copy that chain file there
manually.

The `oh-my-pi` package provides explicit `/omp-split-*` and
`/omp-workspace*` cmux commands plus native cmux notifications.

## Codex Skill Installation

### Install a single skill

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

python3 "$CODEX_HOME/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo DiversioTeam/agent-skills-marketplace \
  --path plugins/repo-docs/skills/repo-docs-generator
```

Preferred pattern:

- Use `$CODEX_HOME` instead of hardcoded absolute paths.
- Prefer `--repo DiversioTeam/agent-skills-marketplace`.
- Prefer `--path plugins/<plugin>/skills/<skill>`.
- Add `--ref <branch-or-tag>` when you want to pin a branch, tag, or commit.
- Restart Codex after installation.

### Install multiple skills

Repeat `--path` once per skill:

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

python3 "$CODEX_HOME/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo DiversioTeam/agent-skills-marketplace \
  --ref main \
  --path plugins/repo-docs/skills/repo-docs-generator \
  --path plugins/visual-explainer/skills/visual-explainer
```

Codex console example:

```text
$skill-installer install from github repo=DiversioTeam/agent-skills-marketplace path=plugins/repo-docs/skills/repo-docs-generator
```

See `docs/plugins/catalog.md` for the full set of skill paths.

### Replace an existing skill

The installer does not overwrite an existing skill directory. Remove the old
directory first, then reinstall.

If you are replacing the upstream `visual-explainer` skill with this repo's
version, remove the existing directory first:

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
rm -rf "$CODEX_HOME/skills/visual-explainer"
```

### Uninstall all Diversio Codex skills

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

SKILLS=(
  monty-code-review
  backend-atomic-commit
  backend-pr-workflow
  bruno-api
  code-review-digest-writer
  plan-directory
  backend-ralph-plan
  pr-description-writer
  process-code-review
  mixpanel-analytics
  clickup-ticket
  github-ticket
  repo-docs-generator
  visual-explainer
  release-manager
  dependabot-remediation
  terraform-atomic-commit
  terraform-pr-workflow
  login-cta-attribution-skill
  frontend
)

for skill in "${SKILLS[@]}"; do
  rm -rf "$CODEX_HOME/skills/$skill"
done
```

Restart Codex after uninstalling and reinstalling skills.
