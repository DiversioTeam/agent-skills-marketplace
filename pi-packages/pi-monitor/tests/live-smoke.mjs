// Explicit opt-in: this test uses the operator's configured model and authentication.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

assert.equal(process.env.PI_MONITOR_LIVE_TEST, '1', 'Set PI_MONITOR_LIVE_TEST=1 to authorize model usage.');
const directory = await mkdtemp(join(tmpdir(), 'pi-monitor-live-'));
const packageDirectory = fileURLToPath(new URL('../', import.meta.url));
const proofPath = process.env.PI_MONITOR_LIVE_PROOF || join(tmpdir(), 'pi-monitor-live-proof.json');
const quote = text => `'${text.replaceAll("'", "'\\''")}'`;
const producerPath = join(directory, 'producer.mjs');
const noncePath = join(directory, 'nonce.txt');
await writeFile(producerPath, `import { randomUUID } from 'node:crypto';
import { writeFileSync } from 'node:fs';
setTimeout(() => { const nonce = 'PI-MONITOR-LIVE-' + randomUUID();
writeFileSync(${JSON.stringify(noncePath)}, nonce); console.log(nonce); }, 1000);\n`);
const command = `${quote(process.execPath)} ${quote(producerPath)}`;
const child = spawn(process.env.PI_TEST_BINARY || 'pi', ['--mode', 'rpc', '--no-session', '--no-context-files',
  '--no-extensions', '-e', packageDirectory, '--no-prompt-templates', '--no-skills', '--thinking', 'off',
  '--tools', 'monitor,monitor_list,monitor_stop', '--monitor-allow-commands'], {
  cwd: directory, env: { ...process.env, PI_OFFLINE: '1', PI_TELEMETRY: '0' }, stdio: ['pipe', 'pipe', 'pipe'],
});
const records = [];
let pending = '', stderr = '';
child.stdout.setEncoding('utf8');
child.stderr.setEncoding('utf8');
child.stderr.on('data', chunk => { stderr = (stderr + chunk).slice(-16000); });
child.stdout.on('data', chunk => {
  pending += chunk;
  let newline;
  while ((newline = pending.indexOf('\n')) !== -1) {
    const line = pending.slice(0, newline);
    pending = pending.slice(newline + 1);
    if (line) records.push({ ...JSON.parse(line), proofReceivedAt: Date.now() });
  }
});
function send(record) { child.stdin.write(JSON.stringify(record) + '\n'); }
async function waitFor(predicate, label) {
  const deadline = Date.now() + 120000;
  while (Date.now() < deadline) {
    const result = predicate();
    if (result) return result;
    if (child.exitCode !== null) throw new Error(`Pi exited waiting for ${label}: ${stderr}`);
    await delay(25);
  }
  throw new Error(`Timed out waiting for ${label}: ${stderr}`);
}
// One monitor-event message carries every event queued since the last delivery.
const findEvent = predicate => {
  for (const record of records) {
    if (record.type !== 'message_end' || record.message?.customType !== 'monitor-event') continue;
    const event = record.message.details.events.find(predicate);
    if (event) return { record, event };
  }
};
let summary, failure;
try {
  send({ id: 'state', type: 'get_state' });
  const state = await waitFor(() => records.find(record => record.id === 'state'), 'model state');
  assert.equal(state.success, true);
  send({ id: 'start', type: 'prompt', message: `Integration test of pi-monitor. Call monitor EXACTLY ONCE with command ${JSON.stringify(command)}, description "live runtime nonce proof", timeout_ms 10000. The script will emit a random nonce you cannot know in advance. Immediately after the tool returns, reply ARMED and finish your turn. Do not poll, sleep, list, stop, or call any other tool. When a background monitor event arrives, acknowledge it; for an output event, repeat the complete emitted nonce prefixed RECEIVED. Do not restart anything.` });
  const started = await waitFor(() => records.find(record => record.type === 'tool_execution_end' && record.toolName === 'monitor'), 'monitor tool');
  assert.equal(started.isError, false, JSON.stringify(started));
  assert.equal(started.result.details.status, 'running');
  const { record: output, event: outputEvent } = await waitFor(() => findEvent(event => event.kind === 'output'), 'runtime nonce event');
  const nonce = await readFile(noncePath, 'utf8');
  assert.equal(outputEvent.text, nonce);
  assert.match(nonce, /^PI-MONITOR-LIVE-[0-9a-f-]{36}$/);
  await waitFor(() => records.some(record => record.type === 'message_end' && record.message?.role === 'assistant'
    && JSON.stringify(record.message.content).includes(nonce)), 'real model acknowledgement of nonce');
  await waitFor(() => findEvent(event => event.kind === 'exited' && event.exitCode === 0), 'successful terminal event');
  const calls = records.filter(record => record.type === 'tool_execution_start');
  assert.deepEqual(calls.map(record => record.toolName), ['monitor'], 'no polling or extra tools');
  assert.ok(started.proofReceivedAt < output.proofReceivedAt, 'tool returned before the output arrived');
  summary = { result: 'PASS', model: state.data.model, nonce, monitorId: started.result.details.id,
    toolCalls: calls.length, toolReturnedAt: started.proofReceivedAt, outputDeliveredAt: output.proofReceivedAt };
} catch (error) { failure = error; }
finally {
  child.stdin.end();
  await Promise.race([once(child, 'exit'), delay(5000).then(() => { if (child.exitCode === null) child.kill('SIGKILL'); })]);
  await writeFile(proofPath, JSON.stringify({ summary, failure: failure?.stack, records, stderr }, null, 2));
  await rm(directory, { recursive: true, force: true });
}
if (failure) throw failure;
console.log(JSON.stringify({ ...summary, proofPath }, null, 2));
