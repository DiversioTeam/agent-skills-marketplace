# ci-status

Pi extension for checking CI from inside pi. It fetches GitHub Actions, CircleCI, and published commit statuses (including local-ci), renders a compact widget/status line, provides an interactive TUI detail view grouped by CI provider and workflow/cycle, fetches failure logs, and auto-watches after `git push`.

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

Use `--no-extensions -e` for one-off extension testing while actively editing
this package from the repo root. That loads only this package for the current
Pi run without changing global or project settings, and avoids loading a second
copy from the root marketplace manifest:

```bash
# From the agent-skills-marketplace repo root
pi --no-extensions -e ./pi-packages/ci-status
```

Use a project-local install only when you need to test `.pi/settings.json`,
`/reload`, or persistence behavior:

```bash
# From the agent-skills-marketplace repo root
pi install -l ./pi-packages/ci-status
```

Run these checks before opening a PR:

```bash
# Node 24 built-ins; SDK/network/shell seams are mocked. No peer install needed.
pnpm --config.verify-deps-before-run=false --dir pi-packages/ci-status test
jq -e . pi-packages/ci-status/package.json >/dev/null

pnpm --config.verify-deps-before-run=false --dir pi-packages/ci-status pack --dry-run --json >/tmp/ci-status-pack.json

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

These tools are the fallback used by the workflow CI skill when interactive
slash commands are not available.

## Scope And Log Identity

- Status is for the current checkout's GitHub `origin`, branch, and commit SHA.
  PR rollups are used only for an open PR at that exact branch/head. Closed,
  merged, or different-head PRs cannot replace the checkout SHA; the extension
  reports the mismatch and queries Actions runs plus paginated commit statuses
  for the local commit instead. Unpushed
  commits may correctly have no remote checks yet.
- `/ci-logs` and `ci_fetch_job_logs` fetch a fresh summary rather than reusing a
  display snapshot from another repository, branch, or earlier commit. TUI
  log/fix/rerun actions use the displayed snapshot's repository/SHA; refresh
  that view before selecting newer runs.
- Prefer a full job ID from `get_ci_status`. Supplied `jobId`, `runId`, and
  `jobNumber` are constraints, not fallback choices. Conflicting identifiers
  fail; names or partial queries must match exactly one job. A `runId` with
  several jobs returns the candidate IDs instead of selecting the first job.
  Run-only queries and names paired with `runId` inspect the full run inventory,
  not just the PR rollup.
- Explicit GitHub run IDs can be inspected even when absent from the rollup,
  but must match the checkout SHA. A `github-job:<id>` queries that exact job
  directly, including earlier attempts missing from the latest inventory; any
  supplied `runId` must match it. Runs with no jobs report unavailable logs; a
  workflow may have failed validation before any job could produce output.
- GitHub job IDs from URLs take precedence over names. Their actual repository,
  run, and commit are checked before fetching output, including older attempts.
  Name-only ambiguity also blocks the shared selected-job rerun helper rather
  than guessing a failed sibling. Workflow-name prefixes and similar run names
  are not job identity. Non-Actions URLs cannot borrow an Actions run, and CLI
  diagnostics are not returned as console output. Late log responses do not
  redraw a closed detail view. This does not add automatic reruns or deploys.

## local-ci Compatibility

`local-ci` owns **execution and publication**; this extension only reads results.
Its v0.1.0-compatible inspection commands provide native `runs`, `show`, and
`logs`. Runner v0.2.0 adds [v1 publication receipts](https://github.com/DiversioTeam/local-ci-runner/blob/v0.2.0/cmd/local-ci/MANUAL.md#81-publication-receipts-binary-contract)
to runner events; ci-status 0.1.1 recognizes those records without a version
probe or a new command.

- Published `StatusContext` entries remain commit statuses, never guessed
  Actions jobs—even if their target URL resembles an Actions URL. This also
  preserves the backend's legacy `Fast Checks / Checks (Fast)` context.
- `local:` / `local/` contexts and the native aggregate's `local verification …`
  descriptions identify local-ci. Other contexts retain the generic **Commit
  statuses** label; custom step ownership is not guessed from a name.
- When `.local-ci.toml` exists, the extension reads commit-status descriptions
  directly (the PR rollup omits them). A missing recognizable local-ci aggregate
  is **unknown**, even if safety workflows or individual local steps passed.
  Lookup failures are incomplete results, not all-green notifications or TUI
  guidance. This is not a branch-protection/config/required-gate validator.
- Published local-ci statuses carry **no run ID or log URL**. The extension
  cannot prove which local artifact produced one and will not choose a run by
  timestamp, SHA alone, or similar step name. An observed aggregate is not a
  runner receipt. Status discovery does not scan local runs, and historical
  receipts never change the CI widget, all-green logic, or live status results.

Find an explicit run and step using read-only native commands:

```bash
local-ci runs --json
local-ci show 20260627T150405Z-deadbeef --json
```

Then use `/ci-logs local-ci:20260627T150405Z-deadbeef:checks-fast` or:

```json
{"jobId":"local-ci:20260627T150405Z-deadbeef:checks-fast"}
```

Omit `:<step-id>` for **runner events and historical publication evidence**,
not a guessed step. The same output is available through `/ci-logs` and
`ci_fetch_job_logs`:

```text
/ci-logs local-ci:20260627T150405Z-deadbeef
```

- Only exactly one requested/posted pair with matching attempt ID, run, target
  repo/SHA, context, source, step, and status establishes an **acknowledgement**.
  Sequence order must agree; timestamps are validated, not used for matching.
- Execution (including resume) and explicit publish receipts are supported.
  Every retry keeps its own ID. A later unknown attempt does not erase an older
  acknowledgement or become associated with it.
- Missing outcomes, reporter errors, duplicate/conflicting records, malformed
  fields, unsupported versions, and legacy events remain **unknown**. Empty
  events do not prove that nothing was posted. Unknown additive fields are
  ignored; the full native event array is assessed before output truncation.
- Acknowledged `failure`/`error` means that status was posted, not that checks
  passed. Acknowledged `pending` does not mean checks completed. Other targets
  are labeled historical evidence for a **different target**, never the selected
  commit. Original snapshot metadata is preserved, including dirty-run provenance.
- Receipts are local records, not signed attestations. They prove neither
  current GitHub status, complete required-context publication, latest resumed
  coverage, current worktree/config/plan validity, nor deployment permission.
- Step-log queries remain unchanged and do **not** additionally fetch receipts.
  Raw runner events remain below the evidence summary, within the existing
  500-line limit. Use native runner logs for the full output.

Do not combine local IDs with GitHub `runId` or CircleCI `jobNumber`. Native
`show --json` and `logs --step … --combined --json` perform the reads; there is
no second artifact parser or planner execution. Use native `--planner` directly
for planner logs.

The run must belong to this checkout/repository. Its stored tree must match the
selected commit, or it must be an explicitly labeled dirty snapshot based on
that commit. Original HEAD, dirty flag, and stored tree remain visible. This
also permits inspecting a dirty run after committing its exact tree, **without
claiming publication**. Current working-tree contents and config/plan validity
are not inferred; use the repo-owned validation workflow for those guarantees.
Missing CLI/artifacts, mismatched identities, and unknown steps fail explicitly.

Neither log lookup nor the selected-job rerun action starts, resumes, or
publishes local-ci. Logs are not authorization for validation, publishing,
merged-head deployment, or branch synchronization. Published statuses work
without the local binary; native log inspection requires a v0.1.0-compatible
`local-ci` on PATH and artifacts in this checkout.

## CircleCI Console Output

CircleCI Cloud GitHub projects use the v1.1 build endpoint to obtain step
metadata, then fetch every available action's `output_url` to read console
messages (including parallel actions). This follows CircleCI's
[step-output guide](https://github.com/circleci/circleci-docs/blob/main/docs/guides/modules/orchestrate/pages/analyze-pipelines-during-an-incident.adoc).
The selected job's revision must match the CI snapshot.

The API token is sent only to `circleci.com`. Presigned output URLs receive no
authentication headers, must use HTTPS without embedded user credentials, and
are never printed in errors. Localhost names and all IP-literal output URLs
are refused. Native HTTPS connections validate every DNS answer against
non-public/special-use address ranges, then connect using those same answers
(no second lookup). Mixed public/private answers are rejected. Redirects are
not followed; fresh direct connections avoid pooled sockets and proxy-side DNS.
This requires direct public-network access; private proxies and IPv6 transition
addresses are not supported for log downloads. Use the provider UI instead.

The v1.1 metadata and output downloads share a 30-second deadline; preceding v2 status requests each
have their own timeout. Missing auth, unsupported/unavailable API
responses, missing output, expired URLs, and malformed output are errors—not
job metadata presented as logs. Use the job page in status details when API
output is unavailable.

Output is buffered and limited to the first 500 lines with a truncation notice;
very large logs may need the provider UI instead. Console text remains untrusted
job output and can contain secrets printed by the job; do not publish it blindly.

**Upgrade from 0.0.1:** commands and tool parameters are unchanged. Ambiguous
selectors now fail explicitly, log lookups refresh their scope, and CircleCI
log requests perform actual read-only API/output requests instead of returning
metadata. No user settings or credentials are rewritten.

## Environment

- `gh` CLI must be installed and authenticated for GitHub Actions/PR/status lookup,
  including support for `gh api --paginate --slurp`.
- `local-ci` is optional for published statuses and required only for native log reads.
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
- `x` rerun the selected failed job one-by-one (`gh run rerun --job <job-id>` for GitHub Actions; CircleCI reruns require enriched workflow data and `CIRCLECI_TOKEN`). Commit statuses/local-ci are not rerun by this action.
- `l` open the selected job URL in browser
- `c` copy the selected job URL; the view shows the exact copy target
- `g` jump to first failing job, switching CI/cycle if needed
- `Esc` close/back

Focus defaults to the highest-priority CI and cycle. For example, if CircleCI failed while GitHub Actions passed, `/ci-detail` opens with CircleCI focused and the failing CircleCI cycle selected. The UI is data-driven so additional CI providers or multiple cycles within one CI can be navigated the same way.

Set `PI_CI_ASCII=1` before launching pi for emoji-free status labels.
