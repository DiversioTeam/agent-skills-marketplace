# Pi Monitor 0.1.0 — recorded verification

Observed on **2026-10-18**, macOS ARM64, Node **24.15.0**. These are executed
checks, not proposed acceptance criteria. Re-run them on your own host; no finite
test suite proves every possible script, OS failure, or Pi extension combination.

## Results

| Check | Observed result |
| --- | --- |
| `npm test` | **17/17 passed**; real child processes plus focused buffer/rate/signal-error checks |
| `npm run test:pi`, installed Pi **1.1.0** | **10/10 supported-host checks passed**, one old-host-only check skipped |
| `npm run test:pi`, freshly installed `@earendil-works/pi-coding-agent@1.1.0` | **10/10 supported-host checks passed**, one old-host-only check skipped |
| Legacy Pi **0.70.6** startup rejection | **1/1 passed**; ten supported-host tests deliberately skipped |
| Extracted `npm pack` on fresh Pi **1.1.0** | **10/10 supported-host checks passed** against the distributable files |
| Authenticated live-model smoke | **PASS**, `openai-codex/gpt-5.6-sol`, exactly one `monitor` call |
| Root marketplace manifest discovery | **PASS**, `/monitors` discovered through the root package |
| JSON manifests, `git diff --check`, all skill-size checks | **PASS** |
| Marketplace website `npm run build` | **PASS**, including the Pi Monitor catalog/docs page |

The ten supported-host RPC tests use a **deterministic loopback OpenAI-compatible server**, not
an LLM. They exercise Pi's actual resource loader, schema validation, model tool
execution, custom-message queue, and provider request conversion. Provider
receipt assertions inspect event messages, not the original command containing
the same marker.

They cover:

1. Immediate tool return; stdout observed while the provider is busy; follow-up
   delivery after that response; actual event receipt by the provider; no polling.
2. Finite output/completion still delivered when another extension delays its
   `agent_end` handler (a previously discovered scheduler-stall regression).
3. RPC approval denied: error returned, no child-created marker file.
4. RPC approval granted: script runs without the blanket launch flag.
5. Timeout: terminal event and the recorded shell PID no longer exists.
6. Session replacement: process removed, inventory empty, no stale old-session notice.
7. Unanswered approval aborted: returns in under two seconds, not the 60-second timeout.
8. Real tree navigation after abort: buffered old-branch events are discarded,
   never passed to the provider. The implementation does not clear human queues.
9. Explicit user stop and orderly RPC shutdown: recorded process groups removed.
10. Slow manual compaction: watches stop before summarization, no event starts an
    unrecorded model turn, and the operator is told to re-arm after compaction.

Earlier investigation ran the main suite on 0.70.6, but review found its idle
check unsafe during compaction's asynchronous authentication window. Those
passes are **not** a compatibility guarantee. Final code rejects starts on
hosts older than 1.1.0; the root package remains discoverable there.

Node-only tests additionally cover UTF-8 split boundaries, final unterminated
lines, stderr-only failures, pipeline failures, spawn failure, idempotent stop,
SIGTERM-ignoring descendants/shells, and leftover background children. A simulated
`EPERM` regression proves that signal errors produce `cleanup_failed` instead of
crashing or hanging the harness; the test then kills its own fixture explicitly.

## Live model evidence

The [curated protocol trace](evidence/live-smoke.json) is derived from an actual
authenticated Pi RPC run. It is a recorded observation, **not** an executable test
fixture or a signed third-party attestation. It includes hashes of the tested
runner and extension, and the full local transcript's SHA-256. Temporary command
paths are redacted; system prompts and irrelevant metadata are omitted.

The producer generated this UUID **after the monitor started**, using
`crypto.randomUUID()`. The UUID was not present in the prompt or command:

```text
monitor tool returns status=running
assistant: ARMED
monitor output: PI-MONITOR-LIVE-b4defbf8-c9c5-4629-87e4-429075da5a21
assistant: RECEIVED PI-MONITOR-LIVE-b4defbf8-c9c5-4629-87e4-429075da5a21
monitor terminal event: exited, exitCode=0
```

- Tool calls: **1**, only `monitor`; no Bash, sleeps, list calls, or tool polling.
- Tool returned at epoch **1792302544400 ms**.
- Output delivered at epoch **1792302545941 ms**, **1,541 ms later**.
- Monitor ID: `159acbcc-5fdb-4352-b44e-cf27fd1e6fef`.
- Full local transcript SHA-256:
  `6ea697adea10cfbf96d7a61cc547fb423088d67a2ce575ae2669178ad04d6a4f`.

The full local artifact was saved as `/tmp/pi-monitor-live-proof.json`. That path
is specific to the verification machine, not a reviewer-accessible download.
The curated trace above is committed so reviewers can inspect the observation.

## Reproduce

```bash
cd pi-packages/pi-monitor
npm test
PI_TEST_BINARY="$(command -v pi)" \
  PI_MONITOR_PROOF_DIR=/tmp/pi-monitor-rpc-proof npm run test:pi
```

For another supported Pi version, set `PI_TEST_BINARY` to its installed CLI.
Capture an absolute CLI path before running npm: dependency-local `pi` binaries
can otherwise shadow the intended host inside npm's modified PATH.
The RPC suite uses a temporary agent directory and does not modify normal Pi
settings or read credentials. `PI_MONITOR_TEST_PACKAGE` can point at an extracted
npm pack to exercise exactly the distributable files.

The optional real-model test uses your existing configured model and credentials
and consumes model usage; it requires explicit opt-in and never runs in CI:

```bash
PI_MONITOR_LIVE_TEST=1 PI_MONITOR_LIVE_PROOF=/tmp/pi-monitor-live-proof.json \
  node tests/live-smoke.mjs
```

## Deliberate limits

No claim is made for Windows, deliberately daemonized/process-group-escaping
children, OS-denied signals, a SIGKILL/crash of Pi itself, durable watches, or
native WebSocket sources. Signal denial is surfaced as unconfirmed cleanup,
not success. A lossy bounded notification feed is not a complete log archive.
The package README documents approval, model costs, output limits, and cleanup.
