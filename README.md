# Agent Skills Marketplace

Diversio's shared agent workflows for Claude Code, Pi, and Codex.

**Browse the rendered docs and tools at
[engineering.diversio.com](https://engineering.diversio.com).**

## What This Repository Provides

- **Claude Code plugins** for review, planning, releases, documentation,
  frontend/backend workflows, and operational tasks.
- **Pi packages** for CI visibility, daily workflows, image routing, cmux
  integration, timestamps, and marketplace skill discovery.
- **Portable Agent Skills** using the open
  [Agent Skills standard](https://agentskills.io/specification).
- **Source documentation** for the Agentic Tools section of the Diversio
  Engineering website.

Use the [plugin catalog](docs/plugins/catalog.md) to choose a Claude Code plugin
or skill. Use the [Pi package index](pi-packages/README.md) to see Pi commands,
shortcuts, and package-specific documentation.

Each runtime installs independently: `pi install` changes only Pi settings,
Claude Code plugins use the Claude marketplace, and Codex skills use the Codex
installer.

## Install

### Claude Code

Add the marketplace once:

```bash
claude plugin marketplace add DiversioTeam/agent-skills-marketplace
```

Install the plugin you need. For example:

```bash
claude plugin install monty-code-review@diversiotech
claude plugin install frontend@diversiotech
```

User scope is the recommended default because it works across git worktrees.
Use `--scope project` only when the plugin should be recorded in project
settings.

List or update installed plugins:

```bash
claude plugin list
claude plugin marketplace update diversiotech
claude plugin update frontend@diversiotech
```

See the [plugin catalog](docs/plugins/catalog.md) for every plugin, its purpose,
and its slash commands. The [distribution runbook](docs/runbooks/distribution.md)
keeps the complete Claude install-all and uninstall-all commands, project scope,
troubleshooting, and the `visual-explainer` replacement caveat.

### Pi

Install all Pi packages, including `skills-bridge`, from one stable source:

```bash
pi install git:github.com/DiversioTeam/agent-skills-marketplace
```

Run `/reload` in Pi after installation. Update later with:

```bash
pi update --extensions
```

This command does not install Claude Code plugins or copy skills into Codex.
`skills-bridge` can expose marketplace skills inside Pi when Pi starts in a
matching checkout or an explicit marketplace root is configured.

Pi packages can execute code with your system permissions. Review package
sources before installation. For package details, bridge configuration, and
local-development commands, see [`pi-packages/README.md`](pi-packages/README.md).

### Codex

Install an individual skill with Codex's bundled skill installer:

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

python3 "$CODEX_HOME/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo DiversioTeam/agent-skills-marketplace \
  --ref main \
  --path plugins/monty-code-review/skills/monty-code-review
```

Restart Codex after installation. The
[distribution runbook](docs/runbooks/distribution.md#codex-skill-installation)
has the complete install-all and uninstall-all commands, every skill path,
pinning guidance, and the replacement workflow.

## Uninstall

### Claude Code

For example:

```bash
claude plugin uninstall frontend@diversiotech
```

Use the [plugin catalog](docs/plugins/catalog.md) for exact plugin names. Add
`--scope project` when removing a project-scoped copy. After uninstalling
all Diversio plugins, remove the marketplace if it is no longer needed:

```bash
claude plugin marketplace remove diversiotech
```

### Pi

```bash
pi remove git:github.com/DiversioTeam/agent-skills-marketplace
```

Use `-l` only when removing a project-local installation.

### Codex

The Codex installer does not currently provide an uninstall command. Remove the
installed skill directory, then restart Codex:

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
rm -rf "$CODEX_HOME/skills/monty-code-review"
```

For bulk uninstall commands and scope troubleshooting, use the
[distribution runbook](docs/runbooks/distribution.md).

## Repository Layout

```text
.claude-plugin/   Claude Code marketplace manifest
plugins/          Plugin manifests, skills, commands, and focused references
pi-packages/      Pi extensions and Pi-local skills
website/          Astro site for engineering.diversio.com
docs/             Architecture, catalog, quality, and distribution guidance
```

Detailed behavior belongs with its owner:

- plugin and slash-command inventory: [`docs/plugins/catalog.md`](docs/plugins/catalog.md)
- installation and troubleshooting: [`docs/runbooks/distribution.md`](docs/runbooks/distribution.md)
- Pi package details: [`pi-packages/README.md`](pi-packages/README.md) and each
  package's README
- orchestrated PR review: [`plugins/monolith-review-orchestrator/README.md`](plugins/monolith-review-orchestrator/README.md)
- repository architecture: [`docs/architecture/overview.md`](docs/architecture/overview.md)

## Contributing

Start with [`AGENTS.md`](AGENTS.md), then read
[`CONTRIBUTING.md`](CONTRIBUTING.md). Keep the root README focused on discovery
and installation; put detailed behavior in the owning plugin, package, or
focused document.

Useful validation commands:

```bash
bash scripts/validate-skills.sh
jq -e . .claude-plugin/marketplace.json >/dev/null
```

See [`docs/quality/gates.md`](docs/quality/gates.md) for the complete validation
matrix.

## License

MIT License — see [LICENSE](LICENSE).
