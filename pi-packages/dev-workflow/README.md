# dev-workflow

Daily developer workflow for pi: plan review, self-review, standards, CI, documentation, PR review feedback, release PR prep, handoff, and shipping. Ships `15` core workflow prompts plus `/workflow:help`, `/workflow:flow`, `/workflow:run`, and `/workflow:prompts`, with XDG/project prompt customization.

## Install

```bash
# From the agent-skills-marketplace repo root, project-level (writes to .pi/settings.json)
pi install -l ./pi-packages/dev-workflow

# From the Diversio monolith root
pi install -l ./agent-skills-marketplace/pi-packages/dev-workflow

# Personal/global install from a local checkout
pi install /path/to/agent-skills-marketplace/pi-packages/dev-workflow
```

Then `/reload` in any pi session.

## Commands

### Core workflow
| Command | Code | Does |
|---|---|---|
| `/workflow:plan` | `workflow.plan` | Fresh-eyes review of the plan before implementing |
| `/workflow:self` | `workflow.self` | Implementor rereads own code with fresh eyes |
| `/workflow:standards` | `workflow.standards` | Coding standards pass (lint, types, ORM, imports, Ruff) |
| `/workflow:ci` | `workflow.ci` | CI check — `/ci`, `/ci-detail`, logs, ours-vs-flake analysis |
| `/workflow:docs` | `workflow.docs` | Documentation pass — explain the *why* |
| `/workflow:ship` | `workflow.ship` | Smart ship — verify CI, atomic commit, PR description, open/update PR |
| `/workflow:pr-review-comments` | `workflow.pr-review-comments` | Address PR review comments, validate, push, resolve threads, re-request review |
| `/workflow:release-prs` | `workflow.release-prs` | Prepare backend/frontend/optimo-frontend/design-system release PRs |

### Session bootstrap & handoff
| Command | Code | Does |
|---|---|---|
| `/workflow:context` | `workflow.context` | Load context from existing PRs (local or remote), deep-read diff |
| `/workflow:handoff` | `workflow.handoff` | Generate handoff message for new engineer or fresh subagent |
| `/workflow:onboard` | `workflow.onboard` | Generate onboarding message for engineers |

### Subagent-enhanced (pi-subagents recommended)
| Command | Code | Agent | Does |
|---|---|---|---|
| `/workflow:scout` | `workflow.scout` | `scout` | Codebase recon — files, data flow, risks |
| `/workflow:oracle` | `workflow.oracle` | `oracle` | Second opinion — challenge assumptions, no editing |
| `/workflow:reviewer` | `workflow.reviewer` | `reviewer` | Independent review with forked context |
| `/workflow:parallel` | `workflow.parallel` | 3× `reviewer` | Parallel reviews (correctness, tests, complexity) |

### Navigation and prompt registry
| Command / Shortcut | Does |
|---|---|
| `/workflow:help` or `Ctrl+Shift+/` | Interactive TUI prompt browser — browse, run, queue, edit |
| `/workflow:flow` | Text overview of the full workflow |
| `/workflow:run <code>` | Run a core, project, or user prompt by stable code |
| `/workflow:prompts` or `/workflow:prompts studio` | Open native TUI Prompt Studio for adding user prompts or overriding core prompts |
| `/workflow:prompts add` | Open a field-based form to add/update a `user.*` prompt |
| `/workflow:prompts override [workflow.code]` | Pick or directly override a core `workflow.*` prompt with a field-based form |
| `/workflow:prompts list` | List loaded prompts with source labels |
| `/workflow:prompts paths` | Show project/user/legacy config paths |
| `/workflow:prompts validate` | Validate prompt config and show warnings |
| `/workflow:prompts init` | Create a starter user config |
| `/workflow:prompts reload` | Reload prompt config for dynamic help/run usage |

## Help panel

`/workflow:help` opens a tabbed TUI panel:

- **↑↓** navigate prompts · **←→/Tab** switch tabs
- **↵** run prompt · configured **`app.message.followUp`** key (default Alt+Enter / Option+Enter) queues the selected prompt · **d** details
- **e** edits the prompt before running on core tabs, but edits the saved prompt/config on the **CUSTOM** tab
- **n** adds a user prompt · **o** overrides the selected prompt
- In edit mode: **Ctrl+Y** copy, configured **`app.message.followUp`** queues the edited prompt, configured `tui.input.newLine` inserts a newline, **Esc** close/back

Rows show source labels such as `[core]`, `[project]`, `[user]`, `[override:project]`, and `[override:user]`.

Prompt Studio uses native Pi TUI forms: short metadata fields are single-line inputs, while the prompt body opens a multi-line editor so prompts can be formatted with readable sections and newlines. The form validates before saving, including required fields, `user.*` code format, and duplicate code collisions.

## Prompt customization

Core prompts are bundled in the extension. Add project or user prompts using JSON config:

```text
project: <git-root>/.pi/dev-workflow/prompts.json
user:    ${XDG_CONFIG_HOME:-~/.config}/pi/dev-workflow/prompts.json
legacy:  ~/.pi/agent/dev-workflow/prompts.json
```

Create a starter config:

```text
/workflow:prompts init
```

Example:

```json
{
  "version": 1,
  "overrides": {
    "workflow.standards": {
      "append": "Also check for missing database indexes and unsafe queryset patterns."
    }
  },
  "prompts": [
    {
      "code": "user.backend-migrations",
      "label": "Backend migration safety",
      "short": "Review migrations for deploy and rollback risk",
      "category": "user",
      "prompt": "Review migration files in this branch for lock risk, rollback safety, data migration risk, and deploy ordering."
    }
  ]
}
```

Rules:
- user prompt codes must start with `user.`
- project prompt codes must start with `project.`
- core prompts use reserved `workflow.*` codes
- invalid config warns and falls back to valid prompts instead of crashing pi
- custom prompts are immediately usable via `/workflow:help` and `/workflow:run <code>`
- custom top-level slash command aliases are intentionally not registered dynamically yet

## Subagent chain

The optional workflow pipeline chain is bundled at `agents/workflow-pipeline.chain.md`.
If your `pi-subagents` setup only scans `.pi/agents/`, copy it there after install:

```bash
mkdir -p .pi/agents
cp pi-packages/dev-workflow/agents/workflow-pipeline.chain.md .pi/agents/workflow-pipeline.chain.md
```

Run with:

```text
/run-chain workflow-pipeline -- <task>
```

## Requirements

- pi >= 1.0.0
- Recommended: install the separate `ci-status` package for `/ci`, `/ci-detail`, and `/ci-logs`:

  ```bash
  pi install -l ./pi-packages/ci-status
  ```

Subagent commands require [pi-subagents](https://github.com/nicobailon/pi-subagents) for true agent isolation; they fall back to inline execution without it. CI prompts prefer the `ci-status` package when installed and only fall back to `get_ci_status` / `ci_fetch_job_logs` when the current harness exposes those tools.
