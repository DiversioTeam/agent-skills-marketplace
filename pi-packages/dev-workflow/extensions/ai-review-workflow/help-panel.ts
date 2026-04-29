import type { Theme } from "@mariozechner/pi-coding-agent";
import { DynamicBorder } from "@mariozechner/pi-coding-agent";
import { matchesKey, Key, truncateToWidth, wrapTextWithAnsi, Text, Spacer } from "@mariozechner/pi-tui";

// ── Detailed command data ─────────────────────────────────

interface HelpCommand {
  name: string;
  short: string;
  whatItDoes: string[];
  whenToUse: string;
  example: string;
  category: "core" | "bootstrap" | "subagent";
}

const ALL_COMMANDS: HelpCommand[] = [
  // ── Core ──
  {
    name: "/review:plan",
    short: "Fresh-eyes review of the plan before implementing",
    whatItDoes: [
      "Reads the written plan and surrounding existing code",
      "Looks carefully for bugs, errors, ambiguity, or confusion",
      "Updates the plan based on anything uncovered",
    ],
    whenToUse: "Before writing any code. When you have just written a plan and want to challenge it before implementation gains momentum. This catches expensive mistakes early.",
    example: "/review:plan focus on the auth middleware",
    category: "core",
  },
  {
    name: "/review:self",
    short: "Implementor rereads all new & modified code with fresh eyes",
    whatItDoes: [
      "Rereads every new and modified file with fresh eyes",
      "Looks for obvious bugs, errors, problems, or confusion",
      "Fixes anything found before the independent reviewer sees it",
    ],
    whenToUse: "After implementation but before independent review. The implementor should catch its own obvious mistakes first — don't waste reviewer attention on things you should have found yourself.",
    example: "/review:self pay extra attention to error handling",
    category: "core",
  },
  {
    name: "/review:standards",
    short: "Coding standards pass: lint, types, imports, ORM, Ruff",
    whatItDoes: [
      "Checks all modified files against 12 coding standards rules",
      "No local imports, no unnecessary getattr(), no large try/except",
      "Structured logging in optimo_ apps, TypedDict over loose dict",
      "Ruff happiness, no string type hints, no typing.cast()",
      "No repeated test fixtures, use Django ORM reverse relations",
      "Pedantic type hints — avoid Any, use ast-grep where helpful",
    ],
    whenToUse: "After self-review, before documentation. This is the policy and hygiene pass. It narrows the implementation to team conventions before anyone treats the work as ready.",
    example: "/review:standards also check for missing DB indexes",
    category: "core",
  },
  {
    name: "/review:ci",
    short: "Check CI — interactive TUI view, logs, ours-vs-flake analysis",
    whatItDoes: [
      "Runs the /ci and /ci-detail commands from the ci-status extension",
      "Interactive TUI view groups jobs by CI provider and workflow/cycle",
      "Automatically focuses the most important failing/running CI and cycle",
      "Native pickers for CI providers and workflow/cycles, plus in-place refresh",
      "Per-cycle job list sorted by importance, with metadata and log access (press r for logs)",
      "Quick actions: l to open in browser, c to copy URL, g to jump to first failure",
      "Uses /ci-logs <job-name> to pull failure logs directly",
      "Analyzes each failure: ours or flake? root cause? proposed fix?",
      "Covers GitHub Actions + CircleCI (CIRCLECI_TOKEN for CircleCI enrichment)",
    ],
    whenToUse: "Step 5 of the review workflow — before local verification and before shipping. Catches CI failures early. Also use /ci-detail anytime you want to explore CI results interactively without leaving the terminal.",
    example: "/review:ci check only the backend tests",
    category: "core",
  },
  {
    name: "/review:docs",
    short: "Documentation pass — explain the why for future readers",
    whatItDoes: [
      "Documents all updated code, especially new additions",
      "Uses simple, visual, first-principles-driven language",
      "Explains why changes were made, not just what changed",
      "Uses docstrings, comments, and any helpful documentation",
    ],
    whenToUse: "At the very end, after all code changes are final. Documentation should reflect the final shape of the change, not an earlier draft that drifted.",
    example: "/review:docs focus on the new API endpoints",
    category: "core",
  },
  {
    name: "/review:ship",
    short: "Smart ship: discover PR context, atomic commit, open PR",
    whatItDoes: [
      "Verifies CI is green first (ci-status extension, with builtin-tool fallback)",
      "Discovers context — checks branch, existing PRs, issues via gh CLI",
      "Updates existing PR if one is open, or creates a new one",
      "Asks you questions if unsure about anything",
      "Runs atomic commit (lint, types, tests, pre-commit must pass)",
      "Generates PR description and opens the PR on GitHub",
    ],
    whenToUse: "When you're done with all reviews and ready to ship. This is the final step — it handles both new PRs and updating existing ones. It asks before acting if context is unclear.",
    example: "/review:ship target is the staging branch",
    category: "core",
  },

  // ── Bootstrap ──
  {
    name: "/review:context",
    short: "Load context from existing PRs (local or remote), deep-read diff",
    whatItDoes: [
      "Discovers PRs on current branch via gh pr list",
      "Lists your open PRs if none found locally",
      "Checks out remote PRs with gh pr checkout",
      "Deep-reads the full diff across all modified files",
      "Checks CI status and unresolved review threads",
      "Notes submodule pointer changes (important in monorepo)",
      "Asks clarifying questions, then presents summary ready to continue",
    ],
    whenToUse: "When starting a new pi session and you need to continue work on an existing PR. Instead of manually re-explaining everything, this loads the full context automatically.",
    example: "/review:context check PR #1234",
    category: "bootstrap",
  },
  {
    name: "/review:handoff",
    short: "Generate handoff message for new engineer or fresh subagent",
    whatItDoes: [
      "Generates a comprehensive handoff: task overview, current state, remaining work",
      "Includes key files, setup commands, test/verify commands",
      "Documents decisions made, risks, and success criteria",
      "Formats as a pasteable message for a new pi session or engineer",
      "Supports back-and-forth refinement until satisfied",
    ],
    whenToUse: "When you need to hand work to another engineer or spawn a fresh subagent session. The handoff sets them up for success with everything they need to continue.",
    example: "/review:handoff include the database migration steps",
    category: "bootstrap",
  },
  {
    name: "/review:onboard",
    short: "Generate onboarding message for engineers about the workflow",
    whatItDoes: [
      "Explains the multi-agent parallel review workflow",
      "Covers readonly-only rule: no commits, pushes, or PRs from agents",
      "Documents the handoff pattern for back-and-forth collaboration",
      "Includes example session showing start-to-finish usage",
      "Ready to share in Slack, email, or docs",
    ],
    whenToUse: "When onboarding new engineers to the developer workflow. Generates a clear, motivating message they can reference.",
    example: "/review:onboard focus on the backend team workflow",
    category: "bootstrap",
  },

  // ── Subagent ──
  {
    name: "/review:scout",
    short: "Codebase recon → scout agent (files, data flow, risks)",
    whatItDoes: [
      "Launches a scout subagent for fast codebase recon",
      "Identifies relevant files, entry points, and data flow",
      "Maps dependencies and existing patterns",
      "Surfaces risks and gotchas",
      "Recommends where another agent should start",
      "Falls back to inline recon if pi-subagents is not installed",
    ],
    whenToUse: "Before planning or implementing a change in unfamiliar territory. The scout gives you a map of the codebase so you don't waste time navigating blind.",
    example: "/review:scout focus on the payment processing pipeline",
    category: "subagent",
  },
  {
    name: "/review:oracle",
    short: "Second opinion → oracle agent (challenge, no editing)",
    whatItDoes: [
      "Launches an oracle subagent for a second opinion",
      "Challenges all assumptions in the plan or implementation",
      "Surfaces what you're missing, risks you're not seeing",
      "Recommends the safest next move",
      "Does NOT edit any code — only advises",
      "Falls back to inline analysis if pi-subagents is not installed",
    ],
    whenToUse: "When the decision feels risky or you want a second set of eyes on the direction. The oracle challenges your thinking before you commit to a path.",
    example: "/review:oracle is this refactor approach safe?",
    category: "subagent",
  },
  {
    name: "/review:reviewer",
    short: "Independent review → reviewer agent (forked context)",
    whatItDoes: [
      "Launches a reviewer subagent with forked session context",
      "Checks correctness, edge cases, tests, and simplicity",
      "Reviews with truly fresh eyes (separate session)",
      "Brings results back and summarizes actionable fixes",
      "Falls back to inline review if pi-subagents is not installed",
    ],
    whenToUse: "When you want a truly independent review. Unlike /review:self (same session), this spawns a separate AI session that sees the code with completely fresh context.",
    example: "/review:reviewer focus on the new API error handling",
    category: "subagent",
  },
  {
    name: "/review:parallel",
    short: "3 parallel reviewers (correctness, tests, complexity)",
    whatItDoes: [
      "Runs three reviewer subagents in parallel",
      "Reviewer 1: correctness and edge cases",
      "Reviewer 2: test coverage and quality",
      "Reviewer 3: unnecessary complexity and code smells",
      "Synthesizes all feedback into a prioritized fix list",
      "Falls back to multi-angle inline review if no subagents",
    ],
    whenToUse: "When you want maximum review coverage. Instead of one reviewer checking everything, three specialists each focus on their area for deeper analysis.",
    example: "/review:parallel only review the backend changes",
    category: "subagent",
  },
];

// ── Tabs definition ───────────────────────────────────────

interface Tab {
  label: string;
  category: "core" | "bootstrap" | "subagent" | "all";
}

const TABS: Tab[] = [
  { label: "CORE", category: "core" },
  { label: "BOOTSTRAP", category: "bootstrap" },
  { label: "SUBAGENT", category: "subagent" },
  { label: "ALL", category: "all" },
];

// ── Color mapping ─────────────────────────────────────────

function catColor(cat: string): string {
  switch (cat) {
    case "bootstrap": return "warning";  // amber
    case "subagent":  return "success";  // green
    default:          return "accent";   // teal
  }
}

// ── Help Panel Component ──────────────────────────────────

type Mode = "list" | "detail";

interface PromptEditorKeybindings {
  matches(data: string, keybinding: string): boolean;
  getKeys?(keybinding: string): string[];
}

export class HelpPanel {
  private mode: Mode = "list";
  private activeTab = 3; // default to ALL
  private selectedIdx = 0;  // index into visible commands in list mode
  private detailIdx = 0;    // index into ALL_COMMANDS in detail mode

  private cachedWidth?: number;
  private cachedLines?: string[];

  public onSelect?: (commandName: string) => void;
  public onQueue?: (commandName: string) => void;
  public onEdit?: (commandName: string) => void;
  public onCancel?: () => void;

  constructor(
    private theme: Theme,
    private hasSubagents: boolean,
    private keybindings?: PromptEditorKeybindings,
  ) {
    this.clampSelection();
  }

  // ── Helpers ──────────────────────────────────────────

  private visibleCommands(): HelpCommand[] {
    const cat = TABS[this.activeTab].category;
    if (cat === "all") return ALL_COMMANDS;
    return ALL_COMMANDS.filter((c) => c.category === cat);
  }

  private clampSelection(): void {
    const cmds = this.visibleCommands();
    if (this.selectedIdx >= cmds.length) this.selectedIdx = cmds.length - 1;
    if (this.selectedIdx < 0) this.selectedIdx = 0;
  }

  private activeCategory(): string {
    return TABS[this.activeTab].category;
  }

  private matchesBinding(data: string, keybinding: string): boolean {
    try {
      return this.keybindings?.matches(data, keybinding) ?? false;
    } catch {
      return false;
    }
  }

  private keyLabel(keybinding: string, fallback: string): string {
    try {
      const keys = this.keybindings?.getKeys?.(keybinding);
      if (keys && keys.length > 0) return keys[0].split("+").map((part) => part.length === 1 ? part.toUpperCase() : part[0].toUpperCase() + part.slice(1)).join("+");
    } catch {
      // Use fallback below.
    }
    return fallback;
  }

  // ── Input handling ───────────────────────────────────

  handleInput(data: string): void {
    if (this.mode === "list") {
      this.handleListInput(data);
    } else {
      this.handleDetailInput(data);
    }
  }

  private handleListInput(data: string): void {
    const cmds = this.visibleCommands();

    if (matchesKey(data, Key.up)) {
      if (this.selectedIdx > 0) { this.selectedIdx--; this.invalidate(); }
    } else if (matchesKey(data, Key.down)) {
      if (this.selectedIdx < cmds.length - 1) { this.selectedIdx++; this.invalidate(); }
    } else if (matchesKey(data, Key.left)) {
      this.activeTab = (this.activeTab - 1 + TABS.length) % TABS.length;
      this.selectedIdx = 0;
      this.clampSelection();
      this.invalidate();
    } else if (matchesKey(data, Key.right)) {
      this.activeTab = (this.activeTab + 1) % TABS.length;
      this.selectedIdx = 0;
      this.clampSelection();
      this.invalidate();
    } else if (matchesKey(data, Key.tab)) {
      this.activeTab = (this.activeTab + 1) % TABS.length;
      this.selectedIdx = 0;
      this.clampSelection();
      this.invalidate();
    } else if (this.matchesBinding(data, "app.message.followUp")) {
      const cmd = cmds[this.selectedIdx];
      if (cmd) this.onQueue?.(cmd.name);
    } else if (matchesKey(data, Key.enter)) {
      const cmd = cmds[this.selectedIdx];
      if (cmd) this.onSelect?.(cmd.name);
    } else if (data === "d" || data === "D") {
      const cmd = cmds[this.selectedIdx];
      if (cmd) {
        this.detailIdx = ALL_COMMANDS.indexOf(cmd);
        this.mode = "detail";
        this.invalidate();
      }
    } else if (data === "e" || data === "E") {
      const cmd = cmds[this.selectedIdx];
      if (cmd) this.onEdit?.(cmd.name);
    } else if (matchesKey(data, Key.escape)) {
      this.onCancel?.();
    }
  }

  private handleDetailInput(data: string): void {
    if (matchesKey(data, Key.left)) {
      if (this.detailIdx > 0) { this.detailIdx--; this.invalidate(); }
    } else if (matchesKey(data, Key.right)) {
      if (this.detailIdx < ALL_COMMANDS.length - 1) { this.detailIdx++; this.invalidate(); }
    } else if (this.matchesBinding(data, "app.message.followUp")) {
      const cmd = ALL_COMMANDS[this.detailIdx];
      if (cmd) this.onQueue?.(cmd.name);
    } else if (matchesKey(data, Key.enter)) {
      // Inject and close
      const cmd = ALL_COMMANDS[this.detailIdx];
      if (cmd) this.onSelect?.(cmd.name);
    } else if (data === "e" || data === "E") {
      const cmd = ALL_COMMANDS[this.detailIdx];
      if (cmd) this.onEdit?.(cmd.name);
    } else if (matchesKey(data, Key.escape)) {
      // Back to list
      this.mode = "list";
      // Try to restore position
      const cat = this.activeCategory();
      const vis = this.visibleCommands();
      const current = ALL_COMMANDS[this.detailIdx];
      if (current && (cat === "all" || current.category === cat)) {
        this.selectedIdx = vis.indexOf(current);
        if (this.selectedIdx < 0) this.selectedIdx = 0;
      }
      this.invalidate();
    }
  }

  // ── Rendering ────────────────────────────────────────

  render(width: number): string[] {
    if (this.cachedLines && this.cachedWidth === width) {
      return this.cachedLines;
    }
    this.cachedWidth = width;

    const lines = this.mode === "list"
      ? this.renderList(width)
      : this.renderDetail(width);

    this.cachedLines = lines;
    return lines;
  }

  invalidate(): void {
    this.cachedWidth = undefined;
    this.cachedLines = undefined;
  }

  // ── List view ────────────────────────────────────────

  private renderList(width: number): string[] {
    const t = this.theme;
    const pad = 2;
    const innerW = Math.max(width - pad * 2, 20);
    const lines: string[] = [];

    // Top border
    lines.push(...new DynamicBorder((s: string) => t.fg("accent", s)).render(width));

    // Title
    lines.push(...new Text(t.fg("accent", t.bold("Dev Workflow — Command Reference")), pad, 0).render(width));
    lines.push(...new Spacer(1).render(width));

    // Tabs row
    lines.push(...this.renderTabs(width, pad));

    // Subagent note when viewing subagent commands but subagents not installed
    if (TABS[this.activeTab].category === "subagent" && !this.hasSubagents) {
      lines.push(...new Spacer(0).render(width));
      const note = t.fg("dim", "(pi-subagents not detected — these commands fall back to inline execution)");
      lines.push(...new Text(note, pad, 0).render(width));
      lines.push(...new Spacer(1).render(width));
    }

    // Divider after tabs
    lines.push(this.renderTabDivider(width, pad));
    lines.push(...new Spacer(1).render(width));

    // Command list
    const cmds = this.visibleCommands();
    for (let i = 0; i < cmds.length; i++) {
      const cmd = cmds[i];
      const isSelected = i === this.selectedIdx;
      lines.push(this.renderCommandRow(width, pad, cmd, isSelected));
    }

    lines.push(...new Spacer(1).render(width));

    // Footer
    const queueKey = this.keyLabel("app.message.followUp", "Alt+Enter");
    const footer = t.fg("dim", `↑↓ navigate    ←→/Tab switch tabs    ↵ inject    ${queueKey} queue    d details    e edit    Esc close`);
    lines.push(...new Text(footer, pad, 0).render(width));

    // Bottom border
    lines.push(...new DynamicBorder((s: string) => t.fg("accent", s)).render(width));

    return lines;
  }

  private renderTabs(width: number, pad: number): string[] {
    const t = this.theme;
    const tabStrs: string[] = [];

    for (let i = 0; i < TABS.length; i++) {
      const tab = TABS[i];
      const isActive = i === this.activeTab;
      const color = isActive ? catColor(tab.category) : "dim";

      let text: string;
      if (isActive) {
        text = t.fg(color, t.bold(` ${tab.label} `));
      } else {
        text = t.fg(color, ` ${tab.label} `);
      }

      // Add separator between tabs (except before first)
      if (i > 0) {
        tabStrs.push(t.fg("dim", "│"));
      }
      tabStrs.push(text);
    }

    const line = tabStrs.join("");
    return [" ".repeat(pad) + truncateToWidth(line, width - pad)];
  }

  private renderTabDivider(width: number, pad: number): string {
    const t = this.theme;
    const active = TABS[this.activeTab];
    const color = catColor(active.category);
    // Simple divider line under active tab
    return " ".repeat(pad) + t.fg(color, "─".repeat(Math.min(width - pad, 60)));
  }

  private renderCommandRow(width: number, pad: number, cmd: HelpCommand, selected: boolean): string {
    const t = this.theme;

    const prefix = selected ? "▶" : " ";
    const cmdStyled = selected
      ? t.fg("accent", cmd.name)
      : t.fg("text", cmd.name);
    const descStyled = selected
      ? t.fg("text", cmd.short)
      : t.fg("dim", cmd.short);
    const categoryBadge = this.activeCategory() === "all"
      ? t.fg(catColor(cmd.category), `[${cmd.category}]`) + " "
      : "";

    // Layout: "  ▶ [core] /review:plan   Description..." in ALL, no badge in filtered tabs.
    const leftPart = `  ${prefix} ${categoryBadge}${cmdStyled}`;
    const gap = "   ";

    let line = truncateToWidth(leftPart + gap + descStyled, width - pad);

    if (selected) {
      line = t.bg("selectedBg", line);
    }

    return " ".repeat(pad) + line;
  }

  // ── Detail view ──────────────────────────────────────

  private renderDetail(width: number): string[] {
    const t = this.theme;
    const pad = 2;
    const innerW = Math.max(width - pad * 2 - 2, 20); // -2 for left indent
    const lines: string[] = [];
    const cmd = ALL_COMMANDS[this.detailIdx];
    const catCol = catColor(cmd.category);

    // Top border
    lines.push(...new DynamicBorder((s: string) => t.fg(catCol, s)).render(width));

    // Title with position indicator
    const posStr = `[${this.detailIdx + 1} of ${ALL_COMMANDS.length}]`;
    const titleLine = t.fg(catCol, t.bold(`${cmd.name} — ${cmd.short}`));
    const posLine = t.fg("dim", posStr);
    const combined = truncateToWidth(titleLine + "  " + posLine, width - pad);
    lines.push(...new Text(combined, pad, 0).render(width));

    lines.push(...new Spacer(1).render(width));

    // What it does
    lines.push(...this.renderDetailSection(width, pad, innerW, t, "What it does", cmd.whatItDoes));
    lines.push(...new Spacer(1).render(width));

    // When to use
    lines.push(...this.renderDetailParagraph(width, pad, innerW, t, "When to use", cmd.whenToUse));
    lines.push(...new Spacer(1).render(width));

    // Example
    lines.push(...this.renderDetailExample(width, pad, innerW, t, "Example", cmd.example));

    lines.push(...new Spacer(1).render(width));

    // Footer
    const queueKey = this.keyLabel("app.message.followUp", "Alt+Enter");
    const footer = t.fg("dim", `↵ inject    ${queueKey} queue    e edit first    ←→ prev/next command    Esc back to list`);
    lines.push(...new Text(footer, pad, 0).render(width));

    // Bottom border
    lines.push(...new DynamicBorder((s: string) => t.fg(catCol, s)).render(width));

    return lines;
  }

  private renderDetailSection(width: number, pad: number, innerW: number, t: Theme, heading: string, items: string[]): string[] {
    const lines: string[] = [];
    const headingStyled = t.fg("accent", t.bold(heading));
    lines.push(...new Text(headingStyled, pad, 0).render(width));

    for (const item of items) {
      const bullet = t.fg("dim", "•");
      const wrapped = wrapTextWithAnsi(t.fg("text", item), innerW);
      for (const wline of wrapped) {
        lines.push(" ".repeat(pad + 2) + bullet + " " + wline);
      }
    }

    return lines;
  }

  private renderDetailParagraph(width: number, pad: number, innerW: number, t: Theme, heading: string, text: string): string[] {
    const lines: string[] = [];
    const headingStyled = t.fg("accent", t.bold(heading));
    lines.push(...new Text(headingStyled, pad, 0).render(width));

    const wrapped = wrapTextWithAnsi(t.fg("text", text), innerW);
    for (const wline of wrapped) {
      lines.push(" ".repeat(pad + 2) + wline);
    }

    return lines;
  }

  private renderDetailExample(width: number, pad: number, innerW: number, t: Theme, heading: string, example: string): string[] {
    const lines: string[] = [];
    const headingStyled = t.fg("accent", t.bold(heading));
    lines.push(...new Text(headingStyled, pad, 0).render(width));

    const wrapped = wrapTextWithAnsi(t.fg("dim", example), innerW);
    for (const wline of wrapped) {
      lines.push(" ".repeat(pad + 2) + wline);
    }

    return lines;
  }
}

// ── Prompt Editor Component ───────────────────────────────
// A minimal multi-line editor shown when the user presses "e"
// in the help panel. Shift+Enter inserts newlines, Enter submits.

export class PromptEditor {
  private lines: string[];
  private cursorLine: number;
  private cursorCol: number;
  private scrollCol = 0;
  private pendingCancel = false; // first Esc → warn, second Esc → actually cancel

  private cachedWidth?: number;
  private cachedLines?: string[];

  public onDone?: (text: string) => void;
  public onQueue?: (text: string) => void;
  public onCancel?: () => void;
  public onCopyRequested?: (text: string) => void;

  constructor(
    initialText: string,
    private theme: Theme,
    private label: string,
    private keybindings?: PromptEditorKeybindings,
  ) {
    this.lines = initialText.length > 0 ? initialText.split("\n") : [""];
    this.cursorLine = this.lines.length - 1;
    this.cursorCol = this.lines[this.cursorLine].length;
  }

  // ── Input ────────────────────────────────────────────

  handleInput(data: string): void {
    // If waiting for cancel confirmation, any non-Esc key dismisses the warning
    if (this.pendingCancel) {
      if (matchesKey(data, Key.escape)) {
        this.onCancel?.();
      } else {
        this.pendingCancel = false;
        this.invalidate();
      }
      return;
    }

    if (this.matchesBinding(data, "app.message.followUp")) {
      this.onQueue?.(this.lines.join("\n"));
    } else if (this.matchesBinding(data, "tui.input.submit", Key.enter)) {
      this.onDone?.(this.lines.join("\n"));
    } else if (matchesKey(data, Key.escape)) {
      // First Esc — ask for confirmation
      this.pendingCancel = true;
      this.invalidate();
    } else if (matchesKey(data, Key.ctrl("y"))) {
      // Ctrl+Y — copy to clipboard
      this.onCopyRequested?.(this.lines.join("\n"));
    } else if (this.matchesBinding(data, "tui.input.newLine") || this.isShiftEnter(data)) {
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
      this.scrollCol = 0;
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

  private matchesBinding(data: string, keybinding: string, fallback?: string): boolean {
    try {
      if (this.keybindings?.matches(data, keybinding)) return true;
    } catch {
      // App keybindings may not be available in older pi versions.
    }
    return fallback ? matchesKey(data, fallback) : false;
  }

  private keyLabel(keybinding: string, fallback: string): string {
    try {
      const keys = this.keybindings?.getKeys?.(keybinding);
      if (keys && keys.length > 0) return keys[0].split("+").map((part) => part.length === 1 ? part.toUpperCase() : part[0].toUpperCase() + part.slice(1)).join("+");
    } catch {
      // Use fallback below.
    }
    return fallback;
  }

  // Shift+Enter detection across common terminal protocols
  private isShiftEnter(data: string): boolean {
    return (
      data === "\x1b[13;2u" ||  // Kitty protocol
      data === "\x1b[1;2P" ||   // xterm modifyOtherKeys
      data === "\x1b[13;2~"     // rxvt/urxvt
    );
  }

  private currentLine(): string {
    return this.lines[this.cursorLine] ?? "";
  }

  private moveCol(delta: number): void {
    this.cursorCol = Math.max(0, Math.min(this.currentLine().length, this.cursorCol + delta));
    this.clampScroll();
    this.invalidate();
  }

  private moveLine(delta: number): void {
    this.cursorLine = Math.max(0, Math.min(this.lines.length - 1, this.cursorLine + delta));
    this.cursorCol = Math.min(this.cursorCol, this.currentLine().length);
    this.clampScroll();
    this.invalidate();
  }

  /** Keep scrollCol such that the cursor is visible within the viewport */
  private clampScroll(): void {
    // contentW is unknown here — we'll re-clamp in render with the actual width.
    // For now just ensure scrollCol doesn't wildly exceed line length.
    const lineLen = this.currentLine().length;
    if (this.scrollCol > lineLen) this.scrollCol = Math.max(0, lineLen - 10);
  }

  private insertChar(ch: string): void {
    const line = this.currentLine();
    this.lines[this.cursorLine] = line.slice(0, this.cursorCol) + ch + line.slice(this.cursorCol);
    this.cursorCol++;
    this.scrollCol = 0; // reset horizontal scroll on edit
    this.invalidate();
  }

  private insertNewline(): void {
    const line = this.currentLine();
    const before = line.slice(0, this.cursorCol);
    const after = line.slice(this.cursorCol);
    this.lines[this.cursorLine] = before;
    this.lines.splice(this.cursorLine + 1, 0, after);
    this.cursorLine++;
    this.cursorCol = 0;
    this.scrollCol = 0;
    this.invalidate();
  }

  private backspace(): void {
    if (this.cursorCol > 0) {
      const line = this.currentLine();
      this.lines[this.cursorLine] = line.slice(0, this.cursorCol - 1) + line.slice(this.cursorCol);
      this.cursorCol--;
      this.invalidate();
    } else if (this.cursorLine > 0) {
      // Join with previous line
      const prevLen = this.lines[this.cursorLine - 1].length;
      this.lines[this.cursorLine - 1] += this.lines[this.cursorLine];
      this.lines.splice(this.cursorLine, 1);
      this.cursorLine--;
      this.cursorCol = prevLen;
      this.invalidate();
    }
  }

  private deleteForward(): void {
    const line = this.currentLine();
    if (this.cursorCol < line.length) {
      this.lines[this.cursorLine] = line.slice(0, this.cursorCol) + line.slice(this.cursorCol + 1);
      this.invalidate();
    } else if (this.cursorLine < this.lines.length - 1) {
      // Join with next line
      this.lines[this.cursorLine] += this.lines[this.cursorLine + 1];
      this.lines.splice(this.cursorLine + 1, 1);
      this.invalidate();
    }
  }

  // ── Rendering ────────────────────────────────────────

  render(width: number): string[] {
    if (this.cachedLines && this.cachedWidth === width) {
      return this.cachedLines;
    }
    this.cachedWidth = width;

    const t = this.theme;
    const pad = 2;
    const contentW = Math.max(width - pad * 2, 10);
    const scrollMargin = 4; // keep cursor this far from viewport edges

    // Adjust scrollCol so cursor is visible
    const curLine = this.currentLine();
    if (this.cursorCol < this.scrollCol + scrollMargin) {
      this.scrollCol = Math.max(0, this.cursorCol - scrollMargin);
    }
    if (this.cursorCol > this.scrollCol + contentW - scrollMargin - 1) {
      this.scrollCol = Math.max(0, this.cursorCol - contentW + scrollMargin + 1);
    }

    const lines: string[] = [];

    // Top border
    lines.push(...new DynamicBorder((s: string) => t.fg("accent", s)).render(width));

    // Title
    const title = t.fg("accent", t.bold(`Editing — ${this.label}`));
    lines.push(...new Text(title, pad, 0).render(width));
    lines.push(...new Spacer(1).render(width));

    // Text area — render visible window of each line with scroll indicators
    for (let i = 0; i < this.lines.length; i++) {
      const line = this.lines[i];
      const isCursorLine = i === this.cursorLine;

      // Visible slice of this line
      const visible = line.slice(this.scrollCol, this.scrollCol + contentW);
      const hasLeft = this.scrollCol > 0;
      const hasRight = this.scrollCol + contentW < line.length;

      if (isCursorLine && line.length === 0) {
        // Empty line with cursor — show reverse-video space
        const cursorBlock = "\x1b[7m \x1b[27m";
        const filler = " ".repeat(contentW - 1);
        lines.push(" ".repeat(pad) + " " + cursorBlock + filler + " ");
      } else if (isCursorLine) {
        // Line with cursor — apply reverse video at cursor position
        const cursorVis = this.cursorCol - this.scrollCol; // cursor position in visible slice
        let rendered = "";
        for (let j = 0; j < visible.length; j++) {
          if (j === cursorVis && cursorVis >= 0 && cursorVis < visible.length) {
            rendered += "\x1b[7m" + visible[j] + "\x1b[27m";
          } else {
            rendered += visible[j];
          }
        }
        // If cursor is past the visible end of the line (appending)
        if (this.cursorCol >= this.scrollCol + visible.length &&
            this.cursorCol <= line.length) {
          rendered += "\x1b[7m \x1b[27m";
        }
        // Scroll indicators
        const leftMark = hasLeft ? t.fg("dim", "←") : " ";
        const rightMark = hasRight ? t.fg("dim", "→") : " ";
        lines.push(" ".repeat(pad) + leftMark + rendered + rightMark);
      } else {
        // Non-cursor line — pad visible text to contentW for consistent width
        const leftMark = hasLeft ? t.fg("dim", "←") : " ";
        const rightMark = hasRight ? t.fg("dim", "→") : " ";
        const padded = visible.padEnd(contentW, " ");
        lines.push(" ".repeat(pad) + leftMark + padded.slice(0, contentW) + rightMark);
      }
    }

    lines.push(...new Spacer(1).render(width));

    // Footer — changes when pendingCancel is active
    if (this.pendingCancel) {
      const warnFooter = t.fg("warning", t.bold("Cancel editing?  Press Esc again to confirm  —  any other key to resume"));
      lines.push(...new Text(warnFooter, pad, 0).render(width));
    } else {
      const submitKey = this.keyLabel("tui.input.submit", "Enter");
      const newlineKey = this.keyLabel("tui.input.newLine", "Shift+Enter");
      const queueKey = this.keyLabel("app.message.followUp", "Alt+Enter");
      const footer = t.fg("dim", `${submitKey} submit    ${queueKey} queue follow-up    ${newlineKey} newline    ^Y copy    Esc cancel`);
      lines.push(...new Text(footer, pad, 0).render(width));
    }

    // Bottom border
    lines.push(...new DynamicBorder((s: string) => t.fg("accent", s)).render(width));

    this.cachedLines = lines;
    return lines;
  }

  invalidate(): void {
    this.cachedWidth = undefined;
    this.cachedLines = undefined;
  }
}
