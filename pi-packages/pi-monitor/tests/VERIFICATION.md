# Pi Monitor 0.1.1 — recorded verification

Observed on **2026-10-18**, macOS ARM64, Node **24.15.0**. These are executed
checks, not proposed acceptance criteria. Re-run them on your own host; no finite
test suite proves every possible script, OS failure, or Pi extension combination.

## Why 0.1.1 exists

Pi session `01a14d94` used 0.1.0 to wait for a PR approval. Background events
did not reach the model while it was working:

- The model slept in Bash between calls, and Pi only delivered events once the
  whole run ended. Output observed at 06:04–06:12 UTC was delivered at 06:26.
- Each queued event then started its own model turn.
- Two of those events came from a monitor the model had already stopped, plus
  its own self-caused stop notice.
- A command that failed immediately (`bash: --: invalid option`) was reported as
  `running` and surfaced 14 minutes later.
- An unanswered approval returned the same error as a denial, after which the
  model tried to put `--monitor-allow-commands` inside the command.

## Before and after

Run with the same Pi **1.3.0** binary. "Shipped" is `origin/main` at `3646d73`
(0.1.0); "fixed" is 0.1.1.

| Check | Shipped 0.1.0 | Fixed 0.1.1 |
| --- | --- | --- |
| `npm test` (Node-only) | 17 passed, **1 failed** (launch-flag rejection) | **18/18 passed** |
| `npm run test:pi`, 10 original tests | 9 passed; the busy-streaming test fails only because it now reads the 0.1.1 `details.events` shape (with its 0.1.0 assertions, all 10 passed) | 10 passed |
| `npm run test:pi`, 6 new regression tests | **all 6 failed** | **all 6 passed** |
| Live busy-model replay, `openai-codex/gpt-5.6-sol` | **FAIL**: 6 Bash sleeps, "no background event arrived" | **PASS, 3/3 runs**: 1 Bash sleep, event in the same run |

The six new RPC regression tests, each failing on the shipped code:

1. **Mid-run delivery.** The model runs `monitor`, then sleeps in Bash. The
   event must reach the provider call right after that Bash call, before the
   run ends, with no extra follow-up run. Shipped: delivered only after the run.
2. **Batching.** Three lines and an exit, queued while busy, must arrive as one
   message and one follow-up run. Shipped: four messages.
3. **Stale events on stop.** Output queued while busy, then `monitor_stop`,
   must produce no event at all. Shipped: the `BEFORE-STOP` output and a
   `stopped` notice, both delivered after the stop — the session's exact symptom.
4. **Startup failure.** `exit 2` with stderr must return an error tool result
   with the exit code and stderr. Shipped: `status: running`.
5. **Launch flag in a command.** Must be rejected before any approval prompt.
   Shipped: shown for approval, then run.
6. **Approval timeout.** An unanswered dialog must report "No approval answer
   within 60 s", not "not approved". Shipped: indistinguishable from denial.

## Fixed 0.1.1 results

| Check | Observed result |
| --- | --- |
| `npm test` | **18/18 passed** |
| `npm run test:pi`, installed Pi **1.3.0** | **16 passed**, one old-host-only check skipped |
| Same, 5 consecutive runs, approval-timeout test excluded for time | **15/15 passed every run** (no flakes; run on a revision differing only in the tool description text) |
| `npm run test:pi`, freshly installed `@earendil-works/pi-coding-agent@1.1.0` | **16 passed**, one old-host-only check skipped |
| Extracted `npm pack` (0.1.1) on fresh Pi **1.1.0** | **15/15 passed** against the distributable files (approval-timeout test excluded; it passed 16/16 on an earlier pack differing only in the tool description text) |
| Legacy Pi **0.70.6** (CI pin) and **0.73.1** | Startup rejection **passed**; supported-host tests skipped |
| Live busy-model replay (`live-busy-smoke.mjs`) | **PASS ×3** on the final source (and ×3 on an earlier revision differing only in the tool description text) |
| Live idle-path smoke (`live-smoke.mjs`) | **PASS**, one `monitor` call |
| Root marketplace discovery of `/monitors`, `validate-skills.sh --all`, `git diff --check`, website build | **PASS** |

Earlier 0.1.0 coverage still holds: the ten original RPC tests (approval
deny/allow/abort, timeout, session replacement, tree navigation, user stop,
shutdown, delayed `agent_end` handlers, slow compaction) pass unchanged in intent.
Two of them (busy streaming and tree navigation) now print their marker after
the new 0.5-second startup check, because output printed before `monitor`
returns is now delivered right after the tool result, on the same branch. They
still test output that arrives while the provider is busy.

The RPC tests use a **deterministic loopback OpenAI-compatible server**, not an
LLM. They exercise Pi's actual resource loader, tool execution, steering and
follow-up queues, and provider request conversion.

## Why steering is safe

Busy delivery uses `deliverAs: 'steer'` from a `turn_end` handler, and only for
turns that ran tools and were not aborted. In Pi 1.1.0 and 1.3.0, extension
`turn_end` handlers are awaited inside `finishTurn`, which the agent loop runs
immediately before it polls the steering queue (`agent-loop.js`, `finishTurn`
then `getSteeringMessages`). So a steered event is consumed before the next
model call and never waits in Pi's own queue, which `abort()` does not clear.
The loop skips that poll only when `finishTurn` returns `end`, which Pi's coding
agent never does; it comes only from an SDK-supplied `agent.finishTurn`.

Turns with no tool calls end the run, so their events still use the existing
idle follow-up path, which tree navigation and compaction can discard. A long
foreground tool call still delays delivery until it returns: Pi has no way to
interrupt a running tool.

## Live model evidence

The [curated before/after trace](evidence/live-busy-smoke.json) comes from
two authenticated Pi RPC runs with the same prompt, model and Pi binary. Its
fixed-build source hashes match the committed `lib/monitor.mjs` and
`extensions/pi-monitor/index.ts`. It is
an observation, **not** an executable fixture or a signed attestation. It holds
the source hashes of both builds and each full local transcript's SHA-256.
Temporary paths are redacted.

The producer creates a `crypto.randomUUID()` nonce 2.5 seconds after the
monitor starts, then keeps running like a PR poll. The model is told to sleep
in Bash (`sleep 3`, at most six times) until an event arrives, then stop the
watch and repeat the nonce.

Fixed build:

```text
tool monitor → running
tool bash "sleep 3"
monitor event message: output PI-MONITOR-BUSY-9dda8c10-8115-4009-8645-57bd6ca2dfa2
tool monitor_stop → stopped
assistant: RECEIVED PI-MONITOR-BUSY-9dda8c10-8115-4009-8645-57bd6ca2dfa2
agent_end   (1 run, 1 monitor message, nothing afterwards)
```

Shipped build:

```text
tool monitor → running
tool bash "sleep 3"   ×6
assistant: RECEIVED nonce unavailable (no background event arrived).
agent_end
```

Two further fixed-build runs also passed, with the same tool sequence
(`monitor`, `bash`, `monitor_stop`):

| Nonce | Emit → delivery | Transcript SHA-256 |
| --- | --- | --- |
| `PI-MONITOR-BUSY-1ee6a8dd-a150-41a9-97ac-362d94d4bc8e` | 2,380 ms | `f3272b31c4c5c03290c16738c1832aaf330834943e08c4d17d899fa50cb836a3` |
| `PI-MONITOR-BUSY-7d76425b-ba67-44ab-aef5-6015db7726a6` | 2,124 ms | `8b5156d320779fb12e311ccb9f4117afcf981ff0c18375ee9a144db549d9153e` |

Delivery latency is the rest of the Bash sleep in progress when the nonce was
printed: the event enters at the next tool boundary.

The idle-path smoke on 0.1.1 also passed: one `monitor` call, nonce
`PI-MONITOR-LIVE-8d656852-7f61-4606-ab79-38a7159546de` delivered 1,982 ms after
the tool returned (the producer prints after one second) (transcript SHA-256
`696910ce43216245b6d77550936a0cd8b70ed770b54c7cc07e9874eb938a8001`).
[`evidence/live-smoke.json`](evidence/live-smoke.json) is the original 0.1.0
observation and is kept unchanged.

Full transcripts were saved locally on the verification machine only; they are
not reviewer-accessible downloads.

## Reproduce

```bash
cd pi-packages/pi-monitor
npm test
PI_TEST_BINARY="$(command -v pi)" \
  PI_MONITOR_PROOF_DIR=/tmp/pi-monitor-rpc-proof npm run test:pi
```

The approval-timeout test waits the real 60 seconds. For another supported Pi
version, set `PI_TEST_BINARY` to its installed CLI. Capture an absolute CLI path
before running npm: dependency-local `pi` binaries can otherwise shadow the
intended host inside npm's modified PATH. `PI_MONITOR_TEST_PACKAGE` can point at
an extracted npm pack to exercise exactly the distributable files.

To see the regression tests fail on 0.1.0, export `3646d73:pi-packages/pi-monitor`
to a temporary directory, copy the 0.1.1 `tests/` into it, and run the same
commands there.

The optional real-model tests use your configured model and credentials, consume
model usage, require explicit opt-in, and never run in CI:

```bash
PI_MONITOR_LIVE_TEST=1 PI_MONITOR_LIVE_PROOF=/tmp/pi-monitor-live-proof.json \
  node tests/live-smoke.mjs
PI_MONITOR_LIVE_TEST=1 PI_MONITOR_LIVE_PROOF=/tmp/pi-monitor-live-busy-proof.json \
  node tests/live-busy-smoke.mjs
```

## Deliberate limits

No claim is made for Windows, deliberately daemonized/process-group-escaping
children, OS-denied signals, a SIGKILL/crash of Pi itself, durable watches, or
native WebSocket sources. Signal denial is surfaced as unconfirmed cleanup,
not success. A lossy bounded notification feed is not a complete log archive.
Events cannot interrupt a running tool call. The package README documents
approval, model costs, output limits, and cleanup.
