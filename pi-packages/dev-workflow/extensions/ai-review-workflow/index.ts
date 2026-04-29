import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { HelpPanel, PromptEditor } from "./help-panel";

// ── Verbatim Prompts (from the AI Review Workflow) ──────────
// Append your own project-specific context by passing args.
// E.g., /review:plan focus on the auth middleware

const PROMPTS = {
  /** Step 1: Fresh-eyes review of the plan before implementation */
  plan: `Great, now I want you to carefully read over the plan you just wrote and the existing code you already reviewed with "fresh eyes."

Look super carefully for any obvious bugs, errors, problems, issues, or confusion.

Carefully update the plan based on anything you uncover.`,

  /** Step 3: Implementor fresh-eyes self-review */
  self: `Great, now I want you to carefully read over all of the new code you just wrote and the existing code you just modified with "fresh eyes."

Look super carefully for any obvious bugs, errors, problems, issues, or confusion.

Carefully fix anything you uncover.`,

  /** Step 4: Coding standards and pre-commit cleanup */
  standards: `Please help me fix the files in \`git status\` so they match our coding standards and pre-commit requirements.

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

  /** Step 7: Documentation pass */
  docs: `Let's please make sure all the updated code, especially the newly added code, is very well documented in simple language.

Please keep the documentation visual and first-principles-driven. Explain why those changes or additions are being made.

Use commands, docs, strings, and anything else helpful so that future readers of the code can understand why we added something like this and how to make use of it.`,

  /** Step 8: Smart ship — verifies CI, discovers PR context, and ships */
  ship: `Let's finalize and ship this work.

**First, check CI.** Prefer the ci-status extension commands if they are available:
- Run /ci for the quick overview
- Use /ci-detail for the interactive job list and details
- Use /ci-logs <job> for specific failing job logs

If those commands are not available, use get_ci_status and ci_fetch_job_logs if those tools are available. If neither the slash commands nor the tools are available, ask the user to install the ci-status package before proceeding. If anything is failing:
- Determine if failures are from our changes or pre-existing flakes
- Fix any failures caused by our code before proceeding
- If everything is green, confirm and move on

**Next, discover PR context.** Check what branch we're on and look for any existing GitHub PRs or issues related to this work. Use \`gh pr list\`, \`gh issue list\`, or whatever is needed.

- If an **existing PR** is already open for this branch, update it with the current changes.
- If **no PR exists** yet, create one.
- If there's a related **GitHub issue**, link the PR to it.

**If you are unsure about anything**, ask me before proceeding — I'll clarify. Present your questions clearly so I can answer quickly.

**Then, ship it.** Use the atomic commit skill and make sure everything passes (lint, type-checks, tests, pre-commit). Do not compromise by excluding things that are part of this PR — anything touched needs to be improved as much as possible.

Once the code is ready, use the PR description writer skill to generate a reviewer-friendly description, and open the PR on GitHub.`,

  // ── Subagent-aware prompts (pi-subagents enhanced workflow) ──

  /** Launch a reviewer subagent with forked context */
  reviewer: `Use the reviewer subagent to review the current changes with fresh eyes. Fork context from this session so the reviewer sees the full picture.

Ask the reviewer to check for:
- **Correctness**: does the code do what it's supposed to?
- **Edge cases**: what could go wrong? Nulls, empties, race conditions, error paths?
- **Tests**: are the right things tested? Missing coverage?
- **Simplicity**: is anything unnecessarily complex or over-engineered?

Bring the results back and summarize the actionable fixes. If the subagent tool is not available, review the code yourself with fresh eyes instead.`,

  /** Oracle: second opinion, challenge assumptions, no editing */
  oracle: `Use the oracle subagent for a second opinion. Challenge all assumptions in the current plan or implementation. Ask:

- What am I missing?
- What risks am I not seeing?
- What's the safest next move?
- Is there a simpler or more robust approach?

The oracle must not edit any code — just surface concerns and recommend the direction. If the subagent tool is not available, do a similar fresh-eyes analysis yourself without editing.`,

  /** Run parallel reviewers with distinct focus areas */
  parallel: `Run parallel reviewer subagents on the current diff. I want three reviewers, each with a distinct focus:

1. **Correctness & edge cases** — does the code work? What breaks?
2. **Test coverage & quality** — are we testing the right things? False positives?
3. **Unnecessary complexity & code smells** — what's over-engineered, duplicated, or hard to follow?

Synthesize their feedback into a single prioritized list of actionable fixes. If the subagent tool is not available, do a thorough multi-angle review yourself.`,

  /** Scout: codebase recon before planning or implementing */
  scout: `Use the scout subagent to understand the codebase context for this change. Identify:

- Relevant files and entry points
- Data flow and dependencies
- Existing patterns and conventions
- Risks and gotchas
- Where another agent should start

Bring back a concise scout report. If the subagent tool is not available, do a similar recon yourself with read, grep, and ls.`,

  // ── Session bootstrap & handoff prompts ──

  /** Load context from an existing PR (local or remote) for continuation work */
  context: `Let's load context from existing PRs so I can continue working on this.

**First, discover what's available.** Check the current branch and look for local PRs:
- \`gh pr list --head $(git branch --show-current)\`
- If no local PR, list my recent open PRs: \`gh pr list --author @me --state open\`
- Also check for any open PRs in this repo that might be related

**For the PR I want to work on:**
- If it's already checked out locally, do a deep diff review
- If it's on a remote branch, check it out: \`gh pr checkout <number>\`

**Then, deeply understand it:**
- Read the full diff — every modified file, not just the summary
- Understand what problem it solves and how
- Check CI status with get_ci_status and fetch failure logs with ci_fetch_job_logs if needed
- Review PR comments and unresolved review threads
- Identify what's been done and what might still be needed
- Note any submodule pointer changes or cross-repo impacts
- In this monorepo, check if changes span multiple submodules (frontend, backend, design-system, etc.)

**Ask me questions** if you're unsure which PR to focus on, if you need to check out a remote branch, or if you need clarification about what needs to be done next. Present your questions clearly.

**Finally, give me a brief summary** of what the PR does, what state it's in, and what the likely next steps are. Then be ready for me to give you further instructions.`,

  /** Generate a comprehensive handoff message for a new engineer or fresh subagent session */
  handoff: `Generate a comprehensive handoff message for a new engineer (or a fresh AI subagent session) who will be working on this task now. They will be using this machine itself.

The handoff should set them up for success and explain the whole task in-depth so they can hit the ground running.

Include:

1. **Task overview** — what are we building or fixing, and why?
2. **Current state** — what's been done so far, what's working, what's been validated?
3. **What's left** — remaining work items in priority order, with enough detail to act on
4. **Files and modules** — key files changed and files they'll need to modify, where to focus
5. **Setup commands** — exact commands they should run first to get oriented (build, migrate, install deps)
6. **Test and verify commands** — how to check their work locally (lint, type-check, test, run)
7. **Decisions made** — any non-obvious choices and their rationale so they don't second-guess
8. **Risks and gotchas** — what to watch out for, known edge cases, things that are easy to break
9. **Success criteria** — how to know when the work is truly done

**Format this as a message I can paste directly** into a new pi session or share with another engineer. Use clear section headers, include exact copy-pasteable commands, and keep it scannable.

After generating the handoff, we'll do a back-and-forth until we're completely satisfied with it. Ask me if anything needs clarification or refinement.`,

  /** Generate an onboarding message for engineers about the multi-agent parallel workflow */
  onboard: `Generate a message I can share with engineers (I refer to them as "agents") to get them started with the multi-agent review workflow.

The message should explain:

- **Multiple agents in parallel** — how each engineer can use their own AI agent session to tackle different parts of the work simultaneously. Each agent focuses on a distinct slice (e.g., one on backend, one on frontend, one on infrastructure).
- **Readonly only** — they are only allowed to do readonly operations: reading code, analyzing changes, generating plans, writing reports, suggesting fixes. No commits, no pushes, no PR creation, no file writes.
- **Include commands** — they should include the exact commands to execute for any action. The final apply (committing, pushing, opening PRs) will be done by me and only me.
- **The review workflow** — the step-by-step flow: plan review, self-review, standards pass, documentation, handoff. Commands like /review:plan, /review:self, /review:standards, /review:docs.
- **Subagents for depth** — how to use scout, oracle, reviewer, and parallel reviewers for deeper analysis (/review:scout, /review:oracle, /review:reviewer, /review:parallel).
- **The handoff pattern** — when done with their part, generate a handoff message that the next person (or me) can pick up and continue. We do back-and-forth until everything is complete.
- **Example session** — a concrete example of what a typical session looks like from start to handoff.

Make it clear, motivating, and actionable. Assume they know the codebase but not this specific workflow. Include example commands they can copy-paste to try immediately.`,

  // ── CI integration (ci-status slash commands; optional get_ci_status/ci_fetch_job_logs tools) ──

  /** Check CI status using the ci-status extension */
  ci: `Let's check CI for this branch.

**Check the status.** Run the /ci command first for a quick overview. It shows a per-job breakdown in the widget area. For the full interactive view with job details and log access, use /ci-detail — it has:

- CI providers and workflow/cycles grouped separately in a clean TUI view, with automatic focus on the most important failing/running area
- Tab or arrow keys to switch CI provider; [ and ] switch cycles inside a provider
- Press \`p\` to pick a CI provider, \`w\` to pick a workflow/cycle, \`R\` to refresh in place, \`?\` for help
- Arrow keys to navigate jobs, Enter for job detail view
- Press \`r\` to fetch failure logs, \`f\` to jump to the first error-like log line, \`l\` to open the selected job in the browser, \`c\` to copy the selected job URL
- Press \`g\` to jump to the first failing job, switching CI/cycle if needed

**For a specific failing job**, use /ci-logs <job-name> to pull its logs directly. If the ci-status package is not installed or the slash commands are unavailable, use get_ci_status and ci_fetch_job_logs if those tools are available. If neither path is available, ask the user to install ci-status before proceeding.

**Then analyze:** For every failing job:
- **Ours or flake?** Is this failure caused by our changes, or is it a pre-existing flake?
- **Root cause.** If ours, what's the actual problem?
- **Fix.** Propose the specific code change, test update, or config tweak needed.
- **If flake.** Note it clearly so we don't waste time chasing it.

**Summarize at the end:** overall status, per-job verdict table, fixes needed. If everything is green, confirm we're clear to proceed.`,
};

// Map command names to their prompt text (for the edit-before-inject flow)
const PROMPT_MAP: Record<string, string> = {
  "/review:plan": PROMPTS.plan,
  "/review:self": PROMPTS.self,
  "/review:standards": PROMPTS.standards,
  "/review:docs": PROMPTS.docs,
  "/review:ship": PROMPTS.ship,
  "/review:reviewer": PROMPTS.reviewer,
  "/review:oracle": PROMPTS.oracle,
  "/review:parallel": PROMPTS.parallel,
  "/review:scout": PROMPTS.scout,
  "/review:context": PROMPTS.context,
  "/review:handoff": PROMPTS.handoff,
  "/review:onboard": PROMPTS.onboard,
  "/review:ci": PROMPTS.ci,
};

// ── Command Registry ───────────────────────────────────────

interface CommandDef {
  name: string;
  description: string;
  prompt: string;
  notify: string;
}

type NotifyKind = "info" | "warning" | "error";

interface ReviewUi {
  notify(message: string, kind: NotifyKind): void;
  custom<T>(factory: (tui: any, theme: any, keybindings: any, done: (value: T) => void) => any): Promise<T>;
}

interface ReviewHelpContext {
  ui: ReviewUi;
  isIdle?: () => boolean;
}

const COMMANDS: CommandDef[] = [
  {
    name: "review:plan",
    description: "Step 1 — Fresh-eyes review of the written plan before implementing",
    prompt: PROMPTS.plan,
    notify: "Injecting plan review prompt…",
  },
  {
    name: "review:self",
    description: "Step 3 — Implementor fresh-eyes self-review of new/modified code",
    prompt: PROMPTS.self,
    notify: "Injecting self-review prompt…",
  },
  {
    name: "review:standards",
    description: "Step 4 — Coding standards and pre-commit cleanup pass",
    prompt: PROMPTS.standards,
    notify: "Injecting standards pass prompt…",
  },
  {
    name: "review:docs",
    description: "Step 7 — Documentation pass (explain changes for future readers)",
    prompt: PROMPTS.docs,
    notify: "Injecting documentation prompt…",
  },
  {
    name: "review:ship",
    description:
      "Step 8 — Ship it: verify CI green, discover context (existing PRs, issues), atomic commit, PR description, open PR",
    prompt: PROMPTS.ship,
    notify: "Injecting ship-it prompt…",
  },
  // ── Subagent-aware commands ──
  {
    name: "review:reviewer",
    description: "Launch a reviewer subagent (forked context) — correctness, edge cases, tests, simplicity",
    prompt: PROMPTS.reviewer,
    notify: "Injecting reviewer subagent prompt…",
  },
  {
    name: "review:oracle",
    description: "Get a second opinion — challenge assumptions, surface risks, recommend direction",
    prompt: PROMPTS.oracle,
    notify: "Injecting oracle subagent prompt…",
  },
  {
    name: "review:parallel",
    description: "Run parallel reviewers (correctness, tests, complexity) and synthesize feedback",
    prompt: PROMPTS.parallel,
    notify: "Injecting parallel reviewer prompt…",
  },
  {
    name: "review:scout",
    description: "Scout the codebase — relevant files, data flow, risks, where to start",
    prompt: PROMPTS.scout,
    notify: "Injecting scout subagent prompt…",
  },
  // ── Session bootstrap & handoff commands ──
  {
    name: "review:context",
    description: "Load context from existing PRs — discover, checkout, deep-read, summarize, ready to continue",
    prompt: PROMPTS.context,
    notify: "Injecting PR context-loading prompt…",
  },
  {
    name: "review:handoff",
    description: "Generate a handoff message for a new engineer or fresh subagent session",
    prompt: PROMPTS.handoff,
    notify: "Injecting handoff generation prompt…",
  },
  {
    name: "review:onboard",
    description: "Generate an onboarding message for engineers about the multi-agent parallel workflow",
    prompt: PROMPTS.onboard,
    notify: "Injecting engineer onboarding prompt…",
  },
  // ── CI command ──
  {
    name: "review:ci",
    description: "Check CI status — fetch results, analyze failures, distinguish ours vs flakes, propose fixes",
    prompt: PROMPTS.ci,
    notify: "Injecting CI check prompt…",
  },
];

// ── Extension Entry Point ──────────────────────────────────

export default function (pi: ExtensionAPI) {
  // Detect pi-subagents lazily because extension load order can change what tools exist.
  const detectSubagents = (): boolean => {
    try {
      return pi.getAllTools?.().some((t: { name: string }) => t.name === "subagent") ?? false;
    } catch {
      // getAllTools may not exist on older pi versions — safe to ignore.
      return false;
    }
  };

  // Helper: copy text to system clipboard via shell pipe
  const copyToClipboard = async (text: string) => {
    const delimiter = "CPEND_" + Math.random().toString(36).slice(2, 10);
    const heredoc = `cat <<'${delimiter}'`;
    const copyCmd = process.platform === "darwin"
      ? `${heredoc} | pbcopy\n${text}\n${delimiter}`
      : `if command -v xclip >/dev/null 2>&1; then\n${heredoc} | xclip -selection clipboard\n${text}\n${delimiter}\nelif command -v wl-copy >/dev/null 2>&1; then\n${heredoc} | wl-copy\n${text}\n${delimiter}\nfi`;
    try {
      await pi.exec("bash", ["-c", copyCmd], { timeout: 3000 });
    } catch {
      // Silently fail — text is still in the editor
    }
  };

  const waitForIdleWithTimeout = async (
    ctx: { waitForIdle: () => Promise<void>; ui: Pick<ReviewUi, "notify"> },
    timeoutMs = 30_000,
  ): Promise<boolean> => {
    let timeout: ReturnType<typeof setTimeout> | undefined;

    try {
      const timedOut = await Promise.race([
        ctx.waitForIdle().then(() => false),
        new Promise<boolean>((resolve) => {
          timeout = setTimeout(() => resolve(true), timeoutMs);
        }),
      ]);

      if (timedOut) {
        ctx.ui.notify("Review workflow is still waiting for the current agent turn to finish. Try again once pi is idle.", "warning");
        return false;
      }

      return true;
    } finally {
      if (timeout) clearTimeout(timeout);
    }
  };

  // Shared help-panel launcher (reused by command + shortcut)
  const showHelp = async (ctx: ReviewHelpContext) => {
    let editRequested: string | null = null;
    let queueRequested: string | null = null;

    const sendWorkflowMessage = (text: string, deliverAs: "normal" | "followUp" = "normal") => {
      const idle = ctx.isIdle?.() ?? true;
      const options = idle ? undefined : { deliverAs: deliverAs === "followUp" ? "followUp" as const : "steer" as const };
      pi.sendUserMessage(text, options);
    };

    const result = await ctx.ui.custom<string | null>((tui: any, theme: any, keybindings: any, done: any) => {
      const panel = new HelpPanel(theme, detectSubagents(), keybindings);
      panel.onSelect = (commandName) => done(commandName);
      panel.onQueue = (commandName) => {
        queueRequested = commandName;
        done(null);
      };
      panel.onEdit = (commandName) => {
        editRequested = commandName;
        done(null); // close help panel — editor opens next
      };
      panel.onCancel = () => done(null);
      return {
        render: (w: number) => panel.render(w),
        invalidate: () => panel.invalidate(),
        handleInput: (data: string) => {
          panel.handleInput(data);
          tui.requestRender();
        },
      };
    });

    if (result) {
      // Direct inject. If the agent is currently streaming, this matches normal Enter behavior and steers.
      ctx.ui.notify(`Injecting ${result}…`, "info");
      sendWorkflowMessage(result);
    } else if (queueRequested) {
      const willQueue = !(ctx.isIdle?.() ?? true);
      ctx.ui.notify(`${willQueue ? "Queueing" : "Injecting"} ${queueRequested}${willQueue ? " as follow-up" : ""}…`, "info");
      sendWorkflowMessage(queueRequested, "followUp");
    } else if (editRequested) {
      // Edit-before-inject flow
      const promptText = PROMPT_MAP[editRequested] ?? editRequested;
      const edited = await ctx.ui.custom<{ text: string; deliverAs: "normal" | "followUp" } | null>((tui: any, theme: any, keybindings: any, done: any) => {
        const editor = new PromptEditor(promptText, theme, editRequested!, keybindings);
        editor.onDone = (text) => done({ text, deliverAs: "normal" });
        editor.onQueue = (text) => done({ text, deliverAs: "followUp" });
        editor.onCancel = () => done(null);
        editor.onCopyRequested = (text) => {
          copyToClipboard(text);
        };
        return {
          render: (w: number) => editor.render(w),
          invalidate: () => editor.invalidate(),
          handleInput: (data: string) => {
            editor.handleInput(data);
            tui.requestRender();
          },
        };
      });
      if (edited) {
        const willQueue = edited.deliverAs === "followUp" && !(ctx.isIdle?.() ?? true);
        ctx.ui.notify(`${willQueue ? "Queueing" : "Injecting"} edited ${editRequested}${willQueue ? " as follow-up" : ""}…`, "info");
        sendWorkflowMessage(edited.text, edited.deliverAs);
      }
    }
  };

  // Register each prompt-injection command
  for (const cmd of COMMANDS) {
    pi.registerCommand(cmd.name, {
      description: cmd.description,
      handler: async (args, ctx) => {
        // Wait for any in-flight agent work to settle, but avoid hanging forever.
        if (!(await waitForIdleWithTimeout(ctx))) return;

        // Let the user append extra context: /review:plan focus on auth
        const extra = args?.trim();
        const fullPrompt = extra ? `${cmd.prompt}\n\nAdditional context: ${extra}` : cmd.prompt;

        ctx.ui.notify(cmd.notify, "info");
        pi.sendUserMessage(fullPrompt);
      },
    });
  }

  // Interactive help panel (TUI) — command
  pi.registerCommand("review:help", {
    description: "Open an interactive help panel — browse, learn, and inject any review command",
    handler: async (_args, ctx) => {
      await showHelp(ctx);
    },
  });

  // Keyboard shortcut for help panel
  pi.registerShortcut("ctrl+shift+/", {
    description: "Open dev workflow help",
    handler: async (ctx) => {
      await showHelp(ctx);
    },
  });

  // Flow overview command
  pi.registerCommand("review:flow", {
    description: "Show the full Dev Workflow overview (with subagent-enhanced paths)",
    handler: async (_args, ctx) => {
      ctx.ui.notify(
        [
          "Dev Workflow",
          "",
          "  Core workflow (always available):",
          "  1. /review:plan       — Fresh-eyes review of the plan",
          "  2.  [manual]          — Save implementation details, park reviewer session",
          "  3. /review:self       — Implementor fresh-eyes self-review",
          "  4. /review:standards  — Coding standards pass (lint, types, patterns)",
          "  5. /review:ci         — Check CI: fetch status, analyze failures, fix or note flakes",
          "  6.  [manual]          — Verify locally, then run waiting reviewer, loop if needed",
          "  7. /review:docs       — Documentation pass",
          "  8. /review:ship       — Ship: verify CI green, discover PR context, atomic commit, open PR",
          "",
          "  Session bootstrap & handoff:",
          "  /review:context      — Load context from existing PRs (local or remote)",
          "  /review:handoff      — Generate handoff message for new engineer/subagent",
          "  /review:onboard      — Generate onboarding message for engineers",
          "",
          detectSubagents()
            ? [
                "  Subagent-enhanced (pi-subagents detected):",
                "  /review:scout        — Scout codebase before planning (→ scout agent)",
                "  /review:oracle       — Second opinion, challenge assumptions (→ oracle agent)",
                "  /review:reviewer     — Independent review, forked context (→ reviewer agent)",
                "  /review:parallel     — 3 parallel reviewers (correctness, tests, complexity)",
                "",
                "  Quick chains:",
                "  /run-chain review-pipeline -- <task>    Full scout→plan→review pipeline",
              ].join("\n")
            : [
                "  Subagent-enhanced (install pi-subagents to unlock):",
                "  /review:scout        — Codebase recon (inline if no subagent tool)",
                "  /review:oracle       — Second opinion (inline if no subagent tool)",
                "  /review:reviewer     — Independent review (inline if no subagent tool)",
                "  /review:parallel     — Multi-angle review (inline if no subagent tool)",
              ].join("\n"),
          "",
          "Append extra context: /review:plan focus on auth middleware",
          "Interactive help: /review:help",
          "Full workflow docs: /skill:ai-review-workflow",
        ].join("\n"),
        "info",
      );
    },
  });
}
