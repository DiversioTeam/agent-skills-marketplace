import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { createServer } from 'node:http';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import test from 'node:test';

const packageDirectory = process.env.PI_MONITOR_TEST_PACKAGE || fileURLToPath(new URL('../', import.meta.url));
const binary = process.env.PI_TEST_BINARY || 'pi';
const proofDirectory = process.env.PI_MONITOR_PROOF_DIR;
const hostVersion = spawnSync(binary, ['--version'], { encoding: 'utf8' }).stdout.trim();
const [majorVersion, minorVersion] = hostVersion.split('.').map(Number);
const supportedHost = majorVersion > 1 || (majorVersion === 1 && minorVersion >= 1);
function testSupported(name, options, callback) { return test(name, { ...options, skip: !supportedHost }, callback); }
const quote = text => `'${text.replaceAll("'", "'\\''")}'`;

// `script(payload, index)` replaces the default replies: { delay, text } or { delay, calls: [{ name, arguments }] }.
async function buildFixture(context, name, { command, allow = true, confirm = false, slowReply = false, timeout_ms = 5000, treeHelper = false, delayedEndHelper = false, slowCompaction = false, tools = 'monitor,monitor_list,monitor_stop', script }) {
  const directory = await mkdtemp(join(tmpdir(), 'pi-monitor-rpc-'));
  const agentDirectory = join(directory, 'agent');
  await mkdir(agentDirectory);
  if (slowCompaction) await writeFile(join(agentDirectory, 'settings.json'), JSON.stringify({
    compaction: { enabled: true, keepRecentTokens: 100, reserveTokens: 1024 },
  }));
  const records = [], requests = [];
  let stderr = '', initialCallSent = false, sequence = 0;
  const server = createServer(async (request, response) => {
    let body = '';
    for await (const chunk of request) body += chunk;
    const payload = JSON.parse(body);
    requests.push(payload);
    response.writeHead(200, { 'Content-Type': 'text/event-stream' });
    const send = (delta, finish_reason = null) => response.write(`data: ${JSON.stringify({
      id: `reply-${requests.length}`, object: 'chat.completion.chunk', created: 1, model: 'monitor-test',
      choices: [{ index: 0, delta, finish_reason }],
    })}\n\n`);
    if (script) {
      const reply = script(payload, requests.length);
      if (reply.delay) await delay(reply.delay);
      if (reply.calls) {
        send({ role: 'assistant', tool_calls: reply.calls.map((call, index) => ({ index, id: `call-${requests.length}-${index}`,
          type: 'function', function: { name: call.name, arguments: JSON.stringify(call.arguments) } })) });
        send({}, 'tool_calls');
      } else {
        send({ role: 'assistant', content: reply.text });
        send({}, 'stop');
      }
    } else if (slowCompaction && requests.length === 3) {
      send({ role: 'assistant', content: '## Goal\nVerify monitor cleanup during compaction.\n## Progress\nThe monitor was stopped before compaction.' });
      await delay(750);
      send({}, 'stop');
    } else if (!initialCallSent) {
      initialCallSent = true;
      send({ role: 'assistant', tool_calls: [{ index: 0, id: 'start-monitor', type: 'function', function: {
        name: 'monitor', arguments: JSON.stringify({ command, description: name, timeout_ms }),
      } }] });
      send({}, 'tool_calls');
    } else {
      const receivedEvent = JSON.stringify(payload.messages).includes('Background monitor event');
      send({ role: 'assistant', content: receivedEvent ? `OBSERVED-${name}` : `WORKING-${name}` });
      if (slowReply && requests.length === 2) await delay(1300);
      send({}, 'stop');
    }
    response.end('data: [DONE]\n\n');
  });
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  await writeFile(join(agentDirectory, 'models.json'), JSON.stringify({ providers: { 'monitor-test': {
    baseUrl: `http://127.0.0.1:${server.address().port}/v1`, api: 'openai-completions', apiKey: 'test-only',
    models: [{ id: 'monitor-test', name: 'Deterministic test server', reasoning: false, input: ['text'],
      contextWindow: 200000, maxTokens: 2000, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } }],
  } } }));
  const helperPath = join(directory, 'tree-helper.mjs');
  if (treeHelper) await writeFile(helperPath, `export default pi => pi.registerCommand('fixture-tree', {
    handler: async (_arguments, context) => {
      await context.abort();
      await context.waitForIdle();
      const target = context.sessionManager.getBranch().find(entry => entry.type === 'message' && entry.message.role === 'user');
      await context.navigateTree(target.id, { summarize: false });
    }
  });`);
  const delayedEndPath = join(directory, 'delayed-end.mjs');
  if (delayedEndHelper) await writeFile(delayedEndPath, `export default pi => pi.on('agent_end',
    () => new Promise(done => setTimeout(done, 200)));`);
  const child = spawn(binary, ['--mode', 'rpc', '--no-session', '--no-context-files', '--no-extensions',
    '-e', packageDirectory, ...(treeHelper ? ['-e', helperPath] : []),
    ...(delayedEndHelper ? ['-e', delayedEndPath] : []), '--no-prompt-templates', '--no-skills', '--provider', 'monitor-test', '--model', 'monitor-test',
    '--tools', tools, ...(allow ? ['--monitor-allow-commands'] : [])], {
    cwd: directory, env: { ...process.env, PI_CODING_AGENT_DIR: agentDirectory, PI_OFFLINE: '1', PI_TELEMETRY: '0' },
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  child.stderr.setEncoding('utf8');
  child.stderr.on('data', chunk => { stderr += chunk; });
  let pending = '';
  child.stdout.setEncoding('utf8');
  child.stdout.on('data', chunk => {
    pending += chunk;
    let newline;
    while ((newline = pending.indexOf('\n')) !== -1) {
      const line = pending.slice(0, newline);
      pending = pending.slice(newline + 1);
      if (!line) continue;
      const record = JSON.parse(line);
      records.push({ ...record, proofReceivedAt: Date.now() });
      if (record.type === 'extension_ui_request' && record.method === 'confirm' && confirm !== null) {
        child.stdin.write(JSON.stringify({ type: 'extension_ui_response', id: record.id, confirmed: confirm }) + '\n');
      }
    }
  });
  async function waitFor(predicate, label, milliseconds = 15000) {
    const deadline = Date.now() + milliseconds;
    while (Date.now() < deadline) {
      const found = predicate();
      if (found) return found;
      if (child.exitCode !== null) throw new Error(`Pi exited before ${label}: ${stderr}`);
      await delay(20);
    }
    throw new Error(`Timed out: ${label}\n${stderr}\n${JSON.stringify(records.slice(-5))}`);
  }
  async function sendCommand(type, extra = {}) {
    const id = `request-${++sequence}`;
    child.stdin.write(JSON.stringify({ id, type, ...extra }) + '\n');
    const response = await waitFor(() => records.find(record => record.type === 'response' && record.id === id), type);
    assert.equal(response.success, true, JSON.stringify(response));
    return response;
  }
  async function shutdown() {
    if (child.exitCode !== null) return;
    child.stdin.end();
    await Promise.race([once(child, 'exit'), delay(5000).then(() => {
      if (child.exitCode === null) { child.kill('SIGKILL'); throw new Error('Pi did not shut down cleanly'); }
    })]);
  }
  context.after(async () => {
    await shutdown();
    server.closeAllConnections();
    await new Promise(done => server.close(done));
    if (proofDirectory) {
      await mkdir(proofDirectory, { recursive: true });
      await writeFile(join(proofDirectory, `${name}.json`), JSON.stringify({
        binary, version: spawnSync(binary, ['--version'], { encoding: 'utf8' }).stdout.trim(),
        records, requests, stderr,
      }, null, 2));
    }
    await rm(directory, { recursive: true, force: true });
  });
  return { directory, records, requests, sendCommand, waitFor, shutdown };
}

function getToolResult(fixture) {
  return fixture.records.find(record => record.type === 'tool_execution_end' && record.toolName === 'monitor');
}
function getMonitorMessages(fixture) {
  return fixture.records.filter(record => record.type === 'message_end' && record.message?.customType === 'monitor-event');
}
function getMonitorEvents(fixture) {
  return getMonitorMessages(fixture).flatMap(({ message: { details } }) => Array.isArray(details.events) ? details.events : [details]);
}
function getRequestHasEvent(request, text = '') {
  return request.messages.some(message => {
    const content = JSON.stringify(message.content);
    return content.includes('Background monitor event') && content.includes(text);
  });
}
function getMonitorId(payload) {
  const result = payload.messages.find(message => message.role === 'tool' && JSON.stringify(message.content).includes('\\"status\\":\\"running\\"'));
  return JSON.parse(typeof result.content === 'string' ? result.content : result.content[0].text).id;
}

testSupported('real Pi loads the package, runs its tool, queues events while busy, then sends them to the provider', { timeout: 30000 }, async context => {
  const fixture = await buildFixture(context, 'stream-proof', {
    command: 'sleep 0.8; printf "NONCE-stream-59142\\n"; sleep 1.4; printf "SECOND-stream-59142\\n"', slowReply: true,
  });
  const discovery = await fixture.sendCommand('get_commands');
  assert.ok(discovery.data.commands.some(command => command.name === 'monitors'));
  await fixture.sendCommand('prompt', { message: 'Run the test monitor.' });
  const started = await fixture.waitFor(() => getToolResult(fixture), 'monitor tool result');
  assert.equal(started.isError, false, JSON.stringify(started));
  assert.equal(started.result.details.status, 'running');
  await fixture.waitFor(() => getMonitorEvents(fixture).some(event => event.kind === 'exited'), 'exit notification');
  await fixture.waitFor(() => fixture.requests.some(request => request.messages.some(message => {
    const content = JSON.stringify(message.content);
    return content.includes('Background monitor event') && content.includes('NONCE-stream-59142');
  })), 'provider receipt of event, not just the original command');
  await fixture.waitFor(() => fixture.records.some(record => record.type === 'message_end' && record.message?.role === 'assistant'
    && JSON.stringify(record.message.content).includes('OBSERVED-stream-proof')), 'provider follow-up response');
  const workingEnd = fixture.records.findIndex(record => record.type === 'message_end' && record.message?.role === 'assistant'
    && JSON.stringify(record.message.content).includes('WORKING-stream-proof'));
  const outputIndex = fixture.records.findIndex(record => record.type === 'message_end' && record.message?.customType === 'monitor-event');
  assert.ok(outputIndex > workingEnd, 'follow-up delivered after the busy response finished');
  assert.ok(fixture.records[outputIndex].message.details.events[0].observedAt < fixture.records[workingEnd].proofReceivedAt,
    'event observed while the busy response was still streaming');
  assert.equal(fixture.records.filter(record => record.type === 'tool_execution_start').length, 1, 'no tool polling');
  assert.ok(getMonitorEvents(fixture).every(event => event.monitorId === started.result.details.id));
  assert.equal(getMonitorEvents(fixture).filter(event => event.kind === 'exited').length, 1);
  assert.equal(fixture.records.some(record => record.type === 'extension_error'), false);
});

testSupported('buffered finite output is delivered after another extension delays agent_end', { timeout: 30000 }, async context => {
  const fixture = await buildFixture(context, 'delayed-end-proof', {
    command: 'sleep 0.2; printf "DELAYED-END-NONCE\\\\n"', slowReply: true, delayedEndHelper: true,
  });
  await fixture.sendCommand('prompt', { message: 'Run a finite monitor while another extension delays idle.' });
  await fixture.waitFor(() => getMonitorEvents(fixture).some(event => event.kind === 'exited'), 'delayed terminal delivery');
  assert.ok(getMonitorEvents(fixture).some(event => event.text === 'DELAYED-END-NONCE'));
  await fixture.waitFor(() => fixture.requests.some(request => request.messages.some(message =>
    JSON.stringify(message.content).includes('Background monitor event'))), 'delayed provider receipt');
});

testSupported('real RPC approval denial prevents command execution', { timeout: 30000 }, async context => {
  const marker = join(tmpdir(), `pi-monitor-denied-${process.pid}-${Date.now()}`);
  const fixture = await buildFixture(context, 'denial-proof', { command: `printf forbidden > ${quote(marker)}`, allow: false });
  await fixture.sendCommand('prompt', { message: 'Request a monitor, then deny it.' });
  const result = await fixture.waitFor(() => getToolResult(fixture), 'denied tool');
  assert.equal(result.isError, true);
  assert.match(JSON.stringify(result), /not approved/);
  await assert.rejects(readFile(marker), { code: 'ENOENT' });
  assert.equal(getMonitorEvents(fixture).length, 0);
  assert.ok(fixture.records.some(record => record.type === 'extension_ui_request' && record.method === 'confirm'));
});

testSupported('real RPC confirmation allows a command without the blanket launch flag', { timeout: 30000 }, async context => {
  const fixture = await buildFixture(context, 'approval-proof', { command: 'printf "approved-proof\\n"', allow: false, confirm: true });
  await fixture.sendCommand('prompt', { message: 'Approve this safe monitor.' });
  const result = await fixture.waitFor(() => getToolResult(fixture), 'approved tool');
  assert.equal(result.isError, false);
  await fixture.waitFor(() => getMonitorEvents(fixture).some(event => event.kind === 'exited'), 'approved exit');
  assert.ok(getMonitorEvents(fixture).some(event => event.text === 'approved-proof'));
});

testSupported('real Pi delivers timeout and removes the process', { timeout: 30000 }, async context => {
  const fixture = await buildFixture(context, 'timeout-proof', { command: 'sleep 60', timeout_ms: 1000 });
  await fixture.sendCommand('prompt', { message: 'Start a monitor that expires.' });
  const result = await fixture.waitFor(() => getToolResult(fixture), 'timeout tool');
  await fixture.waitFor(() => getMonitorEvents(fixture).some(event => event.kind === 'timeout'), 'timeout event');
  assert.throws(() => process.kill(result.result.details.pid, 0), { code: 'ESRCH' });
});

testSupported('real Pi stop command and session replacement kill tasks without stale events', { timeout: 30000 }, async context => {
  const fixture = await buildFixture(context, 'session-proof', { command: 'sleep 60' });
  await fixture.sendCommand('prompt', { message: 'Start a session-owned monitor.' });
  const result = await fixture.waitFor(() => getToolResult(fixture), 'session monitor');
  await fixture.waitFor(() => fixture.records.some(record => record.type === 'agent_end'), 'initial run idle');
  await fixture.sendCommand('new_session');
  assert.throws(() => process.kill(result.result.details.pid, 0), { code: 'ESRCH' });
  assert.equal(getMonitorEvents(fixture).length, 0, 'no old-session terminal message');
  await fixture.sendCommand('prompt', { message: '/monitors' });
  const status = fixture.records.find(record => record.type === 'message_end' && record.message?.customType === 'monitor-status');
  assert.ok(status);
  assert.deepEqual(status.message.details, []);
});

testSupported('aborting an unanswered RPC approval returns promptly and starts no process', { timeout: 30000 }, async context => {
  const fixture = await buildFixture(context, 'abort-approval-proof', { command: 'printf forbidden', allow: false, confirm: null });
  await fixture.sendCommand('prompt', { message: 'Ask for approval, then abort.' });
  await fixture.waitFor(() => fixture.records.some(record => record.type === 'extension_ui_request' && record.method === 'confirm'), 'unanswered approval');
  const start = Date.now();
  await fixture.sendCommand('abort');
  assert.ok(Date.now() - start < 2000, 'abort must not wait for the 60-second dialog timeout');
  assert.equal(getMonitorEvents(fixture).length, 0);
  const result = getToolResult(fixture);
  assert.equal(result?.isError, true);
});

testSupported('real tree navigation discards buffered old-branch events', { timeout: 30000 }, async context => {
  const fixture = await buildFixture(context, 'tree-proof', {
    command: 'sleep 0.8; printf "OLD-BRANCH-NONCE\\\\n"; sleep 60', slowReply: true, treeHelper: true,
  });
  await fixture.sendCommand('prompt', { message: 'Start a monitor, then change the tree branch.' });
  const result = await fixture.waitFor(() => getToolResult(fixture), 'tree monitor start');
  await fixture.waitFor(() => fixture.requests.length >= 2, 'busy provider request');
  await delay(650);
  await fixture.sendCommand('prompt', { message: '/fixture-tree' });
  assert.throws(() => process.kill(result.result.details.pid, 0), { code: 'ESRCH' });
  await fixture.sendCommand('prompt', { message: 'New branch; reply without tools.' });
  await fixture.waitFor(() => fixture.records.filter(record => record.type === 'agent_end').length >= 2, 'new branch response');
  assert.equal(getMonitorEvents(fixture).length, 0, 'buffered old event did not cross the tree boundary');
  assert.equal(fixture.requests.some(request => request.messages.some(message =>
    JSON.stringify(message.content).includes('Background monitor event'))), false);
});

testSupported('slow manual compaction stops watches before summarization and never starts an unrecorded event turn', { timeout: 30000 }, async context => {
  const fixture = await buildFixture(context, 'compaction-proof', {
    command: 'sleep 0.5; printf "MUST-NOT-ARRIVE\\\\n"; sleep 60', slowCompaction: true,
  });
  await fixture.sendCommand('prompt', { message: 'Start the watch, then compact the session.' });
  const result = await fixture.waitFor(() => getToolResult(fixture), 'pre-compaction monitor');
  await fixture.waitFor(() => fixture.records.some(record => record.type === 'agent_end'), 'pre-compaction idle');
  await fixture.sendCommand('compact', { customInstructions: 'Summarize the completed setup.' });
  assert.throws(() => process.kill(result.result.details.pid, 0), { code: 'ESRCH' });
  assert.equal(getMonitorEvents(fixture).length, 0, 'no output or terminal notices injected during compaction');
  assert.ok(fixture.records.some(record => record.type === 'extension_ui_request'
    && record.method === 'notify' && record.message.includes('Compaction stopped')));
  assert.equal(fixture.requests.length, 3, 'only initial tool call, initial answer, and summary request');
  await fixture.sendCommand('prompt', { message: '/monitors' });
  const status = fixture.records.find(record => record.type === 'message_end' && record.message?.customType === 'monitor-status');
  assert.deepEqual(status.message.details, []);
});

test('unsupported old hosts reject monitor startup with an actionable upgrade error', { timeout: 30000, skip: supportedHost }, async context => {
  const fixture = await buildFixture(context, 'unsupported-host-proof', { command: 'printf forbidden' });
  await fixture.sendCommand('prompt', { message: 'Try to start a monitor on this unsupported host.' });
  const result = await fixture.waitFor(() => getToolResult(fixture), 'unsupported host error');
  assert.equal(result.isError, true);
  assert.match(JSON.stringify(result), /requires Pi 1.1.0 or newer/);
  assert.equal(getMonitorEvents(fixture).length, 0);
});

testSupported('real Pi user stop and orderly shutdown remove running process groups', { timeout: 30000 }, async context => {
  for (const action of ['stop', 'shutdown']) {
    const fixture = await buildFixture(context, `${action}-proof`, { command: 'sleep 60' });
    await fixture.sendCommand('prompt', { message: 'Start a monitor for cleanup proof.' });
    const result = await fixture.waitFor(() => getToolResult(fixture), 'cleanup monitor');
    if (action === 'stop') {
      await fixture.sendCommand('prompt', { message: '/monitors stop all' });
      await fixture.waitFor(() => getMonitorEvents(fixture).some(event => event.kind === 'stopped'), 'stop notification');
    } else await fixture.shutdown();
    assert.throws(() => process.kill(result.result.details.pid, 0), { code: 'ESRCH' });
  }
});

// Regression: session 01a14d94 slept in Bash while events waited for the whole run to end.
testSupported('a busy model receives events at its next tool boundary, inside the same run', { timeout: 30000 }, async context => {
  let monitorId;
  const fixture = await buildFixture(context, 'steer-proof', {
    command: 'sleep 0.3; printf "MID-RUN-NONCE\\n"; sleep 60', tools: 'monitor,monitor_list,monitor_stop,bash',
    script: (payload, index) => {
      if (index === 1) return { calls: [{ name: 'monitor', arguments: { command: 'sleep 0.3; printf "MID-RUN-NONCE\\n"; sleep 60', description: 'steer-proof', timeout_ms: 30000 } }] };
      monitorId ??= getMonitorId(payload);
      if (JSON.stringify(payload.messages).includes('\\"status\\":\\"stopped\\"')) return { text: 'DONE' };
      if (getRequestHasEvent(payload, 'MID-RUN-NONCE')) return { calls: [{ name: 'monitor_stop', arguments: { monitor_id: monitorId } }] };
      if (index < 6) return { calls: [{ name: 'bash', arguments: { command: 'sleep 1' } }] };
      return { text: 'DONE' };
    },
  });
  await fixture.sendCommand('prompt', { message: 'Start a watch, then keep sleeping in Bash.' });
  await fixture.waitFor(() => fixture.records.some(record => record.type === 'agent_end'), 'first run end');
  const firstEnd = fixture.records.findIndex(record => record.type === 'agent_end');
  const delivered = fixture.records.findIndex(record => record.type === 'message_end' && record.message?.customType === 'monitor-event');
  assert.ok(delivered !== -1 && delivered < firstEnd, 'event entered the context before the run ended');
  const receiving = fixture.requests.findIndex(request => getRequestHasEvent(request, 'MID-RUN-NONCE'));
  assert.equal(receiving, 2, 'the provider call right after the first Bash sleep carried the event');
  assert.equal(fixture.records.filter(record => record.type === 'tool_execution_start' && record.toolName === 'bash').length, 1);
  assert.equal(fixture.records.filter(record => record.type === 'agent_start').length, 1, 'no extra follow-up run');
});

testSupported('queued events become one message and one follow-up turn', { timeout: 30000 }, async context => {
  const command = 'sleep 0.8; for n in 1 2 3; do printf "LINE-$n\\n"; sleep 0.3; done';
  const fixture = await buildFixture(context, 'batch-proof', {
    command,
    script: (payload, index) => {
      if (index === 1) return { calls: [{ name: 'monitor', arguments: { command, description: 'batch-proof', timeout_ms: 30000 } }] };
      if (index === 2) return { delay: 2500, text: 'WORKING' };
      return { text: 'OBSERVED' };
    },
  });
  await fixture.sendCommand('prompt', { message: 'Start the watch.' });
  await fixture.waitFor(() => getMonitorEvents(fixture).some(event => event.kind === 'exited'), 'terminal event');
  await fixture.waitFor(() => fixture.records.filter(record => record.type === 'agent_end').length >= 2, 'follow-up run end');
  await delay(500);
  assert.deepEqual(getMonitorEvents(fixture).map(event => event.kind === 'output' ? event.text : event.kind), ['LINE-1', 'LINE-2', 'LINE-3', 'exited']);
  assert.equal(getMonitorMessages(fixture).length, 1, 'one message for all queued events');
  assert.equal(fixture.records.filter(record => record.type === 'agent_start').length, 2, 'one follow-up run, not four');
});

testSupported('monitor_stop discards queued output and sends no stale stop notice', { timeout: 30000 }, async context => {
  const fixture = await buildFixture(context, 'stale-stop-proof', {
    command: 'sleep 0.8; printf "BEFORE-STOP\\n"; sleep 60',
    script: (payload, index) => {
      if (index === 1) return { calls: [{ name: 'monitor', arguments: { command: 'sleep 0.8; printf "BEFORE-STOP\\n"; sleep 60', description: 'stale-stop-proof', timeout_ms: 30000 } }] };
      if (index === 2) return { delay: 1500, calls: [{ name: 'monitor_stop', arguments: { monitor_id: getMonitorId(payload) } }] };
      return { text: 'STOPPED' };
    },
  });
  await fixture.sendCommand('prompt', { message: 'Start a watch, then stop it.' });
  const stopped = await fixture.waitFor(() => fixture.records.find(record => record.type === 'tool_execution_end' && record.toolName === 'monitor_stop'), 'stop result');
  assert.equal(stopped.result.details.status, 'stopped');
  await fixture.waitFor(() => fixture.records.some(record => record.type === 'agent_end'), 'run end');
  await delay(1000);
  assert.deepEqual(getMonitorEvents(fixture), [], 'no stale output or self-caused stop notice');
  assert.equal(fixture.requests.some(request => getRequestHasEvent(request)), false);
  assert.equal(fixture.records.filter(record => record.type === 'agent_start').length, 1);
});

testSupported('a command that fails at startup returns an error with stderr, not status running', { timeout: 30000 }, async context => {
  const fixture = await buildFixture(context, 'early-failure-proof', { command: 'printf "EARLY-BOOM\\n" >&2; exit 2' });
  await fixture.sendCommand('prompt', { message: 'Start a broken watch.' });
  const result = await fixture.waitFor(() => getToolResult(fixture), 'early failure result');
  assert.equal(result.isError, true, JSON.stringify(result));
  assert.match(JSON.stringify(result.result), /exit code 2/);
  assert.match(JSON.stringify(result.result), /EARLY-BOOM/);
  await fixture.waitFor(() => fixture.records.some(record => record.type === 'agent_end'), 'run end');
  await delay(500);
  assert.deepEqual(getMonitorEvents(fixture), [], 'the failure is not repeated later as an event');
});

testSupported('a command carrying the launch flag is rejected before any approval prompt', { timeout: 30000 }, async context => {
  const fixture = await buildFixture(context, 'flag-proof', { command: '--monitor-allow-commands bash /tmp/monitor.sh', allow: false, confirm: true });
  await fixture.sendCommand('prompt', { message: 'Try to skip approval.' });
  const result = await fixture.waitFor(() => getToolResult(fixture), 'flag rejection');
  assert.equal(result.isError, true);
  assert.match(JSON.stringify(result.result), /Pi launch flag/);
  assert.equal(fixture.records.some(record => record.type === 'extension_ui_request' && record.method === 'confirm'), false);
});

testSupported('an unanswered approval reports a timeout, not a denial', { timeout: 90000 }, async context => {
  const fixture = await buildFixture(context, 'approval-timeout-proof', { command: 'printf forbidden', allow: false, confirm: null });
  await fixture.sendCommand('prompt', { message: 'Ask for approval and wait.' });
  const result = await fixture.waitFor(() => getToolResult(fixture), 'approval timeout', 75000);
  assert.equal(result.isError, true);
  assert.match(JSON.stringify(result.result), /No approval answer within 60 s/);
  assert.doesNotMatch(JSON.stringify(result.result), /not approved/);
});
