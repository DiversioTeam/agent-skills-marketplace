// Explicit opt-in: this test uses the operator's configured model and authentication.
// It replays session 01a14d94: the model keeps working in Bash while a watch is pending.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

assert.equal(process.env.PI_MONITOR_LIVE_TEST, '1', 'Set PI_MONITOR_LIVE_TEST=1 to authorize model usage.');
const directory = await mkdtemp(join(tmpdir(), 'pi-monitor-live-busy-'));
const packageDirectory = fileURLToPath(new URL('../', import.meta.url));
const proofPath = process.env.PI_MONITOR_LIVE_PROOF || join(tmpdir(), 'pi-monitor-live-busy-proof.json');
const quote = text => `'${text.replaceAll("'", "'\\''")}'`;
const producerPath = join(directory, 'producer.mjs');
const noncePath = join(directory, 'nonce.json');
// Like a PR poll: one meaningful line, then the watch keeps running until stopped.
await writeFile(producerPath, `import { randomUUID } from 'node:crypto';
import { writeFileSync } from 'node:fs';
setTimeout(() => { const nonce = 'PI-MONITOR-BUSY-' + randomUUID();
writeFileSync(${JSON.stringify(noncePath)}, JSON.stringify({ nonce, emittedAt: Date.now() })); console.log(nonce); }, 2500);
setInterval(() => {}, 1000);\n`);
const command = `${quote(process.execPath)} ${quote(producerPath)}`;
const child = spawn(process.env.PI_TEST_BINARY || 'pi', ['--mode', 'rpc', '--no-session', '--no-context-files',
  '--no-extensions', '-e', packageDirectory, '--no-prompt-templates', '--no-skills', '--thinking', 'off',
  '--tools', 'monitor,monitor_list,monitor_stop,bash', '--monitor-allow-commands'], {
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
  const deadline = Date.now() + 180000;
  while (Date.now() < deadline) {
    const result = predicate();
    if (result) return result;
    if (child.exitCode !== null) throw new Error(`Pi exited waiting for ${label}: ${stderr}`);
    await delay(25);
  }
  throw new Error(`Timed out waiting for ${label}: ${stderr}`);
}
const indexOf = predicate => records.findIndex(predicate);
const isMonitorMessage = record => record.type === 'message_end' && record.message?.customType === 'monitor-event';
let summary, failure;
try {
  send({ id: 'state', type: 'get_state' });
  const state = await waitFor(() => records.find(record => record.id === 'state'), 'model state');
  assert.equal(state.success, true);
  send({ id: 'start', type: 'prompt', message: `Integration test of pi-monitor. First call monitor EXACTLY ONCE with command ${JSON.stringify(command)}, description "busy runtime nonce proof", timeout_ms 60000. The script will print a random nonce you cannot know in advance, a few seconds from now, and then keep running. While you wait, keep working: call bash with command "sleep 3", one call at a time, at most 6 times. Do not call monitor_list. As soon as a background monitor event with the nonce is in your context, stop sleeping, call monitor_stop for that monitor, then reply with RECEIVED followed by the complete nonce, and finish.` });
  const started = await waitFor(() => records.find(record => record.type === 'tool_execution_end' && record.toolName === 'monitor'), 'monitor tool');
  assert.equal(started.isError, false, JSON.stringify(started));
  assert.equal(started.result.details.status, 'running');
  const firstEnd = await waitFor(() => { const index = indexOf(record => record.type === 'agent_end'); return index === -1 ? 0 : index; }, 'first run end');
  const { nonce, emittedAt } = JSON.parse(await readFile(noncePath, 'utf8'));
  assert.match(nonce, /^PI-MONITOR-BUSY-[0-9a-f-]{36}$/);
  const deliveredIndex = indexOf(record => isMonitorMessage(record) && JSON.stringify(record.message.details).includes(nonce));
  assert.ok(deliveredIndex !== -1 && deliveredIndex < firstEnd, 'nonce event entered the context before the working run ended');
  const answerIndex = indexOf(record => record.type === 'message_end' && record.message?.role === 'assistant'
    && record.message.content.some(part => part.type === 'text' && part.text.includes(`RECEIVED ${nonce}`)));
  assert.ok(answerIndex > deliveredIndex && answerIndex < firstEnd, 'model repeated the nonce within the same run');
  const stopIndex = indexOf(record => record.type === 'tool_execution_end' && record.toolName === 'monitor_stop');
  assert.ok(stopIndex > deliveredIndex, 'model stopped the watch after seeing the event');
  assert.equal(records[stopIndex].result.details.status, 'stopped');
  const calls = records.filter(record => record.type === 'tool_execution_start').map(record => record.toolName);
  const bashCalls = calls.filter(name => name === 'bash').length;
  assert.ok(bashCalls < 6, 'the event cut the sleep loop short');
  assert.equal(calls.filter(name => name === 'monitor_list').length, 0, 'no list polling');
  // Old behavior: queued output plus a self-caused stop notice arrived as later follow-up runs.
  await delay(5000);
  assert.equal(records.filter(record => record.type === 'agent_start').length, 1, 'no stale follow-up run after the stop');
  assert.equal(records.filter(isMonitorMessage).length, 1, 'exactly one monitor message in the session');
  summary = { result: 'PASS', model: `${state.data.model.provider}/${state.data.model.id}`, nonce, monitorId: started.result.details.id,
    toolCalls: calls, bashCalls, nonceEmittedAt: emittedAt, eventDeliveredAt: records[deliveredIndex].proofReceivedAt,
    deliveryLatencyMs: records[deliveredIndex].proofReceivedAt - emittedAt,
    firstRunEndedAt: records[firstEnd].proofReceivedAt, agentRuns: 1, monitorMessages: 1 };
} catch (error) { failure = error; }
finally {
  child.stdin.end();
  await Promise.race([once(child, 'exit'), delay(5000).then(() => { if (child.exitCode === null) child.kill('SIGKILL'); })]);
  await writeFile(proofPath, JSON.stringify({ summary, failure: failure?.stack, records, stderr }, null, 2));
  await rm(directory, { recursive: true, force: true });
}
if (failure) throw failure;
console.log(JSON.stringify({ ...summary, proofPath }, null, 2));
