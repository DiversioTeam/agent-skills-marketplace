import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';

export const limits = Object.freeze({
  batchMilliseconds: 200, lineCharacters: 500, batchCharacters: 3000,
  pendingCharacters: 1048576, stderrCharacters: 2000,
  burst: 10, refillMilliseconds: 2000, floodMilliseconds: 30000,
  maximumEvents: 100, defaultTimeoutMilliseconds: 300000, maximumTimeoutMilliseconds: 1800000,
  startupMilliseconds: 500, approvalMilliseconds: 60000,
});

export function validateMonitorInput({ command, description, timeout_ms = limits.defaultTimeoutMilliseconds }) {
  if (process.platform === 'win32') throw new Error('pi-monitor requires macOS or Linux; Windows process-tree cleanup is not supported.');
  if (typeof command !== 'string' || !command.trim() || command.length > 16384 || /[\x00-\x08\x0b-\x1f\x7f-\x9f]/u.test(command)) {
    throw new Error('command must be nonempty, at most 16384 characters, with no hidden control characters.');
  }
  // A model once prefixed this flag to a command, hoping to skip approval; bash then failed on it.
  if (/(^|\s)--monitor-allow-commands(\s|=|$)/u.test(command)) {
    throw new Error('--monitor-allow-commands is a Pi launch flag, not part of a monitor command, and a tool call cannot grant it. Ask the user to approve the command, or to relaunch Pi with the flag.');
  }
  if (typeof description !== 'string' || !description.trim() || description.length > 200 || /[\x00-\x1f\x7f-\x9f]/u.test(description)) {
    throw new Error('description must be nonempty, at most 200 characters, with no control characters.');
  }
  if (!Number.isInteger(timeout_ms) || timeout_ms < 1000 || timeout_ms > limits.maximumTimeoutMilliseconds) {
    throw new Error(`timeout_ms must be an integer between 1000 and ${limits.maximumTimeoutMilliseconds}.`);
  }
  return { command, description: description.trim(), timeout_ms };
}

export function buildLineBuffer(onBatch) {
  let pending = '', batch = '', timer;
  function flush(includePartial = false) {
    clearTimeout(timer);
    timer = undefined;
    if (includePartial && pending) addLine(pending);
    if (includePartial) pending = '';
    if (!batch) return;
    const output = batch;
    batch = '';
    onBatch(output);
  }
  function addLine(line) {
    const text = line.trim();
    if (!text || batch.length >= limits.batchCharacters) return;
    const clipped = text.length > limits.lineCharacters ? text.slice(0, limits.lineCharacters) + '…[truncated]' : text;
    batch = (batch ? batch + '\n' : '') + clipped;
    if (batch.length > limits.batchCharacters) batch = batch.slice(0, limits.batchCharacters) + '…[truncated]';
  }
  function addChunk(chunk) {
    pending += chunk;
    // A newline-free producer must not grow memory indefinitely.
    if (pending.length > limits.pendingCharacters) pending = pending.slice(-limits.pendingCharacters);
    let newline;
    while ((newline = pending.indexOf('\n')) !== -1) {
      addLine(pending.slice(0, newline));
      pending = pending.slice(newline + 1);
    }
    if (batch && !timer) timer = setTimeout(flush, limits.batchMilliseconds);
  }
  return { addChunk, flush, dispose() { clearTimeout(timer); pending = ''; batch = ''; } };
}

export function buildRateLimit(now = Date.now) {
  let tokens = limits.burst, lastRefill = now(), suppressed = 0, firstSuppressed;
  return {
    getDecision() {
      const current = now();
      const refill = Math.floor((current - lastRefill) / limits.refillMilliseconds);
      tokens = Math.min(limits.burst, tokens + refill);
      lastRefill += refill * limits.refillMilliseconds;
      if (tokens > 0) {
        tokens--;
        const dropped = suppressed;
        suppressed = 0;
        if (refill > 3) firstSuppressed = undefined;
        return { allowed: true, dropped, stop: false };
      }
      suppressed++;
      firstSuppressed ??= current;
      return { allowed: false, dropped: 0, stop: current - firstSuppressed >= limits.floodMilliseconds };
    },
    getSuppressed() { return suppressed; },
  };
}

function removeProcessGroup(child, signal) {
  if (!child.pid) return;
  try { process.kill(-child.pid, signal); }
  catch (error) {
    if (error.code !== 'ESRCH') return `Could not send ${signal} to process group ${child.pid}: ${error.code ?? error.message}`;
  }
}

export async function buildMonitor(input, cwd, onEvent) {
  const settings = validateMonitorInput(input);
  const state = { id: randomUUID(), description: settings.description, command: settings.command,
    status: 'running', startedAt: new Date().toISOString(), pid: undefined, events: 0, stderr: '' };
  const child = spawn('/bin/bash', ['--noprofile', '--norc', '-o', 'pipefail', '-c', settings.command], {
    cwd, detached: true, stdio: ['ignore', 'pipe', 'pipe'],
  });
  const rateLimit = buildRateLimit();
  let deadline, killTimer, stopDeadline, stoppedAs, closed = false, quiet = false;
  let finishDone;
  const done = new Promise(doneCallback => { finishDone = doneCallback; });
  function addEvent(kind, text, extra = {}) {
    if (quiet) return;
    onEvent({ monitorId: state.id, description: state.description, kind, text, ...extra });
  }
  function removeGroup(signal) {
    const error = removeProcessGroup(child, signal);
    if (error) state.cleanupError = error;
  }
  function stop(reason = 'stopped', silently = false) {
    quiet ||= silently;
    if (closed || stoppedAs) return done;
    stoppedAs = reason;
    removeGroup('SIGTERM');
    killTimer = setTimeout(() => removeGroup('SIGKILL'), 1000);
    stopDeadline = setTimeout(() => {
      state.cleanupError ??= `Process group ${child.pid} did not close after SIGKILL; cleanup is unconfirmed.`;
      child.stdout.destroy();
      child.stderr.destroy();
      child.unref();
      addTerminalEvent(null, null);
    }, 2000);
    return done;
  }
  function addBatch(text) {
    if (closed || quiet) return;
    const decision = rateLimit.getDecision();
    if (!decision.allowed) {
      if (decision.stop) void stop('output_limit');
      return;
    }
    state.events++;
    addEvent('output', text, { suppressed: decision.dropped });
    if (state.events >= limits.maximumEvents) void stop('event_limit');
  }
  const buffer = buildLineBuffer(addBatch);
  child.stdout.setEncoding('utf8');
  child.stderr.setEncoding('utf8');
  child.stdout.on('data', buffer.addChunk);
  child.stderr.on('data', chunk => { state.stderr = (state.stderr + chunk).slice(-limits.stderrCharacters); });
  // Even a successful shell can leave background children holding pipes open.
  child.on('exit', () => removeGroup('SIGKILL'));
  function addTerminalEvent(code, signal) {
    if (closed) return;
    clearTimeout(deadline);
    buffer.flush(true);
    clearTimeout(killTimer);
    clearTimeout(stopDeadline);
    closed = true;
    buffer.dispose();
    state.status = state.cleanupError ? 'cleanup_failed' : stoppedAs ?? (code === 0 ? 'exited' : 'failed');
    state.exitCode = code;
    state.signal = signal;
    state.endedAt = new Date().toISOString();
    if (quiet && state.cleanupError) console.error(`[pi-monitor] ${state.cleanupError}`);
    try {
      addEvent(state.status, `Monitor ${state.status}; exit code ${code ?? 'none'}, signal ${signal ?? 'none'}.`, {
        exitCode: code, signal, events: state.events, suppressed: rateLimit.getSuppressed(), stderr: state.stderr,
        ...(state.cleanupError && { cleanupError: state.cleanupError }),
      });
    } finally { finishDone(); }
  }
  child.on('close', addTerminalEvent);
  await new Promise((ready, reject) => {
    child.once('spawn', ready);
    child.once('error', error => { quiet = true; reject(new Error(`Monitor could not start: ${error.message}`)); });
  });
  state.pid = child.pid;
  if (!closed) deadline = setTimeout(() => { void stop('timeout'); }, settings.timeout_ms);
  return { state, done, stop };
}
