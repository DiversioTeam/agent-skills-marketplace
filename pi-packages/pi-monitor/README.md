# Pi Monitor

Run an approved background script once and receive its meaningful stdout events
while Pi keeps working. No model polling loop, MCP server, or daemon.

```text
script → stdout lines → bounded batches → owned event queue → Pi follow-up
```

Requires Node 24+, **Pi 1.1.0 or newer**, macOS or Linux, and `/bin/bash`.
Older hosts can discover the package, but starting a monitor fails with an
upgrade message: Pi 0.70.6's idle check is unsafe during compaction/auth refresh.
Windows is rejected because process-group cleanup is not implemented there.

## Install

Included in the marketplace's root Pi manifest:

```bash
pi install git:github.com/DiversioTeam/agent-skills-marketplace
```

For local development, from this repository:

```bash
pi --no-extensions -e ./pi-packages/pi-monitor
# Or persist a local install:
pi install "$PWD/pi-packages/pi-monitor"
```

Run `/reload` after installation. Do not install both the bundle and a separate
local copy. Update with `pi update --extensions`; remove with `pi remove` using
the exact source/path you installed.

## Use

Ask Pi:

> Watch server.log for new errors for five minutes. Start at the end of the
> existing file, report new errors, and keep working on the current task.

The model can call:

```json
{
  "command": "tail -n 0 -F server.log | grep --line-buffered -E 'ERROR|Traceback|FAILED|OOM'",
  "description": "new failures in server.log",
  "timeout_ms": 300000
}
```

This is a `monitor` tool call. Approve the exact command, working directory, and
timeout in Pi's confirmation dialog. The tool returns a monitor ID after a
0.5-second startup check: a command that fails within that window (bad syntax, a
missing file) returns an error with its exit code and stderr instead of
`running`. Output and terminal notices arrive automatically as one custom
`monitor-event` message holding every queued event (`details.events`):

- **While the model is working**, right after its current tool calls finish,
  before its next model call. A model that keeps running tools still sees the
  event within the same run.
- **When Pi is idle**, as a follow-up that starts a new turn.

Events are not human replies. A long foreground tool call (for example a
ten-minute Bash loop) still delays delivery until it returns.

| Surface | Purpose |
| --- | --- |
| `monitor` | Start a script: `command`, `description`, optional `timeout_ms` |
| `monitor_list` | List this session's running/recently finished tasks; not for polling |
| `monitor_stop` | Stop by `monitor_id`; repeated stops of retained tasks are safe |
| `/monitors` | List without calling the model |
| `/monitors stop <id>` | Stop one monitor |
| `/monitors stop all` | Stop this session's monitors |

Stopping a monitor discards its queued, undelivered events. `monitor_stop`
returns the final state and sends no terminal event, since the model asked for
the stop. `/monitors stop` comes from the user, so the model still receives the
terminal event. Only the most recent 20 tasks are retained for listing, and
listed commands are shortened to 120 characters.
The tool ID is extension-owned, not a Pi core background-task ID; use the tools
above, not another package's task-stop operation.

## Approval and unattended runs

**Commands are unsandboxed and inherit Pi's environment and OS permissions.**
They can read credentials, access the network, and change files. Approval does
not make an arbitrary script safe. Other extensions may block the tool call,
but direct child creation does not automatically use their Bash permission or
sandbox implementation. No repository monitor file is automatically executed.

Every start requires confirmation unless the operator explicitly launches:

```bash
pi --no-extensions -e ./pi-packages/pi-monitor --monitor-allow-commands
```

The flag grants this invocation's model permission to start any monitor command
without individual confirmation. Use only for a trusted task, script, and model;
it is not saved. Noninteractive runs without approval fail closed. RPC clients
can instead approve individual `extension_ui_request` confirmations. Cancelling
a pending tool also cancels its approval dialog; it cannot start later. An
unanswered dialog expires after 60 seconds with a distinct "no approval answer"
error, so the model can tell the user is away rather than that they declined. A
command containing `--monitor-allow-commands` is rejected before any dialog:
the flag is only for launching Pi, and a tool call cannot grant it.

Output is labeled untrusted external data. A monitor event does not authorize
new actions. Avoid emitting secrets: output goes to the model and session
transcript just like other tool output.

## Script rules

- Emit changes you would act on, not raw logs or repeated unchanged status.
- End each event with a newline. Flush every pipe stage (`grep --line-buffered`,
  `awk` with `fflush()`, `python -u`).
- Only stdout generates output events. The last 2,000 stderr characters appear
  in the terminal event. Redirect `2>&1` before a filter if those failures should
  also generate live events.
- Cover success **and** failure/cancellation/timeout states. Silence is not success.
- Handle transient network failures explicitly. For remote APIs, use a sensible
  interval (usually 30 seconds or longer), not a tight retry loop.
- For one completion, use a finite script that exits. Avoid an endless `tail -f`
  for a one-shot wait: even `grep -m 1` may leave the producer stuck.
- Bash runs with `pipefail`, no profile files, and closed stdin, in the session's
  working directory. Do not depend on interactive shell aliases or input.

## Bounds and cleanup

- Default lifetime: 5 minutes; explicit timeout: 1 second–30 minutes. No durable
  or infinite watches in this version; re-arm only when still wanted.
- At most four running/pending-approval monitors.
- Lines batch on a 200 ms timer. Each line retains 500 characters; each batch
  retains 3,000, plus truncation markers. Blank lines are omitted. Large bursts
  are deliberately lossy; this is notifications, not full log archival.
- Newline-free pending output is capped at 1 MiB. UTF-8 pipe boundaries are decoded
  safely. An unterminated final line is flushed on exit.
- A token bucket allows ten batches initially, then one every two seconds.
  Excess batches are suppressed and counted; sustained flooding can stop the
  source after approximately 30 seconds. Each task stops after 100 output events.
- Until delivery, an extension-owned queue retains at most 40 events. Overflow
  drops an old output event first (otherwise the oldest event) and reports
  `queueSuppressed` on the next delivery. This queue, unlike native follow-ups,
  can be discarded on branch navigation without clearing human messages. Busy
  delivery steers from `turn_end`, which Pi drains before the next model call,
  so a delivered event never waits in Pi's own queue across an abort or a branch
  change. A cancellable 100 ms idle check also covers delayed lifecycle
  handlers; it does not call the model.
- Exit events report exit code, signal, output-event count, suppressed count,
  and stderr tail. Failure and timeout are not reported as success.
- Stop/timeout sends SIGTERM to the process group, then SIGKILL after one second
  if needed. A shell exit also removes leftover members of its process group.
  Signal errors are reported as `cleanup_failed`, never thrown from a background
  callback. If close cannot be confirmed within two seconds of stopping, the
  task reports its process-group ID and cleanup error instead of hanging Pi.
  Shutdown-only failures go to stderr; inspect the reported group manually.
- Shutdown, reload, session replacement/fork, tree navigation, and compaction
  stop owned processes and discard pending events. Compaction displays a warning:
  re-arm any watch you still need afterward. Tasks also stop if another extension
  subsequently cancels navigation or compaction. Nothing restarts on resume.

**Limits:** A deliberately daemonized descendant that creates a new process
group can escape group cleanup. Abrupt termination of Pi itself (SIGKILL, host
crash) cannot run extension shutdown hooks. This is not an OS sandbox or a
persistent process supervisor. Print/JSON mode exits after its run and shuts
monitors down; use interactive or long-lived RPC mode for continuing watches.

## Verify

No package dependency installation is needed for the Node-only checks:

```bash
cd pi-packages/pi-monitor
npm test
PI_TEST_BINARY="$(command -v pi)" npm run test:pi
```

`test:pi` launches real isolated Pi CLI processes and a loopback deterministic
OpenAI-compatible server. It checks actual tool execution, approval deny/allow,
busy/idle delivery, mid-run delivery at a tool boundary, batching, stale-event
removal on stop, startup failure, approval timeout, launch-flag rejection,
provider receipt, timeout, stop, shutdown, tree navigation, aborted approval,
and slow compaction cleanup. It does **not** claim an LLM was involved. No credentials
or external model requests are needed. Set `PI_MONITOR_PROOF_DIR=/tmp/monitor-proof`
to retain RPC records and server requests (test data only).

An optional **real authenticated model** check costs model usage and is never
run by CI:

```bash
PI_MONITOR_LIVE_TEST=1 PI_MONITOR_LIVE_PROOF=/tmp/pi-monitor-live-proof.json \
  node tests/live-smoke.mjs
```

It uses your current configured model/authentication without modifying settings.
A child generates a random nonce **at runtime**, unknown to the model's prompt.
The test asserts one monitor call, immediate return, an actual matching stdout
event, the model's acknowledgement of that nonce, and successful exit. The
saved transcript is local; review it before sharing.

`tests/live-busy-smoke.mjs` (same opt-in variables) replays the busy case: the
model keeps sleeping in Bash while the watch is pending. It asserts that the
runtime nonce reaches the model within the same run, the model stops sleeping
and stops the watch, and no stale event or follow-up run comes afterwards.

See [recorded verification](tests/VERIFICATION.md) for observed results and
explicit evidence limits. WebSocket sources, persistent watches, and automatic
plugin startup are intentionally not included.
