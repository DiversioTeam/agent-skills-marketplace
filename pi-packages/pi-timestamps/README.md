# Pi Timestamps

## Problem

Pi already knows when messages happened, but the default transcript does not
make that timing easy for a human to scan.

In practice, people want simple answers to simple questions:

- When did I send that prompt?
- How long did the model take to start replying?
- How long did the full turn take?
- How long ago did the last reply happen?

## Solution

`pi-timestamps` adds one **small, subtle timing row** after each user prompt.

Most turns show normal timing data. If no visible assistant reply arrives, the
row falls back to `reply incomplete` instead of pretending the turn completed
normally.

Visual design principles:

- keep the row quiet enough that it does not compete with the transcript
- still make the important timing fields pop
- use color intentionally instead of making the whole row loud

Current highlighting:

- completion time uses a success color
- `reply in` and `total` values use an accent color
- the hide shortcut stays dimmer than the timing data
- the bottom status line keeps the flavor text dimmer
- the live relative age in the bottom status bar is the part that pops most

Labeling note:

- we use `reply in`, not `thought for`
- `reply in` means: "how long until visible answer text appeared"
- that is a user-experience metric, not an internal reasoning metric

Mental model:

```text
user sends prompt
   ↓
extension records start time
   ↓
first visible assistant text appears
   ↓
extension records reply-start timing
(or falls back to assistant-start timing if no text-start event arrives)
   ↓
turn fully ends
   ↓
extension appends one tiny display-only timing row
```

Example row:

```text
2026-06-02 19:18:01 EDT · done 2026-06-02 19:18:08 EDT · reply in 3s · total 7s · hide row: ctrl+shift+h
```

Example status line snippets:

```text
⚽ Cooking, the tin monk is. Glass, tap not.
⚽ 11s ago · Replied, the tin monk has. Your move, captain.
```

## Why it works this way

### Why add a separate timing row?

Because Pi's current extension API can render **custom extension messages**,
but it does **not** let us rewrite the built-in user/assistant chat bubbles
directly.

So the extension does this instead:

```text
normal Pi transcript row
normal Pi transcript row
small timing row added by the extension
```

That keeps the feature reliable without patching Pi core.

### Why is there no bottom panel anymore?

We tried that. It felt too noisy.

The current design aims for:

- low visual weight
- useful timing at a glance
- no persistent second panel competing with the conversation

### Why move the live relative age to the status bar?

A changing `11s ago` label inside historical transcript rows forces Pi to
rerender old chat lines. That is fragile when you have scrolled up and are
trying to read a long response.

So the extension now keeps transcript rows **static** and moves only the newest
relative age to the bottom status bar.

The ticker is still adaptive instead of repainting once per second forever:

```text
first minute  -> update every second  -> 11s ago, 12s ago, ...
first hour    -> update every minute  -> 2m ago, 3m ago, ...
after that    -> update hourly        -> 2h ago, 1d ago change slowly
```

## What gets shown

Each timing row can show:

- exact prompt timestamp
- exact completion timestamp
- reply-start timing when visible text appeared
- fallback assistant-start timing if the provider does not emit a text-start event
- total turn duration
- inline "hide row" shortcut text

The bottom status bar shows playful Yoda-ish lines for the newest turn. While the model is working it rotates through in-progress messages; after completion it rotates through replied/fumbled messages and appends the newest relative age. The flavor text stays relatively dim while the age label is the colorful part that stands out.

Animations come from a pool of ten. On session start an animation is chosen, and each new human message re-rolls the animation for the next turn. The little Yoda-ish bot nickname now shuffles along with the status text itself instead of getting stuck for a whole turn. For now, the football-themed animations are weighted more heavily through July 19.

Visual map:

```text
2026-06-02 19:18:01 EDT · done 2026-06-02 19:18:08 EDT · reply in 3s · total 7s · hide row: ctrl+shift+h
│                        │                              │             │          └─ quick hide-row hint
│                        │                              │             └─ full turn duration
│                        │                              └─ time until the reply became visible
│                        └─ exact completion time
└─ exact prompt time

status: 🥾⚽ Cooking, the tin monk is. Glass, tap not.
status: ⚽ 11s ago · Replied, the tin monk has. Your move, captain.
```

## Quick use

Mental model:

```text
want timing rows?        leave them visible
want a clean transcript? press Ctrl+Shift+H or run /timestamps hidden
want them back?          press Ctrl+Shift+H again or run /timestamps visible
```

## Commands

```text
/timestamps            toggle visible/hidden
/timestamps visible    force visible
/timestamps hidden     force hidden
/timestamps status     show current mode, timezone, shortcut
```

Quick examples:

```bash
# hide timing rows
/timestamps hidden

# show them again
/timestamps visible

# check current mode + timezone + shortcut
/timestamps status
```

## Shortcut

Default shortcut:

```text
Ctrl+Shift+H
```

Inline rows also teach this shortcut with:

```text
hide row: ctrl+shift+h
```

That shortcut hides the entire timing row, not just the hint text.

## Timestamp format

This package intentionally avoids American month/day ordering.

It renders absolute times as:

```text
YYYY-MM-DD HH:mm:ss TZ
```

Example:

```text
2026-06-02 19:18:01 EDT
```

## Design boundaries

This package intentionally stays small.

What it includes:

- subtle transcript timing rows
- exact prompt and completion timestamps
- `reply in` timing
- `total` timing
- newest live relative age in the bottom status bar
- one visibility toggle command and shortcut

What it intentionally does **not** include:

- no bottom panel
- no separate always-visible dashboard
- no explicit thinking-phase metrics
- no mutation of Pi's built-in user/assistant bubble renderer

Why no explicit thinking metric?

Because providers expose reasoning differently.
A durable default UI should measure what the user actually experiences:

```text
When did I see the reply start?
```

not:

```text
When did the model begin internal reasoning?
```

Why keep the scope this small?

Because the hard part is not drawing text — it is making timing feel accurate,
quiet, and non-disruptive across different providers and streaming behaviors.

## Install

From the repo root:

```bash
pi install "$PWD/pi-packages/pi-timestamps"
```

Or install all Pi packages from this repo at once:

```bash
pi install git:github.com/DiversioTeam/agent-skills-marketplace
```

Then run `/reload` in Pi.

## Configuration

Optional environment variables:

```bash
# Render absolute times in a known timezone instead of the machine default.
export PI_TIMESTAMPS_TIME_ZONE="America/Toronto"

# Change the hide/show shortcut and the inline hint text.
export PI_TIMESTAMPS_TOGGLE_SHORTCUT="ctrl+shift+h"

# Optional stable/copy mode: disable the bottom-status relative-age ticker.
export PI_TIMESTAMPS_LIVE_RELATIVE="false"
```

Notes:

- If `PI_TIMESTAMPS_TIME_ZONE` is unset, the extension uses your local system timezone.
- `PI_TIMESTAMPS_TOGGLE_SHORTCUT` changes both the registered shortcut and the inline hint text.
- `PI_TIMESTAMPS_LIVE_RELATIVE=false` disables the bottom-status `... ago` ticker for a maximally stable UI.

Relative-age tradeoff:

```text
show `11s ago` in the bottom status bar
        ↓
must update without waiting for typing/scrolling
        ↓
requires footer/status redraws
        ↓
use adaptive redraws so the label stays honest without repainting every second forever
```

Adaptive ticker mental model:

```text
newest completed turn is 0-59s old
        ↓
relative label can change every second
        ↓
ticker wakes every 1s

newest completed turn is 1-59m old
        ↓
relative label can change every minute
        ↓
ticker wakes every 1m

newest completed turn is 1h+ old
        ↓
relative label changes slowly
        ↓
ticker wakes hourly
```

Stable/copy mode tradeoff:

```text
PI_TIMESTAMPS_LIVE_RELATIVE=false
        ↓
no bottom-status `... ago` ticker
        ↓
no ticker-driven redraws
        ↓
exact prompt/completion timestamps still remain visible
```

## Local testing

```bash
jq -e . pi-packages/pi-timestamps/package.json >/dev/null
(cd pi-packages/pi-timestamps && npm pack --dry-run --json >/tmp/pi-timestamps-pack.json)
pi --no-extensions -e ./pi-packages/pi-timestamps
```

Suggested smoke test:

```text
1. Start Pi with the package loaded
2. Send a prompt
3. Confirm a subtle timing row appears immediately after the turn
4. Confirm `done`, `reply in`, and `total` are easy to spot inline
5. While the model is responding, confirm the bottom status bar shows rotating Yoda-ish in-progress messages
6. After completion, confirm it flips to rotating Yoda-ish replied messages with a relative age like `11s ago` near the front so it stands out
7. Wait without typing and confirm the bottom status bar updates on its own
8. Press Ctrl+Shift+H
9. Confirm timing rows disappear and the status entry clears
10. Press Ctrl+Shift+H again
11. Confirm timing rows return and the status entry comes back
```

Stable/copy mode smoke test:

```text
1. Restart Pi with PI_TIMESTAMPS_LIVE_RELATIVE=false
2. Send a prompt
3. Confirm the row still shows exact times, `reply in`, and `total`
4. Confirm the bottom status bar shows the fun status text without a changing `... ago` label
```

Provider-behavior smoke test:

```text
A. Normal streaming reply
   -> expect a real `reply in` timing from visible text

B. Provider with weak/no text-start events
   -> expect a fallback `reply in` timing close to assistant-start

C. Tool-call-only / no visible assistant reply
   -> expect `reply incomplete`, not fake completion timing
```

## Implementation notes

A few implementation choices may look unusual when you first read the code.
Here is the simple why behind each one.

### Bottom-status relative-age ticker

Why it exists:

```text
historical transcript rows should stay stable
        ↓
the newest turn still benefits from a live `11s ago` label
        ↓
move only that newest relative age into the status bar
        ↓
status updates stay local to the footer instead of mutating old chat rows
```

### Adaptive relative-age ticker

The relative label is useful only when it updates by itself.

```text
bad behavior
  `11s ago` sits still
  user starts typing
  label jumps to `2m ago`
  -> looks stale and misleading

good behavior
  `11s ago` updates on its own
  redraw cadence slows as the label becomes less precise
  -> truthful without constant repainting forever
```

The implementation tracks the newest timing row details:

```text
new row appended
        ↓
latestStatusDetails = newest row details
        ↓
restartTicker()
        ↓
nextTickerDelayMs() chooses 1s / 1m / 1h cadence
```

Stable/copy mode disables this entire path:

```bash
export PI_TIMESTAMPS_LIVE_RELATIVE=false
```

In that mode exact absolute timestamps remain visible, but the bottom-status
relative label stops ticking.

### Deferred timing-row append

Why we do not append the row immediately inside `agent_end()`:

```text
append too early
  -> row can behave like part of the active model turn
  -> assistant may appear to reply to it

wait until Pi reports idle, then append with triggerTurn: false
  -> current run settles first
  -> row appears without queueing a steering/follow-up LLM turn
```

The important Pi behavior is:

```text
inside agent_end
        ↓
Pi is still streaming
        ↓
pi.sendMessage(...) uses the streaming path
        ↓
default streaming delivery is "steer"
        ↓
the LLM may continue and respond to the timing row
```

So the extension uses this safer shape:

```text
agent_end computes timing data
        ↓
schedule a tiny callback
        ↓
callback polls ctx.isIdle()
        ↓
only when idle: pi.sendMessage(..., { triggerTurn: false })
        ↓
row is saved/rendered, but no LLM turn starts
```

In code, that is this pattern:

```ts
const deadline = Date.now() + 10 * 60 * 1_000;
const appendWhenIdle = () => {
  if (!runtimeActive) return;

  if (!ctx.isIdle()) {
    if (Date.now() < deadline) setTimeout(appendWhenIdle, 50);
    return;
  }

  if (!runtimeActive) return;
  pi.sendMessage({ ...timingRow }, { triggerTurn: false });
};
setTimeout(appendWhenIdle, 0);
```

Why the 10 minute deadline?

```text
normal case: Pi becomes idle almost immediately
edge case: another extension opens post-turn UI and waits for a human
bad case: Pi gets stuck streaming forever

10 minute cap
  -> does not drop rows during normal human-paced post-turn UI
  -> still prevents an infinite timer loop if something breaks
```

Why `runtimeActive`?

```text
old runtime schedules callback
        ↓
user runs /reload or switches sessions
        ↓
old runtime shuts down
        ↓
old callback wakes up later
        ↓
runtimeActive=false, so it exits without writing stale rows
```

### Why not `deliverAs: "nextTurn"`?

`nextTurn` sounds tempting, but it means something different in Pi:

```text
deliverAs: "nextTurn"
        ↓
wait for the next user prompt
        ↓
inject the custom message alongside that prompt
        ↓
the timestamp becomes next-turn context, not an immediate transcript row
```

For timestamps we want:

```text
current turn finishes
        ↓
append display-only transcript row now
        ↓
do not start or steer the LLM
```

That is why the extension waits for idle and uses `{ triggerTurn: false }`.

### Backward-compatible visibility restore

Older session entries may still contain:

```text
widgetMode
```

Newer ones write:

```text
visibilityMode
```

We read both so existing sessions do not lose their saved hide/show state.

## Notes for maintainers

- Timing rows are stored as display-only custom messages and filtered out of LLM context.
- Timing rows are appended only after `ctx.isIdle()` is true, with `{ triggerTurn: false }`, so they do not get delivered as steering messages during the active model turn.
- Visibility mode and the current status animation are stored as session custom state, so `/reload` preserves them inside the current session branch.
- Relative-time live updates are enabled by default and use an adaptive ticker in the bottom status bar: every second for fresh turns, every minute after the first minute, hourly after the first hour.
- `PI_TIMESTAMPS_LIVE_RELATIVE=false` disables the bottom-status `... ago` ticker for stable/copy mode.
- Transcript rows stay static; only the newest relative age is dynamic.
- The status animation comes from a pool of ten and re-rolls on each new human message. The Yoda-ish bot nickname rotates with the status text itself. Football-themed animations get extra weight through July 19.

Troubleshooting map:

```text
No timing row appears
  -> check timestamps are visible
  -> run /timestamps status
  -> verify the package is loaded with pi --no-extensions -e ./pi-packages/pi-timestamps
  -> if another extension held Pi non-idle for >10 minutes, the row is intentionally dropped

Assistant seems to respond to the timing row
  -> timing row append is happening too early in the active run
  -> inspect scheduleTimingRowAppend()
  -> confirm the append path waits for ctx.isIdle()
  -> confirm sendMessage uses { triggerTurn: false }

No bottom-status "11s ago" label appears
  -> check PI_TIMESTAMPS_LIVE_RELATIVE is not set to false/off/0/no
  -> exact prompt and completion timestamps are still shown inline

Bottom-status age stops updating
  -> inspect syncTicker()
  -> inspect syncStatusBar()
  -> remember updates become minute-based after the first minute

Rows are hard to copy/select around
  -> set PI_TIMESTAMPS_LIVE_RELATIVE=false for stable/copy mode
  -> or use /timestamps hidden for a clean transcript

Rows do not preserve hidden/visible state after /reload
  -> inspect restoreStateFromSession()
  -> inspect persistSettings()

Rows appear after /reload from an old turn
  -> inspect runtimeActive guards in scheduleTimingRowAppend()
  -> inspect clearPendingAppendTimers()
```

Code-reading map:

```text
restoreStateFromSession()
  -> load visible/hidden mode from session

syncTicker()
  -> start/stop the adaptive bottom-status relative-time loop

message_end(role=user)
  -> start the turn clock

message_start(role=assistant)
  -> save assistant-start fallback time

message_update(text_start/text_delta)
  -> capture real reply-start timing when possible

agent_end()
  -> decide completed vs aborted
  -> compute final durations
  -> hand details to scheduleTimingRowAppend()

scheduleTimingRowAppend()
  -> defer one tick
  -> wait for ctx.isIdle()
  -> guard against old runtimes with runtimeActive
  -> append the display-only timing row safely with triggerTurn: false
```
