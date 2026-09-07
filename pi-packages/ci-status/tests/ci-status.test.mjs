import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
import { join } from 'node:path';
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
async function getExtension(repositories = { '/first': buildRepository() }, fetchResponse) {
  const requests = [];
  const commands = new Map();
  const tools = new Map();
  const notices = [];
  const network = [];
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
    'node:fs/promises': { writeFile() { assert.fail('Unexpected file write'); }, unlink() { assert.fail('Unexpected file deletion'); } },
    'node:os': { tmpdir: () => '/virtual' },
    'node:path': { join },
  };
  const extension = new SourceTextModule(source + '\nexport { fetchJobLogs, githubJobIdForSelectedJob };', { context });
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
        if (arguments_[0] === 'rev-parse') return result(repository.sha);
      }
      if (command === 'gh') {
        if (arguments_[0] === 'api') {
          const runRequest = requests.findLast(request => request.arguments[0] === 'run' && request.arguments[1] === 'view' && request.arguments.includes('--json'));
          return result({ run_id: repository.jobRunId ?? (runRequest ? Number(runRequest.arguments[2]) : 10), head_sha: repository.jobSha ?? repository.sha });
        }
        if (arguments_[0] === 'pr') return result({ number: 1, state: repository.prState ?? 'OPEN', headRefName: repository.branch,
          headRefOid: repository.prSha ?? repository.sha, statusCheckRollup: repository.checks });
        if (arguments_[1] === 'list') return result(repository.runs);
        if (arguments_.includes('--log') || arguments_.includes('--log-failed')) {
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
    requests, network, notices,
    status: (cwd = '/first') => tools.get('get_ci_status').execute('status', {}, undefined, undefined, getContext(cwd)),
    logs: (parameters, cwd = '/first') => tools.get('ci_fetch_job_logs').execute('logs', parameters, undefined, undefined, getContext(cwd)),
    command: (query, cwd = '/first') => commands.get('ci-logs').handler(query, getContext(cwd)),
    readLogs: job => extension.namespace.fetchJobLogs(pi, '/first', job),
    getJobId: job => extension.namespace.githubJobIdForSelectedJob(pi, '/first', 10, job),
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
  await assert.rejects(extension.getJobId({ id: 'github:test', repo: 'team/first', provider: 'github', name: 'Checks / test' }), /ambiguous/i);
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
  for (const request of extension.network.slice(1)) assert.equal(request.options.headers, undefined);
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
