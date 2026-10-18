import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import test from 'node:test';
import { buildLineBuffer, buildMonitor, buildRateLimit, limits, validateMonitorInput } from '../lib/monitor.mjs';

const quote = text => `'${text.replaceAll("'", "'\\''")}'`;
const nodeCommand = source => `${quote(process.execPath)} -e ${quote(source)}`;

async function buildFixture(context, command, timeout_ms = 5000, cwd = tmpdir()) {
  const events = [];
  const monitor = await buildMonitor({ command, description: 'test source', timeout_ms }, cwd, event => events.push(event));
  context.after(() => monitor.stop('stopped', true));
  return { monitor, events };
}

function getProcessAlive(pid) {
  const result = spawnSync('ps', ['-o', 'stat=', '-p', String(pid)], { encoding: 'utf8' });
  return result.status === 0 && result.stdout.trim() && !result.stdout.trim().startsWith('Z');
}

test('validates command, description, platform, and finite timeout bounds', () => {
  assert.equal(validateMonitorInput({ command: 'true', description: ' valid ' }).timeout_ms, 300000);
  for (const input of [
    { command: '' }, { command: 'a\x1bb' }, { description: 'a\nb' },
    { command: 'x'.repeat(16385) }, { description: 'x'.repeat(201) },
    { timeout_ms: 0 }, { timeout_ms: 999 }, { timeout_ms: 1800001 },
    { timeout_ms: 1000.5 }, { timeout_ms: NaN }, { timeout_ms: Infinity },
  ]) assert.throws(() => validateMonitorInput({ command: 'true', description: 'test', ...input }));
});

test('line buffer batches, trims blank lines, clips long lines, and flushes a partial last line', () => {
  const batches = [];
  const buffer = buildLineBuffer(text => batches.push(text));
  buffer.addChunk(' first\n\nsecond\n' + 'x'.repeat(1000) + '\npartial');
  assert.equal(batches.length, 0);
  buffer.flush(true);
  assert.equal(batches.length, 1);
  assert.match(batches[0], /^first\nsecond\nx{500}…\[truncated\]\npartial$/u);
  buffer.dispose();
});

test('line buffer remains bounded for huge bursts and newline-free output', () => {
  const batches = [];
  const buffer = buildLineBuffer(text => batches.push(text));
  buffer.addChunk(('x'.repeat(500) + '\n').repeat(10000));
  buffer.flush();
  buffer.addChunk('y'.repeat(limits.pendingCharacters * 2));
  buffer.flush(true);
  assert.equal(batches.length, 2);
  assert.ok(batches.every(batch => batch.length <= limits.batchCharacters + 12));
  assert.match(batches[1], /^y{500}…\[truncated\]$/u);
  buffer.dispose();
});

test('200 ms timer emits completed lines without waiting for process exit', async () => {
  let output;
  const delivered = new Promise(done => { output = done; });
  const buffer = buildLineBuffer(output);
  buffer.addChunk('live\n');
  assert.equal(await delivered, 'live');
  buffer.dispose();
});

test('token bucket allows a burst of ten then one batch per two seconds', () => {
  let now = 0;
  const rate = buildRateLimit(() => now);
  for (let index = 0; index < 10; index++) assert.equal(rate.getDecision().allowed, true);
  assert.equal(rate.getDecision().allowed, false);
  now = 2000;
  assert.deepEqual(rate.getDecision(), { allowed: true, dropped: 1, stop: false });
  assert.equal(rate.getDecision().allowed, false);
  assert.equal(rate.getSuppressed(), 1);
});

test('sustained flooding requests a stop rather than allowing an endless event queue', () => {
  let now = 0;
  const rate = buildRateLimit(() => now);
  for (let index = 0; index < 11; index++) rate.getDecision();
  let stopped = false;
  for (let index = 0; index < 160; index++) {
    now += 200;
    stopped ||= rate.getDecision().stop;
  }
  assert.equal(stopped, true);
});

test('returns immediately and reports output while the child is still running', { timeout: 10000 }, async context => {
  const { monitor, events } = await buildFixture(context, 'printf "ready\\n"; sleep 1; printf "finished\\n"');
  assert.equal(monitor.state.status, 'running');
  await delay(350);
  assert.equal(monitor.state.status, 'running');
  assert.equal(events[0].text, 'ready');
  await monitor.done;
  assert.equal(monitor.state.status, 'exited');
  assert.equal(events.at(-1).exitCode, 0);
  assert.equal(events.filter(event => event.kind === 'output').map(event => event.text).join('\n'), 'ready\nfinished');
});

test('stderr does not generate output events; failure reports its bounded tail', async context => {
  const { monitor, events } = await buildFixture(context, 'printf "diagnostic\\n" >&2; exit 7');
  await monitor.done;
  assert.equal(events.length, 1);
  assert.equal(events[0].kind, 'failed');
  assert.equal(events[0].exitCode, 7);
  assert.equal(events[0].stderr, 'diagnostic\n');
});

test('pipefail exposes a failed pipeline instead of claiming success', async context => {
  const { monitor, events } = await buildFixture(context, 'false | cat');
  await monitor.done;
  assert.equal(events.at(-1).kind, 'failed');
});

test('preserves Unicode across child pipe chunk boundaries and an unterminated final line', async context => {
  const source = 'const bytes=Buffer.from("😀 final"); process.stdout.write(bytes.subarray(0,2)); setTimeout(()=>process.stdout.write(bytes.subarray(2)),30);';
  const { monitor, events } = await buildFixture(context, nodeCommand(source));
  await monitor.done;
  assert.equal(events[0].text, '😀 final');
});

test('spawn failure rejects without an unhandled error or zombie task', async () => {
  await assert.rejects(buildMonitor({ command: 'true', description: 'bad directory' }, '/no-such-pi-monitor-directory', () => {}), /could not start/);
});

test('timeout kills the shell and emits exactly one terminal event', { timeout: 10000 }, async context => {
  const { monitor, events } = await buildFixture(context, 'sleep 60', 1000);
  await monitor.done;
  assert.equal(monitor.state.status, 'timeout');
  assert.equal(events.filter(event => event.kind !== 'output').length, 1);
  assert.equal(getProcessAlive(monitor.state.pid), false);
});

test('stop is idempotent and kills a pipeline including a SIGTERM-ignoring child', { timeout: 10000 }, async context => {
  const directory = await mkdtemp(join(tmpdir(), 'pi-monitor-tree-'));
  context.after(() => rm(directory, { recursive: true, force: true }));
  const pidPath = join(directory, 'child.pid');
  const source = `require('fs').writeFileSync(${JSON.stringify(pidPath)},String(process.pid)); process.on('SIGTERM',()=>{}); setInterval(()=>{},1000);`;
  const { monitor } = await buildFixture(context, `${nodeCommand(source)} | cat`);
  await delay(250);
  const childPid = Number(await readFile(pidPath, 'utf8'));
  assert.ok(getProcessAlive(childPid));
  await Promise.all([monitor.stop(), monitor.stop()]);
  assert.equal(monitor.state.status, 'stopped');
  assert.equal(getProcessAlive(childPid), false);
  assert.equal(getProcessAlive(monitor.state.pid), false);
});

test('stop escalates to SIGKILL when the shell itself ignores SIGTERM', { timeout: 10000 }, async context => {
  const { monitor } = await buildFixture(context, "trap '' TERM; printf 'armed\\n'; sleep 60");
  await delay(250);
  await monitor.stop();
  assert.equal(monitor.state.status, 'stopped');
  assert.equal(monitor.state.signal, 'SIGKILL');
  assert.equal(getProcessAlive(monitor.state.pid), false);
});

test('a successful shell cannot leave background children holding its output pipes open', { timeout: 10000 }, async context => {
  const { monitor } = await buildFixture(context, 'sleep 60 & printf "done\\n"');
  await monitor.done;
  assert.equal(monitor.state.status, 'exited');
});

test('signal denial reports cleanup_failed without crashing or hanging the harness', { timeout: 10000 }, async context => {
  const originalKill = process.kill;
  const { monitor, events } = await buildFixture(context, 'sleep 60');
  try {
    process.kill = function (pid, signal) {
      if (pid < 0) throw Object.assign(new Error('permission denied'), { code: 'EPERM' });
      return originalKill.call(process, pid, signal);
    };
    await monitor.stop();
    assert.equal(monitor.state.status, 'cleanup_failed');
    assert.equal(events.at(-1).kind, 'cleanup_failed');
    assert.match(events.at(-1).cleanupError, /EPERM/);
  } finally {
    process.kill = originalKill;
    try { originalKill.call(process, -monitor.state.pid, 'SIGKILL'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
  }
});

test('quiet disposal removes the process without injecting stale-session output', async context => {
  const { monitor, events } = await buildFixture(context, 'sleep 60');
  await monitor.stop('stopped', true);
  assert.equal(events.length, 0);
});
