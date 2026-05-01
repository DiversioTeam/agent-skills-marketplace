import type { ExtensionAPI, ToolResultEvent } from "@mariozechner/pi-coding-agent";
import {
  isBashToolResult,
  isEditToolResult,
  isFindToolResult,
  isGrepToolResult,
  isReadToolResult,
  isWriteToolResult,
} from "@mariozechner/pi-coding-agent";
import { basename } from "node:path";
import { isInsideCmux, notify } from "@diversioteam/pi-cmux";

/**
 * Native cmux notifications for Pi
 *
 * First principles:
 * - Pi already knows when an agent run starts, does work, and ends.
 * - cmux already knows how to show notifications, unread state, and focus-aware UX.
 * - So the simplest useful product is: listen to Pi lifecycle events, summarize
 *   the work in plain language, and hand that summary to cmux.
 *
 * This file is intentionally opinionated about *useful summaries* instead of
 * trying to mirror every low-level tool event 1:1. The goal is signal, not spam.
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_THRESHOLD_MS = 15_000;
const DEFAULT_DEBOUNCE_MS = 3_000;
const NOTIFY_TIMEOUT_MS = 5_000;
const DEFAULT_NOTIFY_LEVEL = "all";
const FAILURE_CACHE_CLEAR_MS = 120_000;
const MAX_FAILURES_BEFORE_CACHE = 3;

type NotifyLevel = "all" | "medium" | "low" | "disabled";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * Per-agent-run facts we collect while Pi is working.
 *
 * We use these to build one concise summary at the end instead of sending a
 * notification for every tool call.
 */
interface RunState {
  startedAt: number;
  readFiles: Set<string>;
  changedFiles: Set<string>;
  searchCount: number;
  bashCount: number;
  firstToolError: string | undefined;
}

interface AssistantMessageLike {
  role: "assistant";
  stopReason?: string;
  errorMessage?: string;
  content?: Array<{ type?: string; text?: string }>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Small env parser used for numeric notification settings.
 */
function getNumberFromEnv(name: string, fallback: number): number {
  const value = process.env[name];
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

/**
 * Notification level controls how noisy the package should be.
 *
 * - all     = waiting + success + error
 * - medium  = success + error
 * - low     = error only
 * - disabled = nothing
 */
function getNotifyLevelFromEnv(): NotifyLevel {
  const value = process.env.PI_CMUX_NOTIFY_LEVEL?.trim().toLowerCase();
  if (value === "all" || value === "medium" || value === "low" || value === "disabled") {
    return value;
  }
  return DEFAULT_NOTIFY_LEVEL;
}

function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return count === 1 ? singular : plural;
}

function formatDuration(ms: number): string {
  const totalSeconds = Math.max(1, Math.round(ms / 1_000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) return `${seconds}s`;
  if (seconds === 0) return `${minutes}m`;
  return `${minutes}m ${seconds}s`;
}

function getPathFromInput(event: ToolResultEvent): string | undefined {
  const path = event.input.path;
  return typeof path === "string" && path.length > 0 ? path : undefined;
}

function getFirstText(event: ToolResultEvent): string | undefined {
  const textPart = event.content.find((part) => part.type === "text");
  if (!textPart || textPart.type !== "text") return undefined;
  const text = textPart.text.trim();
  return text.length > 0 ? text : undefined;
}

function summarizeError(event: ToolResultEvent): string {
  const path = getPathFromInput(event);
  if (path) {
    return `${event.toolName} failed for ${basename(path)}`;
  }
  if (isBashToolResult(event)) {
    return "bash command failed";
  }
  const text = getFirstText(event);
  if (!text) {
    return `${event.toolName} failed`;
  }
  return text.length > 120 ? `${text.slice(0, 117)}…` : text;
}

/**
 * Turn the collected run facts into one human-friendly success summary.
 *
 * Why this shape?
 * - File names are more useful than raw counts for short runs.
 * - Counts are more useful than long file lists for larger runs.
 * - Duration helps the user judge whether Pi was doing something substantial
 *   or just came back almost immediately.
 */
function summarizeSuccess(
  state: RunState,
  durationMs: number,
  thresholdMs: number,
): string {
  const parts: string[] = [];

  // Changed files
  const changedCount = state.changedFiles.size;
  if (changedCount > 0) {
    const names = [...state.changedFiles].map((f) => basename(f));
    if (names.length <= 3) {
      parts.push(`Changed ${names.join(", ")}`);
    } else {
      parts.push(`Changed ${names.slice(0, 2).join(", ")} +${changedCount - 2} more`);
    }
  }

  // Read files
  const readCount = state.readFiles.size;
  if (readCount > 0) {
    const names = [...state.readFiles].map((f) => basename(f));
    if (names.length <= 3) {
      parts.push(`Read ${names.join(", ")}`);
    } else {
      parts.push(`Read ${names.slice(0, 2).join(", ")} +${readCount - 2} more`);
    }
  }

  // Searches
  if (state.searchCount > 0) {
    parts.push(`${state.searchCount} ${pluralize(state.searchCount, "search", "searches")}`);
  }

  // Bash commands
  if (state.bashCount > 0) {
    parts.push(`${state.bashCount} ${pluralize(state.bashCount, "cmd", "cmds")}`);
  }

  // Duration is always shown when above threshold or there was activity
  if (durationMs >= thresholdMs || parts.length > 0) {
    parts.push(formatDuration(durationMs));
  }

  if (parts.length === 0) {
    return durationMs >= thresholdMs
      ? `Idle after ${formatDuration(durationMs)}`
      : "Waiting for input";
  }

  return parts.join(" · ");
}

function isAssistantMessage(message: unknown): message is AssistantMessageLike {
  return (
    typeof message === "object" &&
    message !== null &&
    (message as { role?: unknown }).role === "assistant"
  );
}

function getLastAssistantMessage(
  messages: readonly unknown[],
): AssistantMessageLike | undefined {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (isAssistantMessage(message)) return message;
  }
  return undefined;
}

function summarizeAssistantText(message: AssistantMessageLike): string | undefined {
  if (!Array.isArray(message.content)) return undefined;

  const text = message.content
    .filter(
      (part): part is { type: "text"; text: string } =>
        typeof part === "object" &&
        part !== null &&
        part.type === "text" &&
        typeof part.text === "string" &&
        part.text.trim().length > 0,
    )
    .map((part) => part.text.trim())
    .join("\n")
    .trim();

  if (text.length === 0) return undefined;
  return text.length > 120 ? `${text.slice(0, 117)}…` : text;
}

/**
 * Build one error summary from the final assistant message plus the run state.
 *
 * We prefer assistant-provided error text when available because it often has
 * more product context than a single tool failure. We then append a short
 * activity hint like `[2 cmds run]` so future readers know what Pi was doing
 * right before it failed.
 */
function summarizeRunError(
  messages: readonly unknown[],
  fallbackError?: string,
  state?: RunState,
): string | undefined {
  const assistantMessage = getLastAssistantMessage(messages);
  if (!assistantMessage) return fallbackError;

  if (
    assistantMessage.stopReason !== "error" &&
    assistantMessage.stopReason !== "aborted"
  ) {
    return undefined;
  }

  // Build context: what was happening when the error occurred
  const contextParts: string[] = [];
  if (state) {
    const changedCount = state.changedFiles.size;
    if (changedCount > 0) {
      contextParts.push(`${changedCount} ${pluralize(changedCount, "file")} changed`);
    }
    if (state.bashCount > 0) {
      contextParts.push(`${state.bashCount} ${pluralize(state.bashCount, "cmd", "cmds")} run`);
    }
  }
  const context = contextParts.length > 0 ? ` [${contextParts.join(", ")}]` : "";

  const baseSummary =
    assistantMessage.errorMessage?.trim() ||
    summarizeAssistantText(assistantMessage) ||
    fallbackError ||
    "Agent run failed";
  const summary = context && !baseSummary.includes(context)
    ? `${baseSummary}${context}`
    : baseSummary;
  return summary.length > 140 ? `${summary.slice(0, 137)}…` : summary;
}

function buildSubtitle(
  hasRunError: boolean,
  state: RunState,
  durationMs: number,
  thresholdMs: number,
): string {
  if (hasRunError) return "Error";
  if (state.changedFiles.size > 0 || durationMs >= thresholdMs) return "Task Complete";
  return "Waiting";
}

function shouldNotify(level: NotifyLevel, subtitle: string): boolean {
  if (level === "disabled") return false;
  if (level === "all") return true;
  if (level === "medium") return subtitle === "Task Complete" || subtitle === "Error";
  if (level === "low") return subtitle === "Error";
  return true;
}

function createEmptyRunState(): RunState {
  return {
    startedAt: Date.now(),
    readFiles: new Set<string>(),
    changedFiles: new Set<string>(),
    searchCount: 0,
    bashCount: 0,
    firstToolError: undefined,
  };
}

// ---------------------------------------------------------------------------
// Workspace name resolution
// ---------------------------------------------------------------------------

/**
 * Pick the name shown in notification titles.
 *
 * Rules:
 * - If the cmux workspace has an explicit human title, keep it.
 * - If the workspace title is really just a path, shorten it to `basename(cwd)`.
 *
 * This keeps titles informative without flooding the notification UI with long
 * absolute paths.
 */
async function resolveWorkspaceName(pi: ExtensionAPI, cwd: string): Promise<string> {
  try {
    const result = await pi.exec("cmux", ["--json", "current-workspace"], {
      timeout: 3_000,
    });
    if (result.code === 0 && result.stdout) {
      const parsed = JSON.parse(result.stdout);
      const title = parsed?.workspace?.title;
      if (typeof title === "string" && title.trim().length > 0) {
        const trimmedTitle = title.trim();
        // If the tab title looks like a path (including cmux's truncated …/path form),
        // prefer a short cwd basename. Otherwise keep the explicit workspace tab name.
        const looksLikePath = trimmedTitle.startsWith("/") || trimmedTitle.startsWith("~/") || trimmedTitle.startsWith("…/");
        if (!looksLikePath) {
          return trimmedTitle;
        }
      }
    }
  } catch {
    // Fall through
  }
  return basename(cwd) || "pi";
}

// ---------------------------------------------------------------------------
// Extension
// ---------------------------------------------------------------------------

export default function cmuxNotifyExtension(pi: ExtensionAPI) {
  // Notifications are a cmux-only feature. Outside cmux we do nothing on
  // purpose: no warnings, no fallback shell escape codes, no extra noise.
  if (!isInsideCmux()) return;

  const thresholdMs = getNumberFromEnv("PI_CMUX_NOTIFY_THRESHOLD_MS", DEFAULT_THRESHOLD_MS);
  const debounceMs = getNumberFromEnv("PI_CMUX_NOTIFY_DEBOUNCE_MS", DEFAULT_DEBOUNCE_MS);
  const notifyLevel = getNotifyLevelFromEnv();
  const baseTitle = process.env.PI_CMUX_NOTIFY_TITLE || "Pi";

  let runState = createEmptyRunState();
  let workspaceName = "";
  let lastNotificationAt = 0;
  let lastNotificationKey = "";
  let cmuxUnavailable = false;
  let consecutiveFailures = 0;
  let failureCacheClearedAt = Date.now();

  const buildTitle = (): string => {
    const wsPart = workspaceName ? ` — ${workspaceName}` : "";
    return `${baseTitle}${wsPart}`;
  };

  /**
   * Send one deduplicated cmux notification.
   *
   * Why cache failures?
   * - If cmux becomes unavailable, repeatedly trying to notify on every agent
   *   run would just create avoidable delays and noise.
   * - After a short cooldown we try again automatically.
   */
  const sendNotification = async (
    title: string,
    subtitle: string,
    body: string,
  ): Promise<{ ok: boolean; error?: string }> => {
    // Clear cached unavailability after cooldown
    if (cmuxUnavailable && Date.now() - failureCacheClearedAt > FAILURE_CACHE_CLEAR_MS) {
      cmuxUnavailable = false;
      consecutiveFailures = 0;
    }

    if (cmuxUnavailable) {
      return { ok: false, error: "cmux notify is unavailable" };
    }

    // Debounce duplicate notifications
    const notificationKey = `${title}\n${subtitle}\n${body}`;
    const now = Date.now();
    if (notificationKey === lastNotificationKey && now - lastNotificationAt < debounceMs) {
      return { ok: true };
    }

    const result = await notify(pi, title, subtitle, body, { timeout: NOTIFY_TIMEOUT_MS });
    if (!result.ok) {
      consecutiveFailures += 1;
      if (consecutiveFailures >= MAX_FAILURES_BEFORE_CACHE) {
        cmuxUnavailable = true;
        failureCacheClearedAt = Date.now();
      }
      return result;
    }

    consecutiveFailures = 0;
    lastNotificationAt = now;
    lastNotificationKey = notificationKey;
    return { ok: true };
  };

  // Resolve workspace/tab naming once per session start so each notification
  // carries useful context like `Pi — backend` or `Pi — Auth Review`.
  pi.on("session_start", async (_event, ctx) => {
    workspaceName = await resolveWorkspaceName(pi, ctx.cwd);
  });

  // Each user prompt gets a fresh run state.
  pi.on("agent_start", async () => {
    runState = createEmptyRunState();
  });

  // Collect simple facts while Pi works so the final notification can answer:
  // "What just happened?" in one line.
  pi.on("tool_result", async (event) => {
    if (event.isError && !runState.firstToolError) {
      runState.firstToolError = summarizeError(event);
    }

    if (isReadToolResult(event)) {
      const path = getPathFromInput(event);
      if (path) runState.readFiles.add(path);
      return;
    }

    if (isEditToolResult(event) || isWriteToolResult(event)) {
      const path = getPathFromInput(event);
      if (path && !event.isError) runState.changedFiles.add(path);
      return;
    }

    if (isGrepToolResult(event) || isFindToolResult(event)) {
      if (!event.isError) runState.searchCount += 1;
      return;
    }

    if (isBashToolResult(event) && !event.isError) {
      runState.bashCount += 1;
    }
  });

  // Emit one final summary when Pi stops and waits for the next user input.
  pi.on("agent_end", async (event, ctx) => {
    const durationMs = Date.now() - runState.startedAt;
    const runError = summarizeRunError(event.messages, runState.firstToolError, runState);
    const subtitle = buildSubtitle(Boolean(runError), runState, durationMs, thresholdMs);
    if (!shouldNotify(notifyLevel, subtitle)) {
      return;
    }
    const body = runError || summarizeSuccess(runState, durationMs, thresholdMs);
    const title = buildTitle();

    // Also surface the same summary inside Pi itself.
    //
    // Why both?
    // - cmux notifications are great when you are looking elsewhere.
    // - in-Pi notifications are great when the cmux notification panel is not open.
    const notifyType =
      subtitle === "Error" ? "error" : subtitle === "Task Complete" ? "success" : "info";
    ctx.ui.notify(`${title}: ${subtitle} — ${body}`, notifyType);

    await sendNotification(title, subtitle, body);
  });
}
