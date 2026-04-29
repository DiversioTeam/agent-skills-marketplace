# dev-workflow

Daily developer workflow for pi: multi-pass plan review, self-review, standards, CI, documentation, handoff, and shipping. 13 workflow commands plus `/review:help` and `/review:flow`, with an interactive TUI help panel. Inspired by the [AI Review Workflow](https://heroic-tiramisu-9a5057.netlify.app/).

## Install

```bash
# From the agent-skills-marketplace repo root, project-level (writes to .pi/settings.json)
pi install -l ./pi-packages/dev-workflow

# From the Diversio monolith root
pi install -l ./agent-skills-marketplace/pi-packages/dev-workflow

# Personal/global install from a local checkout
pi install /path/to/agent-skills-marketplace/pi-packages/dev-workflow

# If this package is later split into its own repo
pi install git:github.com/DiversioTeam/dev-workflow
```

Then `/reload` in any pi session.

## Commands

### Core workflow
| Command | Step | Does |
|---|---|---|
| `/review:plan` | 1 | Fresh-eyes review of the plan before implementing |
| `/review:self` | 3 | Implementor rereads own code with fresh eyes |
| `/review:standards` | 4 | Coding standards pass (lint, types, ORM, imports, Ruff) |
| `/review:ci` | 5 | CI check — `/ci`, `/ci-detail`, logs, ours-vs-flake analysis |
| `/review:docs` | 7 | Documentation pass — explain the *why* |
| `/review:ship` | 8 | Smart ship — verify CI green, discover PR context, atomic commit, open PR |

### Session bootstrap & handoff
| Command | Does |
|---|---|
| `/review:context` | Load context from existing PRs (local or remote), deep-read diff |
| `/review:handoff` | Generate handoff message for new engineer or fresh subagent |
| `/review:onboard` | Generate onboarding message for engineers |

### Subagent-enhanced (pi-subagents recommended)
| Command | Agent | Does |
|---|---|---|
| `/review:scout` | `scout` | Codebase recon — files, data flow, risks |
| `/review:oracle` | `oracle` | Second opinion — challenge assumptions, no editing |
| `/review:reviewer` | `reviewer` | Independent review with forked context |
| `/review:parallel` | 3× `reviewer` | Parallel reviews (correctness, tests, complexity) |

### Navigation
| Command / Shortcut | Does |
|---|---|
| `/review:help` or `Ctrl+Shift+/` | Interactive TUI help panel — browse, learn, inject, edit |
| `/review:flow` | Text overview of the full workflow |

## Help panel

`/review:help` opens a tabbed TUI panel:

- **↑↓** navigate commands · **←→/Tab** switch tabs
- **↵** inject command · configured **`app.message.followUp`** key (default Alt+Enter / Option+Enter) queues the selected command · **d** details · **e** edit
- In edit mode: **Ctrl+Y** copy, configured **`app.message.followUp`** queues the edited prompt, configured `tui.input.newLine` inserts a newline, **Esc** close/back

Works without pi-subagents — subagent commands gracefully fall back to inline execution. The footer renders the resolved Pi keybinding so custom keybindings are shown instead of assuming the default.

## Subagent chain

The optional review pipeline chain is bundled at `agents/review-pipeline.chain.md`.
If your `pi-subagents` setup only scans `.pi/agents/`, copy it there after install:

```bash
mkdir -p .pi/agents
cp pi-packages/dev-workflow/agents/review-pipeline.chain.md .pi/agents/review-pipeline.chain.md
```

## Customization

Edit the `PROMPTS` object in `extensions/ai-review-workflow/index.ts` to adjust the verbatim prompts for your team's standards, coding conventions, and PR workflow.

## Requirements

- pi >= 1.0.0
- Recommended: install the separate `ci-status` package for `/ci`, `/ci-detail`, and `/ci-logs`:

  ```bash
  # From the agent-skills-marketplace repo root
  pi install -l ./pi-packages/ci-status
  ```

Subagent commands require [pi-subagents](https://github.com/nicobailon/pi-subagents) for true agent isolation; they fall back to inline execution without it. CI prompts prefer the `ci-status` package when installed and only fall back to `get_ci_status` / `ci_fetch_job_logs` when the current harness exposes those tools.
