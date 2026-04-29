import { DynamicBorder, type ExtensionAPI, type ExtensionContext, type Theme } from "@mariozechner/pi-coding-agent";
import { Type } from "typebox";
import { Container, Key, matchesKey, SelectList, Spacer, Text, truncateToWidth, visibleWidth, type SelectItem, type SelectListTheme } from "@mariozechner/pi-tui";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type CiState = "success" | "failed" | "running" | "pending" | "cancelled" | "skipped" | "unknown";
type CiProvider = "github" | "circleci";

type GitHubRepo = { owner: string; repo: string };

type CiJob = {
  id: string;
  provider: CiProvider;
  providerHint?: "github-actions" | "circleci" | "unknown";
  name: string;
  state: CiState;
  url?: string;
  startedAt?: string;
  completedAt?: string;
  durationMs?: number;
  summary?: string;
  /** For GitHub Actions runs, the run databaseId so we can fetch logs */
  runId?: number;
  /** For CircleCI jobs, the job number */
  jobNumber?: number;
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
  if (text.includes("github.com") || text.includes("github actions")) return "github-actions";
  return "unknown";
}

function githubRunIdFromUrl(url: string | null | undefined): number | undefined {
  if (!url) return undefined;
  const match = url.match(/github\.com\/[^/]+\/[^/]+\/actions\/runs\/(\d+)/i);
  if (!match) return undefined;
  const id = Number(match[1]);
  return Number.isSafeInteger(id) && id > 0 ? id : undefined;
}

function normalizedCiName(name: string | undefined): string {
  return (name ?? "").trim().toLowerCase().replace(/\s+/g, " ");
}

function githubJobNameCandidates(job: CiJob): string[] {
  const parts = job.name.split(/\s+\/\s+/).map((part) => part.trim()).filter(Boolean);
  return Array.from(new Set([job.name, parts[0], parts[parts.length - 1]].filter(Boolean)));
}

async function enrichGitHubRunIds(pi: ExtensionAPI, cwd: string, branch: string, sha: string, jobs: CiJob[]): Promise<CiJob[]> {
  const needsRunId = jobs.some((job) => job.provider === "github" && job.providerHint === "github-actions" && !job.runId);
  if (!needsRunId) return jobs;

  let runs: GhRun[] = [];
  try {
    runs = await execJson<GhRun[]>(
      pi,
      "gh",
      ["run", "list", "--commit", sha, "--limit", "50", "--json", "databaseId,name,workflowName,displayTitle,status,conclusion,headSha,url,createdAt,startedAt,updatedAt"],
      cwd,
      20_000,
    );
  } catch {
    try {
      runs = await execJson<GhRun[]>(
        pi,
        "gh",
        ["run", "list", "--branch", branch, "--limit", "50", "--json", "databaseId,name,workflowName,displayTitle,status,conclusion,headSha,url,createdAt,startedAt,updatedAt"],
        cwd,
        20_000,
      );
    } catch {
      return jobs;
    }
  }

  const matchingRuns = runs.filter((run) => !run.headSha || run.headSha === sha);
  const runsForSha = matchingRuns.length > 0 ? matchingRuns : runs;

  return jobs.map((job) => {
    if (job.provider !== "github" || job.providerHint !== "github-actions" || job.runId) return job;

    const urlRunId = githubRunIdFromUrl(job.url);
    if (urlRunId) return { ...job, runId: urlRunId };

    const candidates = new Set(githubJobNameCandidates(job).map(normalizedCiName));
    const match = runsForSha.find((run) => {
      const runNames = [run.name, run.workflowName, run.displayTitle].map(normalizedCiName).filter(Boolean);
      return runNames.some((name) => candidates.has(name));
    });

    return match ? { ...job, runId: match.databaseId } : job;
  });
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
  number?: number; url?: string; headRefName?: string; headRefOid?: string;
  statusCheckRollup?: GhRollupItem[];
};

type GhRun = {
  databaseId: number; name: string; workflowName?: string | null; displayTitle?: string | null;
  status?: string | null; conclusion?: string | null;
  headSha?: string | null; url?: string | null;
  createdAt?: string | null; startedAt?: string | null; updatedAt?: string | null;
};

async function fetchGitHubChecks(pi: ExtensionAPI, cwd: string, branch: string, sha: string): Promise<Partial<CiSummary>> {
  try {
    const pr = await execJson<GhPrView>(pi, "gh", ["pr", "view", "--json", "number,url,headRefName,headRefOid,statusCheckRollup"], cwd, 20_000);
    const jobs = (pr.statusCheckRollup ?? []).map((item, index): CiJob => {
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
        state: normalizeGitHubState(item.status ?? item.state, item.conclusion ?? item.state),
        startedAt: item.startedAt ?? undefined,
        completedAt: item.completedAt ?? undefined,
        summary: item.description ?? undefined,
      };
    });
    const summaryBranch = pr.headRefName ?? branch;
    const summarySha = pr.headRefOid ?? sha;
    const enrichedJobs = await enrichGitHubRunIds(pi, cwd, summaryBranch, summarySha, jobs);
    return { branch: summaryBranch, sha: summarySha, prNumber: pr.number, prUrl: pr.url, jobs: enrichedJobs };
  } catch (prError) {
    try {
      const runs = await execJson<GhRun[]>(pi, "gh", ["run", "list", "--commit", sha, "--limit", "10", "--json", "databaseId,name,status,conclusion,headSha,url,createdAt,updatedAt"], cwd, 20_000);
      const selectedRuns = runs.filter((run) => !run.headSha || run.headSha === sha);
      if (selectedRuns.length === 0) {
        return { warnings: [`No GitHub Actions runs found for ${shortSha(sha)}; not showing branch runs from other commits.`] };
      }
      return {
        jobs: selectedRuns.map((run): CiJob => ({
          id: `github-run:${run.databaseId}`,
          provider: "github", providerHint: "github-actions",
          name: run.name, runId: run.databaseId,
          state: normalizeGitHubState(run.status, run.conclusion),
          url: run.url ?? undefined,
          startedAt: run.createdAt ?? undefined,
          completedAt: run.updatedAt ?? undefined,
        })),
      };
    } catch (runError) {
      return { warnings: [`GitHub checks unavailable via gh. PR lookup: ${truncate(errorMessage(prError), 220)}. Run lookup: ${truncate(errorMessage(runError), 220)}.`] };
    }
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
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`CircleCI API ${response.status} ${response.statusText}${text ? `: ${truncate(text, 500)}` : ""}`);
  }
  return (await response.json()) as T;
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

  const github = await fetchGitHubChecks(pi, root, branch, sha);
  if (github.branch) summary.branch = github.branch;
  if (github.sha) summary.sha = github.sha;
  if (github.prNumber) summary.prNumber = github.prNumber;
  if (github.prUrl) summary.prUrl = github.prUrl;
  if (github.jobs) summary.jobs.push(...github.jobs);
  if (github.warnings) summary.warnings.push(...github.warnings);

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

  return summary;
}

// ---------------------------------------------------------------------------
// Log fetching
// ---------------------------------------------------------------------------

async function fetchGitHubRunLog(pi: ExtensionAPI, cwd: string, runId: number, failedOnly: boolean): Promise<string> {
  const args = ["run", "view", String(runId)];
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

  const output = result.stdout || result.stderr || "";
  if (!output.trim()) return "(no log output)";
  // Truncate for display
  const lines = output.split("\n");
  if (lines.length > 500) {
    return lines.slice(0, 500).join("\n") + `\n\n... truncated (${lines.length - 500} more lines)`;
  }
  return output;
}

async function fetchCircleCIJobOutput(_cwd: string, job: CiJob): Promise<string> {
  // CircleCI v2 API doesn't have a direct log output endpoint.
  // We provide job details and a link to the CircleCI job page.
  const lines: string[] = [];
  lines.push(`CircleCI Job: ${job.name}`);
  lines.push(`Status: ${job.state}`);
  if (job.url) lines.push(`URL: ${job.url}`);
  if (job.startedAt) lines.push(`Started: ${new Date(job.startedAt).toLocaleString()}`);
  if (job.completedAt) lines.push(`Completed: ${new Date(job.completedAt).toLocaleString()}`);
  const dur = durationMs(job);
  if (dur) lines.push(`Duration: ${formatDuration(dur)}`);
  lines.push("");
  lines.push("To view full CircleCI logs, open the job URL above in a browser.");
  lines.push("Alternatively, install the CircleCI CLI and run: circleci job output <job-number>");
  return lines.join("\n");
}

async function fetchJobLogs(pi: ExtensionAPI, cwd: string, job: CiJob): Promise<string> {
  const githubRunId = job.runId ?? githubRunIdFromUrl(job.url);
  if (job.provider === "github" && githubRunId) {
    return fetchGitHubRunLog(pi, cwd, githubRunId, job.state === "failed");
  }
  if (job.provider === "circleci") {
    return await fetchCircleCIJobOutput(cwd, job);
  }
  return "Log fetching not supported for this job type.";
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
  const provider = job.provider === "circleci" ? "CircleCI" : "GitHub";
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
  if (summary.jobs.length === 0) return summary.errors.length > 0 ? "CI unavailable" : "CI no checks";
  const groups = groupJobs(summary);
  if (groups.failed.length > 0) return `CI ❌ ${groups.failed.length} failed · ${groups.running.length} running · ${groups.passing.length} passing`;
  if (groups.running.length > 0) return `CI ⏳ ${groups.running.length} running · ${groups.passing.length} passing`;
  if (groups.cancelled.length > 0) return `CI 🚫 ${groups.cancelled.length} cancelled · ${groups.passing.length} passing`;
  if (groups.unknown.length > 0) return `CI ? ${groups.unknown.length} unknown · ${groups.passing.length} passing`;
  return `CI ✅ all passed (${groups.passing.length})`;
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
  return summary.jobs.length > 0 && summary.jobs.every((job) => ["success", "skipped"].includes(job.state));
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
    if (currentFailureSignature !== lastFailureSignature) {
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
    const shouldRenderWidget = widgetVisible || failedJobs(summary).length > 0;
    if (shouldRenderWidget) ctx.ui.setWidget(WIDGET_KEY, renderSummary(summary), { placement: "aboveEditor" });
    ctx.ui.setStatus(STATUS_KEY, compactStatus(summary));
    notifyTransitions(ctx, lastSummary, summary, reason);
    lastSummary = summary;
    lastErrorMessage = "";
    scheduleNext(ctx, summary);
    return summary;
  } catch (error) {
    const message = errorMessage(error);
    ctx.ui.setStatus(STATUS_KEY, "CI unavailable");
    if (widgetVisible) ctx.ui.setWidget(WIDGET_KEY, renderError(error), { placement: "aboveEditor" });
    if (message !== lastErrorMessage) {
      ctx.ui.notify(`CI refresh failed: ${truncate(message, 240)}`, "warning");
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
  widgetVisible = true;
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

/** Cross-platform clipboard copy. */
function copyToClipboard(pi: ExtensionAPI, text: string) {
  const escaped = text.replace(/'/g, "'\\''");
  const platform = process.platform;
  let clip: string;
  if (platform === "darwin") clip = "pbcopy";
  else if (platform === "win32") clip = "clip";
  else clip = "{ wl-copy 2>/dev/null || xclip -selection clipboard 2>/dev/null; }";
  pi.exec("bash", ["-c", `echo -n '${escaped}' | ${clip}`], { timeout: 5000 }).catch(() => {});
}

// ===========================================================================
// INTERACTIVE CI DETAIL OVERLAY
// ===========================================================================

type DetailView = "jobs" | "detail" | "loadingLogs" | "help" | "pickCi" | "pickCycle";
type CiKey = string;
type CycleKey = string;

const IMPORTANT_STATES = new Set<CiState>(["failed", "running", "pending", "cancelled", "unknown"]);

class CiDetailComponent {
  private summary: CiSummary;
  private pi: ExtensionAPI;
  private cwd: string;
  private done: () => void;
  private requestRender: () => void;
  private theme: Theme;

  private view: DetailView = "jobs";
  private activeCi: CiKey = "github-actions";
  private activeCycle: CycleKey = "Jobs";
  private selectedIndex = 0;
  private logScrollOffset = 0;
  private showAllJobs = false;
  private jobs: CiJob[] = [];
  private selectedJob: CiJob | null = null;
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

  constructor(summary: CiSummary, pi: ExtensionAPI, cwd: string, theme: Theme, done: () => void, requestRender: () => void) {
    this.summary = summary;
    this.pi = pi;
    this.cwd = cwd;
    this.theme = theme;
    this.done = done;
    this.requestRender = requestRender;

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
    if (this.animTimer) clearInterval(this.animTimer);
    if (this.loadingAnimTimer) clearInterval(this.loadingAnimTimer);
  }

  private rerender(): void {
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
    if (text.includes("github.com") && (text.includes("/actions/") || text.includes("github actions"))) return "github-actions";
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

    if (job.provider === "github") return "github-actions";
    return String(job.provider);
  }

  private ciLabel(ci: CiKey): string {
    const labels: Record<string, string> = {
      "github-actions": "GitHub Actions",
      github: "GitHub Actions",
      circleci: "CircleCI",
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
    if (!this.selectedJob || this.logLoading) return;
    this.logLoading = true;
    this.logError = "";
    this.view = "loadingLogs";
    this.startLoadingAnim();

    fetchJobLogs(this.pi, this.cwd, this.selectedJob).then((logs) => {
      this.logContent = logs.split("\n");
      this.logLoading = false;
      this.logScrollOffset = this.firstInterestingLogLine(this.logContent);
      this.view = "detail";
      this.stopLoadingAnim();
      this.rerender();
    }).catch((error) => {
      this.logError = errorMessage(error);
      this.logLoading = false;
      this.view = "detail";
      this.stopLoadingAnim();
      this.rerender();
    });
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
    if (this.refreshing) return;

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
      this.copiedMessage = job ? `No URL for selected job: ${job.name}` : "No selected job URL to copy";
      this.rerender();
      return;
    }

    copyToClipboard(this.pi, job.url);
    this.copiedMessage = `Copied URL for ${this.jobDisplayName(job)}: ${this.shortUrl(job.url, 90)}`;
    this.rerender();
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
    const groups = this.groupsForJobs(jobs);
    if (groups.failed.length > 0) return "Select a failed job, then press r for logs.";
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
      const color: "warning" | "success" = this.statusMessage.startsWith("Refresh failed") || this.refreshing ? "warning" : "success";
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
    container.addChild(this.text(this.theme.fg("dim", "↑↓ select · Enter details · r logs · l open URL · c copy URL · ? help")));
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
    container.addChild(this.text(this.theme.fg("dim", "Esc back · Enter/r logs · f first error · l open URL · c copy URL · R refresh · ? help")));
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
      if (!ctx.hasUI) {
        ctx.ui.notify("CI detail view requires interactive mode.", "warning");
        return;
      }

      // Fetch fresh summary
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

      // Replace the editor instead of using a transparent overlay so old message
      // labels and terminal chrome do not bleed through the CI UI.
      await ctx.ui.custom<void>((tui, theme, _kb, done) => {
        const component = new CiDetailComponent(summary, pi, ctx.cwd, theme, done, () => tui.requestRender());
        return component;
      });
    },
  });

  pi.registerCommand("ci-refresh", {
    description: "Force-refresh CI status",
    handler: async (_args, ctx) => {
      widgetVisible = true;
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

      let summary = lastSummary;
      if (!summary) {
        try {
          summary = await fetchCiSummary(pi, ctx.cwd);
          lastSummary = summary;
        } catch (error) {
          ctx.ui.notify(`Failed to fetch CI status: ${errorMessage(error)}`, "error");
          return;
        }
      }

      const search = args.trim().toLowerCase();
      const job = summary.jobs.find(
        (j) => j.id.toLowerCase().includes(search) || j.name.toLowerCase().includes(search)
      );

      if (!job) {
        ctx.ui.notify(`No job matching "${args.trim()}" found. Available: ${summary.jobs.map(j => j.name).join(", ")}`, "warning");
        return;
      }

      ctx.ui.notify(`Fetching logs for: ${job.name}`, "info");
      try {
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
    description: "Fetch the latest CI status for the current git branch/PR including per-job breakdown with IDs, URLs, and durations. Use gh CLI for GitHub and CIRCLECI_TOKEN for CircleCI enrichment. Use ci_fetch_job_logs to get failure logs for a specific failed job.",
    promptSnippet: "Fetch latest CI status for the current git branch/PR with per-job breakdown",
    promptGuidelines: [
      "Use get_ci_status when the user asks about CI status, failing checks, or whether the current branch is ready after a push.",
      "After get_ci_status shows failed jobs, use ci_fetch_job_logs with a job id or runId to get the failure logs.",
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
    description: "Fetch failure logs for a specific CI job. Pass the job id from get_ci_status output, or a GitHub run databaseId (for GH Actions) or CircleCI job number. Returns the log output truncated to 500 lines.",
    promptSnippet: "Fetch failure logs for a specific CI job",
    promptGuidelines: [
      "Use ci_fetch_job_logs after get_ci_status shows failed jobs, to get detailed failure logs for analysis.",
      "Pass the job id, runId, or jobNumber from the get_ci_status details to identify which job's logs to fetch.",
    ],
    parameters: Type.Object({
      jobId: Type.Optional(Type.String({ description: "The CI job id from get_ci_status details (e.g., 'github-run:12345' or 'circleci:abc123')" })),
      runId: Type.Optional(Type.Number({ description: "GitHub Actions run databaseId from get_ci_status job details" })),
      jobNumber: Type.Optional(Type.Number({ description: "CircleCI job number from get_ci_status job details" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      let summary = lastSummary;
      if (!summary) {
        try {
          summary = await fetchCiSummary(pi, ctx.cwd);
          lastSummary = summary;
        } catch (error) {
          return {
            content: [{ type: "text", text: `Failed to fetch CI status: ${errorMessage(error)}` }],
            details: { error: errorMessage(error) },
            isError: true,
          };
        }
      }

      // Find the matching job
      let job: CiJob | undefined;
      if (params.runId) {
        job = summary.jobs.find((j) => j.runId === params.runId);
      }
      if (!job && params.jobNumber) {
        job = summary.jobs.find((j) => j.jobNumber === params.jobNumber);
      }
      if (!job && params.jobId) {
        job = summary.jobs.find((j) => j.id === params.jobId || j.id.includes(params.jobId!));
      }
      // Fallback: try name match
      if (!job && params.jobId) {
        const search = params.jobId.toLowerCase();
        job = summary.jobs.find((j) => j.name.toLowerCase().includes(search));
      }

      if (!job) {
        const available = summary.jobs.map(j => `${j.id} (${j.name})`).join(", ");
        return {
          content: [{ type: "text", text: `Job not found. Available jobs:\n${available}` }],
          details: { error: "Job not found", availableJobs: summary.jobs.map(j => ({ id: j.id, name: j.name, runId: j.runId, jobNumber: j.jobNumber })) },
          isError: true,
        };
      }

      try {
        const logs = await fetchJobLogs(pi, ctx.cwd, job);
        return {
          content: [{ type: "text", text: `Logs for ${job.name}:\n\n${logs}` }],
          details: { jobId: job.id, jobName: job.name, provider: job.provider, state: job.state, url: job.url, logs },
        };
      } catch (error) {
        return {
          content: [{ type: "text", text: `Failed to fetch logs for ${job.name}: ${errorMessage(error)}` }],
          details: { error: errorMessage(error) },
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
    widgetVisible = true;
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
