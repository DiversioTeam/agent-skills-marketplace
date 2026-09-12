import { DynamicBorder, type ExtensionAPI, type ExtensionContext, type Theme } from "@mariozechner/pi-coding-agent";
import { Type } from "typebox";
import { Container, Key, matchesKey, SelectList, Spacer, Text, truncateToWidth, visibleWidth, type SelectItem, type SelectListTheme } from "@mariozechner/pi-tui";
import { access, writeFile, unlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { lookup } from "node:dns";
import { get } from "node:https";
import { BlockList, isIP, type LookupFunction } from "node:net";
import { join } from "node:path";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type CiState = "success" | "failed" | "running" | "pending" | "cancelled" | "skipped" | "unknown";
type CiProvider = "github" | "circleci" | "github-status" | "local-ci";

type GitHubRepo = { owner: string; repo: string };

type CiJob = {
  id: string;
  provider: CiProvider;
  repo?: string;
  sha?: string;
  providerHint?: "github-actions" | "circleci" | "commit-status" | "local-ci" | "unknown";
  localRunId?: string;
  localStepId?: string;
  isLocalAggregate?: boolean;
  name: string;
  state: CiState;
  url?: string;
  startedAt?: string;
  completedAt?: string;
  durationMs?: number;
  summary?: string;
  /** For GitHub Actions runs, the run databaseId so we can fetch logs */
  runId?: number;
  /** For GitHub Actions jobs, the job databaseId so we can rerun one selected job */
  githubJobId?: number;
  githubJobName?: string;
  /** For CircleCI jobs, the job number */
  jobNumber?: number;
  /** For CircleCI jobs, the workflow id so we can rerun failed workflow jobs */
  workflowId?: string;
};

type CiSummary = {
  repo?: string;
  branch: string;
  sha: string;
  prNumber?: number;
  prUrl?: string;
  checkedAt: number;
  jobs: CiJob[];
  warnings: string[];
  errors: string[];
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const WIDGET_KEY = "ci-status";
const STATUS_KEY = "ci-status";
const ACTIVE_POLL_MS = 30_000;
const COMPLETE_POLL_MS = 180_000;
const ERROR_POLL_MS = 60_000;
const MAX_RENDERED_PASSING_JOBS = 8;
const AUTO_WATCH_ON_START = process.env.PI_CI_AUTO_WATCH !== "0";
const SHOW_WIDGET_ON_START = process.env.PI_CI_SHOW_WIDGET_ON_START === "1";
const CI_DETAIL_SHORTCUT = process.env.PI_CI_DETAIL_SHORTCUT || "ctrl+shift+.";
const STARTUP_REFRESH_DELAY_MS = 1_000;
const LOG_FETCH_TIMEOUT = 30_000;
const ASCII_ICONS = process.env.PI_CI_ASCII === "1";

type ExecFailure = Error & { stdout?: string; stderr?: string; code?: number };

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

let watching = false;
let widgetVisible = false;
let timer: ReturnType<typeof setTimeout> | undefined;
let refreshInFlight = false;
let lastSummary: CiSummary | undefined;
let lastFailureSignature = "";
let hadFailureSinceLastSuccess = false;
let lastErrorMessage = "";
let extensionApi: ExtensionAPI;

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function shortSha(sha: string | undefined): string {
  return sha ? sha.slice(0, 12) : "unknown";
}

function truncate(text: string, max = 500): string {
  const normalized = text.trim();
  return normalized.length > max ? `${normalized.slice(0, max)}…` : normalized;
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

function keyComboLabel(keyCombo: string): string {
  return keyCombo
    .split("+")
    .map((part) => part.length === 1 ? part.toUpperCase() : part[0].toUpperCase() + part.slice(1))
    .join("+");
}

async function execText(
  pi: ExtensionAPI,
  command: string,
  args: string[],
  cwd: string,
  timeout = 15_000,
): Promise<string> {
  const result = await pi.exec(command, args, { cwd, timeout });
  if (result.code !== 0) {
    const message = [
      `${command} ${args.join(" ")} failed with exit code ${result.code}`,
      result.stderr ? `stderr: ${truncate(result.stderr)}` : undefined,
      result.stdout ? `stdout: ${truncate(result.stdout)}` : undefined,
    ]
      .filter(Boolean)
      .join("\n");
    const err = new Error(message) as ExecFailure;
    err.stdout = result.stdout;
    err.stderr = result.stderr;
    err.code = result.code;
    throw err;
  }
  return result.stdout.trim();
}

async function execJson<T>(
  pi: ExtensionAPI,
  command: string,
  args: string[],
  cwd: string,
  timeout = 20_000,
): Promise<T> {
  const stdout = await execText(pi, command, args, cwd, timeout);
  try {
    return JSON.parse(stdout) as T;
  } catch (error) {
    throw new Error(`Failed to parse JSON from ${command} ${args.join(" ")}: ${errorMessage(error)}\n${truncate(stdout)}`);
  }
}

async function getGitRoot(pi: ExtensionAPI, cwd: string): Promise<string> {
  return execText(pi, "git", ["rev-parse", "--show-toplevel"], cwd, 5_000);
}

async function getBranch(pi: ExtensionAPI, cwd: string): Promise<string> {
  const branch = await execText(pi, "git", ["branch", "--show-current"], cwd, 5_000);
  if (branch && branch !== "HEAD") return branch;
  try {
    const containingRefs = await execText(
      pi, "git",
      ["for-each-ref", "--format=%(refname:short)", "--contains", "HEAD", "refs/heads", "refs/remotes"],
      cwd, 5_000,
    );
    const refs = containingRefs.split("\n").map((line) => line.trim()).filter(Boolean);
    const local = refs.find((ref) => !ref.startsWith("origin/"));
    const remote = refs.find((ref) => ref.startsWith("origin/"));
    if (local) return local;
    if (remote) return remote.replace(/^origin\//, "");
  } catch { /* ignore */ }
  return execText(pi, "git", ["rev-parse", "--abbrev-ref", "HEAD"], cwd, 5_000);
}

async function getSha(pi: ExtensionAPI, cwd: string): Promise<string> {
  return execText(pi, "git", ["rev-parse", "HEAD"], cwd, 5_000);
}

async function getOriginRemote(pi: ExtensionAPI, cwd: string): Promise<string | undefined> {
  try { return await execText(pi, "git", ["remote", "get-url", "origin"], cwd, 5_000); }
  catch { return undefined; }
}

function parseGitHubRemote(remote: string | undefined): GitHubRepo | undefined {
  if (!remote) return undefined;
  const scpLike = remote.match(/^git@github\.com:([^/]+)\/(.+?)(?:\.git)?$/);
  if (scpLike) return { owner: scpLike[1], repo: scpLike[2].replace(/\.git$/, "") };
  try {
    const url = new URL(remote);
    if (url.hostname !== "github.com") return undefined;
    const parts = url.pathname.replace(/^\//, "").split("/");
    if (parts.length < 2) return undefined;
    return { owner: decodeURIComponent(parts[0]), repo: decodeURIComponent(parts[1].replace(/\.git$/, "")) };
  } catch { return undefined; }
}

function normalizeGitHubState(status?: string | null, conclusion?: string | null): CiState {
  const statusValue = (status ?? "").toUpperCase();
  const conclusionValue = (conclusion ?? "").toUpperCase();
  const value = conclusionValue || statusValue;
  if (["SUCCESS", "PASSED"].includes(value)) return "success";
  if (["FAILURE", "FAILED", "ERROR", "TIMED_OUT", "TIMEDOUT", "ACTION_REQUIRED", "STARTUP_FAILURE", "INFRASTRUCTURE_FAIL"].includes(value)) return "failed";
  if (["CANCELLED", "CANCELED"].includes(value)) return "cancelled";
  if (["SKIPPED", "NEUTRAL"].includes(value)) return "skipped";
  if (["IN_PROGRESS", "RUNNING"].includes(statusValue)) return "running";
  if (["QUEUED", "PENDING", "REQUESTED", "WAITING"].includes(statusValue)) return "pending";
  if (statusValue === "COMPLETED" && !conclusionValue) return "unknown";
  return "unknown";
}

function normalizeCircleState(status?: string | null): CiState {
  const value = (status ?? "").toLowerCase();
  if (["success"].includes(value)) return "success";
  if (["failed", "failing", "error", "infrastructure_fail", "timedout", "timed_out", "unauthorized"].includes(value)) return "failed";
  if (["canceled", "cancelled"].includes(value)) return "cancelled";
  if (["running"].includes(value)) return "running";
  if (["queued", "scheduled", "blocked", "on_hold", "not_running"].includes(value)) return "pending";
  if (["not_run", "skipped"].includes(value)) return "skipped";
  return "unknown";
}

function providerHintFromUrlOrName(url: string | undefined, name: string): CiJob["providerHint"] {
  const text = `${url ?? ""} ${name}`.toLowerCase();
  if (text.includes("circleci")) return "circleci";
  if (githubRunIdFromUrl(url)) return "github-actions";
  return "unknown";
}

function githubRunIdFromUrl(url: string | null | undefined): number | undefined {
  if (!url) return undefined;
  try {
    const parsedUrl = new URL(url);
    if (parsedUrl.protocol !== "https:" || parsedUrl.hostname !== "github.com" || parsedUrl.username || parsedUrl.password) return undefined;
    const match = parsedUrl.pathname.match(/^\/[^/]+\/[^/]+\/actions\/runs\/(\d+)(?:\/|$)/);
    const runId = match ? Number(match[1]) : undefined;
    return runId && Number.isSafeInteger(runId) ? runId : undefined;
  } catch { return undefined; }
}

function getGitHubJobIdFromUrl(url: string | undefined): number | undefined {
  if (!url) return undefined;
  try {
    const parsedUrl = new URL(url);
    if (!githubRunIdFromUrl(url)) return undefined;
    const match = parsedUrl.pathname.match(/^\/[^/]+\/[^/]+\/actions\/runs\/\d+\/job\/(\d+)\/?$/);
    const jobId = match ? Number(match[1]) : undefined;
    return jobId && Number.isSafeInteger(jobId) ? jobId : undefined;
  } catch { return undefined; }
}

// ---------------------------------------------------------------------------
// Data fetching
// ---------------------------------------------------------------------------

type GhRollupItem = {
  __typename?: string; name?: string; workflowName?: string; context?: string;
  status?: string | null; state?: string | null; conclusion?: string | null;
  detailsUrl?: string | null; targetUrl?: string | null;
  startedAt?: string | null; completedAt?: string | null; description?: string | null;
};

type GhPrView = {
  number?: number; url?: string; state?: string; headRefName?: string; headRefOid?: string;
  statusCheckRollup?: GhRollupItem[];
};

type GhRun = {
  databaseId: number; name: string; workflowName?: string | null; displayTitle?: string | null;
  status?: string | null; conclusion?: string | null;
  headSha?: string | null; url?: string | null;
  createdAt?: string | null; startedAt?: string | null; updatedAt?: string | null;
};

type GhRunJob = {
  databaseId: number; name: string; status?: string | null; conclusion?: string | null; url?: string | null;
};

type GhCommitStatus = { context: string; state?: string | null; target_url?: string | null; description?: string | null };

function buildCommitStatusJob(status: GhCommitStatus): CiJob {
  if (!status || typeof status.context !== "string" || !status.context.trim()) throw new Error("Commit status has no context identity.");
  const isLocalAggregate = /^local verification (running|passed|failed)$/.test(status.description ?? "");
  const isLocal = status.context.startsWith("local:") || status.context.startsWith("local/") || isLocalAggregate;
  return {
    id: `${isLocal ? "local-ci-status" : "github-status"}:${status.context}`,
    provider: isLocal ? "local-ci" : "github-status",
    providerHint: isLocal ? "local-ci" : providerHintFromUrlOrName(status.target_url ?? undefined, status.context) === "circleci" ? "circleci" : "commit-status",
    name: status.context, state: normalizeGitHubState(status.state, status.state), isLocalAggregate,
    url: status.target_url ?? undefined, summary: status.description ?? undefined,
  };
}

async function getCommitStatusJobs(pi: ExtensionAPI, cwd: string, repository: string, sha: string): Promise<CiJob[]> {
  const pages = await execJson<Array<{ sha: string; statuses: GhCommitStatus[] }>>(pi, "gh",
    ["api", `repos/${repository}/commits/${sha}/status?per_page=100`, "--paginate", "--slurp"], cwd);
  if (!Array.isArray(pages) || !pages.length || pages.some(page => page?.sha !== sha || !Array.isArray(page.statuses))) {
    throw new Error("Commit-status response does not match the selected SHA or expected format.");
  }
  const jobs = new Map<string, CiJob>();
  for (const status of pages.flatMap(page => page.statuses)) {
    if (!status || typeof status.context !== "string" || !status.context) throw new Error("Commit status has no context identity.");
    if (!jobs.has(status.context)) jobs.set(status.context, buildCommitStatusJob(status));
  }
  return [...jobs.values()];
}

async function fetchGitHubChecks(pi: ExtensionAPI, cwd: string, branch: string, sha: string, repository: string): Promise<Partial<CiSummary>> {
  try {
    const pr = await execJson<GhPrView>(pi, "gh", ["pr", "view", branch, "--repo", repository, "--json", "number,url,state,headRefName,headRefOid,statusCheckRollup"], cwd, 20_000);
    if (pr.state !== "OPEN" || pr.headRefOid !== sha || pr.headRefName !== branch) {
      throw new Error(`PR #${pr.number ?? "unknown"} is not open at the current branch and SHA; querying checkout commit ${shortSha(sha)} instead.`);
    }
    const jobs = (pr.statusCheckRollup ?? []).map((item, index): CiJob => {
      if (item.__typename === "StatusContext") {
        return buildCommitStatusJob({ context: item.context ?? "", state: item.state,
          target_url: item.targetUrl, description: item.description });
      }
      const rawName = item.name ?? item.context ?? item.workflowName ?? `${item.__typename ?? "GitHub check"} ${index + 1}`;
      const name = item.workflowName && item.workflowName !== rawName
        ? `${item.workflowName} / ${rawName}`
        : rawName;
      const url = item.detailsUrl ?? item.targetUrl ?? undefined;
      return {
        id: `github:${item.__typename ?? "check"}:${name}:${url ?? index}`,
        provider: "github",
        providerHint: providerHintFromUrlOrName(url, name),
        name, url,
        runId: githubRunIdFromUrl(url),
        githubJobId: getGitHubJobIdFromUrl(url), githubJobName: item.name,
        state: normalizeGitHubState(item.status ?? item.state, item.conclusion ?? item.state),
        startedAt: item.startedAt ?? undefined,
        completedAt: item.completedAt ?? undefined,
        summary: item.description ?? undefined,
      };
    });
    const summaryBranch = pr.headRefName ?? branch;
    const summarySha = pr.headRefOid ?? sha;
    return { branch: summaryBranch, sha: summarySha, prNumber: pr.number, prUrl: pr.url, jobs };
  } catch (prError) {
    const jobs: CiJob[] = [];
    const errors: string[] = [];
    try {
      const runs = await execJson<GhRun[]>(pi, "gh", ["run", "list", "--repo", repository, "--commit", sha, "--limit", "10", "--json", "databaseId,name,status,conclusion,headSha,url,createdAt,updatedAt"], cwd, 20_000);
      jobs.push(...runs.filter(run => run.headSha === sha).map((run): CiJob => ({
        id: `github-run:${run.databaseId}`, provider: "github", providerHint: "github-actions",
        name: run.name, runId: run.databaseId, state: normalizeGitHubState(run.status, run.conclusion),
        url: run.url ?? undefined, startedAt: run.createdAt ?? undefined, completedAt: run.updatedAt ?? undefined,
      })));
    } catch (error) {
      errors.push(`GitHub Actions lookup unavailable: ${truncate(errorMessage(error), 220)}`);
    }
    // Actions runs do not include commit statuses published by local-ci or other reporters.
    try { jobs.push(...await getCommitStatusJobs(pi, cwd, repository, sha)); }
    catch (error) { errors.push(`Commit-status lookup unavailable: ${truncate(errorMessage(error), 220)}`); }
    return { jobs, errors, warnings: [`PR checks unavailable for the checkout: ${truncate(errorMessage(prError), 220)}`] };
  }
}

type CirclePipelineList = {
  items?: Array<{ id: string; number?: number; state?: string; created_at?: string; vcs?: { revision?: string; branch?: string } }>;
};
type CircleWorkflowList = {
  items?: Array<{ id: string; name: string; status?: string; created_at?: string; stopped_at?: string }>;
};
type CircleJobList = {
  items?: Array<{ id: string; name: string; job_number?: number; status?: string; started_at?: string; stopped_at?: string; duration?: number; web_url?: string }>;
};

async function circleFetch<T>(path: string, token: string): Promise<T> {
  const response = await fetch(`https://circleci.com/api/v2${path}`, {
    headers: { Accept: "application/json", "Circle-Token": token },
    signal: AbortSignal.timeout(LOG_FETCH_TIMEOUT), redirect: "error",
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`CircleCI API ${response.status} ${response.statusText}${text ? `: ${truncate(text, 500)}` : ""}`);
  }
  return (await response.json()) as T;
}

async function circlePost<T>(path: string, token: string, body: unknown): Promise<T> {
  const response = await fetch(`https://circleci.com/api/v2${path}`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json", "Circle-Token": token },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`CircleCI API ${response.status} ${response.statusText}${text ? `: ${truncate(text, 500)}` : ""}`);
  }
  return (await response.json().catch(() => ({}))) as T;
}

async function fetchCircleCIJobs(repo: GitHubRepo, branch: string, sha: string): Promise<CiJob[]> {
  const token = process.env.CIRCLECI_TOKEN?.trim();
  if (!token) return [];

  const projectPath = `/project/gh/${encodeURIComponent(repo.owner)}/${encodeURIComponent(repo.repo)}`;
  const pipelineList = await circleFetch<CirclePipelineList>(`${projectPath}/pipeline?branch=${encodeURIComponent(branch)}`, token);
  const pipelines = pipelineList.items ?? [];
  if (pipelines.length === 0) return [];

  const pipeline = pipelines.find((item) => item.vcs?.revision === sha);
  if (!pipeline) return [];

  const workflows = await circleFetch<CircleWorkflowList>(`/pipeline/${pipeline.id}/workflow`, token);

  const jobs: CiJob[] = [];
  for (const workflow of workflows.items ?? []) {
    const workflowJobs = await circleFetch<CircleJobList>(`/workflow/${workflow.id}/job`, token);
    for (const job of workflowJobs.items ?? []) {
      const url = job.web_url ?? (pipeline.number && job.job_number
        ? `https://app.circleci.com/pipelines/github/${repo.owner}/${repo.repo}/${pipeline.number}/workflows/${workflow.id}/jobs/${job.job_number}`
        : undefined);
      jobs.push({
        id: `circleci:${job.id}`, provider: "circleci", providerHint: "circleci",
        name: `${workflow.name} / ${job.name}`,
        state: normalizeCircleState(job.status), url, jobNumber: job.job_number,
        workflowId: workflow.id,
        startedAt: job.started_at, completedAt: job.stopped_at, durationMs: job.duration,
      });
    }
  }
  return jobs;
}

async function fetchCiSummary(pi: ExtensionAPI, cwd: string): Promise<CiSummary> {
  const root = await getGitRoot(pi, cwd);
  const [branch, sha, remote] = await Promise.all([getBranch(pi, root), getSha(pi, root), getOriginRemote(pi, root)]);
  const repo = parseGitHubRemote(remote);
  const summary: CiSummary = {
    repo: repo ? `${repo.owner}/${repo.repo}` : undefined,
    branch, sha, checkedAt: Date.now(), jobs: [], warnings: [], errors: [],
  };

  const github: Partial<CiSummary> = summary.repo
    ? await fetchGitHubChecks(pi, root, branch, sha, summary.repo)
    : { warnings: ["No github.com origin found; refusing an implicit repository lookup."] };
  if (github.branch) summary.branch = github.branch;
  if (github.sha) summary.sha = github.sha;
  if (github.prNumber) summary.prNumber = github.prNumber;
  if (github.prUrl) summary.prUrl = github.prUrl;
  if (github.jobs) summary.jobs.push(...github.jobs);
  if (github.warnings) summary.warnings.push(...github.warnings);
  if (github.errors) summary.errors.push(...github.errors);

  const localConfigured = await access(join(root, ".local-ci.toml")).then(() => true, (error: { code?: string }) => {
    if (error.code === "ENOENT" || error.code === "ENOTDIR") return false;
    throw new Error("Cannot inspect .local-ci.toml; local validation availability is unknown.");
  });
  if (localConfigured && github.prNumber && summary.repo) {
    // gh's PR rollup omits status descriptions; the native reporter identifies its aggregate there.
    try {
      const statuses = await getCommitStatusJobs(pi, root, summary.repo, sha);
      summary.jobs = summary.jobs.filter(job => job.provider !== "local-ci" && job.provider !== "github-status");
      summary.jobs.push(...statuses);
    } catch (error) { summary.errors.push(`Commit-status lookup unavailable: ${truncate(errorMessage(error), 220)}`); }
  }
  if (localConfigured && !summary.jobs.some(job => job.isLocalAggregate)) {
    summary.jobs.push({ id: "local-ci-status:unverified", provider: "local-ci", providerHint: "local-ci",
      name: "local-ci publication unverified", state: "unknown",
      summary: "No recognizable published local-ci aggregate found. Inspect local-ci runs/show; local artifacts are not inferred as published validation." });
  }

  const hasCircleChecksFromGitHub = summary.jobs.some((job) => job.providerHint === "circleci");
  const token = process.env.CIRCLECI_TOKEN?.trim();

  if (repo && token) {
    try {
      const circleJobs = await fetchCircleCIJobs(repo, summary.branch, summary.sha);
      if (circleJobs.length > 0) {
        summary.jobs = summary.jobs.filter((job) => job.providerHint !== "circleci");
        summary.jobs.push(...circleJobs);
      } else if (hasCircleChecksFromGitHub) {
        summary.warnings.push("CircleCI API did not find workflow jobs for the current commit; showing GitHub check-rollup data for CircleCI checks.");
      }
    } catch (error) {
      summary.warnings.push(`CircleCI API unavailable: ${truncate(errorMessage(error), 300)}.`);
    }
  } else if (hasCircleChecksFromGitHub && !token) {
    summary.warnings.push("Set CIRCLECI_TOKEN to enrich CircleCI checks with workflow/job details; showing GitHub check-rollup data only.");
  } else if (repo && !token && summary.jobs.length === 0) {
    summary.warnings.push("CircleCI provider disabled: CIRCLECI_TOKEN is not set.");
  }

  if (summary.jobs.length === 0 && summary.warnings.length === 0) {
    summary.warnings.push("No CI checks found for the current branch/SHA.");
  }

  summary.jobs = summary.jobs.map((job) => ({ ...job, repo: summary.repo, sha: summary.sha }));
  return summary;
}

// ---------------------------------------------------------------------------
// Log fetching
// ---------------------------------------------------------------------------

async function fetchGitHubRunLog(pi: ExtensionAPI, cwd: string, repository: string, runId: number, githubJobId: number, failedOnly: boolean): Promise<string> {
  const args = ["run", "view", String(runId), "--repo", repository, "--job", String(githubJobId)];
  if (failedOnly) args.push("--log-failed");
  else args.push("--log");
  const result = await pi.exec("gh", args, { cwd, timeout: LOG_FETCH_TIMEOUT });
  if (result.code !== 0) {
    const details = [
      `gh ${args.join(" ")} failed with exit code ${result.code}`,
      result.stderr ? `stderr: ${truncate(result.stderr, 800)}` : undefined,
      result.stdout ? `stdout: ${truncate(result.stdout, 800)}` : undefined,
    ].filter(Boolean).join("\n");
    throw new Error(details);
  }

  const output = result.stdout || "";
  if (!output.trim() && result.stderr.trim()) throw new Error(`GitHub returned no console output: ${truncate(result.stderr, 800)}`);
  if (!output.trim()) return "(no log output)";
  return getLimitedLogText(output);
}

function getLimitedLogText(output: string): string {
  // ponytail: provider payloads are buffered; add bounded streaming if large logs exhaust memory.
  const lines = output.split("\n");
  if (lines.length > 500) {
    return lines.slice(0, 500).join("\n") + `\n\n... truncated (${lines.length - 500} more lines)`;
  }
  return output;
}

const nonPublicAddresses = new BlockList();
for (const [address, prefixLength] of [
  ["0.0.0.0", 8], ["10.0.0.0", 8], ["100.64.0.0", 10], ["127.0.0.0", 8],
  ["169.254.0.0", 16], ["172.16.0.0", 12], ["192.0.0.0", 24], ["192.0.2.0", 24],
  ["192.88.99.0", 24], ["192.168.0.0", 16], ["198.18.0.0", 15], ["198.51.100.0", 24],
  ["203.0.113.0", 24], ["224.0.0.0", 4], ["240.0.0.0", 4],
] as Array<[string, number]>) nonPublicAddresses.addSubnet(address, prefixLength, "ipv4");
// IPv6 must be global unicast, excluding protocol assignments, 6to4, and documentation ranges.
for (const [address, prefixLength] of [["2001::", 23], ["2001:db8::", 32], ["2002::", 16], ["3fff::", 20]] as Array<[string, number]>) {
  nonPublicAddresses.addSubnet(address, prefixLength, "ipv6");
}
const globalIpv6Addresses = new BlockList();
globalIpv6Addresses.addSubnet("2000::", 3, "ipv6");

const getPublicAddress: LookupFunction = (hostname, options, callback) => {
  lookup(hostname, { ...options, all: true }, (error, addresses) => {
    if (error) { callback(error, ""); return; }
    const allPublic = addresses.length > 0 && addresses.every(({ address, family }) =>
      (family === 4 && isIP(address) === 4 && !nonPublicAddresses.check(address, "ipv4")) ||
      (family === 6 && isIP(address) === 6 && globalIpv6Addresses.check(address, "ipv6") && !nonPublicAddresses.check(address, "ipv6")));
    if (!allPublic) { callback(new Error("CircleCI destination is not public."), ""); return; }
    if (options.all) callback(null, addresses);
    else callback(null, addresses[0].address, addresses[0].family);
  });
};

async function getCircleLogJson(url: string, signal: AbortSignal, headers?: Record<string, string>): Promise<unknown> {
  let requestUrl: URL;
  try { requestUrl = new URL(url); }
  catch { throw new Error("CircleCI returned an invalid log URL; the URL is omitted for security."); }
  const hostname = requestUrl.hostname.toLowerCase().replace(/\.$/, "");
  if (requestUrl.protocol !== "https:" || requestUrl.username || requestUrl.password ||
      hostname === "localhost" || hostname.endsWith(".localhost") || isIP(hostname.replace(/^\[|\]$/g, ""))) {
    throw new Error("CircleCI returned an unsafe log URL; refusing to fetch it.");
  }
  let result: { statusCode: number; output: string };
  try {
    result = await new Promise<{ statusCode: number; output: string }>((accept, reject) => {
      // Validate the addresses used by this socket, not a separate DNS preflight.
      // A fresh direct connection avoids pooled sockets/proxy-side DNS; redirects are not followed.
      const request = get(requestUrl.href, { headers, signal, agent: false, lookup: getPublicAddress }, response => {
        response.on("error", reject);
        const statusCode = response.statusCode ?? 0;
        if (statusCode < 200 || statusCode >= 300) {
          accept({ statusCode, output: "" });
          response.destroy();
          return;
        }
        let output = "";
        response.setEncoding("utf8");
        response.on("data", (chunk: string) => { output += chunk; });
        response.on("end", () => { accept({ statusCode, output }); });
      });
      request.on("error", reject);
    });
  } catch {
    // Transport errors can contain signed URLs. Never forward their message or cause.
    throw new Error("CircleCI log request was blocked, failed, or timed out; URL details are omitted for security.");
  }
  if (result.statusCode < 200 || result.statusCode >= 300) throw new Error(`CircleCI log request failed (HTTP ${result.statusCode}); no logs were returned.`);
  try { return JSON.parse(result.output); }
  catch { throw new Error("CircleCI log response was not valid JSON; no logs were returned."); }
}

async function fetchCircleCIJobOutput(_cwd: string, job: CiJob): Promise<string> {
  const token = process.env.CIRCLECI_TOKEN?.trim();
  if (!token) throw new Error("Set CIRCLECI_TOKEN to retrieve CircleCI console output.");
  if (!job.repo || !Number.isSafeInteger(job.jobNumber) || !job.jobNumber || job.jobNumber < 1) {
    throw new Error("CircleCI repository/job number is unavailable; refresh with CircleCI enrichment enabled.");
  }
  const repositoryPath = job.repo.split("/").map(encodeURIComponent).join("/");
  const signal = AbortSignal.timeout(LOG_FETCH_TIMEOUT);
  const metadata = await getCircleLogJson(
    `https://circleci.com/api/v1.1/project/github/${repositoryPath}/${job.jobNumber}`,
    signal, { Accept: "application/json", "Circle-Token": token },
  ) as { vcs_revision?: string; steps?: Array<{ actions?: Array<{ name?: string; index?: number; output_url?: string }> }> };
  if (!metadata || !Array.isArray(metadata.steps)) throw new Error("CircleCI step metadata is unavailable; no console output was retrieved.");
  if (job.sha && metadata.vcs_revision !== job.sha) throw new Error("CircleCI job commit does not match the selected CI snapshot.");
  const actions = metadata.steps.flatMap((step) => Array.isArray(step?.actions) ? step.actions : [])
    .filter((action) => action && typeof action.output_url === "string");
  if (!actions.length) throw new Error("No CircleCI console output is available for this job; open its job page or retry after steps finish.");

  const output: string[] = [];
  for (const action of actions) {
    // Output URLs are presigned. API credentials must not leave circleci.com.
    const messages = await getCircleLogJson(action.output_url!, signal);
    if (!Array.isArray(messages) || messages.some((entry) => !entry || typeof entry.message !== "string")) {
      throw new Error("CircleCI console output has an unexpected format; no logs were returned.");
    }
    output.push(`--- ${action.name ?? "Step output"} (parallel index ${action.index ?? "unknown"}) ---\n${messages.map((entry) => entry.message).join("")}`);
  }
  return getLimitedLogText(output.join("\n\n"));
}

type CiJobSelection = { jobId?: string; runId?: number; jobNumber?: number };

function getSelectedJob(jobs: CiJob[], selection: CiJobSelection): CiJob {
  if (!selection.jobId && selection.runId === undefined && selection.jobNumber === undefined) {
    throw new Error("Supply a job ID/name, GitHub runId, or CircleCI jobNumber.");
  }
  let candidates = jobs.filter((job) =>
    (selection.runId === undefined || (job.provider === "github" && job.runId === selection.runId)) &&
    (selection.jobNumber === undefined || (job.provider === "circleci" && job.jobNumber === selection.jobNumber)));
  if (selection.jobId) {
    const exactId = candidates.filter((job) => job.id === selection.jobId);
    const search = selection.jobId.toLowerCase();
    const exactName = candidates.filter((job) => job.name.toLowerCase() === search);
    const explicitId = /^(github:|github-run:|github-job:|github-status:|circleci:|local-ci-status:|local-ci:)/i.test(selection.jobId);
    candidates = explicitId || exactId.length ? exactId : exactName.length ? exactName
      : candidates.filter((job) => job.id.toLowerCase().includes(search) || job.name.toLowerCase().includes(search));
  }
  if (candidates.length === 1) return candidates[0];
  const available = (candidates.length ? candidates : jobs).map((job) => `${job.id} (${job.name}; runId=${job.runId ?? "none"}; jobNumber=${job.jobNumber ?? "none"})`).join("\n");
  throw new Error(`${candidates.length ? "Ambiguous job selection; supply an exact job ID along with any runId." : "Job not found; supplied identifiers must all match."}\nAvailable jobs:\n${available || "none"}`);
}

async function getLogJob(pi: ExtensionAPI, cwd: string, summary: CiSummary, selection: CiJobSelection): Promise<CiJob> {
  if (selection.jobId?.startsWith("local-ci:")) {
    const local = selection.jobId.match(/^local-ci:([A-Za-z0-9][A-Za-z0-9_-]*)(?::([A-Za-z0-9][A-Za-z0-9._-]*))?$/);
    if (!local || selection.runId !== undefined || selection.jobNumber !== undefined) {
      throw new Error("Use local-ci:<run-id>[:<step-id>] without GitHub runId or CircleCI jobNumber constraints.");
    }
    return { id: selection.jobId, provider: "local-ci", providerHint: "local-ci", repo: summary.repo, sha: summary.sha,
      localRunId: local[1], localStepId: local[2], state: "unknown", name: `local-ci snapshot ${local[1]} / ${local[2] ?? "runner events"}` };
  }
  const aggregateRun = selection.jobId?.match(/^github-run:(\d+)$/);
  const runId = selection.runId ?? (aggregateRun ? Number(aggregateRun[1]) : undefined);
  for (const [name, value] of Object.entries({ runId, jobNumber: selection.jobNumber })) {
    if (value !== undefined && (!Number.isSafeInteger(value) || value < 1)) throw new Error(`${name} must be a positive integer.`);
  }
  if (aggregateRun && selection.runId !== undefined && Number(aggregateRun[1]) !== selection.runId) {
    throw new Error("Conflicting job ID and runId; they must identify the same run.");
  }
  const explicitJob = selection.jobId?.match(/^github-job:(\d+)$/);
  if (explicitJob) {
    const githubJobId = Number(explicitJob[1]);
    if (!Number.isSafeInteger(githubJobId) || githubJobId < 1 || selection.jobNumber !== undefined || !summary.repo) {
      throw new Error("An exact GitHub job requires a valid repository/job ID and cannot use CircleCI jobNumber.");
    }
    // An earlier attempt's job can be absent from both the rollup and the latest run inventory.
    const job = await execJson<{ id: number; run_id: number; head_sha: string; name: string; status?: string; conclusion?: string; html_url?: string }>(pi, "gh",
      ["api", `repos/${summary.repo}/actions/jobs/${githubJobId}`], cwd);
    if (job.id !== githubJobId || job.head_sha !== summary.sha || !Number.isSafeInteger(job.run_id) || job.run_id < 1 ||
        typeof job.name !== "string" || (runId !== undefined && job.run_id !== runId)) {
      throw new Error("GitHub job does not match the selected run and commit SHA.");
    }
    return { id: `github-job:${githubJobId}`, provider: "github", providerHint: "github-actions",
      repo: summary.repo, sha: summary.sha, runId: job.run_id, githubJobId, name: job.name,
      state: normalizeGitHubState(job.status, job.conclusion), url: job.html_url };
  }
  const hasExactJob = summary.jobs.some(job => job.provider === "github" && job.runId === runId &&
    job.id === selection.jobId && !job.id.startsWith("github-run:"));
  if (runId && !hasExactJob) {
    if (!summary.repo) throw new Error("Repository identity is unavailable for the requested run.");
    const run = await execJson<{ headSha: string; jobs: GhRunJob[] }>(pi, "gh",
      ["run", "view", String(runId), "--repo", summary.repo, "--json", "headSha,jobs"], cwd, 20_000);
    if (run.headSha !== summary.sha) throw new Error("Requested GitHub run does not match the checkout commit SHA.");
    if (!Array.isArray(run.jobs) || !run.jobs.length) throw new Error(`GitHub run ${runId} has no jobs; logs may be unavailable because workflow validation failed before jobs started.`);
    const runJobs = run.jobs.map((job): CiJob => ({
      id: `github-job:${job.databaseId}`, provider: "github", providerHint: "github-actions",
      repo: summary.repo, sha: summary.sha, runId, githubJobId: job.databaseId,
      name: job.name, state: normalizeGitHubState(job.status, job.conclusion),
      url: job.url ?? `https://github.com/${summary.repo}/actions/runs/${runId}/job/${job.databaseId}`,
    }));
    summary.jobs = [...summary.jobs.filter((job) => job.runId !== runId), ...runJobs];
  }
  return getSelectedJob(summary.jobs, { ...selection, runId, jobId: aggregateRun ? undefined : selection.jobId });
}

const LOCAL_CI_LOG_HELP = "Published commit statuses do not identify an Actions job or local run. For local-ci, inspect `local-ci runs --json` and `local-ci show <run-id> --json`, then request jobId `local-ci:<run-id>:<step-id>` (omit step for runner events). Otherwise use the provider's job page.";

type LocalSnapshot = {
  run_id: string; run_dir: string;
  meta: { run_id: string; repo_root: string; repo_slug: string; head_sha: string; head_tree_hash?: string; worktree_tree_hash: string; dirty_worktree?: boolean };
  steps: Array<{ step_id: string }>;
};

function getLocalPublicationEvidence(events: unknown[], runId: string, repo: string, sha: string): string {
  const attempts = new Map<string, Record<string, unknown>[]>();
  const sequences = new Map<unknown, number>();
  let unattributed = 0;
  for (const value of events) {
    if (!value || typeof value !== "object" || Array.isArray(value)) { unattributed++; continue; }
    const event = value as Record<string, unknown>;
    sequences.set(event.sequence, (sequences.get(event.sequence) ?? 0) + 1);
    if (!(typeof event.type === "string" && event.type.startsWith("github.status.")) && event.github_post === undefined) continue;
    const post = event.github_post;
    if (!post || typeof post !== "object" || Array.isArray(post)) { unattributed++; continue; }
    const attemptId = (post as Record<string, unknown>).attempt_id;
    if (typeof attemptId !== "string" || !attemptId.trim()) { unattributed++; continue; }
    const records = attempts.get(attemptId) ?? [];
    records.push(event);
    attempts.set(attemptId, records);
  }
  const lines = [
    "Historical publication evidence (local records, not signed attestations):",
    "Acknowledgements do not prove current GitHub status, complete publication, latest resumed coverage, current validation, or deployment permission.",
  ];
  for (const [attemptId, records] of attempts) {
    const [request, outcome] = records;
    const post = request.github_post as Record<string, unknown>;
    const validRecords = records.every(event => {
      const target = event.github_post as Record<string, unknown>;
      return event.run_id === runId && Number.isSafeInteger(event.sequence) && Number(event.sequence) > 0 &&
        sequences.get(event.sequence) === 1 && typeof event.time === "string" &&
        /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z$/.test(event.time) && Number.isFinite(Date.parse(event.time)) &&
        new Date(event.time).toISOString().slice(0, 19) === event.time.slice(0, 19) &&
        (event.step_id === undefined || (typeof event.step_id === "string" && event.step_id.length > 0)) &&
        typeof event.status === "string" && ["pending", "success", "failure", "error"].includes(event.status) &&
        target.version === 1 && typeof target.source === "string" && ["execution", "publish"].includes(target.source) &&
        typeof target.repo === "string" && /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(target.repo) &&
        typeof target.sha === "string" && /^[a-f0-9]{40}(?:[a-f0-9]{24})?$/.test(target.sha) &&
        typeof target.context === "string" && target.context.trim().length > 0;
    });
    const acknowledged = validRecords && records.length === 2 &&
      request.type === "github.status.requested" && outcome.type === "github.status.posted" &&
      Number(request.sequence) < Number(outcome.sequence) && request.step_id === outcome.step_id && request.status === outcome.status &&
      ["version", "attempt_id", "repo", "sha", "context", "source"].every(field =>
        post[field] === (outcome.github_post as Record<string, unknown>)[field]);
    if (!acknowledged) {
      lines.push(`Attempt ${JSON.stringify(attemptId)}: unknown (missing, failed, conflicting, malformed, or unsupported receipt).`);
      continue;
    }
    const target = JSON.stringify({ repo: post.repo, sha: post.sha, context: post.context, source: post.source,
      step: request.step_id ?? "(aggregate)", status: request.status });
    lines.push(`Attempt ${JSON.stringify(attemptId)}: acknowledged ${target}; ${post.repo === repo && post.sha === sha ? "selected target" : "different target, not evidence for the selected commit"}.`);
  }
  if (unattributed) lines.push(`${unattributed} legacy/malformed records without an attempt ID: outcome unknown.`);
  if (!attempts.size) lines.push("No attributable receipts: publication unknown (not proof that nothing was posted).");
  return lines.join("\n");
}

async function getLocalJobLogs(pi: ExtensionAPI, cwd: string, job: CiJob): Promise<string> {
  if (!job.localRunId || !job.sha) throw new Error(LOCAL_CI_LOG_HELP);
  const root = await getGitRoot(pi, cwd);
  const runDirectory = join(root, ".local-ci", "runs", job.localRunId);
  const snapshot = await execJson<LocalSnapshot>(pi, "local-ci", ["show", job.localRunId, "--json"], root);
  const tree = await execText(pi, "git", ["rev-parse", `${job.sha}^{tree}`], root);
  const hasValidHashes = [snapshot?.meta?.head_sha, snapshot?.meta?.worktree_tree_hash]
    .every(value => typeof value === "string" && /^[a-f0-9]{40}(?:[a-f0-9]{24})?$/.test(value));
  const matchesCommitTree = snapshot?.meta?.worktree_tree_hash === tree;
  const isDirtySnapshotOfCommit = snapshot?.meta?.dirty_worktree === true && snapshot.meta.head_sha === job.sha &&
    snapshot.meta.head_tree_hash === tree;
  if (snapshot?.run_id !== job.localRunId || snapshot.run_dir !== runDirectory ||
      snapshot.meta?.run_id !== job.localRunId || snapshot.meta.repo_root !== root ||
      (job.repo && snapshot.meta.repo_slug !== job.repo) || !hasValidHashes ||
      (snapshot.meta.dirty_worktree !== undefined && typeof snapshot.meta.dirty_worktree !== "boolean") ||
      (!matchesCommitTree && !isDirtySnapshotOfCommit)) {
    throw new Error("Stored local-ci run identity or snapshot tree does not match the selected checkout/commit. Inspect it with the native CLI; no logs were returned.");
  }
  if (job.localStepId && (!Array.isArray(snapshot.steps) || snapshot.steps.filter(step => step?.step_id === job.localStepId).length !== 1)) {
    throw new Error("The exact local-ci step is missing or ambiguous; inspect local-ci show for step IDs.");
  }
  const selector = job.localStepId ? ["--step", job.localStepId, "--combined"] : ["--runner"];
  const output = await execJson<{ run_id: string; run_dir: string; source: string; step_id?: string; view?: string; content?: string; events?: unknown[] }>(
    pi, "local-ci", ["logs", job.localRunId, ...selector, "--json"], root, LOG_FETCH_TIMEOUT);
  if (output?.run_id !== job.localRunId || output.run_dir !== runDirectory ||
      output.source !== (job.localStepId ? "step" : "runner") ||
      (job.localStepId && (output.step_id !== job.localStepId || output.view !== "combined")) ||
      (output.content !== undefined && typeof output.content !== "string") ||
      (output.events !== undefined && !Array.isArray(output.events))) {
    throw new Error("local-ci log output does not match the requested run/step or expected format.");
  }
  const logs = job.localStepId ? output.content ?? "" : (output.events ?? []).map(event => JSON.stringify(event)).join("\n");
  return getLimitedLogText([
    `Local snapshot: ${job.localRunId}; original HEAD ${snapshot.meta.head_sha}; dirty=${snapshot.meta.dirty_worktree ?? false}; stored tree ${snapshot.meta.worktree_tree_hash}.`,
    matchesCommitTree ? `Tree matches selected commit ${job.sha}.` : `Stored dirty snapshot based on ${job.sha}; current working-tree contents were not compared.`,
    job.localStepId ? "These logs are not proof of publication, current worktree validation, or current config/plan validity." :
      getLocalPublicationEvidence(output.events ?? [], job.localRunId, snapshot.meta.repo_slug, job.sha),
    job.localStepId ? `Step ${job.localStepId} combined output:` : "local-ci runner events:",
    logs || "(no log output)",
  ].join("\n"));
}

async function fetchJobLogs(pi: ExtensionAPI, cwd: string, job: CiJob): Promise<string> {
  if (job.provider === "local-ci") return getLocalJobLogs(pi, cwd, job);
  if (job.provider === "github-status") throw new Error(LOCAL_CI_LOG_HELP);
  if (!job.repo) throw new Error("Repository identity is unavailable; refresh CI before fetching logs.");
  const githubRunId = job.runId ?? githubRunIdFromUrl(job.url);
  if (job.provider === "github" && githubRunId) {
    const githubJobId = await githubJobIdForSelectedJob(pi, cwd, githubRunId, job);
    return fetchGitHubRunLog(pi, cwd, job.repo, githubRunId, githubJobId, job.state === "failed");
  }
  if (job.provider === "circleci") {
    return await fetchCircleCIJobOutput(cwd, job);
  }
  throw new Error("Log fetching is unavailable for this job type; no logs were retrieved.");
}

async function githubJobIdForSelectedJob(pi: ExtensionAPI, cwd: string, runId: number, job: CiJob): Promise<number> {
  if (!job.repo) throw new Error("Repository identity is unavailable; refresh CI before selecting a job.");
  const explicitJobId = job.githubJobId ?? getGitHubJobIdFromUrl(job.url);
  if (explicitJobId) {
    // The job endpoint also identifies earlier attempts, unlike a latest-attempt job list.
    const selected = await execJson<{ run_id: number; head_sha: string }>(pi, "gh",
      ["api", `repos/${job.repo}/actions/jobs/${explicitJobId}`], cwd, 20_000);
    if (selected.run_id !== runId || (job.sha && selected.head_sha !== job.sha)) {
      throw new Error("GitHub job does not match the selected run and commit SHA.");
    }
    return explicitJobId;
  }
  const run = await execJson<{ headSha: string; jobs: GhRunJob[] }>(pi, "gh",
    ["run", "view", String(runId), "--repo", job.repo, "--json", "headSha,jobs"], cwd, 20_000);
  if (job.sha && run.headSha !== job.sha) throw new Error("GitHub run does not match the selected commit SHA.");
  const jobs = run.jobs;
  if (!Array.isArray(jobs) || !jobs.length) throw new Error(`GitHub run ${runId} has no jobs; no job logs are available.`);
  const sameName = job.id.startsWith("github-run:") ? jobs
    : jobs.filter((runJob) => Boolean(job.githubJobName) && runJob.name === job.githubJobName);
  if (sameName.length === 1) return sameName[0].databaseId;
  if (sameName.length > 1) throw new Error(`Ambiguous GitHub job name ${job.name}; use an exact job ID or URL.`);

  const available = jobs.map((runJob) => runJob.name).filter(Boolean).join(", ");
  throw new Error(`Could not identify the GitHub Actions job id for ${job.name}. Available jobs in run ${runId}: ${available || "none"}`);
}

function circleJobId(job: CiJob): string | undefined {
  if (job.provider !== "circleci") return undefined;
  return job.id.startsWith("circleci:") ? job.id.slice("circleci:".length) : job.id;
}

async function rerunFailedJob(pi: ExtensionAPI, cwd: string, job: CiJob): Promise<string> {
  if (job.provider === "local-ci" || job.provider === "github-status") {
    throw new Error("Commit status reruns are not Actions reruns. Use the owning workflow explicitly; this action will not run, resume, or publish local-ci validation.");
  }
  if (job.state !== "failed") {
    throw new Error(`Selected job is ${job.state}; rerun is only enabled for failed jobs.`);
  }

  const githubRunId = job.runId ?? githubRunIdFromUrl(job.url);
  if (job.provider === "github" && githubRunId) {
    const githubJobId = await githubJobIdForSelectedJob(pi, cwd, githubRunId, job);
    await execText(pi, "gh", ["run", "rerun", String(githubRunId), "--job", String(githubJobId), ...(job.repo ? ["--repo", job.repo] : [])], cwd, 20_000);
    return `Requested GitHub rerun for ${job.name} in run ${githubRunId}.`;
  }

  if (job.provider === "circleci") {
    const token = process.env.CIRCLECI_TOKEN?.trim();
    if (!token) throw new Error("Set CIRCLECI_TOKEN to rerun CircleCI workflow jobs.");
    if (!job.workflowId) throw new Error("CircleCI workflow id is unavailable for this job; refresh after enabling CircleCI enrichment.");
    const jobId = circleJobId(job);
    if (!jobId) throw new Error("CircleCI job id is unavailable for this job.");
    await circlePost(`/workflow/${job.workflowId}/rerun`, token, { jobs: [jobId] });
    return `Requested CircleCI rerun for ${job.name}.`;
  }

  throw new Error("Rerun is not supported for this job type yet.");
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function durationMs(job: CiJob): number | undefined {
  if (typeof job.durationMs === "number" && job.durationMs > 0) return job.durationMs;
  if (!job.startedAt) return undefined;
  const start = Date.parse(job.startedAt);
  if (Number.isNaN(start)) return undefined;
  const end = job.completedAt ? Date.parse(job.completedAt) : Date.now();
  if (Number.isNaN(end) || end < start) return undefined;
  return end - start;
}

function formatDuration(ms: number | undefined): string {
  if (!ms) return "";
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) return `${seconds}s`;
  const hours = Math.floor(minutes / 60);
  if (hours === 0) return `${minutes}m ${seconds}s`;
  return `${hours}h ${minutes % 60}m`;
}

function icon(state: CiState): string {
  if (ASCII_ICONS) {
    switch (state) {
      case "success": return "PASS";
      case "failed": return "FAIL";
      case "running": return "RUN";
      case "pending": return "WAIT";
      case "cancelled": return "CANCEL";
      case "skipped": return "SKIP";
      default: return "?";
    }
  }

  switch (state) {
    case "success": return "✅";
    case "failed": return "❌";
    case "running": return "⏳";
    case "pending": return "⌛";
    case "cancelled": return "🚫";
    case "skipped": return "↷";
    default: return "?";
  }
}

function stateRank(state: CiState): number {
  return { failed: 0, running: 1, pending: 2, cancelled: 3, unknown: 4, success: 5, skipped: 6 }[state];
}

function groupJobs(summary: CiSummary) {
  const jobs = [...summary.jobs].sort((a, b) => stateRank(a.state) - stateRank(b.state) || a.name.localeCompare(b.name));
  return {
    failed: jobs.filter((job) => job.state === "failed"),
    running: jobs.filter((job) => job.state === "running" || job.state === "pending"),
    cancelled: jobs.filter((job) => job.state === "cancelled"),
    unknown: jobs.filter((job) => job.state === "unknown"),
    passing: jobs.filter((job) => job.state === "success"),
    skipped: jobs.filter((job) => job.state === "skipped"),
  };
}

// ---------------------------------------------------------------------------
// Widget / Status rendering (existing style)
// ---------------------------------------------------------------------------

function renderJob(job: CiJob): string[] {
  const duration = formatDuration(durationMs(job));
  const provider = { github: "GitHub", circleci: "CircleCI", "github-status": "Commit status", "local-ci": "local-ci" }[job.provider];
  const lines = [`  ${icon(job.state)} ${job.name}${duration ? ` · ${duration}` : ""} · ${provider}`];
  if (job.summary) lines.push(`     ${job.summary}`);
  if (job.url) lines.push(`     ${job.url}`);
  return lines;
}

function renderSummary(summary: CiSummary): string[] {
  const groups = groupJobs(summary);
  const lines: string[] = [];
  const repo = summary.repo ? `${summary.repo} · ` : "";
  const pr = summary.prNumber ? ` · PR #${summary.prNumber}` : "";
  lines.push(`CI for ${repo}${summary.branch}${pr}`);
  lines.push(`SHA ${shortSha(summary.sha)} · updated ${new Date(summary.checkedAt).toLocaleTimeString()}`);
  if (summary.prUrl) lines.push(summary.prUrl);
  if (summary.errors.length > 0) {
    lines.push("", "Errors:");
    for (const error of summary.errors) lines.push(`  ❌ ${error}`);
  }
  if (summary.warnings.length > 0) {
    lines.push("", "Warnings:");
    for (const warning of summary.warnings) lines.push(`  ⚠️ ${warning}`);
  }
  if (summary.jobs.length === 0) return lines;
  if (groups.failed.length > 0) {
    lines.push("", `❌ Failing (${groups.failed.length})`);
    for (const job of groups.failed) lines.push(...renderJob(job));
  }
  if (groups.running.length > 0) {
    lines.push("", `⏳ Running/Pending (${groups.running.length})`);
    for (const job of groups.running) lines.push(...renderJob(job));
  }
  if (groups.cancelled.length > 0) {
    lines.push("", `🚫 Cancelled (${groups.cancelled.length})`);
    for (const job of groups.cancelled) lines.push(...renderJob(job));
  }
  if (groups.unknown.length > 0) {
    lines.push("", `? Unknown (${groups.unknown.length})`);
    for (const job of groups.unknown) lines.push(...renderJob(job));
  }
  if (groups.passing.length > 0) {
    lines.push("", `✅ Passing (${groups.passing.length})`);
    for (const job of groups.passing.slice(0, MAX_RENDERED_PASSING_JOBS)) lines.push(...renderJob(job));
    if (groups.passing.length > MAX_RENDERED_PASSING_JOBS) {
      lines.push(`  … ${groups.passing.length - MAX_RENDERED_PASSING_JOBS} more passing checks`);
    }
  }
  if (groups.skipped.length > 0) lines.push("", `↷ Skipped/Neutral: ${groups.skipped.length}`);
  return lines;
}

function compactStatus(summary: CiSummary): string {
  const hint = `· ${keyComboLabel(CI_DETAIL_SHORTCUT)} details`;
  if (summary.errors.length) return `CI incomplete · ${summary.errors.length} lookup error(s) ${hint}`;
  if (summary.jobs.length === 0) return `${summary.errors.length > 0 ? "CI unavailable" : "CI no checks"} ${hint}`;
  const groups = groupJobs(summary);
  if (groups.failed.length > 0) return `CI ❌ ${groups.failed.length} failed · ${groups.running.length} running · ${groups.passing.length} passing ${hint}`;
  if (groups.running.length > 0) return `CI ⏳ ${groups.running.length} running · ${groups.passing.length} passing ${hint}`;
  if (groups.cancelled.length > 0) return `CI 🚫 ${groups.cancelled.length} cancelled · ${groups.passing.length} passing ${hint}`;
  if (groups.unknown.length > 0) return `CI ? ${groups.unknown.length} unknown · ${groups.passing.length} passing ${hint}`;
  return `CI ✅ all passed (${groups.passing.length}) ${hint}`;
}

function renderDetailedSummary(summary: CiSummary): string {
  const groups = groupJobs(summary);
  const lines: string[] = [];
  const repo = summary.repo ? `${summary.repo} · ` : "";
  const pr = summary.prNumber ? ` · PR #${summary.prNumber}` : "";
  lines.push(`CI for ${repo}${summary.branch}${pr}`);
  lines.push(`SHA ${shortSha(summary.sha)} · updated ${new Date(summary.checkedAt).toLocaleTimeString()}`);
  if (summary.prUrl) lines.push(summary.prUrl);

  if (summary.errors.length > 0) {
    lines.push("", "Errors:");
    for (const error of summary.errors) lines.push(`  ❌ ${error}`);
  }
  if (summary.warnings.length > 0) {
    lines.push("", "Warnings:");
    for (const warning of summary.warnings) lines.push(`  ⚠️ ${warning}`);
  }
  if (summary.jobs.length === 0) return lines.join("\n");

  if (groups.failed.length > 0) {
    lines.push("", `❌ Failing (${groups.failed.length})`);
    for (const job of groups.failed) {
      lines.push(...renderJob(job));
      // Add job detail lines for the LLM
      const dur = formatDuration(durationMs(job));
      lines.push(`     id: ${job.id}, provider: ${job.provider}, state: ${job.state}${dur ? `, duration: ${dur}` : ""}`);
      if (job.runId) lines.push(`     github_run_id: ${job.runId}`);
      if (job.jobNumber) lines.push(`     circleci_job_number: ${job.jobNumber}`);
    }
  }
  if (groups.running.length > 0) {
    lines.push("", `⏳ Running/Pending (${groups.running.length})`);
    for (const job of groups.running) lines.push(...renderJob(job));
  }
  if (groups.cancelled.length > 0) {
    lines.push("", `🚫 Cancelled (${groups.cancelled.length})`);
    for (const job of groups.cancelled) lines.push(...renderJob(job));
  }
  if (groups.unknown.length > 0) {
    lines.push("", `? Unknown (${groups.unknown.length})`);
    for (const job of groups.unknown) lines.push(...renderJob(job));
  }
  if (groups.passing.length > 0) {
    lines.push("", `✅ Passing (${groups.passing.length})`);
    for (const job of groups.passing.slice(0, MAX_RENDERED_PASSING_JOBS)) lines.push(...renderJob(job));
    if (groups.passing.length > MAX_RENDERED_PASSING_JOBS) {
      lines.push(`  … ${groups.passing.length - MAX_RENDERED_PASSING_JOBS} more`);
    }
  }
  if (groups.skipped.length > 0) lines.push("", `↷ Skipped/Neutral: ${groups.skipped.length}`);
  return lines.join("\n");
}

function hasActiveJobs(summary: CiSummary): boolean {
  return summary.jobs.some((job) => job.state === "running" || job.state === "pending");
}

function allPassing(summary: CiSummary): boolean {
  return summary.errors.length === 0 && summary.jobs.length > 0 && summary.jobs.every((job) => ["success", "skipped"].includes(job.state));
}

function failedJobs(summary: CiSummary): CiJob[] {
  return summary.jobs.filter((job) => job.state === "failed");
}

function failureSignature(summary: CiSummary): string {
  const failed = failedJobs(summary);
  if (failed.length === 0) return "";
  return [summary.sha, ...failed.map((job) => `${job.provider}:${job.id}:${job.name}`).sort()].join("|");
}

function summarizeJobNames(jobs: CiJob[], max = 4): string {
  const names = jobs.map((job) => job.name);
  if (names.length <= max) return names.join(", ");
  return `${names.slice(0, max).join(", ")} + ${names.length - max} more`;
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

function notifyTransitions(ctx: ExtensionContext, previous: CiSummary | undefined, next: CiSummary, reason: string) {
  const currentFailureSignature = failureSignature(next);
  const currentFailures = failedJobs(next);
  if (previous && previous.sha !== next.sha && hasActiveJobs(next)) {
    ctx.ui.notify(`CI started for new commit ${shortSha(next.sha)}`, "info");
  } else if (!previous && reason === "git-push" && hasActiveJobs(next)) {
    ctx.ui.notify(`CI started for ${shortSha(next.sha)}`, "info");
  }
  if (currentFailureSignature) {
    hadFailureSinceLastSuccess = true;
    if (!previous && reason === "startup") {
      lastFailureSignature = currentFailureSignature;
    } else if (currentFailureSignature !== lastFailureSignature) {
      ctx.ui.notify(`CI failed: ${summarizeJobNames(currentFailures)}`, "error");
      lastFailureSignature = currentFailureSignature;
    }
  }
  if (!currentFailureSignature && hadFailureSinceLastSuccess && allPassing(next)) {
    ctx.ui.notify(`CI recovered: all checks passed for ${shortSha(next.sha)}`, "info");
    hadFailureSinceLastSuccess = false;
    lastFailureSignature = "";
  }
}

function renderError(error: unknown): string[] {
  return ["CI unavailable", "", errorMessage(error)];
}

// ---------------------------------------------------------------------------
// Polling
// ---------------------------------------------------------------------------

function clearTimer() {
  if (timer) clearTimeout(timer);
  timer = undefined;
}

function scheduleNext(ctx: ExtensionContext, summary: CiSummary | undefined) {
  if (!watching) return;
  clearTimer();
  const delay = summary ? (hasActiveJobs(summary) ? ACTIVE_POLL_MS : COMPLETE_POLL_MS) : ERROR_POLL_MS;
  timer = setTimeout(() => { void refreshAndRender(ctx, "watch").catch(() => undefined); }, delay);
}

async function refreshAndRender(ctx: ExtensionContext, reason: string): Promise<CiSummary | undefined> {
  if (refreshInFlight) return lastSummary;
  refreshInFlight = true;
  try {
    const summary = await fetchCiSummary(extensionApi, ctx.cwd);
    if (widgetVisible) ctx.ui.setWidget(WIDGET_KEY, renderSummary(summary), { placement: "aboveEditor" });
    else ctx.ui.setWidget(WIDGET_KEY, undefined);
    ctx.ui.setStatus(STATUS_KEY, compactStatus(summary));
    notifyTransitions(ctx, lastSummary, summary, reason);
    lastSummary = summary;
    lastErrorMessage = "";
    scheduleNext(ctx, summary);
    return summary;
  } catch (error) {
    const message = errorMessage(error);
    ctx.ui.setStatus(STATUS_KEY, `CI unavailable · ${keyComboLabel(CI_DETAIL_SHORTCUT)} details`);
    if (widgetVisible) ctx.ui.setWidget(WIDGET_KEY, renderError(error), { placement: "aboveEditor" });
    if (reason !== "startup" && message !== lastErrorMessage) {
      ctx.ui.notify(`CI refresh failed: ${truncate(message, 240)}`, "warning");
      lastErrorMessage = message;
    } else if (reason === "startup") {
      lastErrorMessage = message;
    }
    scheduleNext(ctx, undefined);
    return undefined;
  } finally {
    refreshInFlight = false;
  }
}

// ---------------------------------------------------------------------------
// Watch controls
// ---------------------------------------------------------------------------

function startWatching(ctx: ExtensionContext, reason: string) {
  watching = true;
  clearTimer();
  void refreshAndRender(ctx, reason).catch(() => undefined);
}

function stopWatching(ctx: ExtensionContext) {
  watching = false;
  clearTimer();
  ctx.ui.notify("Stopped CI watch", "info");
}

function looksLikeGitPush(command: string): boolean {
  return /(^|[;&|\s])git\s+push(\s|$)/.test(command);
}

/** Cross-platform URL opener. Falls back to the already visible URL in the UI. */
function openUrl(pi: ExtensionAPI, url: string) {
  const platform = process.platform;
  const command = platform === "darwin" ? "open" : platform === "win32" ? "cmd" : "xdg-open";
  const args = platform === "win32" ? ["/c", "start", "", url] : [url];
  pi.exec(command, args, { timeout: 5000 }).catch(() => {
    // Fallback: URL is already shown in the UI.
  });
}

async function withTempClipboardFile<T>(text: string, fn: (path: string) => Promise<T>): Promise<T> {
  const path = join(tmpdir(), `pi-ci-clipboard-${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2)}.txt`);
  await writeFile(path, text, "utf8");
  try {
    return await fn(path);
  } finally {
    await unlink(path).catch(() => undefined);
  }
}

/** Cross-platform clipboard copy. */
async function copyToClipboard(pi: ExtensionAPI, text: string): Promise<void> {
  await withTempClipboardFile(text, async (path) => {
    if (process.platform === "win32") {
      await execText(pi, "cmd", ["/c", `clip < "${path.replace(/"/g, "\"\"")}"`], process.cwd(), 5_000);
    } else if (process.platform === "darwin") {
      await execText(pi, "bash", ["-c", `pbcopy < "$1"`, "bash", path], process.cwd(), 5_000);
    } else {
      await execText(pi, "bash", ["-c", `if command -v wl-copy >/dev/null 2>&1; then wl-copy < "$1"; elif command -v xclip >/dev/null 2>&1; then xclip -selection clipboard < "$1"; else echo 'No clipboard command found (install wl-copy or xclip)' >&2; exit 127; fi`, "bash", path], process.cwd(), 5_000);
    }
  });
}

// ===========================================================================
// INTERACTIVE CI DETAIL OVERLAY
// ===========================================================================

type DetailView = "jobs" | "detail" | "loadingLogs" | "help" | "pickCi" | "pickCycle";
type CiKey = string;
type CycleKey = string;

const IMPORTANT_STATES = new Set<CiState>(["failed", "running", "pending", "cancelled", "unknown"]);

type CiDetailResult = { action: "fix"; job: CiJob; summary: CiSummary } | undefined;

type CiModel = {
  id: string;
  name: string;
  provider: string;
  contextWindow?: number;
  maxTokens?: number;
};

interface CiKeybindings {
  matches(data: string, keybinding: string): boolean;
  getKeys?(keybinding: string): string[];
}

type PromptAction = "run" | "queue" | "edit" | "cancel";


function keyLabel(keybindings: CiKeybindings | undefined, keybinding: string, fallback: string): string {
  try {
    const keys = keybindings?.getKeys?.(keybinding);
    if (keys && keys.length > 0) {
      return keys[0]
        .split("+")
        .map((part) => part.length === 1 ? part.toUpperCase() : part[0].toUpperCase() + part.slice(1))
        .join("+");
    }
  } catch {
    // Use fallback below.
  }
  return fallback;
}

function matchesBinding(keybindings: CiKeybindings | undefined, data: string, keybinding: string, fallback?: string): boolean {
  try {
    if (keybindings?.matches(data, keybinding)) return true;
  } catch {
    // App keybindings may not be available in older pi versions.
  }
  return fallback ? matchesKey(data, fallback) : false;
}

class FixPromptPreview {
  private cachedWidth?: number;
  private cachedLines?: string[];
  public onAction?: (action: PromptAction) => void;

  constructor(
    private theme: Theme,
    private jobName: string,
    private modelLabel: string,
    private prompt: string,
    private keybindings?: CiKeybindings,
  ) {}

  handleInput(data: string): void {
    if (matchesBinding(this.keybindings, data, "app.message.followUp")) {
      this.onAction?.("queue");
    } else if (matchesBinding(this.keybindings, data, "tui.select.confirm", Key.enter) || matchesKey(data, Key.enter)) {
      this.onAction?.("run");
    } else if (data === "e" || data === "E") {
      this.onAction?.("edit");
    } else if (matchesKey(data, Key.escape)) {
      this.onAction?.("cancel");
    }
  }

  render(width: number): string[] {
    if (this.cachedLines && this.cachedWidth === width) return this.cachedLines;

    const t = this.theme;
    const container = new Container();
    container.addChild(new DynamicBorder((s: string) => t.fg("accent", s)));
    container.addChild(new Spacer(1));
    container.addChild(new Text(t.fg("accent", t.bold("Fix CI failure")), 1, 0));
    container.addChild(new Text(`Job:   ${this.jobName}`, 1, 0));
    container.addChild(new Text(`Model: ${this.modelLabel}`, 1, 0));
    container.addChild(new Spacer(1));
    container.addChild(new Text(t.fg("dim", "Review the prompt below. Press e to edit, Enter to run, or the follow-up key to queue."), 1, 0));
    container.addChild(new Spacer(1));
    container.addChild(new Text(this.prompt, 1, 0));
    container.addChild(new Spacer(1));
    const queueKey = keyLabel(this.keybindings, "app.message.followUp", "Alt+Enter");
    container.addChild(new Text(t.fg("dim", `Enter run · ${queueKey} queue follow-up · e edit · Esc cancel`), 1, 0));
    container.addChild(new Spacer(1));
    container.addChild(new DynamicBorder((s: string) => t.fg("accent", s)));

    this.cachedWidth = width;
    this.cachedLines = container.render(width);
    return this.cachedLines;
  }

  invalidate(): void {
    this.cachedWidth = undefined;
    this.cachedLines = undefined;
  }
}

class FixPromptEditor {
  private lines: string[];
  private cursorLine: number;
  private cursorCol: number;
  private pendingCancel = false;
  private cachedWidth?: number;
  private cachedLines?: string[];

  public onDone?: (text: string, deliverAs: "normal" | "followUp") => void;
  public onCancel?: () => void;

  constructor(
    initialText: string,
    private theme: Theme,
    private label: string,
    private keybindings?: CiKeybindings,
  ) {
    this.lines = initialText.length > 0 ? initialText.split("\n") : [""];
    this.cursorLine = this.lines.length - 1;
    this.cursorCol = this.lines[this.cursorLine].length;
  }

  handleInput(data: string): void {
    if (this.pendingCancel) {
      if (matchesKey(data, Key.escape)) this.onCancel?.();
      else {
        this.pendingCancel = false;
        this.invalidate();
      }
      return;
    }

    if (matchesBinding(this.keybindings, data, "app.message.followUp")) {
      this.onDone?.(this.lines.join("\n"), "followUp");
    } else if (matchesBinding(this.keybindings, data, "tui.input.submit", Key.enter)) {
      this.onDone?.(this.lines.join("\n"), "normal");
    } else if (matchesKey(data, Key.escape)) {
      this.pendingCancel = true;
      this.invalidate();
    } else if (matchesBinding(this.keybindings, data, "tui.input.newLine") || this.isShiftEnter(data)) {
      this.insertNewline();
    } else if (matchesKey(data, Key.left)) {
      this.moveCol(-1);
    } else if (matchesKey(data, Key.right)) {
      this.moveCol(1);
    } else if (matchesKey(data, Key.up)) {
      this.moveLine(-1);
    } else if (matchesKey(data, Key.down)) {
      this.moveLine(1);
    } else if (matchesKey(data, Key.home)) {
      this.cursorCol = 0;
      this.invalidate();
    } else if (matchesKey(data, Key.end)) {
      this.cursorCol = this.currentLine().length;
      this.invalidate();
    } else if (matchesKey(data, Key.backspace)) {
      this.backspace();
    } else if (matchesKey(data, Key.delete)) {
      this.deleteForward();
    } else if (data.length === 1 && data >= " ") {
      this.insertChar(data);
    }
  }

  private isShiftEnter(data: string): boolean {
    return data === "\x1b[13;2u" || data === "\x1b[1;2P" || data === "\x1b[13;2~";
  }

  private currentLine(): string {
    return this.lines[this.cursorLine] ?? "";
  }

  private moveCol(delta: number): void {
    this.cursorCol = Math.max(0, Math.min(this.currentLine().length, this.cursorCol + delta));
    this.invalidate();
  }

  private moveLine(delta: number): void {
    this.cursorLine = Math.max(0, Math.min(this.lines.length - 1, this.cursorLine + delta));
    this.cursorCol = Math.min(this.cursorCol, this.currentLine().length);
    this.invalidate();
  }

  private insertChar(ch: string): void {
    const line = this.currentLine();
    this.lines[this.cursorLine] = line.slice(0, this.cursorCol) + ch + line.slice(this.cursorCol);
    this.cursorCol++;
    this.invalidate();
  }

  private insertNewline(): void {
    const line = this.currentLine();
    this.lines[this.cursorLine] = line.slice(0, this.cursorCol);
    this.lines.splice(this.cursorLine + 1, 0, line.slice(this.cursorCol));
    this.cursorLine++;
    this.cursorCol = 0;
    this.invalidate();
  }

  private backspace(): void {
    if (this.cursorCol > 0) {
      const line = this.currentLine();
      this.lines[this.cursorLine] = line.slice(0, this.cursorCol - 1) + line.slice(this.cursorCol);
      this.cursorCol--;
      this.invalidate();
    } else if (this.cursorLine > 0) {
      const previousLength = this.lines[this.cursorLine - 1].length;
      this.lines[this.cursorLine - 1] += this.currentLine();
      this.lines.splice(this.cursorLine, 1);
      this.cursorLine--;
      this.cursorCol = previousLength;
      this.invalidate();
    }
  }

  private deleteForward(): void {
    const line = this.currentLine();
    if (this.cursorCol < line.length) {
      this.lines[this.cursorLine] = line.slice(0, this.cursorCol) + line.slice(this.cursorCol + 1);
      this.invalidate();
    } else if (this.cursorLine < this.lines.length - 1) {
      this.lines[this.cursorLine] += this.lines[this.cursorLine + 1];
      this.lines.splice(this.cursorLine + 1, 1);
      this.invalidate();
    }
  }

  render(width: number): string[] {
    if (this.cachedLines && this.cachedWidth === width) return this.cachedLines;

    const t = this.theme;
    const pad = 2;
    const contentWidth = Math.max(20, width - pad * 2 - 2);
    const lines: string[] = [];
    lines.push(...new DynamicBorder((s: string) => t.fg("accent", s)).render(width));
    lines.push(...new Text(t.fg("accent", t.bold(`Editing fix prompt — ${this.label}`)), pad, 0).render(width));
    lines.push(...new Spacer(1).render(width));

    for (let i = 0; i < this.lines.length; i++) {
      const line = this.lines[i];
      const isCursorLine = i === this.cursorLine;
      let rendered = "";
      for (let col = 0; col <= line.length; col++) {
        if (isCursorLine && col === this.cursorCol) rendered += "\x1b[7m \x1b[27m";
        if (col < line.length) rendered += line[col];
      }
      lines.push(" ".repeat(pad) + truncateToWidth(rendered, contentWidth, ""));
    }

    lines.push(...new Spacer(1).render(width));
    if (this.pendingCancel) {
      lines.push(...new Text(t.fg("warning", t.bold("Cancel editing? Press Esc again to confirm — any other key to resume")), pad, 0).render(width));
    } else {
      const submitKey = keyLabel(this.keybindings, "tui.input.submit", "Enter");
      const queueKey = keyLabel(this.keybindings, "app.message.followUp", "Alt+Enter");
      const newlineKey = keyLabel(this.keybindings, "tui.input.newLine", "Shift+Enter");
      lines.push(...new Text(t.fg("dim", `${submitKey} run · ${queueKey} queue follow-up · ${newlineKey} newline · Esc cancel`), pad, 0).render(width));
    }
    lines.push(...new DynamicBorder((s: string) => t.fg("accent", s)).render(width));

    this.cachedWidth = width;
    this.cachedLines = lines;
    return lines;
  }

  invalidate(): void {
    this.cachedWidth = undefined;
    this.cachedLines = undefined;
  }
}

class CiDetailComponent {
  private summary: CiSummary;
  private pi: ExtensionAPI;
  private cwd: string;
  private done: () => void;
  private requestRender: () => void;
  private theme: Theme;
  private onFix: (job: CiJob, summary: CiSummary) => void;

  private view: DetailView = "jobs";
  private activeCi: CiKey = "github-actions";
  private activeCycle: CycleKey = "Jobs";
  private selectedIndex = 0;
  private logScrollOffset = 0;
  private showAllJobs = false;
  private jobs: CiJob[] = [];
  private selectedJob: CiJob | null = null;
  private disposed = false;
  private logContent: string[] = [];
  private logLoading = false;
  private logError = "";
  private copiedMessage = "";
  private statusMessage = "";
  private refreshing = false;
  private list: SelectList | undefined;
  private pickerList: SelectList | undefined;
  private itemJobs = new Map<string, CiJob>();

  private cachedLines: string[] | undefined;
  private cachedWidth: number | undefined;

  private frameIndex = 0;
  private animTimer: ReturnType<typeof setInterval> | undefined;
  private loadingFrame = 0;
  private loadingAnimTimer: ReturnType<typeof setInterval> | undefined;

  constructor(
    summary: CiSummary,
    pi: ExtensionAPI,
    cwd: string,
    theme: Theme,
    done: () => void,
    requestRender: () => void,
    onFix: (job: CiJob, summary: CiSummary) => void,
  ) {
    this.summary = summary;
    this.pi = pi;
    this.cwd = cwd;
    this.theme = theme;
    this.done = done;
    this.requestRender = requestRender;
    this.onFix = onFix;

    const groups = groupJobs(summary);
    this.jobs = this.sortedJobsFromSummary(summary);

    this.activeCi = this.pickInitialCi();
    this.activeCycle = this.pickInitialCycle(this.activeCi);
    this.clampSelection();

    if (groups.running.length > 0) {
      this.animTimer = setInterval(() => {
        this.frameIndex++;
        this.invalidate();
        this.requestRender();
      }, 500);
    }
  }

  dispose(): void {
    this.disposed = true;
    if (this.animTimer) clearInterval(this.animTimer);
    if (this.loadingAnimTimer) clearInterval(this.loadingAnimTimer);
  }

  private rerender(): void {
    if (this.disposed) return;
    this.cachedLines = undefined;
    this.cachedWidth = undefined;
    this.requestRender();
  }

  private sortedJobsFromSummary(summary: CiSummary): CiJob[] {
    const groups = groupJobs(summary);
    return [
      ...groups.failed,
      ...groups.running,
      ...groups.cancelled,
      ...groups.unknown,
      ...groups.passing,
      ...groups.skipped,
    ];
  }

  private text(content: string, paddingX = 1, paddingY = 0): Text {
    return new Text(content, paddingX, paddingY);
  }

  private selectTheme(): SelectListTheme {
    return {
      selectedPrefix: (text: string) => this.theme.fg("accent", text),
      selectedText: (text: string) => this.theme.fg("accent", text),
      description: (text: string) => this.theme.fg("muted", text),
      scrollInfo: (text: string) => this.theme.fg("dim", text),
      noMatch: (text: string) => this.theme.fg("warning", text),
    };
  }

  private ciKey(job: CiJob): CiKey {
    if (job.providerHint && job.providerHint !== "unknown") return job.providerHint;

    const text = `${job.url ?? ""} ${job.name}`.toLowerCase();
    if (text.includes("circleci")) return "circleci";
    if (githubRunIdFromUrl(job.url)) return "github-actions";
    if (text.includes("buildkite")) return "buildkite";
    if (text.includes("netlify")) return "netlify";
    if (text.includes("vercel")) return "vercel";
    if (text.includes("codecov")) return "codecov";
    if (text.includes("coveralls")) return "coveralls";
    if (text.includes("semaphore")) return "semaphore";
    if (text.includes("azure") || text.includes("dev.azure.com")) return "azure-pipelines";
    if (text.includes("gitlab")) return "gitlab-ci";
    if (text.includes("jenkins")) return "jenkins";

    if (job.url) {
      try {
        const host = new URL(job.url).hostname.replace(/^www\./, "");
        if (host && host !== "github.com") return `external:${host}`;
      } catch {
        // Ignore malformed URLs and fall back below.
      }
    }

    if (job.provider === "github") return job.runId ? "github-actions" : "github-check";
    return String(job.provider);
  }

  private ciLabel(ci: CiKey): string {
    const labels: Record<string, string> = {
      "github-actions": "GitHub Actions",
      "github-check": "Check runs",
      github: "GitHub Actions",
      circleci: "CircleCI",
      "local-ci": "local-ci",
      "commit-status": "Commit statuses",
      buildkite: "Buildkite",
      netlify: "Netlify",
      vercel: "Vercel",
      codecov: "Codecov",
      coveralls: "Coveralls",
      semaphore: "Semaphore",
      "azure-pipelines": "Azure Pipelines",
      "gitlab-ci": "GitLab CI",
      jenkins: "Jenkins",
    };
    if (labels[ci]) return labels[ci];
    if (ci.startsWith("external:")) return ci.slice("external:".length);
    return ci
      .split(/[\s_-]+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ") || ci;
  }

  private ciIcon(ci: CiKey): string {
    if (ASCII_ICONS) {
      if (ci === "circleci") return "CCI";
      if (ci === "github" || ci === "github-actions") return "GH";
      return "CI";
    }
    if (ci === "circleci") return "○";
    if (ci === "github" || ci === "github-actions") return "⬡";
    return "◆";
  }

  private ciKeys(): CiKey[] {
    const keys = Array.from(new Set(this.jobs.map((job) => this.ciKey(job))));
    return keys.sort((a, b) => {
      const rank = this.rankJobs(this.jobsForCi(a)) - this.rankJobs(this.jobsForCi(b));
      if (rank !== 0) return rank;
      return this.jobsForCi(b).length - this.jobsForCi(a).length;
    });
  }

  private jobsForCi(ci: CiKey): CiJob[] {
    return this.jobs.filter((job) => this.ciKey(job) === ci);
  }

  private cycleKey(job: CiJob): CycleKey {
    const parts = job.name.split(/\s+\/\s+/).map((part) => part.trim()).filter(Boolean);
    if (parts.length > 1) return parts[0];
    return "Jobs";
  }

  private jobDisplayName(job: CiJob): string {
    const cycle = this.cycleKey(job);
    if (cycle === "Jobs") return job.name;
    const prefix = `${cycle} / `;
    return job.name.startsWith(prefix) ? job.name.slice(prefix.length) : job.name;
  }

  private cycleKeys(ci: CiKey): CycleKey[] {
    const keys = Array.from(new Set(this.jobsForCi(ci).map((job) => this.cycleKey(job))));
    return keys.sort((a, b) => {
      const rank = this.rankJobs(this.jobsForCycle(ci, a)) - this.rankJobs(this.jobsForCycle(ci, b));
      if (rank !== 0) return rank;
      return this.jobsForCycle(ci, b).length - this.jobsForCycle(ci, a).length;
    });
  }

  private jobsForCycle(ci: CiKey, cycle: CycleKey): CiJob[] {
    return this.jobsForCi(ci).filter((job) => this.cycleKey(job) === cycle);
  }

  private activeCiJobs(): CiJob[] {
    return this.jobsForCi(this.activeCi);
  }

  private activeCycleJobs(): CiJob[] {
    return this.jobsForCycle(this.activeCi, this.activeCycle);
  }

  private visibleJobs(): CiJob[] {
    const jobs = this.activeCycleJobs();
    if (this.showAllJobs) return jobs;
    const important = jobs.filter((job) => IMPORTANT_STATES.has(job.state));
    return important.length > 0 ? important : jobs;
  }

  private groupsForJobs(jobs: CiJob[]) {
    return groupJobs({ ...this.summary, jobs });
  }

  private rankJobs(jobs: CiJob[]): number {
    if (jobs.length === 0) return 99;
    return Math.min(...jobs.map((job) => stateRank(job.state)));
  }

  private pickInitialCi(): CiKey {
    return this.ciKeys()[0] ?? "github-actions";
  }

  private pickInitialCycle(ci: CiKey): CycleKey {
    return this.cycleKeys(ci)[0] ?? "Jobs";
  }

  private clampSelection(jobs = this.visibleJobs()): void {
    if (jobs.length === 0) {
      this.selectedIndex = 0;
      return;
    }
    this.selectedIndex = Math.max(0, Math.min(this.selectedIndex, jobs.length - 1));
  }

  private switchCi(delta = 1): void {
    const keys = this.ciKeys();
    if (keys.length === 0) return;
    const current = Math.max(0, keys.indexOf(this.activeCi));
    this.activeCi = keys[(current + delta + keys.length) % keys.length] ?? keys[0];
    this.activeCycle = this.pickInitialCycle(this.activeCi);
    this.selectedIndex = 0;
    this.view = "jobs";
    this.selectedJob = null;
    this.copiedMessage = "";
    this.clampSelection();
    this.rerender();
  }

  private switchCycle(delta = 1): void {
    const cycles = this.cycleKeys(this.activeCi);
    if (cycles.length === 0) return;
    const current = Math.max(0, cycles.indexOf(this.activeCycle));
    this.activeCycle = cycles[(current + delta + cycles.length) % cycles.length] ?? cycles[0];
    this.selectedIndex = 0;
    this.view = "jobs";
    this.selectedJob = null;
    this.copiedMessage = "";
    this.clampSelection();
    this.rerender();
  }

  private focusJob(job: CiJob): void {
    this.activeCi = this.ciKey(job);
    this.activeCycle = this.cycleKey(job);
    this.showAllJobs = false;
    let index = this.visibleJobs().indexOf(job);
    if (index < 0) {
      this.showAllJobs = true;
      index = this.visibleJobs().indexOf(job);
    }
    this.selectedIndex = Math.max(0, index);
    this.view = "jobs";
    this.selectedJob = null;
    this.rerender();
  }

  private openJobDetail(job: CiJob): void {
    this.selectedJob = job;
    this.activeCi = this.ciKey(job);
    this.activeCycle = this.cycleKey(job);
    this.view = "detail";
    this.logContent = [];
    this.logError = "";
    this.logScrollOffset = 0;
    this.stopLoadingAnim();
    this.rerender();
  }

  private fetchLogs(): void {
    if (this.disposed || !this.selectedJob || this.logLoading) return;
    this.logLoading = true;
    this.logError = "";
    this.view = "loadingLogs";
    this.startLoadingAnim();

    fetchJobLogs(this.pi, this.cwd, this.selectedJob).then((logs) => {
      if (this.disposed) return;
      this.logContent = logs.split("\n");
      this.logLoading = false;
      this.logScrollOffset = this.firstInterestingLogLine(this.logContent);
      this.view = "detail";
      this.stopLoadingAnim();
      this.rerender();
    }).catch((error) => {
      if (this.disposed) return;
      this.logError = errorMessage(error);
      this.logLoading = false;
      this.view = "detail";
      this.stopLoadingAnim();
      this.rerender();
    });
  }

  private selectedVisibleJob(): CiJob | undefined {
    return this.view === "detail" ? this.selectedJob ?? undefined : this.visibleJobs()[this.selectedIndex];
  }

  private rerunSelectedFailedJob(): void {
    const job = this.selectedVisibleJob();
    if (!job) {
      this.statusMessage = "No selected job to rerun.";
      this.rerender();
      return;
    }
    this.statusMessage = `Requesting rerun for ${this.jobDisplayName(job)}...`;
    this.rerender();

    rerunFailedJob(this.pi, this.cwd, job).then((message) => {
      this.statusMessage = message;
      setTimeout(() => { void this.refreshStatus(); }, 2_000);
    }).catch((error) => {
      this.statusMessage = `Rerun failed: ${truncate(errorMessage(error), 180)}`;
      this.rerender();
    });
  }

  private fixSelectedJob(): void {
    const job = this.selectedVisibleJob();
    if (!job) {
      this.statusMessage = "No selected job to fix.";
      this.rerender();
      return;
    }
    if (job.state !== "failed") {
      this.statusMessage = `Selected job is ${job.state}; fix flow is intended for failed jobs.`;
      this.rerender();
      return;
    }
    this.dispose();
    this.onFix(job, this.summary);
  }

  private firstInterestingLogLine(lines: string[]): number {
    const pattern = /(^|\s)(error|failed|failure|exception|traceback|assertion|timeout|timed out|panic|fatal|not ok|npm err|pytest|ruff|mypy|pyright|eslint|tsc)(\s|:|$)/i;
    const index = lines.findIndex((line) => pattern.test(line));
    return index >= 0 ? Math.max(0, index - 2) : 0;
  }

  private jumpToFirstInterestingLogLine(): void {
    if (this.logContent.length === 0) return;
    this.logScrollOffset = this.firstInterestingLogLine(this.logContent);
    this.rerender();
  }

  private async refreshStatus(): Promise<void> {
    if (this.disposed || this.refreshing) return;

    const previousJobId = this.selectedJob?.id ?? this.visibleJobs()[this.selectedIndex]?.id;
    const previousCi = this.activeCi;
    const previousCycle = this.activeCycle;
    const wasDetail = this.view === "detail";

    this.refreshing = true;
    this.statusMessage = "Refreshing CI...";
    this.rerender();

    try {
      const summary = await fetchCiSummary(this.pi, this.cwd);
      this.summary = summary;
      lastSummary = summary;
      this.jobs = this.sortedJobsFromSummary(summary);

      const ciKeys = this.ciKeys();
      this.activeCi = ciKeys.includes(previousCi) ? previousCi : this.pickInitialCi();
      const cycleKeys = this.cycleKeys(this.activeCi);
      this.activeCycle = cycleKeys.includes(previousCycle) ? previousCycle : this.pickInitialCycle(this.activeCi);

      const updatedJob = previousJobId ? this.jobs.find((job) => job.id === previousJobId) : undefined;
      if (wasDetail) {
        if (updatedJob) {
          this.selectedJob = updatedJob;
          this.activeCi = this.ciKey(updatedJob);
          this.activeCycle = this.cycleKey(updatedJob);
        } else {
          this.selectedJob = null;
          this.view = "jobs";
        }
      }

      const visibleJobs = this.visibleJobs();
      const updatedIndex = updatedJob ? visibleJobs.findIndex((job) => job.id === updatedJob.id) : -1;
      this.selectedIndex = updatedIndex >= 0 ? updatedIndex : 0;
      this.clampSelection();
      this.statusMessage = `Refreshed at ${new Date(summary.checkedAt).toLocaleTimeString()}`;
    } catch (error) {
      this.statusMessage = `Refresh failed: ${truncate(errorMessage(error), 160)}`;
    } finally {
      this.refreshing = false;
      this.rerender();
    }
  }

  private openCiPicker(): void {
    this.view = "pickCi";
    this.copiedMessage = "";
    this.rerender();
  }

  private openCyclePicker(): void {
    this.view = "pickCycle";
    this.copiedMessage = "";
    this.rerender();
  }

  private startLoadingAnim(): void {
    this.stopLoadingAnim();
    this.loadingFrame = 0;
    this.loadingAnimTimer = setInterval(() => {
      this.loadingFrame++;
      this.rerender();
    }, 100);
  }

  private stopLoadingAnim(): void {
    if (this.loadingAnimTimer) {
      clearInterval(this.loadingAnimTimer);
      this.loadingAnimTimer = undefined;
    }
  }

  private shortUrl(url: string, maxWidth: number): string {
    try {
      const parsed = new URL(url);
      const path = `${parsed.pathname}${parsed.search}`.replace(/^\//, "");
      const display = path.length > 0 ? `${parsed.hostname}/${path}` : parsed.hostname;
      if (visibleWidth(display) <= maxWidth) return display;
      const keep = Math.max(12, maxWidth - parsed.hostname.length - 4);
      return `${parsed.hostname}/…${path.slice(-keep)}`;
    } catch {
      return truncateToWidth(url, maxWidth, "");
    }
  }

  private copyJobUrl(job: CiJob | undefined): void {
    if (!job?.url) {
      this.statusMessage = job ? `No URL for selected job: ${job.name}` : "No selected job URL to copy";
      this.rerender();
      return;
    }

    copyToClipboard(this.pi, job.url).then(() => {
      this.copiedMessage = `Copied URL for ${this.jobDisplayName(job)}: ${this.shortUrl(job.url!, 90)}`;
      this.statusMessage = "";
      this.rerender();
    }).catch((error) => {
      this.statusMessage = `Copy failed: ${truncate(errorMessage(error), 160)}`;
      this.rerender();
    });
  }

  private stateText(state: CiState): string {
    switch (state) {
      case "success": return this.theme.fg("success", "PASS");
      case "failed": return this.theme.fg("error", "FAIL");
      case "running": return this.theme.fg("warning", "RUN");
      case "pending": return this.theme.fg("warning", "WAIT");
      case "cancelled": return this.theme.fg("muted", "CANCEL");
      case "skipped": return this.theme.fg("dim", "SKIP");
      default: return this.theme.fg("muted", "UNKNOWN");
    }
  }

  private plainStateText(state: CiState): string {
    switch (state) {
      case "success": return "PASS";
      case "failed": return "FAIL";
      case "running": return "RUN";
      case "pending": return "WAIT";
      case "cancelled": return "CANCEL";
      case "skipped": return "SKIP";
      default: return "UNKNOWN";
    }
  }

  private plainStatusForJobs(jobs: CiJob[]): string {
    if (this.summary.errors.length) return "incomplete — lookup errors";
    const groups = this.groupsForJobs(jobs);
    if (groups.failed.length > 0) return `${groups.failed.length} failed`;
    if (groups.running.length > 0) return `${groups.running.length} running/pending`;
    if (groups.cancelled.length > 0) return `${groups.cancelled.length} cancelled`;
    if (groups.unknown.length > 0) return `${groups.unknown.length} unknown`;
    if (groups.passing.length > 0) return `all passed (${groups.passing.length})`;
    if (groups.skipped.length > 0) return `skipped/neutral only (${groups.skipped.length})`;
    return "no jobs";
  }

  private statusForJobs(jobs: CiJob[]): string {
    if (this.summary.errors.length) return this.theme.fg("warning", "incomplete — lookup errors");
    const groups = this.groupsForJobs(jobs);
    if (groups.failed.length > 0) return this.theme.fg("error", `${groups.failed.length} failed`);
    if (groups.running.length > 0) return this.theme.fg("warning", `${groups.running.length} running/pending`);
    if (groups.cancelled.length > 0) return this.theme.fg("muted", `${groups.cancelled.length} cancelled`);
    if (groups.unknown.length > 0) return this.theme.fg("warning", `${groups.unknown.length} unknown`);
    if (groups.passing.length > 0) return this.theme.fg("success", `all passed (${groups.passing.length})`);
    if (groups.skipped.length > 0) return this.theme.fg("dim", `skipped/neutral only (${groups.skipped.length})`);
    return this.theme.fg("muted", "no jobs");
  }

  private countsForJobs(jobs: CiJob[]): string {
    const groups = this.groupsForJobs(jobs);
    return `${groups.failed.length} failed · ${groups.running.length} running · ${groups.passing.length} passed · ${groups.skipped.length} skipped`;
  }

  private nextActionForJobs(jobs: CiJob[]): string {
    if (this.summary.errors.length) return "Fix status lookup errors and refresh before judging CI readiness.";
    const groups = this.groupsForJobs(jobs);
    if (groups.failed.length > 0) return "Select a failed job, then press r for logs, F to fix, or x to rerun.";
    if (groups.running.length > 0) return "Wait for running checks to finish.";
    if (groups.cancelled.length > 0) return "Confirm the cancellation was expected.";
    if (groups.unknown.length > 0) return "Open details to inspect unknown checks.";
    if (groups.passing.length > 0) return "No action needed.";
    if (this.activeCi === "circleci") return "No CircleCI jobs found. Set CIRCLECI_TOKEN for enrichment.";
    return "No jobs found.";
  }

  private jobIdText(job: CiJob): string {
    if (job.runId) return `run ${job.runId}`;
    if (job.jobNumber) return `job #${job.jobNumber}`;
    return job.id;
  }

  private jobDescription(job: CiJob): string {
    const duration = formatDuration(durationMs(job));
    const parts = [this.plainStateText(job.state), duration, this.jobIdText(job)];
    if (job.url) parts.push(this.shortUrl(job.url, 70));
    else parts.push("no URL");
    return parts.filter(Boolean).join(" · ");
  }

  private hiddenSummary(allJobs: CiJob[], shownJobs: CiJob[]): string {
    const hidden = allJobs.filter((job) => !shownJobs.includes(job));
    if (hidden.length === 0) return "";
    const groups = this.groupsForJobs(hidden);
    const parts = [
      groups.passing.length > 0 ? `${groups.passing.length} passed` : "",
      groups.skipped.length > 0 ? `${groups.skipped.length} skipped` : "",
      groups.failed.length > 0 ? `${groups.failed.length} failed` : "",
      groups.running.length > 0 ? `${groups.running.length} running` : "",
    ].filter(Boolean);
    return `${hidden.length} hidden (${parts.join(", ")}). Press a to show all.`;
  }

  private runningSpinner(): string {
    const frames = ["◐", "◓", "◑", "◒"];
    return frames[this.frameIndex % frames.length];
  }

  private renderHeader(container: Container): void {
    const repo = this.summary.repo ? ` — ${this.summary.repo}` : "";
    const pr = this.summary.prNumber ? ` — PR #${this.summary.prNumber}` : "";
    const allJobs = this.activeCycleJobs();
    const ciKeys = this.ciKeys();
    const cycleKeys = this.cycleKeys(this.activeCi);
    const ciIndex = Math.max(0, ciKeys.indexOf(this.activeCi));
    const cycleIndex = Math.max(0, cycleKeys.indexOf(this.activeCycle));

    container.addChild(new DynamicBorder((s: string) => this.theme.fg("accent", s)));
    container.addChild(new Spacer(1));
    container.addChild(this.text(this.theme.fg("accent", this.theme.bold(`CI Status${repo}${pr}`))));
    container.addChild(this.text(this.theme.fg("dim", `Branch ${this.summary.branch} · SHA ${shortSha(this.summary.sha)} · ${new Date(this.summary.checkedAt).toLocaleTimeString()}`)));
    for (const error of this.summary.errors) container.addChild(this.text(this.theme.fg("warning", `CI incomplete: ${error}`)));
    container.addChild(new Spacer(1));
    container.addChild(this.text(`CI ${ciIndex + 1}/${Math.max(ciKeys.length, 1)}: ${this.ciIcon(this.activeCi)} ${this.ciLabel(this.activeCi)} — ${this.statusForJobs(this.activeCiJobs())}`));

    const otherCi = ciKeys
      .filter((key) => key !== this.activeCi)
      .map((key) => `${this.ciLabel(key)} ${this.statusForJobs(this.jobsForCi(key))}`)
      .join("  |  ");
    if (otherCi) container.addChild(this.text(this.theme.fg("dim", `Other CIs: ${otherCi}`)));

    container.addChild(this.text(`Cycle ${cycleIndex + 1}/${Math.max(cycleKeys.length, 1)}: ${this.activeCycle} — ${this.statusForJobs(allJobs)}`));
    container.addChild(this.text(this.theme.fg("dim", `Counts: ${this.countsForJobs(allJobs)}`)));
    container.addChild(this.text(`Next: ${this.nextActionForJobs(allJobs)}`));
    if (this.statusMessage) {
      const color: "warning" | "success" = /failed|unavailable|no |selected job is/i.test(this.statusMessage) || this.refreshing ? "warning" : "success";
      container.addChild(this.text(this.theme.fg(color, this.statusMessage)));
    }
  }

  private renderJobsView(width: number): string[] {
    const container = new Container();
    const allJobs = this.activeCycleJobs();
    const shownJobs = this.visibleJobs();
    this.clampSelection(shownJobs);

    this.renderHeader(container);
    container.addChild(new Spacer(1));

    const hidden = this.hiddenSummary(allJobs, shownJobs);
    const title = this.showAllJobs ? "Jobs" : "Important jobs";
    container.addChild(this.text(this.theme.fg("accent", this.theme.bold(title)) + (hidden ? this.theme.fg("dim", ` — ${hidden}`) : "")));

    this.itemJobs = new Map<string, CiJob>();
    const items: SelectItem[] = shownJobs.map((job, index) => {
      const value = `${index}:${job.id}`;
      this.itemJobs.set(value, job);
      return {
        value,
        label: `${this.stateText(job.state)}  ${this.jobDisplayName(job)}`,
        description: this.jobDescription(job),
      };
    });

    if (items.length === 0) {
      container.addChild(this.text(this.theme.fg("muted", "No jobs for this CI/cycle.")));
      this.list = undefined;
    } else {
      this.list = new SelectList(items, Math.min(Math.max(items.length, 1), 10), this.selectTheme(), {
        minPrimaryColumnWidth: 28,
        maxPrimaryColumnWidth: 72,
      });
      this.list.setSelectedIndex(this.selectedIndex);
      this.list.onSelectionChange = (item) => {
        const nextIndex = items.findIndex((candidate) => candidate.value === item.value);
        if (nextIndex >= 0) this.selectedIndex = nextIndex;
      };
      this.list.onSelect = (item) => {
        const job = this.itemJobs.get(item.value);
        if (job) this.openJobDetail(job);
      };
      this.list.onCancel = () => this.done();
      container.addChild(this.list);
    }

    const selectedJob = shownJobs[this.selectedIndex];
    container.addChild(new Spacer(1));
    if (selectedJob) {
      container.addChild(this.text(`Selected: ${this.plainStateText(selectedJob.state)} ${this.jobDisplayName(selectedJob)}`));
      container.addChild(this.text(this.theme.fg("dim", `c copies: ${selectedJob.url ? this.shortUrl(selectedJob.url, 96) : "no URL available"}`)));
    }
    if (this.copiedMessage) container.addChild(this.text(this.theme.fg("success", this.copiedMessage)));
    container.addChild(this.text(this.theme.fg("dim", "↑↓ select · Enter details · r logs · F fix · x rerun failed · l open URL · c copy URL · ? help")));
    container.addChild(this.text(this.theme.fg("dim", "Tab/←→ CI · [/] cycle · p pick CI · w pick cycle · R refresh · a all · g fail · Esc close")));
    container.addChild(new Spacer(1));
    container.addChild(new DynamicBorder((s: string) => this.theme.fg("accent", s)));

    return container.render(width);
  }

  private renderDetailView(width: number): string[] {
    const container = new Container();
    const job = this.selectedJob;
    container.addChild(new DynamicBorder((s: string) => this.theme.fg("accent", s)));
    container.addChild(new Spacer(1));

    if (!job) {
      container.addChild(this.text(this.theme.fg("warning", "No job selected.")));
      container.addChild(this.text(this.theme.fg("dim", "Esc back")));
      container.addChild(new DynamicBorder((s: string) => this.theme.fg("accent", s)));
      return container.render(width);
    }

    container.addChild(this.text(this.theme.fg("accent", this.theme.bold("Job details"))));
    container.addChild(this.text(`CI:      ${this.ciIcon(this.ciKey(job))} ${this.ciLabel(this.ciKey(job))}`));
    container.addChild(this.text(`Cycle:   ${this.cycleKey(job)}`));
    container.addChild(this.text(`Job:     ${this.stateText(job.state)} ${this.jobDisplayName(job)}`));
    container.addChild(new Spacer(1));
    const duration = formatDuration(durationMs(job));
    container.addChild(this.text(`Status:  ${this.plainStateText(job.state)}`));
    if (duration) container.addChild(this.text(`Duration: ${duration}`));
    container.addChild(this.text(`ID:      ${this.jobIdText(job)}`));
    if (job.summary) container.addChild(this.text(`Summary: ${job.summary}`));
    if (job.startedAt) container.addChild(this.text(`Started: ${new Date(job.startedAt).toLocaleString()}`));
    if (job.completedAt) container.addChild(this.text(`Ended:   ${new Date(job.completedAt).toLocaleString()}`));
    container.addChild(this.text(`URL:     ${job.url ? this.shortUrl(job.url, 120) : "no URL available"}`));
    if (job.url) container.addChild(this.text(this.theme.fg("dim", `c copies: ${this.shortUrl(job.url, 120)}`)));

    container.addChild(new Spacer(1));
    if (this.logLoading) {
      container.addChild(this.text(this.theme.fg("warning", "Loading logs...")));
    } else if (this.logError) {
      container.addChild(this.text(this.theme.fg("error", `Log error: ${this.logError}`)));
    } else if (this.logContent.length > 0) {
      container.addChild(this.text(this.theme.fg("accent", `Logs (${this.logContent.length} lines)`)));
      const visibleLogs = this.logContent.slice(this.logScrollOffset, this.logScrollOffset + 12);
      for (const logLine of visibleLogs) {
        const clean = logLine.replace(/\x1b\[[0-9;]*m/g, "");
        container.addChild(this.text(this.theme.fg("muted", clean), 2, 0));
      }
      if (this.logContent.length > 12) {
        container.addChild(this.text(this.theme.fg("dim", `Showing ${this.logScrollOffset + 1}-${Math.min(this.logScrollOffset + 12, this.logContent.length)} of ${this.logContent.length}`)));
      }
    } else {
      container.addChild(this.text("Press Enter or r to fetch logs for this selected job."));
    }

    container.addChild(new Spacer(1));
    if (this.copiedMessage) container.addChild(this.text(this.theme.fg("success", this.copiedMessage)));
    container.addChild(this.text(this.theme.fg("dim", "Esc back · Enter/r logs · f first error · F fix · x rerun failed · l open URL · c copy URL · R refresh · ? help")));
    container.addChild(new Spacer(1));
    container.addChild(new DynamicBorder((s: string) => this.theme.fg("accent", s)));
    return container.render(width);
  }

  private renderLoadingView(width: number): string[] {
    const spinners = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
    const spin = spinners[this.loadingFrame % spinners.length];
    const container = new Container();
    container.addChild(new DynamicBorder((s: string) => this.theme.fg("accent", s)));
    container.addChild(new Spacer(1));
    container.addChild(this.text(this.theme.fg("warning", `${spin} Fetching logs`)));
    container.addChild(this.text(`Job: ${this.selectedJob ? this.jobDisplayName(this.selectedJob) : "unknown"}`));
    container.addChild(this.text(this.theme.fg("dim", "This may take a moment...")));
    container.addChild(new Spacer(1));
    container.addChild(new DynamicBorder((s: string) => this.theme.fg("accent", s)));
    return container.render(width);
  }

  private renderHelpView(width: number): string[] {
    const container = new Container();
    container.addChild(new DynamicBorder((s: string) => this.theme.fg("accent", s)));
    container.addChild(new Spacer(1));
    container.addChild(this.text(this.theme.fg("accent", this.theme.bold("CI detail help"))));
    container.addChild(new Spacer(1));
    container.addChild(this.text("Navigate"));
    container.addChild(this.text(this.theme.fg("dim", "↑↓ select job · Enter details · Esc close/back"), 2, 0));
    container.addChild(this.text(this.theme.fg("dim", "Tab or ←→ switch CI · [ and ] switch workflow/cycle"), 2, 0));
    container.addChild(this.text(this.theme.fg("dim", "p pick CI · w pick workflow/cycle · g first failure"), 2, 0));
    container.addChild(new Spacer(1));
    container.addChild(this.text("Actions"));
    container.addChild(this.text(this.theme.fg("dim", "r fetch selected job logs · f jump to first error in loaded logs"), 2, 0));
    container.addChild(this.text(this.theme.fg("dim", "F fix selected failure with a model-picked prompt · x rerun selected failed job"), 2, 0));
    container.addChild(this.text(this.theme.fg("dim", "l open selected job URL · c copy selected job URL"), 2, 0));
    container.addChild(this.text(this.theme.fg("dim", "R refresh status in place · a toggle important-only/all jobs"), 2, 0));
    container.addChild(new Spacer(1));
    container.addChild(this.text(this.theme.fg("muted", "Default view shows failures/running/unknown first. Passing and skipped jobs are hidden when there is actionable work.")));
    container.addChild(this.text(this.theme.fg("muted", "Set PI_CI_ASCII=1 before launching pi for an emoji-free display.")));
    container.addChild(new Spacer(1));
    container.addChild(this.text(this.theme.fg("dim", "Press Esc or ? to return.")));
    container.addChild(new Spacer(1));
    container.addChild(new DynamicBorder((s: string) => this.theme.fg("accent", s)));
    return container.render(width);
  }

  private renderCiPicker(width: number): string[] {
    const container = new Container();
    const keys = this.ciKeys();
    container.addChild(new DynamicBorder((s: string) => this.theme.fg("accent", s)));
    container.addChild(new Spacer(1));
    container.addChild(this.text(this.theme.fg("accent", this.theme.bold("Pick CI provider"))));
    container.addChild(new Spacer(1));

    const items: SelectItem[] = keys.map((key) => ({
      value: key,
      label: `${this.ciIcon(key)} ${this.ciLabel(key)}`,
      description: `${this.plainStatusForJobs(this.jobsForCi(key))} · ${this.countsForJobs(this.jobsForCi(key))}`,
    }));

    this.pickerList = new SelectList(items, Math.min(Math.max(items.length, 1), 12), this.selectTheme());
    this.pickerList.setSelectedIndex(Math.max(0, keys.indexOf(this.activeCi)));
    this.pickerList.onSelect = (item) => {
      this.activeCi = item.value;
      this.activeCycle = this.pickInitialCycle(this.activeCi);
      this.selectedIndex = 0;
      this.view = "jobs";
      this.rerender();
    };
    this.pickerList.onCancel = () => {
      this.view = "jobs";
      this.rerender();
    };
    container.addChild(this.pickerList);
    container.addChild(new Spacer(1));
    container.addChild(this.text(this.theme.fg("dim", "↑↓ navigate · Enter select · Esc cancel")));
    container.addChild(new Spacer(1));
    container.addChild(new DynamicBorder((s: string) => this.theme.fg("accent", s)));
    return container.render(width);
  }

  private renderCyclePicker(width: number): string[] {
    const container = new Container();
    const cycles = this.cycleKeys(this.activeCi);
    container.addChild(new DynamicBorder((s: string) => this.theme.fg("accent", s)));
    container.addChild(new Spacer(1));
    container.addChild(this.text(this.theme.fg("accent", this.theme.bold(`Pick workflow/cycle — ${this.ciLabel(this.activeCi)}`))));
    container.addChild(new Spacer(1));

    const items: SelectItem[] = cycles.map((cycle) => ({
      value: cycle,
      label: cycle,
      description: `${this.plainStatusForJobs(this.jobsForCycle(this.activeCi, cycle))} · ${this.countsForJobs(this.jobsForCycle(this.activeCi, cycle))}`,
    }));

    this.pickerList = new SelectList(items, Math.min(Math.max(items.length, 1), 12), this.selectTheme());
    this.pickerList.setSelectedIndex(Math.max(0, cycles.indexOf(this.activeCycle)));
    this.pickerList.onSelect = (item) => {
      this.activeCycle = item.value;
      this.selectedIndex = 0;
      this.view = "jobs";
      this.rerender();
    };
    this.pickerList.onCancel = () => {
      this.view = "jobs";
      this.rerender();
    };
    container.addChild(this.pickerList);
    container.addChild(new Spacer(1));
    container.addChild(this.text(this.theme.fg("dim", "↑↓ navigate · Enter select · Esc cancel")));
    container.addChild(new Spacer(1));
    container.addChild(new DynamicBorder((s: string) => this.theme.fg("accent", s)));
    return container.render(width);
  }

  render(width: number): string[] {
    if (this.cachedLines && this.cachedWidth === width) return this.cachedLines;
    const lines = this.view === "loadingLogs"
      ? this.renderLoadingView(width)
      : this.view === "detail"
        ? this.renderDetailView(width)
        : this.view === "help"
          ? this.renderHelpView(width)
          : this.view === "pickCi"
            ? this.renderCiPicker(width)
            : this.view === "pickCycle"
              ? this.renderCyclePicker(width)
              : this.renderJobsView(width);
    this.cachedWidth = width;
    this.cachedLines = lines;
    return lines;
  }

  handleInput(data: string): void {
    if (this.view === "loadingLogs") return;

    if (this.view === "help") {
      if (matchesKey(data, Key.escape) || data === "?" || data === "h") {
        this.view = "jobs";
        this.rerender();
      }
      return;
    }

    if (this.view === "pickCi" || this.view === "pickCycle") {
      this.pickerList?.handleInput(data);
      this.rerender();
      return;
    }

    if (this.view === "detail") {
      if (data === "?" || data === "h") {
        this.view = "help";
        this.rerender();
        return;
      }
      if (data === "R") {
        void this.refreshStatus();
        return;
      }
      if (data === "F") {
        this.fixSelectedJob();
        return;
      }
      if (data === "x" || data === "X") {
        this.rerunSelectedFailedJob();
        return;
      }
      if (matchesKey(data, Key.tab) || matchesKey(data, Key.right)) {
        this.switchCi(1);
        return;
      }
      if (matchesKey(data, Key.left)) {
        this.switchCi(-1);
        return;
      }
      if (data === "]") {
        this.switchCycle(1);
        return;
      }
      if (data === "[") {
        this.switchCycle(-1);
        return;
      }
      if (data === "p") {
        this.openCiPicker();
        return;
      }
      if (data === "w") {
        this.openCyclePicker();
        return;
      }
      if (matchesKey(data, Key.escape) || data === "b") {
        this.view = "jobs";
        this.logScrollOffset = 0;
        this.rerender();
        return;
      }
      if (matchesKey(data, Key.down)) {
        this.logScrollOffset = Math.min(this.logScrollOffset + 1, Math.max(0, this.logContent.length - 12));
        this.rerender();
        return;
      }
      if (matchesKey(data, Key.up)) {
        this.logScrollOffset = Math.max(this.logScrollOffset - 1, 0);
        this.rerender();
        return;
      }
      if (matchesKey(data, Key.pageDown)) {
        this.logScrollOffset = Math.min(this.logScrollOffset + 12, Math.max(0, this.logContent.length - 12));
        this.rerender();
        return;
      }
      if (matchesKey(data, Key.pageUp)) {
        this.logScrollOffset = Math.max(this.logScrollOffset - 12, 0);
        this.rerender();
        return;
      }
      if (matchesKey(data, Key.enter) || data === "r" || matchesKey(data, Key.ctrl("r"))) {
        this.fetchLogs();
        return;
      }
      if (data === "f") {
        this.jumpToFirstInterestingLogLine();
        return;
      }
      if ((data === "l" || matchesKey(data, Key.ctrl("l"))) && this.selectedJob?.url) {
        openUrl(this.pi, this.selectedJob.url);
        return;
      }
      if (data === "c") {
        this.copyJobUrl(this.selectedJob ?? undefined);
        return;
      }
      return;
    }

    const shownJobs = this.visibleJobs();
    if (data === "?" || data === "h") {
      this.view = "help";
      this.rerender();
      return;
    }
    if (data === "R") {
      void this.refreshStatus();
      return;
    }
    if (data === "F") {
      this.fixSelectedJob();
      return;
    }
    if (data === "x" || data === "X") {
      this.rerunSelectedFailedJob();
      return;
    }
    if (data === "p") {
      this.openCiPicker();
      return;
    }
    if (data === "w") {
      this.openCyclePicker();
      return;
    }
    if (matchesKey(data, Key.escape)) {
      this.dispose();
      this.done();
      return;
    }
    if (matchesKey(data, Key.tab) || matchesKey(data, Key.right)) {
      this.switchCi(1);
      return;
    }
    if (matchesKey(data, Key.left)) {
      this.switchCi(-1);
      return;
    }
    if (data === "]") {
      this.switchCycle(1);
      return;
    }
    if (data === "[") {
      this.switchCycle(-1);
      return;
    }
    if (data === "a" || data === "A") {
      this.showAllJobs = !this.showAllJobs;
      this.selectedIndex = 0;
      this.clampSelection();
      this.rerender();
      return;
    }
    if (data === "g") {
      const firstFailed = this.jobs.find((job) => job.state === "failed");
      if (firstFailed) this.focusJob(firstFailed);
      return;
    }
    if (data === "c") {
      this.copyJobUrl(shownJobs[this.selectedIndex]);
      return;
    }
    if (data === "l" || matchesKey(data, Key.ctrl("l"))) {
      const job = shownJobs[this.selectedIndex];
      if (job?.url) openUrl(this.pi, job.url);
      return;
    }
    if (data === "r" || matchesKey(data, Key.ctrl("r"))) {
      const job = shownJobs[this.selectedIndex];
      if (job) {
        this.openJobDetail(job);
        this.fetchLogs();
      }
      return;
    }

    this.list?.handleInput(data);
    this.clampSelection();
    this.rerender();
  }

  invalidate(): void {
    this.cachedWidth = undefined;
    this.cachedLines = undefined;
    this.list?.invalidate();
    this.pickerList?.invalidate();
  }
}


function modelLabel(model: CiModel): string {
  return `${model.provider}/${model.id}${model.name ? ` — ${model.name}` : ""}`;
}

async function selectFixModel(ctx: ExtensionContext): Promise<CiModel | undefined> {
  const available = ctx.modelRegistry.getAvailable() as unknown as CiModel[];
  if (available.length === 0) {
    ctx.ui.notify("No models with configured auth are available. Run /login or configure models first.", "warning");
    return undefined;
  }

  const current = ctx.model as unknown as CiModel | undefined;
  const sorted = [...available].sort((a, b) => {
    const aCurrent = current && a.provider === current.provider && a.id === current.id ? -1 : 0;
    const bCurrent = current && b.provider === current.provider && b.id === current.id ? -1 : 0;
    if (aCurrent !== bCurrent) return aCurrent - bCurrent;
    return modelLabel(a).localeCompare(modelLabel(b));
  });

  const selectedValue = await ctx.ui.custom<string | null>((tui, theme, _kb, done) => {
    const items: SelectItem[] = sorted.map((model) => ({
      value: `${model.provider}\u0000${model.id}`,
      label: modelLabel(model),
      description: [
        model.contextWindow ? `context ${model.contextWindow.toLocaleString()}` : "",
        model.maxTokens ? `max ${model.maxTokens.toLocaleString()}` : "",
        current && model.provider === current.provider && model.id === current.id ? "current" : "",
      ].filter(Boolean).join(" · "),
    }));

    const container = new Container();
    container.addChild(new DynamicBorder((s: string) => theme.fg("accent", s)));
    container.addChild(new Spacer(1));
    container.addChild(new Text(theme.fg("accent", theme.bold("Pick model for CI fix")), 1, 0));
    container.addChild(new Spacer(1));
    const list = new SelectList(items, Math.min(items.length, 12), {
      selectedPrefix: (text: string) => theme.fg("accent", text),
      selectedText: (text: string) => theme.fg("accent", text),
      description: (text: string) => theme.fg("muted", text),
      scrollInfo: (text: string) => theme.fg("dim", text),
      noMatch: (text: string) => theme.fg("warning", text),
    });
    list.onSelect = (item) => done(item.value);
    list.onCancel = () => done(null);
    container.addChild(list);
    container.addChild(new Spacer(1));
    container.addChild(new Text(theme.fg("dim", "↑↓ navigate · Enter select · Esc cancel"), 1, 0));
    container.addChild(new Spacer(1));
    container.addChild(new DynamicBorder((s: string) => theme.fg("accent", s)));
    return {
      render: (width: number) => container.render(width),
      invalidate: () => container.invalidate(),
      handleInput: (data: string) => {
        list.handleInput(data);
        tui.requestRender();
      },
    };
  });

  if (!selectedValue) return undefined;
  const [provider, id] = selectedValue.split("\u0000");
  return sorted.find((model) => model.provider === provider && model.id === id);
}

async function safeExecForPrompt(pi: ExtensionAPI, command: string, args: string[], cwd: string, max = 4_000): Promise<string> {
  try {
    return truncate(await execText(pi, command, args, cwd, 10_000), max);
  } catch (error) {
    return `(failed: ${truncate(errorMessage(error), max)})`;
  }
}

function jobFixPrompt(summary: CiSummary, job: CiJob, logs: string, gitContext: string): string {
  const duration = formatDuration(durationMs(job));
  return `Please fix this CI failure.

Goal:
- Identify the root cause of the selected failed CI job.
- Decide whether it is caused by our changes or an unrelated flake.
- If it is caused by our changes, make the smallest correct fix.
- Run the relevant local validation for the touched area.
- Do not commit or push unless explicitly asked.
- local-ci inspection is read-only. Ask before local-ci run/resume; publication or deployment needs separate explicit authorization. Missing publication is unknown, not proof of a failed remote job.

Repository / PR context:
- Repo: ${summary.repo ?? "unknown"}
- Branch: ${summary.branch}
- SHA: ${summary.sha}
- PR: ${summary.prUrl ?? (summary.prNumber ? `#${summary.prNumber}` : "unknown")}

Selected CI job:
- Provider: ${job.providerHint ?? job.provider}
- Name: ${job.name}
- State: ${job.state}
- ID: ${job.runId ? `GitHub run ${job.runId}` : job.jobNumber ? `CircleCI job #${job.jobNumber}` : job.id}
- URL: ${job.url ?? "not available"}
${duration ? `- Duration: ${duration}\n` : ""}${job.summary ? `- Summary: ${job.summary}\n` : ""}
Current local context:
${gitContext}

Failure logs / details:
\`\`\`
${truncate(logs, 12_000)}
\`\`\`

Please proceed carefully:
1. Briefly explain what appears to be failing.
2. Inspect the relevant files before editing.
3. Fix only what is needed.
4. Run the smallest meaningful validation commands.
5. Summarize what changed and what still needs follow-up.`;
}

async function buildFixPrompt(pi: ExtensionAPI, cwd: string, summary: CiSummary, job: CiJob): Promise<string> {
  const [status, diffStat, changedFiles, logs] = await Promise.all([
    safeExecForPrompt(pi, "git", ["status", "--short"], cwd, 3_000),
    safeExecForPrompt(pi, "git", ["diff", "--stat"], cwd, 4_000),
    safeExecForPrompt(pi, "git", ["diff", "--name-only"], cwd, 4_000),
    fetchJobLogs(pi, cwd, job).catch((error) => `Log fetch failed: ${errorMessage(error)}`),
  ]);
  const gitContext = [
    "git status --short:", status || "(clean)",
    "",
    "git diff --stat:", diffStat || "(no unstaged diff stat)",
    "",
    "git diff --name-only:", changedFiles || "(no unstaged changed files)",
  ].join("\n");
  return jobFixPrompt(summary, job, logs, gitContext);
}

async function choosePromptAction(ctx: ExtensionContext, job: CiJob, model: CiModel, prompt: string): Promise<{ prompt: string; deliverAs: "normal" | "followUp" } | undefined> {
  let currentPrompt = prompt;

  while (true) {
    const action = await ctx.ui.custom<PromptAction>((tui, theme, keybindings, done) => {
      const preview = new FixPromptPreview(theme, job.name, modelLabel(model), currentPrompt, keybindings as CiKeybindings);
      preview.onAction = done;
      return {
        render: (width: number) => preview.render(width),
        invalidate: () => preview.invalidate(),
        handleInput: (data: string) => {
          preview.handleInput(data);
          tui.requestRender();
        },
      };
    });

    if (action === "cancel") return undefined;
    if (action === "run") return { prompt: currentPrompt, deliverAs: "normal" };
    if (action === "queue") return { prompt: currentPrompt, deliverAs: "followUp" };

    const edited = await ctx.ui.custom<{ text: string; deliverAs: "normal" | "followUp" } | null>((tui, theme, keybindings, done) => {
      const editor = new FixPromptEditor(currentPrompt, theme, job.name, keybindings as CiKeybindings);
      editor.onDone = (text, deliverAs) => done({ text, deliverAs });
      editor.onCancel = () => done(null);
      return {
        render: (width: number) => editor.render(width),
        invalidate: () => editor.invalidate(),
        handleInput: (data: string) => {
          editor.handleInput(data);
          tui.requestRender();
        },
      };
    });

    if (!edited) continue;
    currentPrompt = edited.text;
    return edited;
  }
}

async function runFixFlow(pi: ExtensionAPI, ctx: ExtensionContext, summary: CiSummary, job: CiJob): Promise<void> {
  const model = await selectFixModel(ctx);
  if (!model) return;

  const success = await pi.setModel(model as any);
  if (!success) {
    ctx.ui.notify(`No API key available for ${modelLabel(model)}.`, "error");
    return;
  }

  ctx.ui.notify(`Preparing fix prompt for ${job.name}…`, "info");
  const prompt = await buildFixPrompt(pi, ctx.cwd, summary, job);
  const action = await choosePromptAction(ctx, job, model, prompt);
  if (!action) return;

  const isIdle = ctx.isIdle();
  const options = isIdle ? undefined : { deliverAs: action.deliverAs === "followUp" ? "followUp" as const : "steer" as const };
  const willQueue = !isIdle && action.deliverAs === "followUp";
  ctx.ui.notify(`${willQueue ? "Queueing" : "Running"} CI fix prompt with ${modelLabel(model)}…`, "info");
  pi.sendUserMessage(action.prompt, options);
}

// ===========================================================================
// Extension entry point
// ===========================================================================

export default function (pi: ExtensionAPI) {
  extensionApi = pi;

  // --- Session start ---
  pi.on("session_start", async (_event, ctx) => {
    if (!ctx.hasUI || !AUTO_WATCH_ON_START) return;
    watching = true;
    widgetVisible = SHOW_WIDGET_ON_START;
    clearTimer();
    timer = setTimeout(() => { void refreshAndRender(ctx, "startup").catch(() => undefined); }, STARTUP_REFRESH_DELAY_MS);
  });

  const showCiDetail = async (ctx: ExtensionContext) => {
    if (!ctx.hasUI) {
      ctx.ui.notify("CI detail view requires interactive mode.", "warning");
      return;
    }

    let summary: CiSummary;
    try {
      summary = await fetchCiSummary(pi, ctx.cwd);
      lastSummary = summary;
    } catch (error) {
      ctx.ui.notify(`Failed to fetch CI status: ${errorMessage(error)}`, "error");
      return;
    }

    if (summary.jobs.length === 0) {
      ctx.ui.notify("No CI jobs found for this branch/SHA.", "info");
      return;
    }

    const result = await ctx.ui.custom<CiDetailResult>((tui, theme, _kb, done) => {
      const component = new CiDetailComponent(
        summary,
        pi,
        ctx.cwd,
        theme,
        done,
        () => tui.requestRender(),
        (job, currentSummary) => done({ action: "fix", job, summary: currentSummary }),
      );
      return component;
    });

    if (result?.action === "fix") {
      await runFixFlow(pi, ctx, result.summary, result.job);
    }
  };

  // --- Commands ---

  pi.registerCommand("ci", {
    description: "Fetch and render CI status for the current branch/PR",
    handler: async (_args, ctx) => {
      widgetVisible = true;
      await refreshAndRender(ctx, "manual");
    },
  });

  pi.registerCommand("ci-detail", {
    description: "Open interactive CI detail view grouped by CI provider and workflow/cycle with log access",
    handler: async (_args, ctx) => {
      await showCiDetail(ctx);
    },
  });

  pi.registerShortcut(CI_DETAIL_SHORTCUT, {
    description: "Open CI detail view",
    handler: async (ctx) => {
      await showCiDetail(ctx);
    },
  });

  pi.registerCommand("ci-refresh", {
    description: "Force-refresh CI status",
    handler: async (_args, ctx) => {
      await refreshAndRender(ctx, "manual");
    },
  });

  pi.registerCommand("ci-watch", {
    description: "Watch CI status and notify when failures/recoveries occur",
    handler: async (_args, ctx) => {
      ctx.ui.notify("Watching CI for this branch", "info");
      startWatching(ctx, "manual-watch");
    },
  });

  pi.registerCommand("ci-unwatch", {
    description: "Stop watching CI status",
    handler: async (_args, ctx) => {
      stopWatching(ctx);
    },
  });

  pi.registerCommand("ci-clear", {
    description: "Clear the CI widget/status from the UI",
    handler: async (_args, ctx) => {
      widgetVisible = false;
      ctx.ui.setWidget(WIDGET_KEY, undefined);
      ctx.ui.setStatus(STATUS_KEY, undefined);
      ctx.ui.notify(watching ? "Cleared CI widget; watch is still running" : "Cleared CI widget", "info");
    },
  });

  pi.registerCommand("ci-logs", {
    description: "Fetch and display failure logs for a specific CI job (usage: /ci-logs <job-name-or-id>)",
    handler: async (args, ctx) => {
      if (!args.trim()) {
        ctx.ui.notify("Usage: /ci-logs <job-name-or-id>", "warning");
        return;
      }

      try {
        const summary = await fetchCiSummary(pi, ctx.cwd);
        lastSummary = summary;
        const job = await getLogJob(pi, ctx.cwd, summary, { jobId: args.trim() });
        ctx.ui.notify(`Fetching logs for: ${job.name}`, "info");
        const logs = await fetchJobLogs(pi, ctx.cwd, job);
        // Show in the widget area
        const logLines = [`Logs for: ${job.name}`, ""];
        logLines.push(...logs.split("\n").slice(0, 100));
        ctx.ui.setWidget("ci-logs", logLines, { placement: "aboveEditor" });
        ctx.ui.notify(`Logs loaded (${logs.split("\n").length} lines)`, "info");
        setTimeout(() => {
          ctx.ui.setWidget("ci-logs", undefined);
        }, 120_000);
      } catch (error) {
        ctx.ui.notify(`Failed to fetch logs: ${errorMessage(error)}`, "error");
      }
    },
  });

  // --- get_ci_status tool ---
  pi.registerTool({
    name: "get_ci_status",
    label: "Get CI Status",
    description: "Fetch CI status for the current checkout's GitHub origin, branch, and commit SHA, with job IDs, URLs, and durations. Closed or different-head PRs cannot replace checkout scope. Includes published local-ci/other commit statuses; missing local-ci publication is unknown, not a remote Actions failure. Use CIRCLECI_TOKEN for CircleCI enrichment and ci_fetch_job_logs for console output.",
    promptSnippet: "Fetch latest CI status for the current git branch/PR with per-job breakdown",
    promptGuidelines: [
      "Use get_ci_status when the user asks about CI status, failing checks, or whether the current branch is ready after a push.",
      "After get_ci_status shows failed jobs, use ci_fetch_job_logs with a job id or runId to get the failure logs.",
      "local-ci commit statuses have no run provenance. Inspect local-ci runs/show read-only, then select an explicit local-ci:<run-id>[:<step-id>] for logs. Runner logs label v1 publication receipts as historical acknowledgements or unknown, never current CI status. Do not run, resume, publish, or deploy automatically.",
    ],
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, ctx) {
      try {
        const summary = await fetchCiSummary(pi, ctx.cwd);
        lastSummary = summary;
        ctx.ui.setStatus(STATUS_KEY, compactStatus(summary));

        // Build structured details for LLM consumption
        const groups = groupJobs(summary);
        const jobDetails = summary.jobs.map((j) => ({
          id: j.id,
          name: j.name,
          provider: j.provider,
          state: j.state,
          url: j.url,
          duration: formatDuration(durationMs(j)),
          runId: j.runId,
          githubJobId: j.githubJobId,
          jobNumber: j.jobNumber,
          summary: j.summary,
        }));

        return {
          content: [{ type: "text", text: renderDetailedSummary(summary) }],
          details: {
            repo: summary.repo,
            branch: summary.branch,
            sha: summary.sha,
            prNumber: summary.prNumber,
            prUrl: summary.prUrl,
            checkedAt: summary.checkedAt,
            summary: {
              total: summary.jobs.length,
              failed: groups.failed.length,
              running: groups.running.length,
              passed: groups.passing.length,
              cancelled: groups.cancelled.length,
              skipped: groups.skipped.length,
              unknown: groups.unknown.length,
            },
            jobs: jobDetails,
            warnings: summary.warnings,
            errors: summary.errors,
          },
        };
      } catch (error) {
        return {
          content: [{ type: "text", text: `CI status unavailable: ${errorMessage(error)}` }],
          details: { error: errorMessage(error) },
          isError: true,
        };
      }
    },
  });

  // --- ci_fetch_job_logs tool ---
  pi.registerTool({
    name: "ci_fetch_job_logs",
    label: "Fetch CI Job Logs",
    description: "Fetch console output for one CI job after refreshing checkout scope. Prefer the exact jobId from get_ci_status; supplied runId/jobNumber must also match. Run-only queries and names paired with runId inspect the full run inventory. An exact github-job:<id> is read directly, including prior attempts; any supplied runId must match. GitHub runs/jobs are checked against the checkout SHA. CircleCI requires CIRCLECI_TOKEN. For local-ci, use jobId local-ci:<run-id>[:<step-id>] after native runs/show inspection: runner events include historical v1 receipt acknowledgements, not proof of current published checks or current validation. Step logs do not inspect receipts. Ambiguous jobs or unavailable output return errors, not substitute logs. Output is limited to 500 lines.",
    promptSnippet: "Fetch failure logs for a specific CI job",
    promptGuidelines: [
      "Use ci_fetch_job_logs after get_ci_status shows failed jobs, to get detailed failure logs for analysis.",
      "Prefer the exact jobId from get_ci_status. If a runId is ambiguous, supply that runId plus one of the returned exact job IDs; never choose a sibling implicitly.",
    ],
    parameters: Type.Object({
      jobId: Type.Optional(Type.String({ description: "Exact CI job ID from get_ci_status, or local-ci:<run-id>[:<step-id>] from native runs/show inspection. Local IDs cannot be combined with remote selectors." })),
      runId: Type.Optional(Type.Number({ description: "GitHub Actions run databaseId for the checkout SHA; combine with exact jobId when the run contains multiple jobs" })),
      jobNumber: Type.Optional(Type.Number({ description: "CircleCI job number from get_ci_status job details" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      let summary: CiSummary | undefined;
      let job: CiJob | undefined;
      try {
        // The display snapshot is not authority for a later checkout or commit.
        summary = await fetchCiSummary(pi, ctx.cwd);
        lastSummary = summary;
        job = await getLogJob(pi, ctx.cwd, summary, params);
        const logs = await fetchJobLogs(pi, ctx.cwd, job);
        return {
          content: [{ type: "text", text: `Logs for ${job.name}:\n\n${logs}` }],
          details: { repo: summary.repo, sha: summary.sha, jobId: job.id, jobName: job.name, provider: job.provider, state: job.state, url: job.url, runId: job.runId, githubJobId: job.githubJobId, jobNumber: job.jobNumber, localRunId: job.localRunId, localStepId: job.localStepId, logs },
        };
      } catch (error) {
        return {
          content: [{ type: "text", text: `CI logs unavailable${job ? ` for ${job.name}` : ""}: ${errorMessage(error)}` }],
          details: { error: errorMessage(error), repo: summary?.repo, sha: summary?.sha,
            availableJobs: summary?.jobs.map((job) => ({ id: job.id, name: job.name, runId: job.runId, jobNumber: job.jobNumber })) },
          isError: true,
        };
      }
    },
  });

  // --- Git push detection ---
  pi.on("tool_result", async (event, ctx) => {
    if (event.toolName !== "bash") return;
    const command = String((event.input as { command?: string }).command ?? "");
    if (!looksLikeGitPush(command) || event.isError) return;
    watching = true;
    ctx.ui.notify("Detected git push; watching CI", "info");
    clearTimer();
    timer = setTimeout(() => { void refreshAndRender(ctx, "git-push").catch(() => undefined); }, 5_000);
  });

  // --- Shutdown ---
  pi.on("session_shutdown", async () => {
    clearTimer();
    watching = false;
    lastSummary = undefined;
    lastFailureSignature = "";
    hadFailureSinceLastSuccess = false;
    lastErrorMessage = "";
  });
}
