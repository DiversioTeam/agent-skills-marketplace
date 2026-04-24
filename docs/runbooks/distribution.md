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
  frontend-bundle
  frontend-atomic-commit
  frontend-pr-workflow
  frontend-testing
  frontend-api-integrator
  frontend-mixpanel
  frontend-sentry
  frontend-cicd
  frontend-plan
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
  frontend-bundle
  frontend-atomic-commit
  frontend-pr-workflow
  frontend-testing
  frontend-api-integrator
  frontend-mixpanel
  frontend-sentry
  frontend-cicd
  frontend-plan
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
  frontend-bundle
  frontend-project-digest
  frontend-atomic-commit
  frontend-pr-workflow
  frontend-pr-review
  frontend-testing
  frontend-api-integrator
  frontend-mixpanel
  frontend-sentry
  frontend-cicd
  frontend-plan
)

for skill in "${SKILLS[@]}"; do
  rm -rf "$CODEX_HOME/skills/$skill"
done
```

Restart Codex after uninstalling and reinstalling skills.
