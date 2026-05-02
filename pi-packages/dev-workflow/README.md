# dev-workflow

Daily developer workflow for pi: plan review, self-review, standards, CI, documentation, PR review feedback, release PR prep, handoff, and shipping. Ships `15` core workflow prompts plus `/workflow:help`, `/workflow:flow`, `/workflow:run`, and `/workflow:prompts`, with XDG/project prompt customization.

## Install

For normal use, install globally from a checkout of this repo. Use `$PWD` so Pi
registers the checkout you intend in user settings.

```bash
# From the agent-skills-marketplace repo root
pi install "$PWD/pi-packages/dev-workflow"

# From the Diversio monolith root
pi install "$PWD/agent-skills-marketplace/pi-packages/dev-workflow"
```

Plain `pi install` writes to global user settings. Then restart pi or run
`/reload` in any pi session.

Install `dev-workflow` in one scope at a time. Use `-l` only when testing the
package project-locally as a developer.

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

### Default cmux behavior for subagent-style workflow commands

When Pi is running **inside cmux**, these subagent-style commands default to a
**fresh split pane** with a seeded child session when they are run directly from
an **idle** parent session:

- `/workflow:scout`
- `/workflow:oracle`
- `/workflow:reviewer`
- `/workflow:parallel`

Why:

- reduce developer overhead — no extra `omp-*` command to remember
- keep the parent workflow lane uncluttered
- preserve a focused adjacent lane for review / recon work

Mental model:

```text
/workflow:reviewer
  ├─ inside cmux + idle parent session -> open seeded split -> run reviewer prompt there
  └─ otherwise                         -> run inline in current session
```

Queued / follow-up flows keep their normal current-session behavior instead of
unexpectedly opening a split later.

If the split launch fails for any reason, the command falls back inline instead
of failing outright.

If `pi-subagents` is installed, the child session can still use the `subagent`
tool from inside that split. So cmux handles **surface separation**, while
`pi-subagents` still handles **agent isolation**.

### What gets seeded into the child lane

The new split is not a blank Pi session.

It starts with a small, focused handoff message that includes:

- the same working directory
- the current git branch
- a short `git status --short` snapshot
- a small recent conversation snapshot from the parent workflow lane
- any extra text you passed to the workflow command
- the parent session's selected model when available

Mental model:

```text
Parent workflow lane
  ├─ /workflow:reviewer focus on API error handling
  └─ New cmux split
       ├─ same repo + cwd
       ├─ seeded child session on disk
       ├─ recent parent context
       └─ reviewer prompt runs there
```

### Why this logic lives inside dev-workflow

You might reasonably ask:

> "Why not force users to run an explicit `/omp-*` command first?"

Because that adds memory burden.

The goal here is:

```text
I want review / recon help
  -> run /workflow:reviewer
  -> get the right lane automatically when cmux can help
```

`oh-my-pi` is still the **explicit user-facing cmux command surface** for people
who want manual control.

`dev-workflow` duplicates a tiny amount of cmux-launch logic on purpose so it:

- works even when installed by itself
- does not require users to remember a second command
- keeps the common workflow as one obvious action

### Examples

```text
/workflow:reviewer
/workflow:reviewer focus on API error handling
/workflow:oracle is this migration rollout safe?
/workflow:parallel only review backend changes
```

Force inline behavior even inside cmux:

```bash
PI_WORKFLOW_CMUX_MODE=inline pi --no-extensions -e ./pi-packages/dev-workflow
```

Prefer a down split instead of a right split:

```bash
PI_WORKFLOW_CMUX_SPLIT_DIRECTION=down pi --no-extensions -e ./pi-packages/dev-workflow
```

### Navigation and prompt registry
| Command / Shortcut | Does |
|---|---|
| `/workflow:help` or `Ctrl+Shift+/` | Interactive TUI prompt browser — browse, run, queue, edit |
| `/workflow:flow` | Text overview of the full workflow |
| `/workflow:run <code>` | Run a core, project, or user prompt by stable code |
| `/workflow:prompts` or `/workflow:prompts studio` | Open native TUI Prompt Studio for adding user prompts or overriding core prompts |
| `/workflow:prompts add` | Open a field-based form to add/update a `user.*` prompt |
| `/workflow:prompts override [workflow.code]` | Pick or directly override a core `workflow.*` prompt with a field-based form |
| `/workflow:prompts delete [code]` | Delete a user prompt, remove a user override, or hide a project prompt after confirmation |
| `/workflow:prompts restore [code]` | Restore a prompt hidden by a user-level disabled override |
| `/workflow:prompts list` | List loaded prompts with source labels and hidden prompts |
| `/workflow:prompts paths` | Show project/user/legacy config paths |
| `/workflow:prompts validate` | Validate prompt config and show warnings |
| `/workflow:prompts init` | Create a starter user config |
| `/workflow:prompts reload` | Reload prompt config for dynamic help/run usage |

## Help panel

`/workflow:help` opens a tabbed TUI panel:

- **↑↓** navigate prompts · **←→/Tab** switch tabs
- **↵** run prompt · configured **`app.message.followUp`** key (default Alt+Enter / Option+Enter) queues the selected prompt · **d** details
- **e** edits the prompt before running on core tabs, but edits the saved prompt/config on the **CUSTOM** tab
- **n** adds a user prompt · **o** overrides the selected prompt · **x** deletes/hides a custom prompt after confirmation
- In edit mode: **Ctrl+Y** copy, configured **`app.message.followUp`** queues the edited prompt, configured `tui.input.newLine` inserts a newline, **Esc** close/back

Rows show source labels such as `[core]`, `[project]`, `[user]`, `[override:project]`, and `[override:user]`.

Prompt Studio uses native Pi TUI forms: short metadata fields are single-line inputs, while the prompt body opens a multi-line editor so prompts can be formatted with readable sections and newlines. The form validates before saving, including required fields, `user.*` code format, and duplicate code collisions. Renaming a user prompt removes the old code entry instead of leaving a duplicate. Deletion is confirmed before writing: user prompts are removed from user config, user overrides are removed, and project prompts are hidden through a user-level disabled override rather than mutating project config. Hidden prompts remain discoverable through `/workflow:prompts list` and can be restored with `/workflow:prompts restore <code>`.

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

## Contributing And Local Testing

Use `-e` for one-off extension testing while actively editing this package. It
loads the package for the current Pi run without changing global or project
settings:

```bash
# From the agent-skills-marketplace repo root
pi --no-extensions -e ./pi-packages/dev-workflow
```

Use a project-local install only when you need to test `.pi/settings.json`,
`/reload`, or persistence behavior:

```bash
# From the agent-skills-marketplace repo root
pi install -l ./pi-packages/dev-workflow
```

Run these checks before opening a PR:

```bash
jq -e . pi-packages/dev-workflow/package.json >/dev/null

(cd pi-packages/dev-workflow && npm pack --dry-run --json >/tmp/dev-workflow-pack.json)

printf '{"id":"cmds","type":"get_commands"}\n' | \
  PI_OFFLINE=1 pi --mode rpc --no-session --no-context-files \
    --no-extensions -e ./pi-packages/dev-workflow \
    --no-prompt-templates --no-skills >/tmp/dev-workflow-commands.json

jq -e '.success == true' /tmp/dev-workflow-commands.json >/dev/null
```

After changing commands, tools, shortcuts, prompt inventory, skills, chain
files, or package resources, update this README plus the top-level `README.md`,
`docs/runbooks/distribution.md`, and `docs/plugins/catalog.md`.

## Configuration

Optional environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `PI_WORKFLOW_CMUX_MODE` | `auto` | `auto` = subagent-style workflow commands prefer a seeded cmux split when available; `inline` = always stay in the current session |
| `PI_WORKFLOW_CMUX_SPLIT_DIRECTION` | `right` | Split direction for subagent-style workflow commands: `right` or `down` |

## Requirements

- pi >= 1.0.0
- Recommended: install the separate `ci-status` package for `/ci`, `/ci-detail`, and `/ci-logs`:

  ```bash
  pi install "$PWD/pi-packages/ci-status"
  ```

  Use the same install scope you use for other pi packages. Do not install
  `ci-status` both globally and from a different project-local path; duplicated
  CI tools can conflict.

Subagent commands can use [pi-subagents](https://github.com/nicobailon/pi-subagents) for true agent isolation. When Pi is inside cmux, the default workflow behavior is to open a seeded split for subagent-style prompts; inside that split, the prompt still asks the AI to use the `subagent` tool when available and to fall back gracefully when it is not. CI prompts prefer the `ci-status` package when installed and only fall back to `get_ci_status` / `ci_fetch_job_logs` when the current harness exposes those tools.
