# oh-my-pi

Pi-native cmux integration package. Provides cmux notifications, split panes, and
workspace tabs via the native cmux CLI — no tmux-compat shims, no OMC/OMX/OMO
dependency.

## Why this package exists

Diversio uses **Pi inside cmux** all day.

That means we already have two strong systems:

- **Pi** knows when the agent starts, reads files, changes code, fails, and waits.
- **cmux** knows how to open panes, create workspace tabs, track unread state,
  and show native notifications.

So the simplest good solution is:

```text
Pi lifecycle events  ──► summarize what happened ──► cmux native UX
```

We intentionally do **not** emulate tmux, fake notifications with OSC escape
sequences, or add runtime-heavy dependencies. We use the cmux features that
already exist.

## Mental model

```text
@diversioteam/pi-cmux
  ├─ knows how to talk to cmux safely
  ├─ builds shell / Pi launch commands
  ├─ opens splits and workspace tabs
  └─ provides the low-level notify primitive

cmux-notify.ts
  ├─ listens to Pi events
  ├─ collects simple facts during a run
  └─ sends one useful notification at the end

cmux-split.ts
  └─ exposes readable /omp-split-* commands (+ short aliases)

cmux-workspace.ts
  └─ exposes readable /omp-workspace* commands (+ short aliases)
```

## How this relates to dev-workflow

`oh-my-pi` is the **explicit** cmux command surface.

### Why `@diversioteam/pi-cmux` exists

This package used to carry all of the low-level cmux mechanics itself.

That worked until the same mechanics also existed somewhere else.

From first principles, split launching is exactly the kind of code that should
have one shared implementation:

```text
open pane
  -> build command string
  -> preserve PATH
  -> start Pi or a shell command
  -> keep the pane readable if startup fails
```

If two packages each implement that flow, they will eventually diverge.
When they diverge, one package gets the hardening and the other keeps the old
failure mode.

So the new architecture is:

```text
oh-my-pi
  ├─ owns the user-facing slash commands
  └─ delegates the brittle cmux mechanics to @diversioteam/pi-cmux

@diversioteam/pi-cmux
  ├─ owns split/workspace/notify primitives
  ├─ owns hardened shell and Pi command building
  └─ is shared by oh-my-pi and dev-workflow
```

That separation keeps `oh-my-pi` easier to reason about: command UX lives here,
terminal mechanics live in the shared library.

That means if you want to manually say:

- "open a split to the right"
- "run this shell command in a split"
- "open a named workspace tab"

then `oh-my-pi` is the package that gives you those commands.

`dev-workflow` now also uses cmux automatically for some workflow commands like
`/workflow:reviewer` when Pi is inside cmux and the parent session is idle.

Why not make `dev-workflow` call `/omp-split-right` directly?

Because the packages should stay independently installable.

So the mental model is:

```text
oh-my-pi      -> explicit user-facing cmux commands
              -> /omp-split-*, /omp-workspace*

dev-workflow  -> automatic cmux use when a workflow lane clearly benefits
              -> /workflow:scout, /workflow:oracle, /workflow:reviewer, /workflow:parallel
```

## Quick Install (local test)

Install the package dependency first. If your environment does not already provide GitHub Packages auth for `@diversioteam`, export `NPM_TOKEN` in the current shell first:

```bash
cd /path/to/agent-skills-marketplace/pi-packages/oh-my-pi
npm install
cd ../..
```

Then, from the marketplace root, use `--no-extensions` so the root marketplace
manifest does not load a second copy of `oh-my-pi`:

```bash
cd /path/to/agent-skills-marketplace
pi --no-extensions -e ./pi-packages/oh-my-pi
```

Or with an absolute path:

```bash
pi --no-extensions -e /path/to/pi-packages/oh-my-pi
```

## Commands

All commands use the `omp` prefix to avoid collisions with other cmux
integrations (e.g., pi-cmux).

## Recommended default

For most day-to-day work, **prefer split panes first**.

Why:

- they keep you in the same workspace tab
- they avoid a focus jump
- they are better for short-lived side work
- they feel more like "open a helper lane next to me"

Use **workspace tabs** when you want stronger isolation, a named lane, or a
longer-lived task you plan to come back to later.

```text
Default for quick adjacent work
├─ /omp-split-right
├─ /omp-split-right-command <cmd>
├─ /omp-split-down
└─ /omp-split-down-command <cmd>

Escalate to a workspace tab when the work deserves its own lane
├─ /omp-workspace [--name <title>] [prompt]
└─ /omp-workspace-command [--name <title>] <cmd>
```

### Split Panes

| Canonical command | Alias | Direction | Launches |
|-------------------|-------|-----------|----------|
| `/omp-split-right` | `/ompv` | Right | Fresh Pi session in current cwd |
| `/omp-split-right-command` | `/ompr` | Right | Arbitrary shell command in current cwd |
| `/omp-split-down` | `/omph` | Down | Fresh Pi session in current cwd |
| `/omp-split-down-command` | `/omphr` | Down | Arbitrary shell command in current cwd |

Launch behavior:

- Fresh Pi splits now launch Pi using the same Node/Pi install that is already
  running the current session, instead of trusting the respawned pane's PATH.
  This avoids the classic `command not found: pi` fast-close failure.
- Shell-command splits restore the current session's PATH before running the
  command. That means commands like `npm run dev` or `npm test` can find the
  same tools you have in the current Pi session.
- If a shell command fails immediately, the pane stays open in a shell with the
  error visible so the lane does not blink shut before you can read it.
- Short successful shell commands still exit when they are done. Long-running or
  interactive commands like `top`, `npm run dev`, or `lazygit` naturally stay
  open.

Mental model:

```text
Pi split command
  └─ open a new adjacent AI lane
       └─ same cwd
       └─ same working Pi install
       └─ optional prompt handed to Pi

Shell split command
  └─ open a new adjacent terminal lane
       └─ same cwd
       └─ restored PATH from the current Pi session
       ├─ success + short command -> lane may exit normally
       ├─ success + interactive command -> lane stays open naturally
       └─ failure -> lane stays open so you can debug it
```

Why this design exists:

- a new cmux pane is a weaker environment than the current running Pi session
- reusing the current session's launcher and PATH is more reliable than hoping a
  fresh shell will rebuild them the same way
- the main UX bug we are solving is "pane opens and disappears before I can see
  what went wrong"

Examples:

```text
# Open an adjacent AI lane
/omp-split-right
/omp-split-right fix the user auth module

# Open an adjacent terminal lane that naturally stays open
/omp-split-right-command top
/omp-split-down-command npm run dev
```

Short aliases still work if you prefer them:

```text
/ompv
/ompr top
/omph
/omphr npm run dev
```

A simple rule of thumb:

```text
Want another Pi lane?                -> /omp-split-right or /omp-split-down
Want another terminal program lane?  -> /omp-split-*-command
Want the lane to stay visible?       -> use an interactive or long-running command
```

### Workspace Tabs

Think of workspace tabs as a **stronger boundary** than split panes.

Choose them when you want:

- a named context like `Auth Review` or `Build Watch`
- a longer-running task
- a lane you expect to revisit later
- clearer unread / focus signals from cmux

| Canonical command | Alias | Launches |
|-------------------|-------|----------|
| `/omp-workspace` | `/ompw` | Fresh Pi session in a new workspace tab. Switches focus to the new tab. |
| `/omp-workspace-command` | `/ompwr` | Arbitrary shell command in a new workspace tab. Switches focus to the new tab. |

Both accept an optional `--name <title>` argument. Quote multi-word titles:

```
/omp-workspace --name "Auth Review" review the login flow
/omp-workspace-command --name "Build Watch" npm run dev
```

You can also use ` -- ` to disambiguate an unquoted multi-word title:

```
/omp-workspace --name Auth Review -- review the login flow
/omp-workspace-command --name Build Watch -- npm run dev
```

**Important**: Creating a new workspace tab switches focus to it. There is no
`--no-focus` option in cmux v1. Do not treat workspace creation as a background
operation.

## Notifications

### How the notification system thinks

The package does **not** notify on every tool call.

That would be noisy and hard to trust.

Instead it follows this model:

```text
agent_start
  └─ start collecting facts
       ├─ read files
       ├─ changed files
       ├─ searches
       ├─ shell commands
       └─ first failure

agent_end
  └─ build one summary
       ├─ Waiting
       ├─ Task Complete
       └─ Error
```

This gives the user one answer to the question:

> "What just happened in that Pi run?"

instead of a stream of low-value noise.

Pi sends native cmux notifications at the end of each agent run. Notification
titles include the workspace name for quick context (e.g. `Pi — my-project`).
Bodies show rich activity detail instead of generic messages.

Notifications are classified as:

- **Waiting** — Pi is idle and waiting for input
- **Task Complete** — Pi changed files or the run exceeded the threshold
- **Error** — The agent run ended in an error

### Example notifications

```text
Title:   Pi — agent-skills-marketplace
Sub:     Task Complete
Body:    Changed cmux-notify.ts, README.md · 47s

Title:   Pi — backend
Sub:     Waiting
Body:    Read settings.py, urls.py · 3 searches · 5s

Title:   Pi — frontend
Sub:     Error
Body:    edit failed for App.tsx [2 cmds run]
```

Notifications also appear as in-Pi TUI notifications for immediate visibility.
They are silent when running outside cmux.

## Configuration (environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `PI_CLI_PATH` | auto-detect | Optional absolute path override for the Pi launcher used in spawned cmux panes. Usually unnecessary because `oh-my-pi` reuses the current session's Node/Pi install automatically. |
| `PI_CMUX_NOTIFY_LEVEL` | `all` | `all`, `medium` (skip "Waiting"), `low` (errors only), `disabled` |
| `PI_CMUX_NOTIFY_THRESHOLD_MS` | `15000` | Duration in ms above which a success run becomes "Task Complete" |
| `PI_CMUX_NOTIFY_DEBOUNCE_MS` | `3000` | Minimum ms between duplicate notifications |
| `PI_CMUX_NOTIFY_TITLE` | `Pi` | Notification title shown in the cmux notification panel |

## Architecture

### Why some behavior looks "strict"

A few choices in this package are intentionally conservative:

- **Shell escaping is centralized** because prompts and commands can contain
  spaces and quotes, and split/tab launches are painful to debug when escaping
  is wrong.
- **Spawned panes restore the current PATH explicitly** because respawned cmux
  surfaces may not inherit the same shell initialization as the current Pi
  session. Without that, commands can work here and fail there.
- **Fresh Pi panes launch through the current Node binary + Pi CLI entrypoint**
  instead of blindly running `pi`. This avoids `#!/usr/bin/env node` wrapper
  failures in stripped respawn environments.
- **`new-workspace` is parsed as plain text** because cmux currently returns
  `OK workspace:<n>` in real usage, even when JSON might be expected.
- **Pi prompts are passed after `--`** so prompts that start with `-` are not
  misread as CLI flags.
- **Notifications are deduplicated** because repeated "Waiting" summaries are
  more annoying than helpful.

## Architecture

```
extensions/oh-my-pi/
├── index.ts           # Entry point (auto-discovered by pi)
├── cmux-notify.ts     # Notification logic (listens to agent_start,
│                      #   tool_result, agent_end)
├── cmux-split.ts      # Split pane commands (/omp-split-* + aliases)
└── cmux-workspace.ts  # Workspace tab commands (/omp-workspace* + aliases)
```

Shared dependency:

```text
@diversioteam/pi-cmux
├── cmux.ts / split.ts / workspace.ts / notify.ts / launch.ts / escape.ts
└── hardened cmux primitives reused by oh-my-pi and dev-workflow
```

### Design decisions

- Uses native `cmux notify` (not OSC escape sequences)
- Uses `cmux --json new-split` + `respawn-pane` (no polling)
- Treats `cmux new-workspace` as text output (not JSON)
- One small shared runtime dependency: `@diversioteam/pi-cmux`
- Silent no-op outside cmux for notifications; interactive commands warn

## Limitations (v1)

- Workspace tab creation always switches focus; no background creation
- No session-file passing across splits/tabs (each new Pi session is independent)
- Notifications occur at agent_end only; no mid-run progress notifications
- Commands are cmux-only; they warn if run outside cmux

## Maintainer notes

### If you need to extend this package later

Use this rule of thumb:

- If the change is about **talking to cmux**, put it in `@diversioteam/pi-cmux`.
- If the change is about **when / what to notify**, put it in `cmux-notify.ts`.
- If the change is about **slash command UX**, put it in `cmux-split.ts` or
  `cmux-workspace.ts`.

### Safe places to evolve next

```text
Good next v2 ideas
├─ custom notification templates
├─ more split directions / aliases
├─ better workspace title parsing
├─ optional background workspace behavior if cmux adds it
└─ richer notification classification
```

## Verification

```bash
# Manifest check
jq -e . pi-packages/oh-my-pi/package.json >/dev/null

# Command registration check
printf '{"id":"cmds","type":"get_commands"}\n' | \
  PI_OFFLINE=1 pi --mode rpc --no-session --no-context-files \
    --no-extensions -e ./pi-packages/oh-my-pi \
    --no-prompt-templates --no-skills | jq .

# Interactive test (inside cmux, isolated from the repo root manifest)
pi --no-extensions -e ./pi-packages/oh-my-pi
```
