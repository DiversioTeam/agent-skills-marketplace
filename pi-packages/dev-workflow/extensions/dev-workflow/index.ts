import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { HelpPanel, PromptEditor, type WorkflowHelpCommand, type WorkflowPromptCategory, type WorkflowPromptSource } from "./help-panel";
import { access, mkdir, readFile, unlink, writeFile } from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { dirname, join } from "node:path";

// ---------------------------------------------------------------------------
// Prompt registry
// ---------------------------------------------------------------------------

type PromptLayer = "project" | "user" | "legacy";

type WorkflowPrompt = WorkflowHelpCommand & {
  prompt: string;
};

type PromptOverride = {
  prepend?: string;
  append?: string;
  replace?: string;
  disabled?: boolean;
  label?: string;
  short?: string;
  whatItDoes?: string[];
  whenToUse?: string;
  example?: string;
};

type CustomPromptConfig = {
  code?: unknown;
  label?: unknown;
  short?: unknown;
  category?: unknown;
  command?: unknown;
  prompt?: unknown;
  whatItDoes?: unknown;
  whenToUse?: unknown;
  example?: unknown;
};

type PromptConfig = {
  version?: unknown;
  overrides?: unknown;
  prompts?: unknown;
};

type PromptRegistry = {
  prompts: WorkflowPrompt[];
  warnings: string[];
  paths: { project?: string; user: string; legacy: string };
};

const CORE_PROMPTS: WorkflowPrompt[] = [
  {
    code: "workflow.plan",
    command: "workflow:plan",
    label: "Plan review",
    short: "Fresh-eyes review of the plan before implementing",
    whatItDoes: [
      "Reads the written plan and surrounding existing code",
      "Looks carefully for bugs, errors, ambiguity, or confusion",
      "Updates the plan based on anything uncovered",
    ],
    whenToUse: "Before writing any code. Use this when you have just written a plan and want to challenge it before implementation gains momentum.",
    example: "/workflow:plan focus on the auth middleware",
    category: "core",
    sourceLabel: "core",
    prompt: `Great, now I want you to carefully read over the plan you just wrote and the existing code you already reviewed with "fresh eyes."

Look super carefully for any obvious bugs, errors, problems, issues, or confusion.

Carefully update the plan based on anything you uncover.`,
  },
  {
    code: "workflow.self",
    command: "workflow:self",
    label: "Self-review",
    short: "Implementor rereads all new and modified code with fresh eyes",
    whatItDoes: [
      "Rereads every new and modified file with fresh eyes",
      "Looks for obvious bugs, errors, problems, or confusion",
      "Fixes anything found before the independent reviewer sees it",
    ],
    whenToUse: "After implementation but before independent review. The implementor should catch obvious mistakes first.",
    example: "/workflow:self pay extra attention to error handling",
    category: "core",
    sourceLabel: "core",
    prompt: `Great, now I want you to carefully read over all of the new code you just wrote and the existing code you just modified with "fresh eyes."

Look super carefully for any obvious bugs, errors, problems, issues, or confusion.

Carefully fix anything you uncover.`,
  },
  {
    code: "workflow.standards",
    command: "workflow:standards",
    label: "Standards pass",
    short: "Coding standards pass: lint, types, imports, ORM, Ruff",
    whatItDoes: [
      "Checks modified files against coding standards and pre-commit hygiene",
      "Catches local imports, unnecessary getattr(), large try/except blocks, loose typing, and ORM import issues",
      "Keeps Ruff, type hints, and test fixtures clean",
    ],
    whenToUse: "After self-review, before documentation. This is the policy and hygiene pass.",
    example: "/workflow:standards also check for missing DB indexes",
    category: "core",
    sourceLabel: "core",
    prompt: `Please help me fix the files in \`git status\` so they match our coding standards and pre-commit requirements.

Please check all of the following:

- No local imports at any cost. Do check circular imports.
- No unnecessary \`getattr()\` calls. Use \`hasattr()\` only if really needed.
- No unwanted or overly large \`try\` / \`except\` blocks.
- In \`optimo_\` apps, strictly use structured logging.
- No hardcoded strings or numbers where structured fields or typed payloads should be used.
- Use \`TypedDict\` instead of loose \`dict\` usage with \`Any\` or mixed-value \`or\` checks.
- Make sure Ruff is completely happy with these files.
- No string-based type hints, for example: \`OptimoRiskQuestionBank\`
- Never use \`typing.cast()\`. It is a code smell.
- Make sure we are not repeating fixtures in tests.
- Use reverse relations in Django ORM queries to prevent unnecessary model imports.
- Be pedantic about type hints. They are very important. Add them without losing information where possible, and avoid \`Any\` as much as possible.
- Feel free to use \`ast-grep\`.`,
  },
  {
    code: "workflow.ci",
    command: "workflow:ci",
    label: "CI check",
    short: "Check CI — interactive TUI view, logs, ours-vs-flake analysis",
    whatItDoes: [
      "Uses /ci and /ci-detail from the ci-status package when available",
      "Fetches specific failure logs with /ci-logs or ci_fetch_job_logs",
      "Analyzes each failure as ours vs flake and proposes concrete fixes",
    ],
    whenToUse: "Before local verification and before shipping. Also use any time you need to understand branch CI.",
    example: "/workflow:ci check only backend tests",
    category: "core",
    sourceLabel: "core",
    prompt: `Let's check CI for this branch.

**Check the status.** Run the /ci command first for a quick overview. It shows a per-job breakdown in the widget area. For the full interactive view with job details and log access, use /ci-detail.

For a specific failing job, use /ci-logs <job-name> to pull its logs directly. If the ci-status package is not installed or the slash commands are unavailable, use get_ci_status and ci_fetch_job_logs if those tools are available. If neither path is available, ask the user to install ci-status before proceeding.

For every failing job:
- **Ours or flake?** Is this failure caused by our changes, or is it a pre-existing flake?
- **Root cause.** If ours, what's the actual problem?
- **Fix.** Propose the specific code change, test update, or config tweak needed.
- **If flake.** Note it clearly so we don't waste time chasing it.

Summarize at the end: overall status, per-job verdict table, and fixes needed. If everything is green, confirm we're clear to proceed.`,
  },
  {
    code: "workflow.docs",
    command: "workflow:docs",
    label: "Documentation pass",
    short: "Documentation pass — explain the why for future readers",
    whatItDoes: [
      "Documents updated code, especially new additions",
      "Uses simple, visual, first-principles-driven language",
      "Explains why changes were made, not just what changed",
    ],
    whenToUse: "At the very end, after all code changes are final.",
    example: "/workflow:docs focus on the new API endpoints",
    category: "core",
    sourceLabel: "core",
    prompt: `Let's please make sure all the updated code, especially the newly added code, is very well documented in simple language.

Please keep the documentation visual and first-principles-driven. Explain why those changes or additions are being made.

Use commands, docs, strings, and anything else helpful so that future readers of the code can understand why we added something like this and how to make use of it.`,
  },
  {
    code: "workflow.ship",
    command: "workflow:ship",
    label: "Ship",
    short: "Smart ship: discover PR context, atomic commit, open/update PR",
    whatItDoes: [
      "Verifies CI first and fixes failures caused by our code",
      "Discovers branch, existing PRs, and linked issues",
      "Runs atomic commit/pre-commit workflows and updates or opens the PR",
      "Uses PR description writer for a reviewer-friendly PR body",
    ],
    whenToUse: "When all review passes are complete and you are ready to ship or update a PR.",
    example: "/workflow:ship target is staging",
    category: "core",
    sourceLabel: "core",
    prompt: `Let's finalize and ship this work.

First, check CI. Prefer the ci-status extension commands if they are available: /ci, /ci-detail, and /ci-logs <job>. If those commands are not available, use get_ci_status and ci_fetch_job_logs if those tools are available. If neither path is available, ask the user to install ci-status before proceeding.

If anything is failing:
- Determine if failures are from our changes or pre-existing flakes
- Fix any failures caused by our code before proceeding
- If everything is green, confirm and move on

Next, discover PR context. Check what branch we're on and look for any existing GitHub PRs or issues related to this work. Use gh pr list, gh issue list, or whatever is needed.

- If an existing PR is already open for this branch, update it with the current changes.
- If no PR exists yet, create one.
- If there's a related GitHub issue, link the PR to it.
- If you are unsure about anything, ask me before proceeding.

Then ship it. Use the atomic commit skill and make sure everything passes (lint, type-checks, tests, pre-commit). Do not compromise by excluding things that are part of this PR — anything touched needs to be improved as much as possible.

Once the code is ready, use the PR description writer skill to generate a reviewer-friendly description, and open or update the PR on GitHub.`,
  },
  {
    code: "workflow.pr-review-comments",
    command: "workflow:pr-review-comments",
    label: "Address PR review comments",
    short: "Fetch review comments, fix them, validate, push, resolve, re-request review",
    whatItDoes: [
      "Identifies one PR, inferred current PR, or multiple provided PRs",
      "Fetches unresolved threads, review summaries, issue comments, and inline comments",
      "Groups feedback by root cause and asks questions when scope or intent is ambiguous",
      "Makes focused fixes, runs atomic/pre-commit checks, commits, pushes, resolves addressed threads, and re-requests review",
    ],
    whenToUse: "When reviewers or bots left PR feedback that must be addressed before re-review. Supports multiple PRs when provided explicitly.",
    example: "/workflow:pr-review-comments PR #68 and PR #69",
    category: "core",
    sourceLabel: "core",
    prompt: `Please address PR review feedback carefully and prepare the PR(s) for re-review.

Scope:
- If I provided one or more PR numbers/URLs, handle those PRs.
- If I did not provide a PR, infer the PR for the current branch.
- If multiple PRs are involved and the target repo/branch/worktree is ambiguous, ask clarifying questions before editing.
- If the PRs span multiple repos, submodules, or worktrees, identify the correct checkout for each before making changes.

Process:
1. Identify the PR(s): confirm PR number, URL, branch, base branch, repo, draft/readiness state, and current local checkout. If anything is ambiguous, stop and ask.
2. Fetch review state: unresolved review threads, review summaries, change-request reviews, issue comments, inline comments, and actionable bot comments such as Codex.
3. Understand the feedback: explain each reviewer intent, group related comments, and ask if product/design clarification is needed.
4. Make focused changes: address only review feedback and directly related cleanup. Preserve style. Avoid broad refactors. Do not force-push unless explicitly authorized.
5. Run checks before pushing: relevant formatting, lint, type, test, build, and repo-local atomic commit or pre-commit workflows.
6. Commit atomically: include all files required for the fix, keep commits reviewable, and keep multiple PR/repo fixes scoped appropriately.
7. Push normally to the PR branch.
8. Resolve review threads: resolve only threads actually addressed by pushed changes. Leave unresolved anything needing clarification or follow-up.
9. Re-request review: ask affected reviewers again. Trigger automation reviewers if needed.
10. Final report: PRs handled, comments addressed, files changed, commits pushed, checks run, threads resolved, reviewers re-requested, and remaining blockers.

Safety rules:
- Never resolve comments that were not addressed.
- Never hide failing checks.
- Never skip required atomic/pre-commit checks.
- Ask questions when PR identity, reviewer intent, target branch, or multi-PR ordering is unclear.`,
  },
  {
    code: "workflow.release-prs",
    command: "workflow:release-prs",
    label: "Prepare release PRs",
    short: "Prepare release PRs for backend, frontend, optimo-frontend, and design-system",
    whatItDoes: [
      "Uses the backend-release skill for backend release mechanics",
      "Reads each repo's own release/contribution guidelines before acting",
      "Prepares release PRs in backend, frontend, optimo-frontend, and design-system repos",
      "Asks clarifying questions when release branches, versions, targets, or repo state are ambiguous",
    ],
    whenToUse: "When coordinating release PRs across the main product repos from the monolith checkout.",
    example: "/workflow:release-prs prepare today's release PRs",
    category: "core",
    sourceLabel: "core",
    prompt: `Please prepare release PRs on GitHub for backend, frontend, optimo-frontend, and design-system in their respective repositories.

Important context:
- Use the backend-release / release-manager skill for the backend release workflow.
- For frontend, optimo-frontend, and design-system, first read and follow each repo's own guidelines if available (AGENTS.md, CLAUDE.md, README, CONTRIBUTING, release docs, package scripts, or repo-local docs).
- These repos may have different base branches, release branches, versioning rules, build steps, and PR body expectations.

Process:
1. Confirm scope and ask questions if needed.
   - Are all four repos in scope: backend, frontend, optimo-frontend, design-system?
   - Are these regular releases or hotfixes?
   - Which target/base branches should each release PR use?
   - Should version bumps happen now, and what version/date convention applies per repo?
   - If any repo is dirty, detached, missing remotes, or on an unexpected branch, stop and ask.

2. For each repo, identify local and upstream state.
   - Check branch, remotes, dirty status, and current HEAD.
   - Fetch relevant branches.
   - Determine whether there are actual release differences before opening a PR.
   - Prefer tree diffs or repo-local release checks over stale commit ancestry when guidelines say so.

3. Read repo-local release guidance before editing.
   - backend: use backend-release / release-manager instructions.
   - frontend: read frontend-local guidance and package scripts.
   - optimo-frontend: read optimo-local guidance and package scripts.
   - design-system: read design-system-local guidance and package scripts.
   - If guidance conflicts or is missing, summarize the uncertainty and ask.

4. Prepare release branches/PRs.
   - Use each repo's expected branch naming, base branch, versioning, changelog, lockfile, and PR body format.
   - Do not force-push unless explicitly authorized.
   - Keep changes scoped per repo.
   - If conflicts occur, resolve only when intent is clear; otherwise ask.

5. Run required checks.
   - Run repo-local formatting, lint, type, test, build, lockfile, or release validation commands required by each repo.
   - If a check cannot be run, explain exactly why and list the manual command.

6. Create or update release PRs.
   - Use gh CLI in the relevant repo.
   - Link included PRs or changelog entries according to repo conventions.
   - If a release PR already exists, update it instead of duplicating it.

7. Final report.
   - For each repo: state, release branch, PR URL, version/changelog, included PRs, checks run, and blockers.
   - Clearly list any repos skipped because there was nothing to release.
   - Clearly list unresolved questions or manual follow-up.

Safety rules:
- Do not invent a release version when repo rules are unclear.
- Do not create empty release PRs.
- Do not mix changes across repos in one commit.
- Do not bypass repo-local release guidance.
- Ask questions when release target, versioning, or included changes are ambiguous.`,
  },
  {
    code: "workflow.context",
    command: "workflow:context",
    label: "Load PR context",
    short: "Load context from existing PRs, checkout if needed, deep-read diff",
    whatItDoes: [
      "Discovers PRs on the current branch or lists recent open PRs",
      "Checks out remote PRs if needed",
      "Deep-reads the full diff, CI, review comments, and unresolved threads",
    ],
    whenToUse: "When starting a new session and you need to continue work on an existing PR.",
    example: "/workflow:context check PR #1234",
    category: "bootstrap",
    sourceLabel: "core",
    prompt: `Let's load context from existing PRs so I can continue working on this.

First, discover what's available. Check the current branch and look for local PRs:
- gh pr list --head $(git branch --show-current)
- If no local PR, list my recent open PRs: gh pr list --author @me --state open
- Also check for any open PRs in this repo that might be related

For the PR I want to work on:
- If it's already checked out locally, do a deep diff review
- If it's on a remote branch, check it out with gh pr checkout <number>

Then deeply understand it:
- Read the full diff across all modified files
- Understand what problem it solves and how
- Check CI status and failure logs if needed
- Review PR comments and unresolved review threads
- Identify what's been done and what might still be needed
- Note any submodule pointer changes or cross-repo impacts

Ask me questions if you're unsure which PR to focus on, if you need to check out a remote branch, or if you need clarification. Finally, summarize what the PR does, what state it's in, and likely next steps.`,
  },
  {
    code: "workflow.handoff",
    command: "workflow:handoff",
    label: "Handoff",
    short: "Generate handoff message for a new engineer or fresh subagent",
    whatItDoes: [
      "Summarizes task overview, current state, remaining work, key files, commands, decisions, risks, and success criteria",
      "Formats output as a pasteable handoff for another engineer or AI session",
    ],
    whenToUse: "When handing work to another engineer or spawning a fresh subagent session.",
    example: "/workflow:handoff include the database migration steps",
    category: "bootstrap",
    sourceLabel: "core",
    prompt: `Generate a comprehensive handoff message for a new engineer (or a fresh AI subagent session) who will be working on this task now. They will be using this machine itself.

Include:
1. Task overview — what are we building or fixing, and why?
2. Current state — what's been done so far, what's working, what's been validated?
3. What's left — remaining work items in priority order, with enough detail to act on
4. Files and modules — key files changed and files they'll need to modify, where to focus
5. Setup commands — exact commands they should run first to get oriented
6. Test and verify commands — how to check their work locally
7. Decisions made — non-obvious choices and rationale
8. Risks and gotchas — known edge cases and things easy to break
9. Success criteria — how to know when the work is truly done

Format this as a message I can paste directly into a new pi session or share with another engineer. Use clear section headers, exact commands, and keep it scannable.`,
  },
  {
    code: "workflow.onboard",
    command: "workflow:onboard",
    label: "Onboard engineers",
    short: "Generate onboarding message for engineers about the workflow",
    whatItDoes: [
      "Explains multi-agent parallel workflow",
      "Covers readonly-only rule and handoff pattern",
      "Includes example commands and a typical session",
    ],
    whenToUse: "When onboarding engineers to the developer workflow.",
    example: "/workflow:onboard focus on backend team workflow",
    category: "bootstrap",
    sourceLabel: "core",
    prompt: `Generate a message I can share with engineers (I refer to them as "agents") to get them started with the multi-agent workflow.

The message should explain:
- Multiple agents in parallel, each with a distinct slice of work
- Readonly only: read, analyze, plan, report, suggest; no commits, pushes, PR creation, or file writes
- Include exact commands for any action; final apply is done by me
- The workflow commands: /workflow:plan, /workflow:self, /workflow:standards, /workflow:docs
- Subagents for depth: /workflow:scout, /workflow:oracle, /workflow:reviewer, /workflow:parallel
- The handoff pattern and back-and-forth refinement
- A concrete example session from start to handoff

Make it clear, motivating, and actionable.`,
  },
  {
    code: "workflow.scout",
    command: "workflow:scout",
    label: "Scout",
    short: "Codebase recon → scout agent",
    whatItDoes: ["Identifies relevant files, entry points, data flow, patterns, risks, and recommended starting points"],
    whenToUse: "Before planning or implementing a change in unfamiliar territory.",
    example: "/workflow:scout focus on payment processing",
    category: "subagent",
    sourceLabel: "core",
    prompt: `Use the scout subagent to understand the codebase context for this change. Identify relevant files and entry points, data flow and dependencies, existing patterns and conventions, risks and gotchas, and where another agent should start. Bring back a concise scout report. If the subagent tool is not available, do a similar recon yourself with read, grep, and ls.`,
  },
  {
    code: "workflow.oracle",
    command: "workflow:oracle",
    label: "Oracle",
    short: "Second opinion → oracle agent",
    whatItDoes: ["Challenges assumptions, surfaces risks, recommends direction, and does not edit code"],
    whenToUse: "When a decision feels risky or you want a second set of eyes.",
    example: "/workflow:oracle is this refactor approach safe?",
    category: "subagent",
    sourceLabel: "core",
    prompt: `Use the oracle subagent for a second opinion. Challenge all assumptions in the current plan or implementation. Ask: What am I missing? What risks am I not seeing? What's the safest next move? Is there a simpler or more robust approach? The oracle must not edit any code — just surface concerns and recommend direction. If the subagent tool is not available, do a similar fresh-eyes analysis yourself without editing.`,
  },
  {
    code: "workflow.reviewer",
    command: "workflow:reviewer",
    label: "Reviewer",
    short: "Independent review → reviewer agent",
    whatItDoes: ["Reviews correctness, edge cases, tests, and simplicity with forked context"],
    whenToUse: "When you want a truly independent review.",
    example: "/workflow:reviewer focus on API error handling",
    category: "subagent",
    sourceLabel: "core",
    prompt: `Use the reviewer subagent to review the current changes with fresh eyes. Fork context from this session so the reviewer sees the full picture. Ask the reviewer to check correctness, edge cases, tests, and simplicity. Bring the results back and summarize actionable fixes. If the subagent tool is not available, review the code yourself with fresh eyes instead.`,
  },
  {
    code: "workflow.parallel",
    command: "workflow:parallel",
    label: "Parallel reviewers",
    short: "Three parallel reviewers: correctness, tests, complexity",
    whatItDoes: ["Runs three specialist reviews and synthesizes a prioritized fix list"],
    whenToUse: "When you want maximum review coverage.",
    example: "/workflow:parallel only review backend changes",
    category: "subagent",
    sourceLabel: "core",
    prompt: `Run parallel reviewer subagents on the current diff. I want three reviewers, each with a distinct focus:

1. Correctness & edge cases — does the code work? What breaks?
2. Test coverage & quality — are we testing the right things? False positives?
3. Unnecessary complexity & code smells — what's over-engineered, duplicated, or hard to follow?

Synthesize their feedback into a single prioritized list of actionable fixes. If the subagent tool is not available, do a thorough multi-angle review yourself.`,
  },
];

// ---------------------------------------------------------------------------
// Config loading and validation
// ---------------------------------------------------------------------------

function cloneCorePrompt(prompt: WorkflowPrompt): WorkflowPrompt {
  return { ...prompt, whatItDoes: [...prompt.whatItDoes] };
}

function xdgConfigHome(): string {
  return process.env.XDG_CONFIG_HOME || join(homedir(), ".config");
}

async function fileExists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

async function execText(pi: ExtensionAPI, command: string, args: string[], cwd: string, timeout = 5_000): Promise<string> {
  const result = await pi.exec(command, args, { cwd, timeout });
  if (result.code !== 0) throw new Error(result.stderr || result.stdout || `${command} failed with exit code ${result.code}`);
  return result.stdout.trim();
}

async function gitRoot(pi: ExtensionAPI, cwd: string): Promise<string | undefined> {
  try {
    return await execText(pi, "git", ["rev-parse", "--show-toplevel"], cwd, 5_000);
  } catch {
    return undefined;
  }
}

async function configPaths(pi: ExtensionAPI, cwd: string) {
  const root = await gitRoot(pi, cwd);
  return {
    project: root ? join(root, ".pi", "dev-workflow", "prompts.json") : undefined,
    user: join(xdgConfigHome(), "pi", "dev-workflow", "prompts.json"),
    legacy: join(homedir(), ".pi", "agent", "dev-workflow", "prompts.json"),
  };
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0 ? value : undefined;
}

function stringArrayValue(value: unknown): string[] | undefined {
  return Array.isArray(value) && value.every((item) => typeof item === "string") ? value : undefined;
}

function validCategory(value: unknown, fallback: WorkflowPromptCategory): WorkflowPromptCategory | undefined {
  if (value === undefined) return fallback;
  return ["core", "bootstrap", "subagent", "project", "user"].includes(String(value)) ? value as WorkflowPromptCategory : undefined;
}

function validateOverride(raw: unknown, code: string, path: string, warnings: string[]): PromptOverride | undefined {
  if (!isObject(raw)) {
    warnings.push(`${path}: override ${code} must be an object`);
    return undefined;
  }
  const override: PromptOverride = {};
  for (const field of ["prepend", "append", "replace", "label", "short", "whenToUse", "example"] as const) {
    if (raw[field] !== undefined) {
      const value = stringValue(raw[field]);
      if (!value) warnings.push(`${path}: override ${code}.${field} must be a non-empty string`);
      else (override as Record<string, unknown>)[field] = value;
    }
  }
  if (raw.disabled !== undefined) {
    if (typeof raw.disabled !== "boolean") warnings.push(`${path}: override ${code}.disabled must be boolean`);
    else override.disabled = raw.disabled;
  }
  if (raw.whatItDoes !== undefined) {
    const value = stringArrayValue(raw.whatItDoes);
    if (!value) warnings.push(`${path}: override ${code}.whatItDoes must be a string array`);
    else override.whatItDoes = value;
  }
  return override;
}

function validateCustomPrompt(raw: unknown, layer: PromptLayer, path: string, index: number, warnings: string[]): WorkflowPrompt | undefined {
  if (!isObject(raw)) {
    warnings.push(`${path}: prompts[${index}] must be an object`);
    return undefined;
  }
  const prompt = raw as CustomPromptConfig;
  const code = stringValue(prompt.code);
  const label = stringValue(prompt.label);
  const short = stringValue(prompt.short);
  const body = stringValue(prompt.prompt);
  const expectedPrefix = layer === "project" ? "project." : "user.";

  if (!code) warnings.push(`${path}: prompts[${index}].code is required`);
  else if (!code.startsWith(expectedPrefix)) warnings.push(`${path}: prompts[${index}].code must start with ${expectedPrefix}`);
  if (!label) warnings.push(`${path}: prompts[${index}].label is required`);
  if (!short) warnings.push(`${path}: prompts[${index}].short is required`);
  if (!body) warnings.push(`${path}: prompts[${index}].prompt is required`);

  const category = validCategory(prompt.category, layer === "project" ? "project" : "user");
  if (!category) warnings.push(`${path}: prompts[${index}].category is invalid`);

  const command = prompt.command === undefined ? undefined : stringValue(prompt.command);
  if (prompt.command !== undefined && !command) warnings.push(`${path}: prompts[${index}].command must be a non-empty string`);
  if (command && !command.startsWith("workflow:")) warnings.push(`${path}: prompts[${index}].command must start with workflow:`);

  if (!code || !label || !short || !body || !category) return undefined;

  return {
    code,
    command,
    label,
    short,
    category,
    prompt: body,
    whatItDoes: stringArrayValue(prompt.whatItDoes) ?? [short],
    whenToUse: stringValue(prompt.whenToUse) ?? short,
    example: stringValue(prompt.example) ?? `/workflow:run ${code}`,
    sourceLabel: layer === "project" ? "project" : "user",
    sourcePath: path,
  };
}

async function readConfig(path: string, layer: PromptLayer, warnings: string[]): Promise<PromptConfig | undefined> {
  if (!(await fileExists(path))) return undefined;
  try {
    const parsed = JSON.parse(await readFile(path, "utf8")) as PromptConfig;
    if (!isObject(parsed)) {
      warnings.push(`${path}: config must be a JSON object`);
      return undefined;
    }
    if (parsed.version !== 1) {
      warnings.push(`${path}: version must be 1`);
      return undefined;
    }
    return parsed;
  } catch (error) {
    warnings.push(`${path}: failed to parse JSON (${error instanceof Error ? error.message : String(error)})`);
    return undefined;
  }
}

function applyConfig(promptsByCode: Map<string, WorkflowPrompt>, config: PromptConfig, layer: PromptLayer, path: string, warnings: string[]): void {
  const overrideSource: WorkflowPromptSource = layer === "project" ? "project override" : "user override";

  if (config.overrides !== undefined) {
    if (!isObject(config.overrides)) {
      warnings.push(`${path}: overrides must be an object`);
    } else {
      for (const [code, rawOverride] of Object.entries(config.overrides)) {
        const existing = promptsByCode.get(code);
        if (!existing) {
          warnings.push(`${path}: override target ${code} does not exist`);
          continue;
        }
        const override = validateOverride(rawOverride, code, path, warnings);
        if (!override) continue;
        if (override.disabled) {
          promptsByCode.delete(code);
          continue;
        }
        const next = { ...existing, whatItDoes: [...existing.whatItDoes], sourceLabel: overrideSource, sourcePath: path };
        if (override.replace) next.prompt = override.replace;
        else next.prompt = `${override.prepend ? `${override.prepend}\n\n` : ""}${next.prompt}${override.append ? `\n\n${override.append}` : ""}`;
        if (override.label) next.label = override.label;
        if (override.short) next.short = override.short;
        if (override.whatItDoes) next.whatItDoes = override.whatItDoes;
        if (override.whenToUse) next.whenToUse = override.whenToUse;
        if (override.example) next.example = override.example;
        promptsByCode.set(code, next);
      }
    }
  }

  if (config.prompts !== undefined) {
    if (!Array.isArray(config.prompts)) {
      warnings.push(`${path}: prompts must be an array`);
    } else {
      config.prompts.forEach((raw, index) => {
        const prompt = validateCustomPrompt(raw, layer, path, index, warnings);
        if (!prompt) return;
        promptsByCode.set(prompt.code, prompt);
      });
    }
  }
}

function validateUniqueCommands(prompts: WorkflowPrompt[], warnings: string[]): void {
  const seen = new Map<string, string>();
  for (const prompt of prompts) {
    if (!prompt.command) continue;
    const previous = seen.get(prompt.command);
    if (previous) warnings.push(`Duplicate command ${prompt.command} on ${previous} and ${prompt.code}; use /workflow:run ${prompt.code} instead.`);
    else seen.set(prompt.command, prompt.code);
  }
}

async function loadPromptRegistry(pi: ExtensionAPI, cwd: string): Promise<PromptRegistry> {
  const paths = await configPaths(pi, cwd);
  const warnings: string[] = [];
  const promptsByCode = new Map(CORE_PROMPTS.map((prompt) => [prompt.code, cloneCorePrompt(prompt)]));

  for (const [layer, path] of [["project", paths.project], ["legacy", paths.legacy], ["user", paths.user]] as Array<[PromptLayer, string | undefined]>) {
    if (!path) continue;
    const config = await readConfig(path, layer, warnings);
    if (config) applyConfig(promptsByCode, config, layer, path, warnings);
  }

  const prompts = Array.from(promptsByCode.values());
  validateUniqueCommands(prompts, warnings);
  return { prompts, warnings, paths };
}

function promptForInput(registry: PromptRegistry, input: string): WorkflowPrompt | undefined {
  const normalized = input.replace(/^\//, "");
  return registry.prompts.find((prompt) => prompt.code === input || prompt.command === normalized || prompt.command === input);
}

function appendExtra(prompt: string, extra: string | undefined): string {
  const trimmed = extra?.trim();
  return trimmed ? `${prompt}\n\nAdditional context: ${trimmed}` : prompt;
}

function configTemplate(): string {
  return JSON.stringify({
    version: 1,
    overrides: {
      "workflow.standards": {
        append: "Add your local standards here."
      }
    },
    prompts: [
      {
        code: "user.example",
        label: "Example custom workflow prompt",
        short: "Demonstrates the expected custom prompt shape",
        category: "user",
        prompt: "Replace this with your own workflow prompt."
      }
    ]
  }, null, 2) + "\n";
}

// ---------------------------------------------------------------------------
// Extension entry point
// ---------------------------------------------------------------------------

interface WorkflowUi {
  notify(message: string, kind: "info" | "warning" | "error"): void;
  custom<T>(factory: (tui: any, theme: any, keybindings: any, done: (value: T) => void) => any): Promise<T>;
}

interface WorkflowContext {
  cwd: string;
  ui: WorkflowUi;
  isIdle?: () => boolean;
}

export default function (pi: ExtensionAPI) {
  const detectSubagents = (): boolean => {
    try {
      return pi.getAllTools?.().some((t: { name: string }) => t.name === "subagent") ?? false;
    } catch {
      return false;
    }
  };

  const execOrThrow = async (command: string, args: string[], timeout = 5_000) => {
    const result = await pi.exec(command, args, { timeout });
    if (result.code !== 0) {
      const details = [
        `${command} ${args.join(" ")} failed with exit code ${result.code}`,
        result.stderr ? `stderr: ${result.stderr.trim().slice(0, 500)}` : undefined,
        result.stdout ? `stdout: ${result.stdout.trim().slice(0, 500)}` : undefined,
      ].filter(Boolean).join("\n");
      throw new Error(details);
    }
  };

  const withTempClipboardFile = async <T>(text: string, fn: (path: string) => Promise<T>): Promise<T> => {
    const path = join(tmpdir(), `pi-workflow-clipboard-${process.pid}-${Date.now()}-${Math.random().toString(36).slice(2)}.txt`);
    await writeFile(path, text, "utf8");
    try {
      return await fn(path);
    } finally {
      await unlink(path).catch(() => undefined);
    }
  };

  const copyToClipboard = async (text: string) => {
    await withTempClipboardFile(text, async (path) => {
      if (process.platform === "win32") await execOrThrow("cmd", ["/c", `clip < "${path.replace(/"/g, "\"\"")}"`]);
      else if (process.platform === "darwin") await execOrThrow("bash", ["-c", `pbcopy < "$1"`, "bash", path]);
      else await execOrThrow("bash", ["-c", `if command -v wl-copy >/dev/null 2>&1; then wl-copy < "$1"; elif command -v xclip >/dev/null 2>&1; then xclip -selection clipboard < "$1"; else echo 'No clipboard command found (install wl-copy or xclip)' >&2; exit 127; fi`, "bash", path]);
    });
  };

  const waitForIdleWithTimeout = async (
    ctx: { waitForIdle: () => Promise<void>; ui: Pick<WorkflowUi, "notify"> },
    timeoutMs = 30_000,
  ): Promise<boolean> => {
    let timeout: ReturnType<typeof setTimeout> | undefined;
    try {
      const timedOut = await Promise.race([
        ctx.waitForIdle().then(() => false),
        new Promise<boolean>((resolve) => { timeout = setTimeout(() => resolve(true), timeoutMs); }),
      ]);
      if (timedOut) {
        ctx.ui.notify("Workflow is still waiting for the current agent turn to finish. Try again once pi is idle.", "warning");
        return false;
      }
      return true;
    } finally {
      if (timeout) clearTimeout(timeout);
    }
  };

  const sendWorkflowMessage = (ctx: WorkflowContext, text: string, deliverAs: "normal" | "followUp" = "normal") => {
    const idle = ctx.isIdle?.() ?? true;
    const options = idle ? undefined : { deliverAs: deliverAs === "followUp" ? "followUp" as const : "steer" as const };
    pi.sendUserMessage(text, options);
  };

  const runPrompt = async (ctx: WorkflowContext, prompt: WorkflowPrompt, extra?: string, deliverAs: "normal" | "followUp" = "normal") => {
    const text = appendExtra(prompt.prompt, extra);
    const willQueue = deliverAs === "followUp" && !(ctx.isIdle?.() ?? true);
    ctx.ui.notify(`${willQueue ? "Queueing" : "Running"} ${prompt.code}${willQueue ? " as follow-up" : ""}…`, "info");
    sendWorkflowMessage(ctx, text, deliverAs);
  };

  const showHelp = async (ctx: WorkflowContext) => {
    const registry = await loadPromptRegistry(pi, ctx.cwd);
    let editRequested: string | null = null;
    let queueRequested: string | null = null;

    const result = await ctx.ui.custom<string | null>((tui: any, theme: any, keybindings: any, done: any) => {
      const panel = new HelpPanel(theme, detectSubagents(), registry.prompts, registry.warnings, keybindings);
      panel.onSelect = (code) => done(code);
      panel.onQueue = (code) => { queueRequested = code; done(null); };
      panel.onEdit = (code) => { editRequested = code; done(null); };
      panel.onCancel = () => done(null);
      return {
        render: (w: number) => panel.render(w),
        invalidate: () => panel.invalidate(),
        handleInput: (data: string) => { panel.handleInput(data); tui.requestRender(); },
      };
    });

    if (result) {
      const prompt = promptForInput(registry, result);
      if (prompt) await runPrompt(ctx, prompt);
    } else if (queueRequested) {
      const prompt = promptForInput(registry, queueRequested);
      if (prompt) await runPrompt(ctx, prompt, undefined, "followUp");
    } else if (editRequested) {
      const prompt = promptForInput(registry, editRequested);
      if (!prompt) return;
      const edited = await ctx.ui.custom<{ text: string; deliverAs: "normal" | "followUp" } | null>((tui: any, theme: any, keybindings: any, done: any) => {
        const editor = new PromptEditor(prompt.prompt, theme, prompt.code, keybindings);
        editor.onDone = (text) => done({ text, deliverAs: "normal" });
        editor.onQueue = (text) => done({ text, deliverAs: "followUp" });
        editor.onCancel = () => done(null);
        editor.onCopyRequested = (text) => {
          copyToClipboard(text)
            .then(() => ctx.ui.notify("Copied prompt to clipboard", "info"))
            .catch((error) => ctx.ui.notify(`Copy failed: ${error instanceof Error ? error.message : String(error)}`, "warning"));
        };
        return {
          render: (w: number) => editor.render(w),
          invalidate: () => editor.invalidate(),
          handleInput: (data: string) => { editor.handleInput(data); tui.requestRender(); },
        };
      });
      if (edited) sendWorkflowMessage(ctx, edited.text, edited.deliverAs);
    }
  };

  for (const corePrompt of CORE_PROMPTS) {
    if (!corePrompt.command) continue;
    pi.registerCommand(corePrompt.command, {
      description: `${corePrompt.label} — ${corePrompt.short}`,
      handler: async (args, ctx) => {
        if (!(await waitForIdleWithTimeout(ctx))) return;
        const registry = await loadPromptRegistry(pi, ctx.cwd);
        const prompt = promptForInput(registry, corePrompt.code);
        if (!prompt) {
          ctx.ui.notify(`${corePrompt.code} is disabled by prompt config.`, "warning");
          return;
        }
        await runPrompt(ctx, prompt, args);
      },
    });
  }

  pi.registerCommand("workflow:run", {
    description: "Run a workflow prompt by code, e.g. /workflow:run workflow.plan",
    handler: async (args, ctx) => {
      if (!(await waitForIdleWithTimeout(ctx))) return;
      const [code, ...rest] = args.trim().split(/\s+/).filter(Boolean);
      if (!code) {
        ctx.ui.notify("Usage: /workflow:run <code> [extra context]", "warning");
        return;
      }
      const registry = await loadPromptRegistry(pi, ctx.cwd);
      const prompt = promptForInput(registry, code);
      if (!prompt) {
        ctx.ui.notify(`No workflow prompt found for ${code}. Use /workflow:prompts list.`, "warning");
        return;
      }
      await runPrompt(ctx, prompt, rest.join(" "));
    },
  });

  pi.registerCommand("workflow:help", {
    description: "Open an interactive workflow prompt browser",
    handler: async (_args, ctx) => { await showHelp(ctx); },
  });

  pi.registerShortcut("ctrl+shift+/", {
    description: "Open dev workflow help",
    handler: async (ctx) => { await showHelp(ctx); },
  });

  pi.registerCommand("workflow:prompts", {
    description: "Manage workflow prompt config: list, paths, validate, init, reload",
    handler: async (args, ctx) => {
      const action = args.trim().split(/\s+/)[0] || "list";
      const registry = await loadPromptRegistry(pi, ctx.cwd);
      if (action === "paths") {
        ctx.ui.notify([
          "Dev Workflow prompt config paths:",
          registry.paths.project ? `project: ${registry.paths.project}` : "project: (no git root detected)",
          `user:    ${registry.paths.user}`,
          `legacy:  ${registry.paths.legacy}`,
        ].join("\n"), "info");
      } else if (action === "validate") {
        ctx.ui.notify(registry.warnings.length > 0 ? `Prompt config warnings:\n- ${registry.warnings.join("\n- ")}` : "Prompt config is valid.", registry.warnings.length > 0 ? "warning" : "info");
      } else if (action === "init") {
        if (await fileExists(registry.paths.user)) {
          ctx.ui.notify(`User prompt config already exists: ${registry.paths.user}`, "warning");
          return;
        }
        await mkdir(dirname(registry.paths.user), { recursive: true });
        await writeFile(registry.paths.user, configTemplate(), "utf8");
        ctx.ui.notify(`Created user prompt config: ${registry.paths.user}`, "info");
      } else if (action === "reload") {
        ctx.ui.notify(`Reloaded workflow prompts (${registry.prompts.length} available).`, "info");
      } else {
        const lines = registry.prompts.map((prompt) => `[${prompt.sourceLabel}] ${prompt.code}${prompt.command ? ` /${prompt.command}` : ""} — ${prompt.short}`);
        ctx.ui.notify(lines.join("\n"), "info");
      }
    },
  });

  pi.registerCommand("workflow:flow", {
    description: "Show the full Dev Workflow overview",
    handler: async (_args, ctx) => {
      ctx.ui.notify([
        "Dev Workflow",
        "",
        "Core workflow:",
        "1. /workflow:plan       — Fresh-eyes review of the plan",
        "2. /workflow:self       — Implementor fresh-eyes self-review",
        "3. /workflow:standards  — Coding standards pass",
        "4. /workflow:ci         — Check CI and analyze failures",
        "5. /workflow:docs       — Documentation pass",
        "6. /workflow:ship       — Ship: CI, atomic commit, PR description, PR",
        "",
        "PR/release operations:",
        "/workflow:pr-review-comments — Address PR review feedback and re-request review",
        "/workflow:release-prs        — Prepare backend/frontend/optimo/design-system release PRs",
        "",
        "Bootstrap:",
        "/workflow:context     — Load context from existing PRs",
        "/workflow:handoff     — Generate handoff",
        "/workflow:onboard     — Generate workflow onboarding",
        "",
        detectSubagents()
          ? "Subagents: /workflow:scout, /workflow:oracle, /workflow:reviewer, /workflow:parallel"
          : "Subagent prompts fall back inline unless pi-subagents is installed.",
        "",
        "Custom prompts:",
        "/workflow:prompts init|paths|validate|list|reload",
        "/workflow:run <code> [extra context]",
      ].join("\n"), "info");
    },
  });
}
