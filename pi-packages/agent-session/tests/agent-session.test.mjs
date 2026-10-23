import assert from 'node:assert/strict';
import * as filesystem from 'node:fs';
import * as paths from 'node:path';
import * as operatingSystem from 'node:os';
import { stripTypeScriptTypes } from 'node:module';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

// Load the extension source without a TypeScript toolchain, as the other Pi package tests do.
const directory = filesystem.mkdtempSync(paths.join(operatingSystem.tmpdir(), 'agent-session-pi-'));
const compiled = paths.join(directory, 'index.mjs');
const source = filesystem.readFileSync(new URL('../extensions/agent-session/index.ts', import.meta.url), 'utf8');
filesystem.writeFileSync(compiled, stripTypeScriptTypes(source));
const extension = await import(compiled);
const extensionDirectory = fileURLToPath(new URL('../extensions/agent-session/', import.meta.url));
const hook = extension.findHook({}, extensionDirectory);
const link = 'https://internal-share.diversio.com/session-demo-feature-x-20261023-h0123456789ab-a1b2c3.html';

test('finds the marketplace hook script beside the package', () => {
  assert.ok(hook?.endsWith('plugins/agent-session/skills/agent-session/scripts/check_pr_hook.py'));
  assert.equal(extension.findHook({}, '/nowhere/extensions/agent-session'), undefined);
});

test('blocks PR bodies without a transcript and passes the rest', () => {
  const blocked = extension.decide("gh pr create --repo DiversioTeam/demo --title T --body 'Summary only'", '/tmp', hook);
  assert.equal(blocked?.block, true);
  assert.match(blocked.reason, /agent session transcript/);
  assert.equal(extension.decide(`gh pr create --repo DiversioTeam/demo --title T --body 'See ${link}'`, '/tmp', hook), undefined);
  assert.equal(extension.decide("gh pr create --repo DiversioTeam/demo --body 'No agent session: manual hotfix'", '/tmp', hook), undefined);
  assert.equal(extension.decide('gh pr edit 7 --repo DiversioTeam/demo --add-label bug', '/tmp', hook), undefined);
  assert.equal(extension.decide('git status', '/tmp', hook), undefined);
});

test('a missing guard blocks only PR commands', () => {
  assert.equal(extension.decide('git push', '/tmp', undefined), undefined);
  assert.match(extension.decide("gh pr create --repo DiversioTeam/demo --body x", '/tmp', undefined).reason, /cannot find check_pr_hook.py/);
});

test('registers a tool_call guard for bash only', async () => {
  const handlers = {};
  extension.default({ on(name, callback) { handlers[name] = callback; } });
  assert.deepEqual(Object.keys(handlers), ['tool_call']);
  assert.equal(await handlers.tool_call({ toolName: 'read', input: { path: 'x' } }, { cwd: '/tmp' }), undefined);
  const result = await handlers.tool_call({ toolName: 'bash', input: { command: "gh pr create --repo DiversioTeam/demo --body x" } }, { cwd: '/tmp' });
  assert.equal(result?.block, true);
});
