import assert from 'node:assert/strict';
import * as filesystem from 'node:fs';
import * as paths from 'node:path';
import * as operatingSystem from 'node:os';
import { stripTypeScriptTypes } from 'node:module';
import { spawn, spawnSync } from 'node:child_process';
import { createInterface } from 'node:readline';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import { createContext, SourceTextModule, SyntheticModule } from 'node:vm';
import test from 'node:test';

const packageDirectory = fileURLToPath(new URL('../', import.meta.url));
const source = stripTypeScriptTypes(filesystem.readFileSync(new URL('../extensions/skills-bridge/index.ts', import.meta.url), 'utf8'));

async function buildFixture(testContext) {
  const directory = filesystem.mkdtempSync(paths.join(operatingSystem.tmpdir(), 'skills-bridge-test-'));
  testContext.after(() => filesystem.rmSync(directory, { recursive: true, force: true }));
  const environment = { XDG_CONFIG_HOME: paths.join(directory, 'config') };
  const warnings = [];
  const context = createContext({ process: { env: environment }, console: { warn: message => warnings.push(message) } });
  const statErrors = new Map();
  const dependencies = { 'node:fs': { ...filesystem, statSync(path) {
    if (statErrors.has(path)) throw Object.assign(new Error('Cannot inspect directory'), { code: statErrors.get(path) });
    return filesystem.statSync(path);
  } }, 'node:path': paths, 'node:os': { homedir: () => directory } };
  const module = new SourceTextModule(source, { context });
  await module.link(name => {
    const dependency = dependencies[name];
    assert.ok(dependency, `Unexpected dependency: ${name}`);
    return new SyntheticModule(Object.keys(dependency), function () {
      for (const [name, value] of Object.entries(dependency)) this.setExport(name, value);
    }, { context });
  });
  await module.evaluate();
  let discover;
  module.namespace.default({ on(name, callback) { assert.equal(name, 'resources_discover'); discover = callback; } });
  function addSkill(root, relativePath, name) {
    const directory = paths.join(root, relativePath);
    filesystem.mkdirSync(directory, { recursive: true });
    filesystem.writeFileSync(paths.join(directory, 'SKILL.md'), `---\nname: ${name}\ndescription: Discovery fixture; do not execute anything.\n---\nNo actions.\n`);
    return directory;
  }
  function addRoot(name) {
    const root = paths.join(directory, name);
    addSkill(root, 'plugins/example/skills/one', 'one');
    return root;
  }
  function addConfig(value) {
    const configDirectory = paths.join(environment.XDG_CONFIG_HOME, 'pi');
    filesystem.mkdirSync(configDirectory, { recursive: true });
    filesystem.writeFileSync(paths.join(configDirectory, 'skills-bridge.json'), typeof value === 'string' ? value : JSON.stringify(value));
  }
  async function getPaths(cwd = directory, reason = 'startup') {
    return Array.from((await discover({ cwd, reason }))?.skillPaths ?? []);
  }
  return { directory, environment, warnings, statErrors, addSkill, addRoot, addConfig, getPaths };
}

function getNativeSkillNames(fixture, root, arguments_) {
  const environment = { ...process.env, PI_OFFLINE: '1', PI_TELEMETRY: '0', PI_SKILLS_PATH: root,
    XDG_CONFIG_HOME: fixture.environment.XDG_CONFIG_HOME, PI_CODING_AGENT_DIR: paths.join(fixture.directory, 'agent') };
  const result = spawnSync(process.env.PI_TEST_BINARY || 'pi', ['--mode', 'rpc', '--no-session', '--no-context-files',
    '--no-extensions', '--no-prompt-templates', '--no-skills', ...arguments_], {
    cwd: fixture.directory, env: environment, input: '{"id":"cmds","type":"get_commands"}\n', encoding: 'utf8', timeout: 30000,
  });
  assert.equal(result.status, 0, result.stderr);
  const response = result.stdout.trim().split('\n').map(line => JSON.parse(line)).find(response => response.id === 'cmds');
  assert.ok(response?.success, result.stdout);
  const skills = response.data.commands.filter(command => command.source === 'skill');
  for (const skill of skills) assert.ok(skill.sourceInfo.path.startsWith(root + paths.sep), `Wrong source for ${skill.name}: ${skill.sourceInfo.path}`);
  return skills.map(command => command.name).sort();
}

test('returns plugin skill directories, leaving recursive discovery to Pi', async context => {
  const fixture = await buildFixture(context);
  const root = fixture.addRoot('marketplace');
  fixture.addSkill(root, 'plugins/example/skills/group/two', 'two');
  fixture.addSkill(root, 'plugins/example/skills/one/references/fixture', 'not-top-level');
  filesystem.mkdirSync(paths.join(root, 'plugins/commands-only/commands'), { recursive: true });
  filesystem.mkdirSync(paths.join(root, 'plugins/not-a-directory'));
  filesystem.writeFileSync(paths.join(root, 'plugins/not-a-directory/skills'), 'not a directory');
  fixture.environment.PI_SKILLS_PATH = root;
  assert.deepEqual(await fixture.getPaths(), [paths.join(root, 'plugins/example/skills')]);
  assert.deepEqual(await fixture.getPaths(root, 'reload'), await fixture.getPaths());
});

test('environment override excludes configured and ancestor roots, including on failure', async context => {
  const fixture = await buildFixture(context);
  const ancestor = fixture.addRoot('ancestor');
  const configured = fixture.addRoot('configured');
  const override = fixture.addRoot('override');
  fixture.addConfig({ skillsPath: configured, additionalPaths: [ancestor] });
  fixture.environment.PI_SKILLS_PATH = ` ${override} `;
  assert.deepEqual(await fixture.getPaths(ancestor), [paths.join(override, 'plugins/example/skills')]);
  fixture.environment.PI_SKILLS_PATH = paths.join(fixture.directory, 'missing');
  assert.deepEqual(await fixture.getPaths(ancestor), []);
  assert.match(fixture.warnings.at(-1), /PI_SKILLS_PATH/);
});

test('config primary and additional roots retain order and normalized-path deduplication', async context => {
  const fixture = await buildFixture(context);
  const primary = fixture.addRoot('primary');
  const extra = fixture.addRoot('extra');
  fixture.addConfig({ skillsPath: primary, additionalPaths: [primary + '/.', extra, '', 2, paths.join(fixture.directory, 'missing')] });
  assert.deepEqual(await fixture.getPaths(), [primary, extra].map(root => paths.join(root, 'plugins/example/skills')));
  assert.equal(fixture.warnings.length, 3);
});

test('stale or malformed config retains the existing ancestor fallback', async context => {
  const fixture = await buildFixture(context);
  const ancestor = fixture.addRoot('ancestor');
  for (const config of ['{', 'null', '[]', { skillsPath: 42 }, { skillsPath: paths.join(fixture.directory, 'missing') }, {}]) {
    fixture.addConfig(config);
    assert.deepEqual(await fixture.getPaths(ancestor), [paths.join(ancestor, 'plugins/example/skills')]);
  }
});

test('walk-up prefers the marketplace child and uses the event cwd on every discovery', async context => {
  const fixture = await buildFixture(context);
  const monolith = fixture.addRoot('monolith');
  const marketplace = fixture.addRoot('monolith/agent-skills-marketplace');
  assert.deepEqual(await fixture.getPaths(paths.join(monolith, 'backend/deep')), [paths.join(marketplace, 'plugins/example/skills')]);
  const second = fixture.addRoot('second');
  assert.deepEqual(await fixture.getPaths(second, 'reload'), [paths.join(second, 'plugins/example/skills')]);
  assert.deepEqual(await fixture.getPaths(), []);
});

test('a disappearing ancestor candidate does not crash discovery', async context => {
  const fixture = await buildFixture(context);
  const monolith = fixture.addRoot('monolith');
  const marketplace = fixture.addRoot('monolith/agent-skills-marketplace');
  fixture.statErrors.set(paths.join(marketplace, 'plugins'), 'ENOENT');
  assert.deepEqual(await fixture.getPaths(monolith), [paths.join(monolith, 'plugins/example/skills')]);
});

test('an inaccessible ancestor stops automatic selection rather than choosing another checkout', async context => {
  const fixture = await buildFixture(context);
  const monolith = fixture.addRoot('monolith');
  const marketplace = fixture.addRoot('monolith/agent-skills-marketplace');
  fixture.statErrors.set(paths.join(marketplace, 'plugins'), 'EACCES');
  assert.deepEqual(await fixture.getPaths(monolith), []);
  assert.match(fixture.warnings.at(-1), /Cannot inspect.*Stopping ancestor discovery/);
});

test('plain skill collections still require native settings rather than a bridge root', async context => {
  const fixture = await buildFixture(context);
  fixture.addSkill(fixture.directory, 'personal/one', 'one');
  fixture.environment.PI_SKILLS_PATH = paths.join(fixture.directory, 'personal');
  assert.deepEqual(await fixture.getPaths(), []);
  assert.match(fixture.warnings.at(-1), /plugins/);
});

test('native Pi honors filtering, skill boundaries, and deep nesting', async context => {
  const fixture = await buildFixture(context);
  const root = fixture.addRoot('marketplace');
  const skillsDirectory = paths.join(root, 'plugins/example/skills');
  fixture.addSkill(root, 'plugins/example/skills/group/two', 'two');
  fixture.addSkill(root, 'plugins/example/skills/a/b/c/d/e/f/deep', 'deep');
  fixture.addSkill(root, 'plugins/example/skills/one/references/fixture', 'not-top-level');
  fixture.addSkill(root, 'plugins/example/skills/.hidden/private', 'hidden');
  fixture.addSkill(root, 'plugins/example/skills/node_modules/dependency', 'dependency');
  fixture.addSkill(root, 'plugins/example/skills/ignored', 'ignored');
  filesystem.writeFileSync(paths.join(root, '.gitignore'), 'plugins/\n');
  filesystem.writeFileSync(paths.join(skillsDirectory, '.gitignore'), 'ignored/\n');
  filesystem.writeFileSync(paths.join(skillsDirectory, 'root.md'), '---\nname: root\ndescription: Native root Markdown skill.\n---\nNo actions.\n');
  for (const arguments_ of [['-e', packageDirectory], ['--skill', skillsDirectory]]) {
    assert.deepEqual(getNativeSkillNames(fixture, root, arguments_), ['skill:deep', 'skill:one', 'skill:root', 'skill:two']);
  }
});

test('native reload replaces the configured checkout instead of retaining old skill paths', { timeout: 30000 }, async context => {
  const fixture = await buildFixture(context);
  const first = fixture.addRoot('first');
  const second = fixture.addRoot('second');
  fixture.addConfig({ skillsPath: first });
  const reloadExtension = paths.join(fixture.directory, 'reload.mjs');
  filesystem.writeFileSync(reloadExtension, 'export default pi => pi.registerCommand("fixture-reload", { handler: async (_arguments, context) => { await context.reload(); } });');
  const environment = { ...process.env, PI_OFFLINE: '1', PI_TELEMETRY: '0', PI_SKILLS_PATH: '',
    XDG_CONFIG_HOME: fixture.environment.XDG_CONFIG_HOME, PI_CODING_AGENT_DIR: paths.join(fixture.directory, 'agent') };
  const child = spawn(process.env.PI_TEST_BINARY || 'pi', ['--mode', 'rpc', '--no-session', '--no-context-files',
    '--no-extensions', '--no-prompt-templates', '--no-skills', '-e', packageDirectory, '-e', reloadExtension], {
    cwd: fixture.directory, env: environment, stdio: ['pipe', 'pipe', 'pipe'], signal: context.signal,
  });
  const exited = once(child, 'exit');
  const lines = createInterface({ input: child.stdout });
  const replies = new Map();
  let errors = '';
  child.stderr.on('data', data => { errors += data; });
  lines.on('line', line => {
    const response = JSON.parse(line);
    replies.get(response.id)?.(response);
  });
  async function getReply(id, command) {
    const reply = new Promise(done => replies.set(id, done));
    child.stdin.write(JSON.stringify({ id, ...command }) + '\n');
    const response = await Promise.race([reply, exited.then(() => { throw new Error(`Pi exited before ${id}: ${errors}`); })]);
    assert.ok(response.success, JSON.stringify(response) + errors);
    return response;
  }
  try {
    const before = await getReply('before', { type: 'get_commands' });
    assert.deepEqual(before.data.commands.filter(command => command.source === 'skill').map(command => command.sourceInfo.path),
      [paths.join(first, 'plugins/example/skills/one/SKILL.md')]);
    fixture.addConfig({ skillsPath: second });
    await getReply('reload', { type: 'prompt', message: '/fixture-reload' });
    const after = await getReply('after', { type: 'get_commands' });
    assert.deepEqual(after.data.commands.filter(command => command.source === 'skill').map(command => command.sourceInfo.path),
      [paths.join(second, 'plugins/example/skills/one/SKILL.md')]);
  } finally {
    child.kill();
    lines.close();
    await exited;
  }
});

test('real marketplace inventory matches explicit native discovery', async context => {
  const fixture = await buildFixture(context);
  const root = paths.resolve(packageDirectory, '../..');
  const native = getNativeSkillNames(fixture, root, ['--skill', paths.join(root, 'plugins')]);
  assert.ok(native.includes('skill:release-manager'));
  assert.deepEqual(getNativeSkillNames(fixture, root, ['-e', packageDirectory]), native);
});
