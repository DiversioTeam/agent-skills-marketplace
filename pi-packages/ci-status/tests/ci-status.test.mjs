import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
import { join } from 'node:path';
import { BlockList, isIP } from 'node:net';
import { EventEmitter } from 'node:events';
import { Readable } from 'node:stream';
import test from 'node:test';
import { createContext, SourceTextModule, SyntheticModule } from 'node:vm';

const source = stripTypeScriptTypes(readFileSync(new URL('../extensions/ci-status/index.ts', import.meta.url), 'utf8'), { mode: 'transform' });
const currentSha = 'a'.repeat(40);
const otherSha = 'b'.repeat(40);

function buildCheck(repository, jobNumber, name = 'test') {
  return { __typename: 'CheckRun', name, workflowName: 'Checks', status: 'COMPLETED', conclusion: 'FAILURE',
    detailsUrl: `https://github.com/${repository}/actions/runs/10/job/${jobNumber}` };
}

function buildRepository(repository = 'team/first') {
  return { repository, sha: currentSha, branch: 'topic',
    checks: [buildCheck(repository, 101), buildCheck(repository, 102)],
    runJobs: [{ databaseId: 101, name: 'test', conclusion: 'failure' }, { databaseId: 102, name: 'test', conclusion: 'failure' }],
    runs: [],
  };
}

// Exercise registered tools/commands and their shared log reader without network,
// shell execution, credentials, filesystem writes, or UI side effects.
async function getExtension(repositories = { '/first': buildRepository() }, fetchResponse,
  getAddresses = () => [{ address: '93.184.216.34', family: 4 }], lookupAll = true) {
  const requests = [];
  const commands = new Map();
  const tools = new Map();
  const notices = [];
  const network = [];
  const lookups = [];
  const context = createContext({
    console, URL, AbortSignal, setTimeout: () => 0, clearTimeout() {},
    process: { env: { PI_CI_AUTO_WATCH: '0', CIRCLECI_TOKEN: fetchResponse ? 'synthetic-token' : '' } },
    fetch: async (url, options) => {
      network.push({ url, options });
      assert.ok(fetchResponse, 'Unexpected network request');
      return fetchResponse(url, options);
    },
  });
  class Component {}
  const dependencies = {
    '@mariozechner/pi-coding-agent': { DynamicBorder: Component },
    '@mariozechner/pi-tui': { Container: Component, Key: {}, matchesKey: () => false, SelectList: Component,
      Spacer: Component, Text: Component, truncateToWidth: text => text, visibleWidth: text => text.length },
    typebox: { Type: new Proxy({}, { get: () => () => ({}) }) },
    'node:fs/promises': { access: async path => { if (!repositories[path.replace(/\/.local-ci.toml$/, '')]?.localConfigured) throw Object.assign(new Error('ENOENT'), { code: 'ENOENT' }); }, writeFile() { assert.fail('Unexpected file write'); }, unlink() { assert.fail('Unexpected file deletion'); } },
    'node:net': { BlockList, isIP },
    'node:dns': { lookup: (hostname, _options, callback) => {
      lookups.push(hostname);
      queueMicrotask(() => {
        const addresses = getAddresses(hostname);
        callback(addresses instanceof Error ? addresses : null, addresses instanceof Error ? undefined : addresses);
      });
    } },
    'node:https': { get: (url, options, callback) => {
      const request = new EventEmitter();
      options.lookup(new URL(url).hostname, { all: lookupAll }, (error, address, family) => {
        if (error) { request.emit('error', error); return; }
        const addresses = Array.isArray(address) ? address : [{ address, family }];
        network.push({ url, options, addresses });
        Promise.resolve().then(async () => {
          const response = await fetchResponse(url, options);
          const stream = Readable.from([await response.text()]);
          stream.statusCode = response.status;
          callback(stream);
        }).catch(error => request.emit('error', error));
      });
      return request;
    } },
    'node:os': { tmpdir: () => '/virtual' },
    'node:path': { join },
  };
  const extension = new SourceTextModule(source + '\nexport { fetchJobLogs, githubJobIdForSelectedJob, rerunFailedJob, allPassing, compactStatus, CiDetailComponent };', { context });
  await extension.link(async name => {
    assert.ok(dependencies[name], `Unexpected dependency: ${name}`);
    const exports = dependencies[name];
    return new SyntheticModule(Object.keys(exports), function () {
      for (const [name, value] of Object.entries(exports)) this.setExport(name, value);
    }, { context });
  });
  await extension.evaluate();
  const pi = {
    on() {}, registerShortcut() {},
    registerTool: tool => tools.set(tool.name, tool),
    registerCommand: (name, command) => commands.set(name, command),
    exec: async (command, arguments_, options) => {
      requests.push({ command, arguments: arguments_, cwd: options.cwd });
      const repository = repositories[options.cwd];
      assert.ok(repository, `Unknown checkout: ${options.cwd}`);
      const result = value => ({ code: 0, stdout: typeof value === 'string' ? value : JSON.stringify(value), stderr: '' });
      if (command === 'git') {
        if (arguments_.includes('--show-toplevel')) return result(options.cwd);
        if (arguments_[0] === 'branch') return result(repository.branch);
        if (arguments_[0] === 'remote') return result(`https://github.com/${repository.repository}.git`);
        if (arguments_[0] === 'rev-parse') return result(arguments_[1].endsWith('^{tree}') ? repository.tree ?? currentSha : repository.sha);
      }
      if (command === 'local-ci') {
        assert.ok(['show', 'logs'].includes(arguments_[0]), 'No local-ci write commands allowed');
        if (repository.localError) return { code: 1, stdout: '', stderr: repository.localError };
        return result(arguments_[0] === 'show' ? repository.localSnapshot : repository.localOutput);
      }
      if (command === 'gh') {
        if (arguments_[0] === 'api' && arguments_[1].includes('/status?')) {
          if (repository.statusError) return { code: 1, stdout: '', stderr: repository.statusError };
          return result(repository.statusPages ?? [{ sha: repository.sha, statuses: [] }]);
        }
        if (arguments_[0] === 'api') {
          const runRequest = requests.findLast(request => request.arguments[0] === 'run' && request.arguments[1] === 'view' && request.arguments.includes('--json'));
          const jobId = Number(arguments_[1].split('/').at(-1));
          return result({ id: jobId, name: 'test', status: 'completed', conclusion: 'failure',
            run_id: repository.jobRunId ?? (runRequest ? Number(runRequest.arguments[2]) : 10), head_sha: repository.jobSha ?? repository.sha });
        }
        if (arguments_[0] === 'pr') return result({ number: 1, state: repository.prState ?? 'OPEN', headRefName: repository.branch,
          headRefOid: repository.prSha ?? repository.sha, statusCheckRollup: repository.checks });
        if (arguments_[1] === 'list') return result(repository.runs);
        if (arguments_.includes('--log') || arguments_.includes('--log-failed')) {
          if (repository.pendingLogs) return result(await repository.pendingLogs.promise);
          if (repository.logDiagnostic) return { code: 0, stdout: '', stderr: repository.logDiagnostic };
          return result(`Output from job ${arguments_[arguments_.indexOf('--job') + 1]}`);
        }
        if (arguments_.includes('--json')) {
          if (arguments_.includes('--jq')) return result(repository.runJobs);
          return result({ headSha: repository.runSha ?? repository.sha, jobs: repository.runJobs, name: 'Checks' });
        }
      }
      assert.fail(`Unexpected command: ${command} ${arguments_.join(' ')}`);
    },
  };
  extension.namespace.default(pi);
  const getContext = cwd => ({ cwd, hasUI: false, ui: { setStatus() {}, setWidget() {}, notify: text => notices.push(text) } });
  return {
    requests, network, notices, lookups,
    status: (cwd = '/first') => tools.get('get_ci_status').execute('status', {}, undefined, undefined, getContext(cwd)),
    logs: (parameters, cwd = '/first') => tools.get('ci_fetch_job_logs').execute('logs', parameters, undefined, undefined, getContext(cwd)),
    command: (query, cwd = '/first') => commands.get('ci-logs').handler(query, getContext(cwd)),
    readLogs: job => extension.namespace.fetchJobLogs(pi, '/first', job),
    getJobId: job => extension.namespace.githubJobIdForSelectedJob(pi, '/first', 10, job),
    rerun: job => extension.namespace.rerunFailedJob(pi, '/first', job),
    allPassing: extension.namespace.allPassing,
    compactStatus: extension.namespace.compactStatus,
    getDetail: summary => Object.assign(Object.create(extension.namespace.CiDetailComponent.prototype), {
      summary, pi, cwd: '/first', jobs: summary.jobs, logContent: [], logLoading: false,
      requestRender() {}, startLoadingAnim() {}, stopLoadingAnim() {},
      theme: { fg: (_color, text) => text },
    }),
  };
}

function getLogRequests(extension) {
  return extension.requests.filter(request => request.arguments.includes('--log') || request.arguments.includes('--log-failed'));
}

test('exact job ID and run ID identify the requested sibling, not the first job', async () => {
  const extension = await getExtension();
  const status = await extension.status();
  const result = await extension.logs({ runId: 10, jobId: status.details.jobs[1].id });
  assert.equal(result.isError, undefined);
  assert.match(result.content[0].text, /Output from job 102/);
});

test('the slash command uses the same exact job selection as the tool', async () => {
  const extension = await getExtension();
  const status = await extension.status();
  await extension.command(status.details.jobs[1].id);
  assert.match(extension.notices.at(-1), /Logs loaded/);
  const request = getLogRequests(extension)[0];
  assert.equal(request.arguments[request.arguments.indexOf('--job') + 1], '102');
});

test('run-only and fuzzy selections reject ambiguity; conflicting selectors do not fall back', async () => {
  const extension = await getExtension();
  const status = await extension.status();
  for (const parameters of [{ runId: 10 }, { jobId: 'test' }, { runId: 99, jobId: status.details.jobs[0].id }, { jobNumber: 10, jobId: status.details.jobs[0].id }]) {
    const result = await extension.logs(parameters);
    assert.equal(result.isError, true, JSON.stringify(parameters));
  }
  await extension.command('test');
  assert.match(extension.notices.at(-1), /ambiguous/i);
  assert.equal(getLogRequests(extension).length, 0);
});

test('a namespaced ID is exact, not a prefix of another job ID', async () => {
  const repository = buildRepository();
  repository.checks = [buildCheck(repository.repository, 1010)];
  const extension = await getExtension({ '/first': repository });
  const status = await extension.status();
  const result = await extension.logs({ jobId: status.details.jobs[0].id.slice(0, -1) });
  assert.equal(result.isError, true);
  assert.equal(getLogRequests(extension).length, 0);
});

test('job URL identity wins over duplicate job names', async () => {
  const extension = await getExtension();
  const jobId = await extension.getJobId({ id: 'github:test', repo: 'team/first', provider: 'github', name: 'Checks / test', url: buildCheck('team/first', 102).detailsUrl });
  assert.equal(jobId, 102);
  await assert.rejects(extension.getJobId({ id: 'github:test', repo: 'team/first', provider: 'github', name: 'Checks / test', githubJobName: 'test' }), /ambiguous/i);
});

test('an exact job must belong to the selected run and commit', async () => {
  const repository = buildRepository();
  const extension = await getExtension({ '/first': repository });
  const status = await extension.status();
  for (const overrides of [{ jobRunId: 99 }, { jobSha: otherSha }]) {
    repository.jobRunId = undefined;
    repository.jobSha = undefined;
    Object.assign(repository, overrides);
    const result = await extension.logs({ jobId: status.details.jobs[0].id });
    assert.equal(result.isError, true);
    assert.match(result.content[0].text, /run and commit/);
  }
  assert.equal(getLogRequests(extension).length, 0);
});

test('log lookup refreshes after a repository or commit change', async () => {
  const first = buildRepository();
  const second = buildRepository('team/second');
  const extension = await getExtension({ '/first': first, '/second': second });
  await extension.status();
  second.checks = [buildCheck(second.repository, 201, 'second-only')];
  second.runJobs = [{ databaseId: 201, name: 'second-only', conclusion: 'failure' }];
  const result = await extension.logs({ jobId: 'second-only' }, '/second');
  assert.equal(result.isError, undefined);
  assert.match(result.content[0].text, /Output from job 201/);
  second.sha = otherSha;
  second.checks = [buildCheck(second.repository, 202, 'new-head')];
  second.runJobs = [{ databaseId: 202, name: 'new-head', conclusion: 'failure' }];
  const updated = await extension.logs({ jobId: 'new-head' }, '/second');
  assert.equal(updated.isError, undefined);
  assert.match(updated.content[0].text, /Output from job 202/);
  for (const request of extension.requests.filter(request => request.command === 'gh' && request.cwd === '/second')) {
    if (request.arguments[0] === 'api') assert.ok(request.arguments[1].startsWith('repos/team/second/'));
    else assert.equal(request.arguments[request.arguments.indexOf('--repo') + 1], 'team/second');
  }
});

for (const changes of [{ prState: 'CLOSED' }, { prSha: otherSha }]) {
  test(`PR scope cannot replace checkout scope: ${JSON.stringify(changes)}`, async () => {
    const repository = { ...buildRepository(), ...changes };
    const extension = await getExtension({ '/first': repository });
    const result = await extension.status();
    assert.equal(result.details.sha, currentSha);
    assert.equal(result.details.jobs.length, 0);
    assert.equal(result.details.prNumber, undefined);
    assert.ok(result.details.warnings.length);
  });
}

test('an explicit run missing from the rollup can be inspected, but must match the current SHA', async () => {
  const repository = buildRepository();
  repository.checks = [];
  repository.runJobs = [{ databaseId: 301, name: 'single-job', conclusion: 'failure' }];
  const extension = await getExtension({ '/first': repository });
  const result = await extension.logs({ runId: 20 });
  assert.equal(result.isError, undefined);
  assert.match(result.content[0].text, /Output from job 301/);
  repository.runSha = otherSha;
  const mismatch = await extension.logs({ runId: 20 });
  assert.equal(mismatch.isError, true);
  assert.match(mismatch.content[0].text, /commit|SHA/i);
  assert.equal(getLogRequests(extension).length, 1);
});

test('aggregate runs require one actual job, including for the shared UI reader', async () => {
  const repository = { ...buildRepository(), checks: [], runJobs: [{ databaseId: 301, name: 'single-job', conclusion: 'failure' }] };
  const extension = await getExtension({ '/first': repository });
  const aggregate = { id: 'github-run:10', repo: repository.repository, provider: 'github', name: 'Checks', runId: 10 };
  assert.equal(await extension.getJobId(aggregate), 301);
  repository.runJobs.push({ databaseId: 302, name: 'other-job', conclusion: 'failure' });
  await assert.rejects(extension.getJobId(aggregate), /ambiguous/i);
  const result = await extension.logs({ jobId: 'github-run:20' });
  assert.equal(result.isError, true);
  assert.match(result.content[0].text, /github-job:301/);
  const selected = await extension.logs({ runId: 20, jobId: 'github-job:302' });
  assert.equal(selected.isError, undefined);
  assert.match(selected.content[0].text, /Output from job 302/);
});

test('a partial PR rollup cannot make a multi-job run unambiguous', async () => {
  const repository = buildRepository();
  repository.checks = [repository.checks[0]];
  const extension = await getExtension({ '/first': repository });
  assert.equal((await extension.logs({ runId: 10 })).isError, true);
  assert.equal((await extension.logs({ runId: 10, jobId: 'test' })).isError, true);
  assert.equal(getLogRequests(extension).length, 0);
});

test('exact numeric job IDs can be selected when the rollup uses check-run aliases', async () => {
  const extension = await getExtension();
  const result = await extension.logs({ runId: 10, jobId: 'github-job:102' });
  assert.equal(result.isError, undefined);
  assert.match(result.content[0].text, /Output from job 102/);
});

test('an explicit job from a prior attempt need not appear in the latest run job list', async () => {
  const extension = await getExtension();
  const result = await extension.logs({ runId: 10, jobId: 'github-job:99' });
  assert.equal(result.isError, undefined);
  assert.match(result.content[0].text, /Output from job 99/);
});

test('a workflow prefix cannot substitute for a missing job name', async () => {
  const repository = { ...buildRepository(), runJobs: [{ databaseId: 103, name: 'Checks', conclusion: 'failure' }] };
  const extension = await getExtension({ '/first': repository });
  await assert.rejects(extension.getJobId({ id: 'github:missing', repo: repository.repository, sha: currentSha,
    provider: 'github', runId: 10, name: 'Checks / missing', githubJobName: 'missing' }), /Could not identify/);
});

for (const detailsUrl of ['https://github.com/team/first/pull/1', 'https://example.test/github.com/team/first/actions/runs/10']) {
  test(`non-Actions links cannot borrow a similarly named Actions run: ${detailsUrl}`, async () => {
    const repository = buildRepository();
    repository.checks = [{ ...repository.checks[0], detailsUrl }];
    repository.runs = [{ databaseId: 10, headSha: currentSha, name: 'Checks', conclusion: 'failure' }];
    repository.runJobs = [repository.runJobs[0]];
    const extension = await getExtension({ '/first': repository });
    const status = await extension.status();
    assert.equal(status.details.jobs[0].runId, undefined);
    assert.notEqual(extension.getDetail(status.details).ciKey(status.details.jobs[0]), 'github-actions');
    assert.equal((await extension.logs({ jobId: status.details.jobs[0].id })).isError, true);
    assert.equal(getLogRequests(extension).length, 0);
  });
}

test('decorated check labels cannot match another raw job name', async () => {
  const repository = buildRepository();
  repository.checks = [{ ...repository.checks[0], detailsUrl: 'https://github.com/team/first/actions/runs/10' }];
  repository.runJobs = [{ databaseId: 101, name: 'Checks / test', conclusion: 'failure' }];
  const extension = await getExtension({ '/first': repository });
  assert.equal((await extension.logs({ jobId: (await extension.status()).details.jobs[0].id })).isError, true);
  assert.equal(getLogRequests(extension).length, 0);
  repository.runJobs[0].name = 'test';
  assert.equal((await extension.logs({ jobId: (await extension.status()).details.jobs[0].id })).isError, undefined);
});

test('GitHub CLI diagnostics are not console output', async () => {
  const repository = { ...buildRepository(), logDiagnostic: 'warning: logs are not available' };
  const extension = await getExtension({ '/first': repository });
  const result = await extension.logs({ jobId: (await extension.status()).details.jobs[0].id });
  assert.equal(result.isError, true);
  assert.match(result.content[0].text, /no console output/i);
});

test('a disposed detail view ignores a late log response', async () => {
  const repository = { ...buildRepository(), pendingLogs: Promise.withResolvers() };
  const extension = await getExtension({ '/first': repository });
  const status = await extension.status();
  const detail = extension.getDetail(status.details);
  detail.selectedJob = { ...status.details.jobs[0], repo: repository.repository, sha: currentSha };
  detail.fetchLogs();
  await new Promise(setImmediate);
  assert.equal(getLogRequests(extension).length, 1);
  detail.dispose();
  let renderCount = 0;
  detail.requestRender = () => renderCount++;
  repository.pendingLogs.resolve('late console output');
  await new Promise(setImmediate);
  assert.equal(renderCount, 0);
  assert.equal(detail.logContent.length, 0);
  const requestCount = extension.requests.length;
  detail.rerender();
  await detail.refreshStatus();
  assert.equal(renderCount, 0);
  assert.equal(extension.requests.length, requestCount);
});

test('invalid numeric identifiers never fetch logs', async () => {
  const extension = await getExtension();
  for (const runId of [0, -1, 1.5]) {
    assert.equal((await extension.logs({ runId })).isError, true);
  }
  assert.equal(getLogRequests(extension).length, 0);
});

test('a run with no jobs reports unavailable logs rather than another job', async () => {
  const repository = { ...buildRepository(), checks: [], runJobs: [] };
  const extension = await getExtension({ '/first': repository });
  const result = await extension.logs({ runId: 20 });
  assert.equal(result.isError, true);
  assert.match(result.content[0].text, /no jobs/i);
  assert.equal(getLogRequests(extension).length, 0);
});

const circleJob = { id: 'circleci:job-id', provider: 'circleci', name: 'Tests / unit', state: 'failed', repo: 'team/first', sha: currentSha, jobNumber: 42 };
const outputUrl = 'https://circle-production-customer-artifacts.s3.amazonaws.com/output?signature=private';

test('CircleCI retrieves console messages without forwarding its token to presigned output URLs', async () => {
  const extension = await getExtension(undefined, async url => {
    if (url.includes('/api/v1.1/')) return Response.json({ vcs_revision: currentSha, steps: [{ name: 'unit', actions: [
      { index: 0, output_url: outputUrl }, { index: 1, output_url: outputUrl + '2' },
    ] }] });
    return Response.json([{ message: 'actual failure\n' }]);
  });
  const logs = await extension.readLogs(circleJob);
  assert.equal((logs.match(/actual failure/g) ?? []).length, 2);
  assert.equal(extension.network[0].options.headers['Circle-Token'], 'synthetic-token');
  assert.ok(extension.network[0].url.endsWith('/api/v1.1/project/github/team/first/42'));
  for (const request of extension.network.slice(1)) {
    assert.equal(request.options.headers, undefined);
    assert.equal(request.options.signal, extension.network[0].options.signal);
  }
  assert.ok(!logs.includes(outputUrl));
});

test('CircleCI jobNumber lookup returns real output for the current repository and SHA', async () => {
  const extension = await getExtension(undefined, async url => {
    if (url.includes('/api/v2/project/')) return Response.json({ items: [{ id: 'pipeline', number: 1, vcs: { revision: currentSha } }] });
    if (url.includes('/pipeline/pipeline/workflow')) return Response.json({ items: [{ id: 'workflow', name: 'Tests' }] });
    if (url.includes('/workflow/workflow/job')) return Response.json({ items: [{ id: 'job-id', name: 'unit', job_number: 42, status: 'failed' }] });
    if (url.includes('/api/v1.1/')) return Response.json({ vcs_revision: currentSha, steps: [{ actions: [{ output_url: outputUrl }] }] });
    return Response.json([{ message: 'CircleCI console failure' }]);
  });
  const result = await extension.logs({ jobNumber: 42 });
  assert.equal(result.isError, undefined);
  assert.equal(result.details.repo, 'team/first');
  assert.equal(result.details.sha, currentSha);
  assert.equal(result.details.jobNumber, 42);
  assert.match(result.content[0].text, /CircleCI console failure/);
});

test('CircleCI rejects local names and IP literals before downloading output', async () => {
  for (const hostname of ['localhost', 'LOCALHOST.', 'service.localhost', '127.0.0.1', '127.1', '2130706433',
    '0x7f000001', '[::1]', '[::ffff:127.0.0.1]', '93.184.216.34', '[2606:4700::1111]', '10.0.0.1', '169.254.169.254', '192.168.1.1', '[fc00::1]']) {
    const extension = await getExtension(undefined, async url => url.includes('/api/v1.1/')
      ? Response.json({ vcs_revision: currentSha, steps: [{ actions: [{ output_url: `https://${hostname}/output?signature=private` }] }] })
      : Response.json([{ message: 'must not download this' }]));
    await assert.rejects(extension.readLogs(circleJob), error => {
      assert.ok(!error.message.includes('signature='));
      return true;
    }, hostname);
    assert.equal(extension.network.length, 1, hostname);
  }
});

test('CircleCI rejects private, special-use, mixed, and empty DNS answers at connection time', async () => {
  const publicAddress = { address: '93.184.216.34', family: 4 };
  const blockedAddresses = ['127.0.0.1', '10.0.0.1', '172.16.1.1', '192.168.1.1', '169.254.169.254',
    '100.64.0.1', '0.0.0.0', '224.0.0.1', '::', '::1', 'fc00::1', 'fd00::1', 'fe80::1', 'fec0::1',
    'ff02::1', '::ffff:127.0.0.1', '2002:7f00:1::', '2001::1', '2001:db8::1'];
  const answers = [[], new Error('lookup failure containing signature=private'), ...blockedAddresses.map(address => [{ address, family: isIP(address) }]),
    [publicAddress, { address: '10.0.0.1', family: 4 }]];
  for (const addresses of answers) {
    const extension = await getExtension(undefined, async url => url.includes('/api/v1.1/')
      ? Response.json({ vcs_revision: currentSha, steps: [{ actions: [{ output_url: outputUrl }] }] })
      : Response.json([{ message: 'must not download this' }]),
    hostname => hostname === 'circleci.com' ? [publicAddress] : addresses);
    await assert.rejects(extension.readLogs(circleJob), error => {
      assert.ok(!error.message.includes('signature='));
      return true;
    });
    assert.equal(extension.network.length, 1, JSON.stringify(addresses));
  }
});

test('CircleCI sockets use the validated public DNS answer without a second lookup', async () => {
  for (const lookupAll of [true, false]) {
    let outputLookups = 0;
    const publicAddress = { address: lookupAll ? '2606:4700::1111' : '93.184.216.34', family: lookupAll ? 6 : 4 };
    const extension = await getExtension(undefined, async url => url.includes('/api/v1.1/')
      ? Response.json({ vcs_revision: currentSha, steps: [{ actions: [{ output_url: outputUrl }] }] })
      : Response.json([{ message: 'public console output' }]), hostname => {
        if (hostname === 'circleci.com') return [publicAddress];
        return ++outputLookups === 1 ? [publicAddress] : [{ address: '127.0.0.1', family: 4 }];
      }, lookupAll);
    assert.match(await extension.readLogs(circleJob), /public console output/);
    assert.equal(outputLookups, 1);
    assert.deepEqual(extension.network[1].addresses, [publicAddress]);
    assert.equal(extension.network[1].options.agent, false);
    assert.equal(extension.network[1].options.headers, undefined);
  }
});

test('CircleCI output redirects are not followed', async () => {
  const extension = await getExtension(undefined, async url => url.includes('/api/v1.1/')
    ? Response.json({ vcs_revision: currentSha, steps: [{ actions: [{ output_url: outputUrl }] }] })
    : new Response('', { status: 302, headers: { Location: 'https://127.0.0.1/private' } }));
  await assert.rejects(extension.readLogs(circleJob), /HTTP 302/);
  assert.equal(extension.network.length, 2);
});

test('CircleCI JSON parse errors do not include response contents', async () => {
  const extension = await getExtension(undefined, async url => url.includes('/api/v1.1/')
    ? Response.json({ vcs_revision: currentSha, steps: [{ actions: [{ output_url: outputUrl }] }] })
    : new Response('not JSON: signature=private'));
  await assert.rejects(extension.readLogs(circleJob), error => {
    assert.match(error.message, /not valid JSON/);
    assert.ok(!error.message.includes('signature='));
    return true;
  });
});

test('CircleCI output is explicitly truncated and missing auth is an error', async () => {
  const extension = await getExtension(undefined, async url => url.includes('/api/v1.1/')
    ? Response.json({ vcs_revision: currentSha, steps: [{ actions: [{ output_url: outputUrl }] }] })
    : Response.json([{ message: Array.from({ length: 600 }, (_, i) => `line ${i}`).join('\n') }]));
  const logs = await extension.readLogs(circleJob);
  assert.match(logs, /truncated/);
  assert.ok(!logs.includes('line 599'));
  const unauthenticated = await getExtension();
  await assert.rejects(unauthenticated.readLogs(circleJob), /CIRCLECI_TOKEN/);
  assert.equal(unauthenticated.network.length, 0);
});

const localRunId = '20260627T150405Z-deadbeef';

function addLocalSnapshot(repository) {
  const runDirectory = `/first/.local-ci/runs/${localRunId}`;
  repository.localSnapshot = { run_id: localRunId, run_dir: runDirectory,
    meta: { run_id: localRunId, repo_root: '/first', repo_slug: repository.repository,
      head_sha: repository.sha, head_tree_hash: currentSha, worktree_tree_hash: currentSha, dirty_worktree: false },
    steps: [{ step_id: 'checks-fast', state: 'failure' }, { step_id: 'checks-deep', state: 'success' }] };
  repository.localOutput = { run_id: localRunId, run_dir: runDirectory, source: 'step', step_id: 'checks-fast',
    view: 'combined', content: 'Native local-ci step failure' };
}

test('commit fallback preserves paginated local-ci and legacy fast-check statuses', async () => {
  const repository = { ...buildRepository(), prState: 'MERGED' };
  repository.statusPages = [
    { sha: currentSha, statuses: [{ context: 'Fast Checks / Checks (Fast)', state: 'failure', description: 'failed' }] },
    { sha: currentSha, statuses: [{ context: 'local: verify', state: 'pending', description: 'local verification running' }] },
  ];
  const extension = await getExtension({ '/first': repository });
  const result = await extension.status();
  assert.equal(result.details.jobs.length, 2);
  assert.equal(result.details.jobs[0].provider, 'github-status');
  assert.equal(result.details.jobs[1].provider, 'local-ci');
  assert.equal(result.details.jobs[1].state, 'pending');
  const request = extension.requests.find(request => request.arguments[1]?.includes('/status?'));
  assert.ok(request.arguments.includes('--paginate') && request.arguments.includes('--slurp'));
});

test('published status contexts never become Actions jobs, even with an Actions URL', async () => {
  const repository = buildRepository();
  repository.checks = ['local: verify', 'Fast Checks / Checks (Fast)'].map(context => ({
    __typename: 'StatusContext', context, state: 'FAILURE', targetUrl: buildCheck(repository.repository, 101).detailsUrl,
  }));
  const extension = await getExtension({ '/first': repository });
  const result = await extension.status();
  for (const job of result.details.jobs) {
    assert.notEqual(job.provider, 'github');
    assert.equal(job.runId, undefined);
    assert.equal((await extension.logs({ jobId: job.id })).isError, true);
    await assert.rejects(extension.rerun({ ...job, repo: repository.repository, sha: currentSha }), /local-ci|commit status/i);
  }
  assert.equal(getLogRequests(extension).length, 0);
  assert.ok(!extension.requests.some(request => request.arguments.includes('rerun')));
});

test('missing publication in a local-ci checkout is unknown, not an all-green result', async () => {
  const repository = { ...buildRepository(), localConfigured: true };
  repository.checks = [{ ...buildCheck(repository.repository, 101), conclusion: 'SUCCESS' }];
  const extension = await getExtension({ '/first': repository });
  const result = await extension.status();
  assert.equal(result.details.summary.unknown, 1);
  assert.match(result.content[0].text, /local-ci.*publication/i);
});

test('local publication needs an aggregate, including custom aggregate context names', async () => {
  const repository = { ...buildRepository(), checks: [], localConfigured: true };
  repository.statusPages = [{ sha: currentSha, statuses: [{ context: 'local/lint', state: 'success', description: 'passed' }] }];
  const extension = await getExtension({ '/first': repository });
  assert.equal((await extension.status()).details.summary.unknown, 1);
  repository.statusPages[0].statuses.push({ context: 'Team verification', state: 'success', description: 'local verification passed' });
  const result = await extension.status();
  assert.equal(result.details.summary.unknown, 0);
  assert.equal(result.details.jobs.find(job => job.name === 'Team verification').provider, 'local-ci');
  assert.equal(result.details.jobs.find(job => job.name === 'local/lint').provider, 'local-ci');
});

test('failed commit-status discovery cannot report all checks passed', async () => {
  const repository = { ...buildRepository(), prState: 'CLOSED', statusError: 'permission denied',
    runs: [{ databaseId: 10, name: 'Safety', headSha: currentSha, conclusion: 'SUCCESS' }] };
  const extension = await getExtension({ '/first': repository });
  const result = await extension.status();
  assert.ok(result.details.errors.length);
  const summary = { ...result.details, jobs: result.details.jobs };
  assert.equal(extension.allPassing(summary), false);
  assert.doesNotMatch(extension.compactStatus(summary), /all passed/);
  const detail = extension.getDetail(summary);
  assert.match(detail.plainStatusForJobs(summary.jobs), /incomplete/);
  assert.match(detail.statusForJobs(summary.jobs), /incomplete/);
  assert.doesNotMatch(detail.nextActionForJobs(summary.jobs), /No action needed/);
});

test('commit-status pages must match the selected SHA and expected JSON shape', async () => {
  const repository = { ...buildRepository(), prState: 'MERGED' };
  const extension = await getExtension({ '/first': repository });
  for (const pages of [[{ sha: otherSha, statuses: [] }], [{ sha: currentSha, statuses: {} }]]) {
    repository.statusPages = pages;
    assert.ok((await extension.status()).details.errors.length);
  }
});

test('explicit local run/step reads use only native show/logs and preserve snapshot provenance', async () => {
  const repository = buildRepository();
  addLocalSnapshot(repository);
  repository.localSnapshot.meta.head_sha = otherSha;
  repository.localSnapshot.meta.dirty_worktree = true;
  const extension = await getExtension({ '/first': repository });
  const result = await extension.logs({ jobId: `local-ci:${localRunId}:checks-fast` });
  assert.equal(result.isError, undefined);
  assert.equal(result.details.provider, 'local-ci');
  assert.equal(result.details.localRunId, localRunId);
  assert.match(result.content[0].text, /Native local-ci step failure/);
  assert.match(result.content[0].text, /not proof of publication/);
  assert.ok(result.content[0].text.includes(otherSha));
  assert.deepEqual(extension.requests.filter(request => request.command === 'local-ci').map(request => [...request.arguments]), [
    ['show', localRunId, '--json'], ['logs', localRunId, '--step', 'checks-fast', '--combined', '--json'],
  ]);
  assert.equal(getLogRequests(extension).length, 0);
});

test('dirty local snapshots can be inspected without claiming committed or current-worktree validation', async () => {
  const repository = buildRepository();
  addLocalSnapshot(repository);
  repository.localSnapshot.meta.dirty_worktree = true;
  repository.localSnapshot.meta.worktree_tree_hash = otherSha;
  const extension = await getExtension({ '/first': repository });
  const result = await extension.logs({ jobId: `local-ci:${localRunId}:checks-fast` });
  assert.equal(result.isError, undefined);
  assert.match(result.content[0].text, /Stored dirty snapshot/);
  assert.match(result.content[0].text, /current working-tree contents were not compared/);
});

test('local runner output is labeled as events and does not pick a step', async () => {
  const repository = buildRepository();
  addLocalSnapshot(repository);
  repository.localOutput = { ...repository.localOutput, source: 'runner', step_id: undefined, events: [{ type: 'step_started' }] };
  const extension = await getExtension({ '/first': repository });
  const result = await extension.logs({ jobId: `local-ci:${localRunId}` });
  assert.equal(result.isError, undefined);
  assert.match(result.content[0].text, /runner events/);
  assert.match(result.content[0].text, /step_started/);
});

for (const mismatch of ['repo_root', 'repo_slug', 'worktree_tree_hash', 'run_id']) {
  test(`local snapshot ${mismatch} mismatch cannot expose step logs`, async () => {
    const repository = buildRepository();
    addLocalSnapshot(repository);
    repository.localSnapshot.meta[mismatch] = 'different';
    const extension = await getExtension({ '/first': repository });
    assert.equal((await extension.logs({ jobId: `local-ci:${localRunId}:checks-fast` })).isError, true);
    assert.ok(!extension.requests.some(request => request.command === 'local-ci' && request.arguments[0] === 'logs'));
  });
}

test('a different valid tree is not accepted as a clean snapshot of the selected commit', async () => {
  const repository = buildRepository();
  addLocalSnapshot(repository);
  repository.localSnapshot.meta.worktree_tree_hash = otherSha;
  const extension = await getExtension({ '/first': repository });
  const result = await extension.logs({ jobId: `local-ci:${localRunId}:checks-fast` });
  assert.equal(result.isError, true);
  assert.ok(!extension.requests.some(request => request.command === 'local-ci' && request.arguments[0] === 'logs'));
});

test('local selectors reject traversal, missing steps, and remote run constraints', async () => {
  const repository = buildRepository();
  addLocalSnapshot(repository);
  const extension = await getExtension({ '/first': repository });
  for (const selection of [
    { jobId: 'local-ci:../secret' }, { jobId: `local-ci:${localRunId}:absent` },
    { jobId: `local-ci:${localRunId}:checks-fast`, runId: 10 },
    { jobId: `local-ci:${localRunId}:checks-fast`, jobNumber: 42 },
  ]) assert.equal((await extension.logs(selection)).isError, true);
  assert.ok(!extension.requests.some(request => request.command === 'local-ci' && request.arguments[0] === 'logs'));
});

test('malformed local snapshot fields cannot be coerced into valid provenance', async () => {
  const repository = buildRepository();
  const extension = await getExtension({ '/first': repository });
  for (const fields of [{ head_sha: 'not-a-sha' }, { dirty_worktree: 'false' },
    { dirty_worktree: true, worktree_tree_hash: [otherSha] }]) {
    addLocalSnapshot(repository);
    Object.assign(repository.localSnapshot.meta, fields);
    assert.equal((await extension.logs({ jobId: `local-ci:${localRunId}:checks-fast` })).isError, true);
  }
  assert.ok(!extension.requests.some(request => request.command === 'local-ci' && request.arguments[0] === 'logs'));
});

test('a malformed PR status does not become an invented passing context', async () => {
  const repository = { ...buildRepository(), checks: [{ __typename: 'StatusContext', state: 'SUCCESS' }] };
  const extension = await getExtension({ '/first': repository });
  const result = await extension.status();
  assert.equal(result.details.jobs.length, 0);
  assert.ok(result.details.warnings.length);
});

test('missing local artifacts and wrong log identities are explicit errors', async () => {
  const repository = buildRepository();
  addLocalSnapshot(repository);
  const extension = await getExtension({ '/first': repository });
  repository.localError = 'local-ci: run artifacts not found';
  assert.equal((await extension.logs({ jobId: `local-ci:${localRunId}:checks-fast` })).isError, true);
  repository.localError = undefined;
  repository.localOutput.step_id = 'checks-deep';
  assert.equal((await extension.logs({ jobId: `local-ci:${localRunId}:checks-fast` })).isError, true);
});

for (const failure of ['expired', 'empty', 'unsafe', 'malformed', 'network', 'wrong-sha']) {
  test(`CircleCI ${failure} output is a clear failure, not metadata labeled as logs`, async () => {
    const extension = await getExtension(undefined, async url => {
      if (url.includes('/api/v1.1/')) return Response.json({ vcs_revision: failure === 'wrong-sha' ? otherSha : currentSha, steps: failure === 'empty' ? [] : [{ actions: [
        { output_url: failure === 'unsafe' ? 'http://localhost/private' : outputUrl },
      ] }] });
      if (failure === 'network') throw new Error(`Request failed: ${url}`);
      if (failure === 'malformed') return new Response('invalid JSON signature=private');
      return new Response('expired', { status: 403 });
    });
    await assert.rejects(extension.readLogs(circleJob), error => {
      assert.ok(!error.message.includes('signature='));
      return true;
    });
  });
}
