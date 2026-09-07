import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
import { join } from 'node:path';
import test from 'node:test';
import { createContext, SourceTextModule, SyntheticModule } from 'node:vm';

const source = stripTypeScriptTypes(readFileSync(new URL('../extensions/image-router/index.ts', import.meta.url), 'utf8'));
const primary = { provider: 'primary', id: 'text', input: ['text'] };
const approved = { provider: 'approved', id: 'vision', input: ['image'] };
const other = { provider: 'other', id: 'vision', input: ['image'] };
const image = { type: 'image', data: 'synthetic-image', mimeType: 'image/png' };

// Exercise the actual registered handlers. Only SDK, filesystem, and TUI seams
// are replaced; no network request or real user preference file is accessed.
async function getRouter({ preference, defaults = {}, hasUI = false, choice = 'route-once', failure, missingAuth = false, model = primary, settings = [], missingAfterLookup = Infinity } = {}) {
  const requests = [];
  const authRequests = [];
  const handlers = new Map();
  const commands = new Map();
  let saved;
  let lookups = 0;
  class Component {
    addChild() {}
    render() { return []; }
    invalidate() {}
  }
  class Selection extends Component {
    constructor(items) { super(); this.items = items; }
    handleInput() {
      if (choice === 'cancel') this.onCancel();
      else this.onSelect(this.items.find(item => item.value === choice));
    }
  }
  class Settings extends Component {
    constructor(_items, _height, _theme, change, done) {
      super();
      for (const [key, value] of settings) change(key, value);
      done();
    }
  }
  const context = createContext({ console, process: { env: {} } });
  const modules = {
    '@mariozechner/pi-coding-agent': {
      DynamicBorder: Component, getAgentDir: () => '/virtual', getSettingsListTheme: () => ({}),
    },
    '@mariozechner/pi-ai': {
      complete: async (destination, payload) => {
        requests.push({ destination, payload });
        if (failure) throw failure;
        return { content: [{ type: 'text', text: 'Synthetic description' }] };
      },
    },
    '@mariozechner/pi-tui': { Container: Component, Text: Component, SelectList: Selection, SettingsList: Settings },
    'node:fs': {
      existsSync: () => true, mkdirSync() {},
      readFileSync: () => JSON.stringify({ ...defaults, modelPrefs: preference ? { 'primary/text': preference } : {} }),
      writeFileSync: (_path, text) => { saved = JSON.parse(text); },
    },
    'node:path': { join },
  };
  const extension = new SourceTextModule(source, { context });
  await extension.link(async name => {
    assert.ok(modules[name], `Unexpected dependency: ${name}`);
    const exports = modules[name];
    return new SyntheticModule(Object.keys(exports), function () {
      for (const [key, value] of Object.entries(exports)) this.setExport(key, value);
    }, { context });
  });
  await extension.evaluate();
  await extension.namespace.default({
    on: (name, callback) => handlers.set(name, callback),
    registerCommand: (name, command) => commands.set(name, command),
  });
  const controller = new AbortController();
  const extensionContext = {
    model, hasUI, signal: controller.signal,
    modelRegistry: {
      getAvailable: () => [other, approved],
      find: (provider, id) => lookups++ >= missingAfterLookup ? undefined
        : [approved, other].find(candidate => candidate.provider === provider && candidate.id === id),
      getApiKeyAndHeaders: async destination => {
        authRequests.push(destination.provider);
        return missingAuth ? { ok: false } : { ok: true, apiKey: 'synthetic-key' };
      },
    },
    sessionManager: { getBranch: () => [] },
    ui: {
      notify() {},
      custom: factory => new Promise(done => {
        const component = factory({ requestRender() {} }, { fg: (_color, text) => text, bold: text => text }, {}, done);
        if (!settings.length) component.handleInput('enter');
      }),
    },
  };
  return {
    requests, authRequests, controller, getSaved: () => saved,
    input: (inputSource = 'interactive') => handlers.get('input')({ images: [image], text: 'Explain the image', source: inputSource }, extensionContext),
    tool: () => handlers.get('tool_result')({ toolName: 'read', content: [{ type: 'text', text: 'Original text' }, image] }, extensionContext),
    settings: () => commands.get('image-router').handler('', extensionContext),
  };
}

for (const inputSource of ['rpc', 'extension', 'interactive']) {
  test(`unapproved ${inputSource} input never contacts a provider`, async () => {
    const router = await getRouter({ hasUI: inputSource !== 'interactive' });
    assert.match((await router.input(inputSource)).text, /approval is required/);
    assert.equal(router.authRequests.length, 0);
    assert.equal(router.requests.length, 0);
  });
}

test('tool ask mode preserves original text and withholds images', async () => {
  const router = await getRouter({ hasUI: true });
  const result = await router.tool();
  assert.equal(result.content[0].text, 'Original text');
  assert.match(result.content[1].text, /approval is required/);
  assert.equal(result.content.some(block => block.type === 'image'), false);
  assert.equal(router.authRequests.length, 0);
});

for (const preference of [
  { mode: 'auto' },
  { mode: 'auto', lastSuccessfulVisionProvider: 'other', lastSuccessfulVisionModelId: 'vision' },
  { mode: 'auto', visionProvider: 'missing', visionModelId: 'vision' },
  { mode: 'auto', visionProvider: 'approved' },
]) {
  test(`auto requires a complete available explicit destination: ${JSON.stringify(preference)}`, async () => {
    const defaults = preference.visionProvider ? { defaultVisionProvider: 'other', defaultVisionModelId: 'vision' } : {};
    const router = await getRouter({ preference, defaults });
    assert.match((await router.input()).text, /No approved vision model/);
    await router.tool();
    assert.equal(router.authRequests.length, 0);
  });
}

for (const options of [{}, { failure: new Error('provider failed') }, { missingAuth: true }]) {
  test(`only the explicit target is attempted: ${JSON.stringify(options)}`, async () => {
    const router = await getRouter({ ...options, preference: {
      mode: 'auto', visionProvider: 'approved', visionModelId: 'vision',
      lastSuccessfulVisionProvider: 'other', lastSuccessfulVisionModelId: 'vision',
    }, defaults: { defaultVisionProvider: 'other', defaultVisionModelId: 'vision' } });
    await router.input('rpc');
    await router.tool();
    assert.deepEqual(router.authRequests, ['approved', 'approved']);
    assert.ok(router.requests.every(request => request.destination.provider === 'approved'));
    assert.equal(router.requests.length, options.missingAuth ? 0 : 2);
  });
}

test('one-time approval does not grant future tool or RPC consent', async () => {
  const router = await getRouter({ hasUI: true });
  assert.match((await router.input()).text, /Synthetic description/);
  await router.tool();
  await router.input('rpc');
  assert.equal(router.requests.length, 1);
  assert.equal(router.getSaved().modelPrefs['primary/text'].mode, 'ask');
});

test('always approval persists the displayed destination for later tools', async () => {
  const router = await getRouter({ hasUI: true, choice: 'route-always' });
  await router.input();
  await router.tool();
  assert.equal(router.requests.length, 2);
  assert.equal(router.getSaved().modelPrefs['primary/text'].visionProvider, router.requests[0].destination.provider);
});

test('cancel and never preserve original routing behavior without secondary requests', async () => {
  for (const options of [{ hasUI: true, choice: 'cancel' }, { preference: { mode: 'never' } }, { model: approved }]) {
    const router = await getRouter(options);
    assert.equal((await router.input()).action, 'continue');
    assert.equal(router.requests.length, 0);
  }
});

test('aborted auto routing performs no authentication or delivery', async () => {
  const router = await getRouter({ preference: { mode: 'auto', visionProvider: 'approved', visionModelId: 'vision' } });
  router.controller.abort();
  await router.input();
  assert.equal(router.authRequests.length, 0);
  assert.equal(router.requests.length, 0);
});

test('configured global destination supports auto input and tools', async () => {
  const router = await getRouter({ preference: { mode: 'auto' },
    defaults: { defaultVisionProvider: 'approved', defaultVisionModelId: 'vision' } });
  await router.input('rpc');
  await router.tool();
  assert.deepEqual(router.authRequests, ['approved', 'approved']);
});

test('interactive approval ignores last-success history', async () => {
  const router = await getRouter({ hasUI: true, preference: {
    mode: 'ask', visionProvider: 'approved', visionModelId: 'vision',
    lastSuccessfulVisionProvider: 'other', lastSuccessfulVisionModelId: 'vision',
  } });
  await router.input();
  assert.deepEqual(router.authRequests, ['approved']);
});

test('destination disappearing during approval does not authorize a replacement', async () => {
  const router = await getRouter({ hasUI: true, missingAfterLookup: 1,
    defaults: { defaultVisionProvider: 'approved', defaultVisionModelId: 'vision' } });
  assert.match((await router.input()).text, /no longer available/);
  assert.equal(router.authRequests.length, 0);
});

test('settings can replace a stale per-model choice without losing routing mode', async () => {
  const router = await getRouter({ preference: { mode: 'auto', visionProvider: 'missing', visionModelId: 'vision' },
    settings: [['vision:primary/text', 'approved/vision']] });
  await router.settings();
  await router.tool();
  assert.deepEqual(router.authRequests, ['approved']);
  assert.equal(router.getSaved().modelPrefs['primary/text'].mode, 'auto');
});
