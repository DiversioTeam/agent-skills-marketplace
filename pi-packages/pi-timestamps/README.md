# Pi Timestamps

## Problem

Pi already knows when messages happened, but the default transcript does not
make that timing easy for a human to scan.

In practice, people want simple answers to simple questions:

- When did I send that prompt?
- How long did the model take to start replying?
- How long did the full turn take?
- How long ago did this happen?

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
- relative age like `11s ago` uses a warning color
- the hide shortcut stays dimmer than the timing data

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
2026-06-02 19:18:01 EDT · done 2026-06-02 19:18:08 EDT · reply in 3s · total 7s · 11s ago · hide row: ctrl+shift+h
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

### Why is there still a hidden widget internally?

Relative text like `11s ago` needs the TUI to re-render periodically.
The extension mounts a **zero-height hidden widget** only so it can keep a TUI
handle and refresh those relative timestamps once per second.

Users do not see that widget.

## What gets shown

Each timing row can show:

- exact prompt timestamp
- exact completion timestamp
- reply-start timing when visible text appeared
- fallback assistant-start timing if the provider does not emit a text-start event
- total turn duration
- relative age like `11s ago`
- inline "hide row" shortcut text

Visual map:

```text
2026-06-02 19:18:01 EDT · done 2026-06-02 19:18:08 EDT · reply in 3s · total 7s · 11s ago · hide row: ctrl+shift+h
│                        │                              │             │          │          └─ quick hide-row hint
│                        │                              │             │          └─ relative age, kept live
│                        │                              │             └─ full turn duration
│                        │                              └─ time until the reply became visible
│                        └─ exact completion time
└─ exact prompt time
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
- live relative age like `11s ago`
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
export PI_TIMESTAMPS_TIME_ZONE="America/Toronto"
export PI_TIMESTAMPS_TOGGLE_SHORTCUT="ctrl+shift+h"
```

Notes:

- If `PI_TIMESTAMPS_TIME_ZONE` is unset, the extension uses your local system timezone.
- `PI_TIMESTAMPS_TOGGLE_SHORTCUT` changes both the registered shortcut and the inline hint text.

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
4. Confirm `done`, `reply in`, `total`, and `11s ago` are easy to spot
5. Press Ctrl+Shift+H
6. Confirm timing rows disappear
7. Press Ctrl+Shift+H again
8. Confirm timing rows return
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

A few implementation choices may look unusual at first glance.
Here is the simple why behind each one.

### Hidden zero-height widget

Why it exists:

```text
relative age text changes over time
        ↓
UI must rerender periodically
        ↓
extension needs a stable TUI handle
        ↓
hidden widget keeps that handle alive
```

### Deferred timing-row append

Why we do not append the row immediately inside `agent_end()`:

```text
append too early
  -> row can behave like part of the active model turn
  -> assistant may appear to reply to it

append one event-loop tick later
  -> current run settles first
  -> row still appears immediately to the user
```

In code, that is this pattern:

```ts
setTimeout(() => {
  pi.sendMessage({ ...timingRow });
}, 0);
```

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
- Timing rows are appended with a tiny deferred `pi.sendMessage(...)` call after the current run settles, so they still appear in the live transcript without being treated as part of the active model turn.
- Visibility mode is stored as a session custom entry, so `/reload` preserves it inside the current session branch.
- Relative-time updates depend on a lightweight 1s TUI re-render tick.
- The hidden zero-height widget exists only to keep that re-render loop alive.

Code-reading map:

```text
restoreStateFromSession()
  -> load visible/hidden mode from session

syncTicker()
  -> start/stop the 1s relative-time rerender loop

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
  -> append the display-only timing row safely
```
