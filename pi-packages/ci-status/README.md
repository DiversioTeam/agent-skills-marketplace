# ci-status

Pi extension for checking CI from inside pi. It currently fetches GitHub Actions and CircleCI, renders a compact widget/status line, provides an interactive TUI detail view grouped by CI provider and workflow/cycle, fetches failure logs, and auto-watches after `git push`.

## Install

For normal use, install globally from a checkout of this repo. Use `$PWD` so Pi
registers the checkout you intend in user settings.

```bash
# From the agent-skills-marketplace repo root
pi install "$PWD/pi-packages/ci-status"

# From the Diversio monolith root
pi install "$PWD/agent-skills-marketplace/pi-packages/ci-status"
```

Plain `pi install` writes to global user settings. Then restart pi or run
`/reload` in an existing pi session.

Install `ci-status` in one scope at a time. If it is installed globally and
also from a different project-local path, Pi can load both copies and duplicate
`get_ci_status` / `ci_fetch_job_logs` tool registration. Remove the duplicate
project package entry from `.pi/settings.json` or uninstall the global copy
before `/reload`.

## Contributing And Local Testing

Use `-e` for one-off extension testing while actively editing this package. It
loads the package for the current Pi run without changing global or project
settings:

```bash
# From the agent-skills-marketplace repo root
pi -e ./pi-packages/ci-status
```

Use a project-local install only when you need to test `.pi/settings.json`,
`/reload`, or persistence behavior:

```bash
# From the agent-skills-marketplace repo root
pi install -l ./pi-packages/ci-status
```

Run these checks before opening a PR:

```bash
jq -e . pi-packages/ci-status/package.json >/dev/null

(cd pi-packages/ci-status && npm pack --dry-run --json >/tmp/ci-status-pack.json)

printf '{"id":"cmds","type":"get_commands"}\n' | \
  PI_OFFLINE=1 pi --mode rpc --no-session --no-context-files \
    --no-extensions -e ./pi-packages/ci-status \
    --no-prompt-templates --no-skills >/tmp/ci-status-commands.json

jq -e '.success == true' /tmp/ci-status-commands.json >/dev/null
```

After changing commands, tools, shortcuts, or package resources, update this
README plus the top-level `README.md`, `docs/runbooks/distribution.md`, and
`docs/plugins/catalog.md`.

## Commands

| Command | Does |
|---|---|
| `/ci` | Fetch and render CI status for the current branch/PR in the widget area |
| `/ci-detail` or `Ctrl+Shift+.` | Open interactive TUI detail view grouped by CI provider and workflow/cycle, automatic focus on the most important CI/cycle, sorted job list, details, log access, selected failed-job rerun, guided fix prompts, browser open, and copy URL |
| `/ci-logs <job>` | Fetch and display logs for a job by name or id |
| `/ci-refresh` | Force-refresh CI status |
| `/ci-watch` | Watch CI status and notify when failures/recoveries occur |
| `/ci-unwatch` | Stop watching CI status |
| `/ci-clear` | Clear the CI widget/status from the UI |

## LLM tools

The extension also registers tools the AI can use directly:

| Tool | Does |
|---|---|
| `get_ci_status` | Fetch latest CI status for the current branch/PR with per-job IDs, URLs, durations, and provider metadata |
| `ci_fetch_job_logs` | Fetch failure logs for a specific job using `jobId`, GitHub `runId`, or CircleCI `jobNumber` |

These tools are the fallback used by `/review:ci` when the interactive slash commands are not available.

## Environment

- `gh` CLI must be installed and authenticated for GitHub Actions/PR lookup.
- Set `CIRCLECI_TOKEN` to enrich CircleCI checks with workflow/job details.
- Set `PI_CI_AUTO_WATCH=0` to disable automatic startup watch.
- Set `PI_CI_SHOW_WIDGET_ON_START=1` to show the CI widget immediately on startup.
- Set `PI_CI_DETAIL_SHORTCUT` to override the `/ci-detail` shortcut, default `ctrl+shift+.`.

## UI shortcuts

From the main pi UI:

- `Ctrl+Shift+.` opens `/ci-detail`.

Inside `/ci-detail`:

- `?` / `h` open help
- `Tab` / `←→` switch between CI providers
- `[` / `]` switch workflow/cycle inside the active CI
- `p` pick a CI provider with a native Pi selector
- `w` pick a workflow/cycle with a native Pi selector
- `R` refresh CI status in place while preserving selection when possible
- `a` toggle important-only vs all jobs in the active cycle
- `↑↓` navigate jobs/logs
- `Enter` open job detail or fetch logs in detail view
- `r` fetch logs for selected job
- `f` jump to the first error-like log line after logs are loaded
- `F` start a guided fix flow for the selected job: pick a model, review a context-rich prompt, press `e` to edit, `Enter` to run, or the configured `app.message.followUp` key to queue
- `x` rerun the selected failed job one-by-one (`gh run rerun --job <job-id>` for GitHub Actions; CircleCI reruns require enriched workflow data and `CIRCLECI_TOKEN`)
- `l` open the selected job URL in browser
- `c` copy the selected job URL; the view shows the exact copy target
- `g` jump to first failing job, switching CI/cycle if needed
- `Esc` close/back

Focus defaults to the highest-priority CI and cycle. For example, if CircleCI failed while GitHub Actions passed, `/ci-detail` opens with CircleCI focused and the failing CircleCI cycle selected. The UI is data-driven so additional CI providers or multiple cycles within one CI can be navigated the same way.

Set `PI_CI_ASCII=1` before launching pi for emoji-free status labels.
