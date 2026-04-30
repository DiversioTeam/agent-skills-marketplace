# Pi Packages

Pi-native packages that extend pi with tools, commands, skills, and UI widgets.

## Available Packages

| Package | What it gives you |
|---------|-------------------|
| [`ci-status`](./ci-status) | `/ci`, `/ci-detail`, `/ci-logs` commands, CI auto-watch after pushes, status-line widget, GitHub Actions + CircleCI support, and `get_ci_status` / `ci_fetch_job_logs` LLM tools |
| [`dev-workflow`](./dev-workflow) | 15 core workflow prompts (`/workflow:help`, `/workflow:run`, `/workflow:prompts`, `/workflow:flow`), CI analysis, PR review feedback, release PR prep, local skills, and optional pi-subagents chain |
| [`skills-bridge`](./skills-bridge) | Auto-discovers all 21 Claude Code plugin skills from `plugins/*/skills/` and registers them as pi skills — one install bridges the entire plugin ecosystem into pi |

## Install

### One command for everything (recommended)

```bash
pi install git:github.com/DiversioTeam/agent-skills-marketplace
```

The root `package.json` at the top of this repo tells pi where to find every
package, so one clone discovers all three. Run `/reload` after installing.

To pull the latest updates later:

```bash
pi update --extensions
```

This does a `git pull` on the cloned repo and reloads all extensions and skills.
Versions are not pinned, so `pi update --extensions` always fetches the latest
`main`.

### One package at a time (local dev)

From a checkout of this repo:

```bash
pi install "$PWD/pi-packages/ci-status"
pi install "$PWD/pi-packages/dev-workflow"
pi install "$PWD/pi-packages/skills-bridge"
```

Use `pi -e ./pi-packages/<pkg>` to test a package without writing to settings.

### Duplicate warning

Install each package in one scope. If the same package is installed from two
different local paths (e.g. two worktrees), pi loads both copies and you get
duplicate extensions. Remove the old entry from `~/.pi/agent/settings.json`
first, or switch to the git-based install which avoids this entirely.

## Structure

```
pi-packages/
├── README.md                 ← this file
├── ci-status/
│   ├── package.json
│   ├── README.md
│   └── extensions/
├── dev-workflow/
│   ├── package.json
│   ├── README.md
│   ├── extensions/
│   ├── skills/
│   └── agents/
└── skills-bridge/
    ├── package.json
    ├── README.md
    └── extensions/
```

Each subdirectory is a standalone pi package with its own `package.json` and
README. The root `package.json` at the repo top references them so pi can
discover everything from a single `git:` install.

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full guide. Key rules:

- Keep each package's `package.json`, `README.md`, and version in sync.
- **When adding or removing a package**, update the root `package.json`
  `pi.extensions` and `pi.skills` arrays so the git-based install stays accurate.
- Use `pi -e ./pi-packages/<pkg>` for local smoke tests.
- Bump the package version when publishing an update.

## More

- [Root README](../README.md) — full repo overview and plugin catalog
- [Distribution runbook](../docs/runbooks/distribution.md) — install, uninstall, and migration guides
