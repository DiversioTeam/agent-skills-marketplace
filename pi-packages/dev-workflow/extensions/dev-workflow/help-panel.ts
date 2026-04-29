import type { Theme } from "@mariozechner/pi-coding-agent";
import { DynamicBorder } from "@mariozechner/pi-coding-agent";
import { matchesKey, Key, truncateToWidth, wrapTextWithAnsi, Text, Spacer } from "@mariozechner/pi-tui";

export type WorkflowPromptCategory = "core" | "bootstrap" | "subagent" | "project" | "user";
export type WorkflowPromptSource = "core" | "project" | "user" | "project override" | "user override";

export interface WorkflowHelpCommand {
  code: string;
  command?: string;
  label: string;
  short: string;
  whatItDoes: string[];
  whenToUse: string;
  example: string;
  category: WorkflowPromptCategory;
  sourceLabel: WorkflowPromptSource;
  sourcePath?: string;
}

interface Tab {
  label: string;
  category: WorkflowPromptCategory | "custom" | "all";
}

const TABS: Tab[] = [
  { label: "CORE", category: "core" },
  { label: "BOOTSTRAP", category: "bootstrap" },
  { label: "SUBAGENT", category: "subagent" },
  { label: "CUSTOM", category: "custom" },
  { label: "ALL", category: "all" },
];

function catColor(cat: string): string {
  switch (cat) {
    case "bootstrap": return "warning";
    case "subagent": return "success";
    case "project": return "warning";
    case "user": return "success";
    case "custom": return "warning";
    default: return "accent";
  }
}

function sourceColor(source: WorkflowPromptSource): string {
  switch (source) {
    case "project":
    case "project override": return "warning";
    case "user":
    case "user override": return "success";
    default: return "accent";
  }
}

function sourceBadge(source: WorkflowPromptSource): string {
  switch (source) {
    case "project override": return "override:project";
    case "user override": return "override:user";
    default: return source;
  }
}

type Mode = "list" | "detail";

interface PromptEditorKeybindings {
  matches(data: string, keybinding: string): boolean;
  getKeys?(keybinding: string): string[];
}

export class HelpPanel {
  private mode: Mode = "list";
  private activeTab = 4;
  private selectedIdx = 0;
  private detailIdx = 0;
  private cachedWidth?: number;
  private cachedLines?: string[];

  public onSelect?: (code: string) => void;
  public onQueue?: (code: string) => void;
  public onEdit?: (code: string) => void;
  public onAddPrompt?: () => void;
  public onOverridePrompt?: (code: string) => void;
  public onCancel?: () => void;

  constructor(
    private theme: Theme,
    private hasSubagents: boolean,
    private commands: WorkflowHelpCommand[],
    private warnings: string[] = [],
    private keybindings?: PromptEditorKeybindings,
  ) {
    this.clampSelection();
  }

  private visibleCommands(): WorkflowHelpCommand[] {
    const cat = TABS[this.activeTab].category;
    if (cat === "all") return this.commands;
    if (cat === "custom") return this.commands.filter((c) => c.category === "project" || c.category === "user");
    return this.commands.filter((c) => c.category === cat);
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
      if (keys && keys.length > 0) {
        return keys[0].split("+").map((part) => part.length === 1 ? part.toUpperCase() : part[0].toUpperCase() + part.slice(1)).join("+");
      }
    } catch {
      // Use fallback below.
    }
    return fallback;
  }

  handleInput(data: string): void {
    if (this.mode === "list") this.handleListInput(data);
    else this.handleDetailInput(data);
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
    } else if (matchesKey(data, Key.right) || matchesKey(data, Key.tab)) {
      this.activeTab = (this.activeTab + 1) % TABS.length;
      this.selectedIdx = 0;
      this.clampSelection();
      this.invalidate();
    } else if (this.matchesBinding(data, "app.message.followUp")) {
      const cmd = cmds[this.selectedIdx];
      if (cmd) this.onQueue?.(cmd.code);
    } else if (matchesKey(data, Key.enter)) {
      const cmd = cmds[this.selectedIdx];
      if (cmd) this.onSelect?.(cmd.code);
    } else if (data === "d" || data === "D") {
      const cmd = cmds[this.selectedIdx];
      if (cmd) {
        this.detailIdx = this.commands.indexOf(cmd);
        this.mode = "detail";
        this.invalidate();
      }
    } else if (data === "e" || data === "E") {
      const cmd = cmds[this.selectedIdx];
      if (cmd) this.onEdit?.(cmd.code);
    } else if (data === "n" || data === "N") {
      this.onAddPrompt?.();
    } else if (data === "o" || data === "O") {
      const cmd = cmds[this.selectedIdx];
      if (cmd) this.onOverridePrompt?.(cmd.code);
    } else if (matchesKey(data, Key.escape)) {
      this.onCancel?.();
    }
  }

  private handleDetailInput(data: string): void {
    if (matchesKey(data, Key.left)) {
      if (this.detailIdx > 0) { this.detailIdx--; this.invalidate(); }
    } else if (matchesKey(data, Key.right)) {
      if (this.detailIdx < this.commands.length - 1) { this.detailIdx++; this.invalidate(); }
    } else if (this.matchesBinding(data, "app.message.followUp")) {
      const cmd = this.commands[this.detailIdx];
      if (cmd) this.onQueue?.(cmd.code);
    } else if (matchesKey(data, Key.enter)) {
      const cmd = this.commands[this.detailIdx];
      if (cmd) this.onSelect?.(cmd.code);
    } else if (data === "e" || data === "E") {
      const cmd = this.commands[this.detailIdx];
      if (cmd) this.onEdit?.(cmd.code);
    } else if (matchesKey(data, Key.escape)) {
      this.mode = "list";
      const cat = this.activeCategory();
      const vis = this.visibleCommands();
      const current = this.commands[this.detailIdx];
      if (current && (cat === "all" || cat === "custom" || current.category === cat)) {
        this.selectedIdx = Math.max(0, vis.indexOf(current));
      }
      this.invalidate();
    }
  }

  render(width: number): string[] {
    if (this.cachedLines && this.cachedWidth === width) return this.cachedLines;
    this.cachedWidth = width;
    this.cachedLines = this.mode === "list" ? this.renderList(width) : this.renderDetail(width);
    return this.cachedLines;
  }

  invalidate(): void {
    this.cachedWidth = undefined;
    this.cachedLines = undefined;
  }

  private renderList(width: number): string[] {
    const t = this.theme;
    const pad = 2;
    const lines: string[] = [];
    lines.push(...new DynamicBorder((s: string) => t.fg("accent", s)).render(width));
    lines.push(...new Text(t.fg("accent", t.bold("Dev Workflow — Prompt Reference")), pad, 0).render(width));
    lines.push(...new Spacer(1).render(width));
    lines.push(...this.renderTabs(width, pad));

    if (TABS[this.activeTab].category === "subagent" && !this.hasSubagents) {
      lines.push(...new Spacer(0).render(width));
      lines.push(...new Text(t.fg("dim", "(pi-subagents not detected — these commands fall back to inline execution)"), pad, 0).render(width));
      lines.push(...new Spacer(1).render(width));
    }

    if (this.warnings.length > 0) {
      lines.push(...new Spacer(0).render(width));
      lines.push(...new Text(t.fg("warning", `Prompt config warnings: ${this.warnings.length}. Use /workflow:prompts validate for details.`), pad, 0).render(width));
      lines.push(...new Spacer(1).render(width));
    }

    lines.push(this.renderTabDivider(width, pad));
    lines.push(...new Spacer(1).render(width));

    const cmds = this.visibleCommands();
    if (cmds.length === 0) {
      lines.push(...new Text(t.fg("muted", "No prompts in this tab yet. Press n to add a user prompt."), pad, 0).render(width));
    } else {
      for (let i = 0; i < cmds.length; i++) {
        lines.push(this.renderCommandRow(width, pad, cmds[i], i === this.selectedIdx));
      }
    }

    lines.push(...new Spacer(1).render(width));
    const queueKey = this.keyLabel("app.message.followUp", "Alt+Enter");
    lines.push(...new Text(t.fg("dim", `↑↓ navigate    ←→/Tab switch tabs    ↵ run    ${queueKey} queue    d details    e edit    n new    o override    Esc close`), pad, 0).render(width));
    lines.push(...new DynamicBorder((s: string) => t.fg("accent", s)).render(width));
    return lines;
  }

  private renderTabs(width: number, pad: number): string[] {
    const t = this.theme;
    const parts: string[] = [];
    for (let i = 0; i < TABS.length; i++) {
      const tab = TABS[i];
      const isActive = i === this.activeTab;
      const color = isActive ? catColor(String(tab.category)) : "dim";
      if (i > 0) parts.push(t.fg("dim", "│"));
      parts.push(isActive ? t.fg(color, t.bold(` ${tab.label} `)) : t.fg(color, ` ${tab.label} `));
    }
    return [" ".repeat(pad) + truncateToWidth(parts.join(""), width - pad)];
  }

  private renderTabDivider(width: number, pad: number): string {
    const active = TABS[this.activeTab];
    return " ".repeat(pad) + this.theme.fg(catColor(String(active.category)), "─".repeat(Math.min(width - pad, 72)));
  }

  private renderCommandRow(width: number, pad: number, cmd: WorkflowHelpCommand, selected: boolean): string {
    const t = this.theme;
    const prefix = selected ? "▶" : " ";
    const source = t.fg(sourceColor(cmd.sourceLabel), `[${sourceBadge(cmd.sourceLabel)}]`);
    const code = selected ? t.fg("accent", cmd.code) : t.fg("text", cmd.code);
    const command = cmd.command ? t.fg("dim", ` ${cmd.command}`) : "";
    const desc = selected ? t.fg("text", cmd.short) : t.fg("dim", cmd.short);
    const left = `  ${prefix} ${source} ${code}${command}`;
    let line = truncateToWidth(`${left}   ${desc}`, width - pad);
    if (selected) line = t.bg("selectedBg", line);
    return " ".repeat(pad) + line;
  }

  private renderDetail(width: number): string[] {
    const t = this.theme;
    const pad = 2;
    const innerW = Math.max(width - pad * 2 - 2, 20);
    const cmd = this.commands[this.detailIdx];
    if (!cmd) return this.renderList(width);
    const color = catColor(cmd.category);
    const lines: string[] = [];
    lines.push(...new DynamicBorder((s: string) => t.fg(color, s)).render(width));
    const pos = t.fg("dim", `[${this.detailIdx + 1} of ${this.commands.length}]`);
    lines.push(...new Text(truncateToWidth(`${t.fg(color, t.bold(`${cmd.code} — ${cmd.label}`))}  ${pos}`, width - pad), pad, 0).render(width));
    lines.push(...new Spacer(1).render(width));
    lines.push(...this.renderMeta(width, pad, t, cmd));
    lines.push(...new Spacer(1).render(width));
    lines.push(...this.renderDetailSection(width, pad, innerW, t, "What it does", cmd.whatItDoes));
    lines.push(...new Spacer(1).render(width));
    lines.push(...this.renderDetailParagraph(width, pad, innerW, t, "When to use", cmd.whenToUse));
    lines.push(...new Spacer(1).render(width));
    lines.push(...this.renderDetailExample(width, pad, innerW, t, "Example", cmd.example));
    lines.push(...new Spacer(1).render(width));
    const queueKey = this.keyLabel("app.message.followUp", "Alt+Enter");
    lines.push(...new Text(t.fg("dim", `↵ run    ${queueKey} queue    e edit first    ←→ prev/next prompt    Esc back to list`), pad, 0).render(width));
    lines.push(...new DynamicBorder((s: string) => t.fg(color, s)).render(width));
    return lines;
  }

  private renderMeta(width: number, pad: number, t: Theme, cmd: WorkflowHelpCommand): string[] {
    const source = `${sourceBadge(cmd.sourceLabel)}${cmd.sourcePath ? ` · ${cmd.sourcePath}` : ""}`;
    return [
      ...new Text(`Command: ${cmd.command ? `/${cmd.command}` : "(run by code only)"}`, pad, 0).render(width),
      ...new Text(`Source:  ${t.fg(sourceColor(cmd.sourceLabel), source)}`, pad, 0).render(width),
    ];
  }

  private renderDetailSection(width: number, pad: number, innerW: number, t: Theme, heading: string, items: string[]): string[] {
    const lines: string[] = [];
    lines.push(...new Text(t.fg("accent", t.bold(heading)), pad, 0).render(width));
    for (const item of items.length > 0 ? items : ["No details provided."]) {
      const wrapped = wrapTextWithAnsi(t.fg("text", item), innerW);
      for (const line of wrapped) lines.push(" ".repeat(pad + 2) + t.fg("dim", "•") + " " + line);
    }
    return lines;
  }

  private renderDetailParagraph(width: number, pad: number, innerW: number, t: Theme, heading: string, text: string): string[] {
    const lines: string[] = [];
    lines.push(...new Text(t.fg("accent", t.bold(heading)), pad, 0).render(width));
    for (const line of wrapTextWithAnsi(t.fg("text", text || "No guidance provided."), innerW)) {
      lines.push(" ".repeat(pad + 2) + line);
    }
    return lines;
  }

  private renderDetailExample(width: number, pad: number, innerW: number, t: Theme, heading: string, example: string): string[] {
    const lines: string[] = [];
    lines.push(...new Text(t.fg("accent", t.bold(heading)), pad, 0).render(width));
    for (const line of wrapTextWithAnsi(t.fg("dim", example || `/workflow:run ${this.commands[this.detailIdx]?.code ?? "<code>"}`), innerW)) {
      lines.push(" ".repeat(pad + 2) + line);
    }
    return lines;
  }
}

export class PromptEditor {
  private lines: string[];
  private cursorLine: number;
  private cursorCol: number;
  private scrollCol = 0;
  private pendingCancel = false;
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

  handleInput(data: string): void {
    if (this.pendingCancel) {
      if (matchesKey(data, Key.escape)) this.onCancel?.();
      else {
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
      this.pendingCancel = true;
      this.invalidate();
    } else if (matchesKey(data, Key.ctrl("y"))) {
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

  private isShiftEnter(data: string): boolean {
    return data === "\x1b[13;2u" || data === "\x1b[1;2P" || data === "\x1b[13;2~";
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

  private clampScroll(): void {
    const lineLen = this.currentLine().length;
    if (this.scrollCol > lineLen) this.scrollCol = Math.max(0, lineLen - 10);
  }

  private insertChar(ch: string): void {
    const line = this.currentLine();
    this.lines[this.cursorLine] = line.slice(0, this.cursorCol) + ch + line.slice(this.cursorCol);
    this.cursorCol++;
    this.scrollCol = 0;
    this.invalidate();
  }

  private insertNewline(): void {
    const line = this.currentLine();
    this.lines[this.cursorLine] = line.slice(0, this.cursorCol);
    this.lines.splice(this.cursorLine + 1, 0, line.slice(this.cursorCol));
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
      this.lines[this.cursorLine] += this.lines[this.cursorLine + 1];
      this.lines.splice(this.cursorLine + 1, 1);
      this.invalidate();
    }
  }

  render(width: number): string[] {
    if (this.cachedLines && this.cachedWidth === width) return this.cachedLines;
    this.cachedWidth = width;

    const t = this.theme;
    const pad = 2;
    const contentW = Math.max(width - pad * 2, 10);
    const scrollMargin = 4;

    if (this.cursorCol < this.scrollCol + scrollMargin) this.scrollCol = Math.max(0, this.cursorCol - scrollMargin);
    if (this.cursorCol > this.scrollCol + contentW - scrollMargin - 1) this.scrollCol = Math.max(0, this.cursorCol - contentW + scrollMargin + 1);

    const lines: string[] = [];
    lines.push(...new DynamicBorder((s: string) => t.fg("accent", s)).render(width));
    lines.push(...new Text(t.fg("accent", t.bold(`Editing — ${this.label}`)), pad, 0).render(width));
    lines.push(...new Spacer(1).render(width));

    for (let i = 0; i < this.lines.length; i++) {
      const line = this.lines[i];
      const isCursorLine = i === this.cursorLine;
      const visible = line.slice(this.scrollCol, this.scrollCol + contentW);
      const hasLeft = this.scrollCol > 0;
      const hasRight = this.scrollCol + contentW < line.length;
      const leftMark = hasLeft ? t.fg("dim", "←") : " ";
      const rightMark = hasRight ? t.fg("dim", "→") : " ";

      if (isCursorLine && line.length === 0) {
        lines.push(" ".repeat(pad) + " " + "\x1b[7m \x1b[27m" + " ".repeat(contentW - 1) + " ");
      } else if (isCursorLine) {
        const cursorVis = this.cursorCol - this.scrollCol;
        let rendered = "";
        for (let j = 0; j < visible.length; j++) rendered += j === cursorVis ? "\x1b[7m" + visible[j] + "\x1b[27m" : visible[j];
        if (this.cursorCol >= this.scrollCol + visible.length && this.cursorCol <= line.length) rendered += "\x1b[7m \x1b[27m";
        lines.push(" ".repeat(pad) + leftMark + rendered + rightMark);
      } else {
        lines.push(" ".repeat(pad) + leftMark + visible.padEnd(contentW, " ").slice(0, contentW) + rightMark);
      }
    }

    lines.push(...new Spacer(1).render(width));
    if (this.pendingCancel) {
      lines.push(...new Text(t.fg("warning", t.bold("Cancel editing?  Press Esc again to confirm  —  any other key to resume")), pad, 0).render(width));
    } else {
      const submitKey = this.keyLabel("tui.input.submit", "Enter");
      const newlineKey = this.keyLabel("tui.input.newLine", "Shift+Enter");
      const queueKey = this.keyLabel("app.message.followUp", "Alt+Enter");
      lines.push(...new Text(t.fg("dim", `${submitKey} run    ${queueKey} queue follow-up    ${newlineKey} newline    ^Y copy    Esc cancel`), pad, 0).render(width));
    }
    lines.push(...new DynamicBorder((s: string) => t.fg("accent", s)).render(width));

    this.cachedLines = lines;
    return lines;
  }

  invalidate(): void {
    this.cachedWidth = undefined;
    this.cachedLines = undefined;
  }
}
