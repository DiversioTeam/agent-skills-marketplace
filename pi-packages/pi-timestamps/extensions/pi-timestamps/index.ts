/**
 * Pi Timestamps
 *
 * What problem are we solving?
 * ---------------------------
 * Pi already knows when messages happen, but the default transcript does not
 * answer the timing questions humans actually ask:
 *
 * - When did I send that prompt?
 * - When did the reply actually finish?
 * - How long until I saw the reply start?
 * - How long did the whole turn take?
 * - How long ago did this happen?
 *
 * First-principles design
 * -----------------------
 * We want timing to be:
 *
 * 1. visible by default
 * 2. subtle enough that it does not fight the transcript
 * 3. easy to hide with one shortcut
 * 4. correct even when providers stream differently
 *
 * So this extension adds one tiny timing row after each user prompt.
 *
 * - normal visible replies show `done`, `reply in`, `total`, and `... ago`
 * - incomplete/non-visible replies fall back to `reply incomplete`
 *
 * Mental model
 * ------------
 *
 *   user prompt ends
 *        ↓
 *   remember prompt timestamp
 *        ↓
 *   assistant starts / streams visible text
 *        ↓
 *   remember reply-start timing
 *        ↓
 *   whole turn ends
 *        ↓
 *   append one display-only timing row
 *   (or `reply incomplete` if no visible assistant reply arrived)
 *
 * Why a separate row instead of changing Pi's normal chat bubbles?
 * ---------------------------------------------------------------
 * Pi's extension API lets us render custom extension messages, but it does not
 * let us directly rewrite the built-in user/assistant bubble renderer.
 *
 * So we do this instead:
 *
 *   normal Pi row
 *   normal Pi row
 *   timing row added by this extension
 *
 * Why is there a hidden widget if there is no visible bottom panel?
 * ---------------------------------------------------------------
 * The zero-height hidden widget keeps a TUI handle so we can request a rerender
 * after appending/toggling timestamp rows and keep `... ago` honest. The ticker
 * is adaptive: quick updates while a row is new, slower updates after that.
 */

import type { Message } from "@mariozechner/pi-ai";
import type { Component, TUI } from "@mariozechner/pi-tui";
import { wrapTextWithAnsi } from "@mariozechner/pi-tui";
import type { ExtensionAPI, ExtensionContext, Theme } from "@mariozechner/pi-coding-agent";

/**
 * Custom message type for the synthetic timing row we append after each turn.
 *
 * This is display-only UI data. We later strip it from model context so the LLM
 * never wastes tokens reading its own timing metadata.
 */
const TURN_MESSAGE_TYPE = "pi-timestamps-turn";

/**
 * Session-persisted settings entry.
 *
 * We only store one thing right now: whether timestamps are visible or hidden.
 */
const SETTINGS_ENTRY_TYPE = "pi-timestamps-settings";

/**
 * Hidden widget key.
 *
 * The widget renders nothing. Its only job is to keep a live TUI handle around
 * so the extension can request rerenders after rows are appended/toggled.
 */
const WIDGET_KEY = "pi-timestamps";

/**
 * Re-render cadence for relative timestamps.
 *
 * `11s ago` is only useful if it is true. So live relative updates are enabled
 * by default, but the ticker is adaptive so it does not repaint forever every
 * second:
 *
 * - under 1 minute old: update every second (`11s ago`, `12s ago`, ...)
 * - under 1 hour old: update every minute (`2m ago`, `3m ago`, ...)
 * - older: update hourly (`2h ago`, `1d ago` change slowly)
 */
const SECOND_MS = 1_000;
const MINUTE_MS = 60 * SECOND_MS;
const HOUR_MS = 60 * MINUTE_MS;

/**
 * Live relative-age updates are enabled unless explicitly disabled.
 *
 * First principles:
 * - If we show `11s ago`, it must keep moving without waiting for the user to
 *   type, scroll, or otherwise cause a redraw.
 * - Repainting every second forever makes copying harder.
 * - Adaptive repainting keeps the label honest while reducing redraws after the
 *   label naturally becomes less granular.
 *
 * Users who strongly prefer a fully stable transcript can disable the relative
 * label and ticker with:
 *
 *   export PI_TIMESTAMPS_LIVE_RELATIVE="false"
 */
const LIVE_RELATIVE_UPDATES = !["0", "false", "no", "off"].includes(
  process.env.PI_TIMESTAMPS_LIVE_RELATIVE?.trim().toLowerCase() ?? "",
);

/**
 * Poll briefly after agent_end until Pi has fully returned to idle.
 *
 * Why polling at all?
 * Pi emits `agent_end` before the run is fully idle. If we append a custom
 * message during that window, Pi treats it as a steering/follow-up message and
 * may ask the LLM to continue. Waiting for idle keeps this row display-only.
 */
const IDLE_APPEND_POLL_MS = 50;

/**
 * Safety cap so a stuck streaming state cannot leave a timer loop running
 * forever.
 *
 * Keep this long enough for other `agent_end` extensions that may show post-turn
 * UI and wait for a human before Pi becomes idle. If Pi is still not idle after
 * this window, dropping one timing row is safer than leaking timers or nudging
 * the model with a queued message.
 */
const MAX_IDLE_APPEND_WAIT_MS = 10 * 60 * 1_000;

/** Timestamps are visible by default unless the session says otherwise. */
const DEFAULT_VISIBILITY_MODE: VisibilityMode = "visible";

/** Optional explicit timezone override. */
const CONFIGURED_TIME_ZONE = process.env.PI_TIMESTAMPS_TIME_ZONE?.trim() || undefined;

/** Keyboard shortcut for hide/show. Kept text-based because the user asked for text, not icons. */
const TOGGLE_SHORTCUT = process.env.PI_TIMESTAMPS_TOGGLE_SHORTCUT?.trim() || "ctrl+shift+h";

/** Two modes only: shown or hidden. We intentionally removed extra modes. */
type VisibilityMode = "visible" | "hidden";

/**
 * `completed` means we saw a visible assistant reply.
 * `aborted` means the turn ended without user-visible assistant text.
 */
type TurnStatus = "completed" | "aborted";

/**
 * Small session-persisted settings payload.
 *
 * We intentionally keep this tiny because session state lasts a long time and
 * should be easy to migrate. If we add more settings later, this is the place.
 */
type VisibilitySettings = {
  visibilityMode: VisibilityMode;
};

/**
 * What we persist on the display-only timing row.
 *
 * We keep this intentionally small. It only stores what the renderer needs.
 */
type TurnTimingDetails = {
  version: 1;
  userTimestamp: number;
  assistantTimestamp?: number;
  totalDurationMs?: number;
  /**
   * User-facing latency label shown as `reply in <duration>`.
   *
   * We persist only the duration, not the exact reply-start timestamp, because
   * the UI does not currently need to render that absolute time. Keeping the
   * saved payload small makes long-lived session history easier to migrate.
   */
  replyStartDurationMs?: number;
  status: TurnStatus;
};

/** In-memory state for the turn currently being processed. */
type LiveTurn = {
  userTimestamp: number;
  /**
   * Coarse fallback for "assistant started replying" when we never receive a
   * text_start/text_delta event. This is better than incorrectly making reply
   * start equal to total duration at turn end.
   */
  assistantStartTimestamp?: number;
  replyStartTimestamp?: number;
  replyStartDurationMs?: number;
};

let visibilityMode: VisibilityMode = DEFAULT_VISIBILITY_MODE;
let currentTurn: LiveTurn | undefined;
let activeTui: TUI | undefined;
let tickTimer: ReturnType<typeof setTimeout> | undefined;

/**
 * Newest completion timestamp among rendered timing rows.
 *
 * The adaptive ticker only needs the newest row because it is the fastest-moving
 * relative label. If the newest row only needs minute-level updates, all older
 * rows are safe at that cadence too.
 *
 * Empty sessions intentionally leave this undefined so the hidden widget does
 * not schedule pointless redraws before any timing row exists.
 */
let latestRelativeTimestamp: number | undefined;

/**
 * Whether this extension runtime is still allowed to append rows.
 *
 * A delayed idle-poll callback can outlive `/reload` or session shutdown. This
 * flag gives those callbacks a simple, explicit exit path so an old runtime
 * cannot write stale timestamp rows into a new session/runtime.
 */
let runtimeActive = false;

/**
 * Timers waiting to append timing rows after the current turn settles.
 *
 * We track them explicitly so reload/shutdown can cancel them and avoid stale
 * rows from an older runtime leaking into a newer session UI.
 */
let pendingAppendTimers = new Set<ReturnType<typeof setTimeout>>();

/** Small runtime type guard for unknown session payloads. */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Runtime guard for the only two supported visibility states. */
function isVisibilityMode(value: unknown): value is VisibilityMode {
  return value === "visible" || value === "hidden";
}

/** Validate timing payloads before trying to render them. */
function isTurnTimingDetails(value: unknown): value is TurnTimingDetails {
  if (!isRecord(value)) return false;
  return (
    value["version"] === 1
    && typeof value["userTimestamp"] === "number"
    && (value["assistantTimestamp"] === undefined || typeof value["assistantTimestamp"] === "number")
    && (value["totalDurationMs"] === undefined || typeof value["totalDurationMs"] === "number")
    && (value["replyStartDurationMs"] === undefined || typeof value["replyStartDurationMs"] === "number")
    && (value["status"] === "completed" || value["status"] === "aborted")
  );
}

function nextTickerDelayMs(): number {
  const timestamp = latestRelativeTimestamp;
  if (timestamp === undefined) return MINUTE_MS;

  const ageMs = Math.max(0, Date.now() - timestamp);

  /**
   * Match the visible precision of formatRelative():
   *
   *   just now / 11s ago  -> can change every second
   *   2m ago              -> can change every minute
   *   2h ago / 1d ago     -> hourly is enough for a subtle transcript row
   */
  if (ageMs < MINUTE_MS) return SECOND_MS;
  if (ageMs < HOUR_MS) return MINUTE_MS;
  return HOUR_MS;
}

function clearTicker(): void {
  if (tickTimer) {
    clearTimeout(tickTimer);
    tickTimer = undefined;
  }
}

/**
 * Start or stop the adaptive rerender tick.
 *
 * Why adaptive?
 *
 *   11s ago  -> changes every second, so update every second
 *   12m ago  -> changes every minute, so update every minute
 *   2h ago   -> changes hourly, so hourly is enough
 *
 * This keeps the `... ago` text truthful without repainting the whole transcript
 * every second forever.
 */
function syncTicker(): void {
  if (!LIVE_RELATIVE_UPDATES || !activeTui || visibilityMode !== "visible" || latestRelativeTimestamp === undefined) {
    clearTicker();
    return;
  }

  if (tickTimer) return;

  tickTimer = setTimeout(() => {
    tickTimer = undefined;
    activeTui?.requestRender();
    syncTicker();
  }, nextTickerDelayMs());
}

function restartTicker(): void {
  /**
   * A newly appended row may need second-level updates even if an older row had
   * already slowed the ticker to minute/hour cadence. Restarting recalculates
   * from the fresh latestRelativeTimestamp immediately.
   */
  clearTicker();
  syncTicker();
}

/**
 * Clear any queued transcript appends.
 *
 * Why: if the extension runtime is torn down during reload or shutdown, we do
 * not want old scheduled callbacks to append stale timing rows into the next
 * runtime.
 */
function clearPendingAppendTimers(): void {
  for (const timer of pendingAppendTimers) {
    clearTimeout(timer);
  }
  pendingAppendTimers.clear();
}

/** Human-readable timezone label for status output. */
function configuredTimeZoneLabel(): string {
  if (CONFIGURED_TIME_ZONE) return CONFIGURED_TIME_ZONE;
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "local";
}

/**
 * Use formatToParts so we control the final layout ourselves.
 *
 * Why: we explicitly do not want the host locale to switch us back to an
 * American month/day order. We normalize into YYYY-MM-DD HH:mm:ss TZ.
 */
function absoluteFormatter(): Intl.DateTimeFormat {
  return new Intl.DateTimeFormat("en", {
    timeZone: CONFIGURED_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZoneName: "short",
  });
}

/** Render absolute timestamps in a fixed non-American layout. */
function formatAbsolute(timestamp: number): string {
  const parts = absoluteFormatter().formatToParts(new Date(timestamp));
  const byType = new Map(parts.map((part) => [part.type, part.value]));
  const year = byType.get("year") ?? "0000";
  const month = byType.get("month") ?? "00";
  const day = byType.get("day") ?? "00";
  const hour = byType.get("hour") ?? "00";
  const minute = byType.get("minute") ?? "00";
  const second = byType.get("second") ?? "00";
  const zone = byType.get("timeZoneName") ?? "";
  return `${year}-${month}-${day} ${hour}:${minute}:${second}${zone ? ` ${zone}` : ""}`;
}

/** Convert a timestamp into "just now", "11s ago", "3m ago", etc. */
function formatRelative(fromTimestamp: number, toTimestamp = Date.now()): string {
  const diffMs = Math.max(0, toTimestamp - fromTimestamp);
  const seconds = Math.floor(diffMs / 1_000);

  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/** Render durations compactly: 4s, 2m 10s, 1h 3m, etc. */
function formatDuration(durationMs: number): string {
  const totalSeconds = Math.max(0, Math.round(durationMs / 1_000));
  if (totalSeconds < 60) return `${totalSeconds}s`;

  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes < 60) return seconds === 0 ? `${minutes}m` : `${minutes}m ${seconds}s`;

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes === 0 ? `${hours}h` : `${hours}h ${remainingMinutes}m`;
}

/** Extract only visible text blocks from a message. */
function extractText(content: Message["content"] | undefined): string {
  if (!content) return "";
  if (typeof content === "string") return content.trim();

  return content
    .filter((block) => block.type === "text")
    .map((block) => block.text.trim())
    .filter(Boolean)
    .join(" ")
    .trim();
}

/**
 * We only consider an assistant reply to have "started" once visible text has
 * appeared. Tool calls or thinking-only content should not count as reply-start
 * timing for the user-facing timestamp row.
 */
function messageContainsVisibleAssistantText(message: Message): boolean {
  if (message.role !== "assistant") return false;
  return extractText(message.content).length > 0;
}

/**
 * Human-readable fallback content stored on the custom message itself.
 *
 * The renderer uses `details`, but keeping `content` readable makes session
 * files easier to inspect manually.
 */
function plainSummary(details: TurnTimingDetails): string {
  const doneText = details.assistantTimestamp
    ? formatAbsolute(details.assistantTimestamp)
    : details.status === "aborted"
      ? "no assistant reply"
      : "waiting";

  let summary = `Turn timing: user ${formatAbsolute(details.userTimestamp)} -> done ${doneText}`;
  if (details.totalDurationMs !== undefined) {
    summary += ` • total ${formatDuration(details.totalDurationMs)}`;
  }
  if (details.replyStartDurationMs !== undefined) {
    summary += ` • reply in ${formatDuration(details.replyStartDurationMs)}`;
  }
  return summary;
}

/**
 * Build the final subtle transcript row.
 *
 * Design goals:
 * - mostly dim text so it feels smaller/secondary
 * - highlight only the useful metrics (`reply in`, `total`)
 * - keep a clear inline shortcut so the user knows it hides the whole timing row
 */
function buildTranscriptLine(details: TurnTimingDetails, theme: Theme): string {
  const separator = theme.fg("dim", " · ");
  const parts: string[] = [theme.fg("dim", formatAbsolute(details.userTimestamp))];

  if (details.assistantTimestamp !== undefined) {
    parts.push(`${theme.fg("muted", "done")} ${theme.fg("success", formatAbsolute(details.assistantTimestamp))}`);
  }

  if (details.replyStartDurationMs !== undefined) {
    parts.push(`${theme.fg("muted", "reply in")} ${theme.fg("accent", formatDuration(details.replyStartDurationMs))}`);
  }

  if (details.assistantTimestamp !== undefined) {
    const total = details.totalDurationMs ?? Math.max(0, details.assistantTimestamp - details.userTimestamp);
    parts.push(`${theme.fg("muted", "total")} ${theme.fg("accent", formatDuration(total))}`);

    if (LIVE_RELATIVE_UPDATES) {
      parts.push(theme.fg("warning", formatRelative(details.assistantTimestamp)));
    }
  } else {
    parts.push(theme.fg("warning", "reply incomplete"));
  }

  if (visibilityMode === "visible") {
    parts.push(`${theme.fg("dim", "hide row:")} ${theme.fg("muted", TOGGLE_SHORTCUT)}`);
  }

  return parts.join(separator);
}

class TurnTimingMessageComponent implements Component {
  constructor(
    private readonly details: TurnTimingDetails,
    private readonly theme: Theme,
  ) {}

  render(width: number): string[] {
    /**
     * Important: existing timing-row components stay mounted after they are
     * first created. So hiding timestamps must be enforced here at render time,
     * not only when the renderer initially chooses which component to build.
     */
    if (visibilityMode === "hidden") {
      return [];
    }

    return wrapTextWithAnsi(buildTranscriptLine(this.details, this.theme), Math.max(1, width));
  }

  invalidate(): void {}
}

/**
 * This component deliberately renders nothing.
 *
 * It exists only so the extension has a stable TUI handle (`activeTui`) for
 * explicit rerenders after appends/toggles and adaptive live relative updates.
 */
class HiddenTickerComponent implements Component {
  render(_width: number): string[] {
    return [];
  }

  invalidate(): void {}
}

/**
 * Restore visibility mode from the current session branch.
 *
 * First principles:
 * session history is the source of truth for user-facing extension state.
 * On reload or resume we reconstruct from saved entries instead of guessing.
 */
function restoreStateFromSession(ctx: ExtensionContext): void {
  visibilityMode = DEFAULT_VISIBILITY_MODE;
  currentTurn = undefined;
  latestRelativeTimestamp = undefined;

  for (const entry of ctx.sessionManager.getBranch()) {
    if (entry.type === "custom" && entry.customType === SETTINGS_ENTRY_TYPE && isRecord(entry.data)) {
      /**
       * Backward compatibility:
       * older session entries stored this under `widgetMode` before we renamed
       * the field to `visibilityMode` to better reflect what it actually controls.
       */
      const maybeMode = entry.data["visibilityMode"] ?? entry.data["widgetMode"];
      if (isVisibilityMode(maybeMode)) {
        visibilityMode = maybeMode;
      }
      continue;
    }

    /**
     * On resume/reload, existing rows may already show `... ago`. Restore the
     * newest completed timestamp so the adaptive ticker can keep those labels
     * moving without waiting for a brand-new turn.
     */
    if (entry.type === "custom_message" && entry.customType === TURN_MESSAGE_TYPE && isTurnTimingDetails(entry.details)) {
      latestRelativeTimestamp = entry.details.assistantTimestamp ?? latestRelativeTimestamp;
    }
  }
}

/**
 * Persist visible/hidden mode so `/reload` and resumes keep the same state.
 *
 * This is the only user preference we store today, which keeps migration logic
 * small and easy to reason about.
 */
function persistVisibilityMode(pi: ExtensionAPI, nextMode: VisibilityMode): void {
  visibilityMode = nextMode;
  const settings: VisibilitySettings = { visibilityMode: nextMode };
  pi.appendEntry(SETTINGS_ENTRY_TYPE, settings);
  syncTicker();
}

/**
 * Accept a few human-friendly command aliases.
 *
 * We keep this parser deliberately tiny so `/timestamps` behavior stays
 * predictable and easy to explain in docs.
 */
function parseVisibilityMode(input: string): VisibilityMode | undefined {
  if (input === "visible" || input === "hidden") return input;
  if (input === "on") return "visible";
  if (input === "off") return "hidden";
  return undefined;
}

/**
 * Queue a timing row after the current run settles.
 *
 * Important Pi behavior:
 *
 *   inside agent_end
 *         ↓
 *   Pi is still streaming
 *         ↓
 *   pi.sendMessage(...) defaults to "steer"
 *         ↓
 *   queued custom message can cause another LLM continuation
 *
 * That is exactly the bug this helper avoids. We wait until `ctx.isIdle()` is
 * true, then append with `{ triggerTurn: false }` so the row is just transcript
 * UI and not work for the model.
 *
 * The runtimeActive checks protect `/reload` and shutdown:
 *
 *   old runtime schedules callback
 *         ↓
 *   /reload tears old runtime down
 *         ↓
 *   callback wakes up later
 *         ↓
 *   runtimeActive=false, so it exits without appending stale rows
 */
function scheduleTimingRowAppend(pi: ExtensionAPI, ctx: ExtensionContext, details: TurnTimingDetails): void {
  const deadline = Date.now() + MAX_IDLE_APPEND_WAIT_MS;

  const appendWhenIdle = () => {
    if (!runtimeActive) {
      return;
    }

    if (!ctx.isIdle()) {
      if (Date.now() >= deadline) {
        return;
      }

      const nextTimer = setTimeout(() => {
        pendingAppendTimers.delete(nextTimer);
        appendWhenIdle();
      }, IDLE_APPEND_POLL_MS);
      pendingAppendTimers.add(nextTimer);
      return;
    }

    if (!runtimeActive) {
      return;
    }

    pi.sendMessage(
      {
        customType: TURN_MESSAGE_TYPE,
        content: plainSummary(details),
        display: true,
        details,
      },
      { triggerTurn: false },
    );

    latestRelativeTimestamp = details.assistantTimestamp ?? latestRelativeTimestamp;
    restartTicker();
    activeTui?.requestRender();
  };

  const timer = setTimeout(() => {
    pendingAppendTimers.delete(timer);
    appendWhenIdle();
  }, 0);

  pendingAppendTimers.add(timer);
}

export default function (pi: ExtensionAPI) {
  pi.registerMessageRenderer(TURN_MESSAGE_TYPE, (message, _options, theme) => {
    /**
     * Always return the real timing-row component for timing messages.
     *
     * Why:
     * - timing rows created while hidden should become visible again later
     * - timing rows created while visible should disappear when hidden
     *
     * That means visibility must be checked inside the component's render path,
     * not here at component-construction time.
     */
    if (!isTurnTimingDetails(message.details)) {
      return new HiddenTickerComponent();
    }
    return new TurnTimingMessageComponent(message.details, theme);
  });

  /**
   * User command surface.
   *
   * Examples:
   *   /timestamps
   *   /timestamps visible
   *   /timestamps hidden
   *   /timestamps status
   */
  pi.registerCommand("timestamps", {
    description: "Toggle or set Pi timestamps visibility (visible|hidden|status)",
    handler: async (args, ctx) => {
      const input = args.trim().toLowerCase();
      if (input === "status") {
        ctx.ui.notify(`Pi timestamps: ${visibilityMode} • ${configuredTimeZoneLabel()} • ${TOGGLE_SHORTCUT}`, "info");
        return;
      }

      const explicitMode = parseVisibilityMode(input);
      const nextMode = explicitMode ?? (visibilityMode === "hidden" ? "visible" : "hidden");
      persistVisibilityMode(pi, nextMode);
      ctx.ui.notify(`Pi timestamps ${nextMode}`, "info");
      activeTui?.requestRender();
    },
  });

  /**
   * One-key hide/show for people who want timing only sometimes.
   *
   * This is intentionally symmetric:
   * - visible -> hidden
   * - hidden  -> visible
   *
   * That makes the shortcut easy to memorize and keeps the inline hint honest.
   */
  pi.registerShortcut(TOGGLE_SHORTCUT, {
    description: "Toggle Pi timestamps visibility",
    handler: async (ctx) => {
      const nextMode: VisibilityMode = visibilityMode === "hidden" ? "visible" : "hidden";
      persistVisibilityMode(pi, nextMode);
      ctx.ui.notify(`Pi timestamps ${nextMode}`, "info");
      activeTui?.requestRender();
    },
  });

  /**
   * Session startup:
   * - restore saved visibility
   * - mount the hidden ticker widget
   * - start relative-time rerenders when needed
   */
  pi.on("session_start", async (_event, ctx) => {
    runtimeActive = true;
    restoreStateFromSession(ctx);

    if (ctx.hasUI) {
      ctx.ui.setWidget(WIDGET_KEY, (tui) => {
        activeTui = tui;
        syncTicker();
        return new HiddenTickerComponent();
      });
    }
  });

  /**
   * Tear down live UI state cleanly when the session runtime exits.
   *
   * This matters most during `/reload`, where old timers from the previous
   * runtime would otherwise keep firing against the new one.
   */
  pi.on("session_shutdown", async () => {
    runtimeActive = false;
    activeTui = undefined;
    currentTurn = undefined;
    clearPendingAppendTimers();
    syncTicker();
  });

  /** Keep timing rows out of model context. They are purely for humans. */
  pi.on("context", async (event) => {
    return {
      messages: event.messages.filter((message) => {
        if (!isRecord(message)) return true;
        return message["customType"] !== TURN_MESSAGE_TYPE;
      }),
    };
  });

  /**
   * Assistant message start gives us a coarse fallback for "reply started".
   *
   * This is only a backup. Real `reply in` timing still comes from visible
   * text events when possible.
   */
  pi.on("message_start", async (event) => {
    if (event.message.role !== "assistant" || !currentTurn) return;
    if (currentTurn.replyStartTimestamp !== undefined) return;

    /**
     * Keep updating this fallback until we see real visible text.
     *
     * Why: an earlier assistant message may contain only tool calls. If the
     * later user-visible assistant message does not emit text_start/text_delta
     * events, we still want a fallback timestamp that is as close as possible
     * to the start of the visible reply, not the earlier tool-call message.
     */
    currentTurn.assistantStartTimestamp = Date.now();
  });

  pi.on("message_end", async (event) => {
    /**
     * The user message ending is our clean "turn start" signal.
     *
     * Why not `input` or `message_start(role=user)`?
     * Because `message_end(role=user)` is the point where Pi has actually
     * accepted the prompt into the conversation history, which makes the timing
     * row line up with what the transcript shows.
     */
    if (event.message.role === "user") {
      currentTurn = { userTimestamp: event.message.timestamp };
      return;
    }

    if (event.message.role !== "assistant" || !currentTurn) return;

    if (!currentTurn.replyStartTimestamp && messageContainsVisibleAssistantText(event.message)) {
      currentTurn.replyStartTimestamp = currentTurn.assistantStartTimestamp ?? Date.now();
      currentTurn.replyStartDurationMs = Math.max(0, currentTurn.replyStartTimestamp - currentTurn.userTimestamp);
    }
  });

  /**
   * Streaming text is the best place to capture reply-start timing.
   *
   * Best case:
   *   assistant text_start/text_delta arrives
   *   -> reply-start timing is exact-ish
   *
   * Fallback case:
   *   provider never emits visible text-start events
   *   -> we later fall back to assistant message_start timing
   */
  pi.on("message_update", async (event) => {
    if (!currentTurn || event.message.role !== "assistant") return;
    if (currentTurn.replyStartTimestamp !== undefined) return;
    if (event.assistantMessageEvent.type !== "text_start" && event.assistantMessageEvent.type !== "text_delta") {
      return;
    }

    currentTurn.replyStartTimestamp = Date.now();
    currentTurn.replyStartDurationMs = Math.max(0, currentTurn.replyStartTimestamp - currentTurn.userTimestamp);
  });

  /**
   * At the end of the whole prompt, emit one display-only timing row.
   *
   * Important rule:
   * We only call the turn `completed` if there was user-visible assistant text.
   * Tool-call-only turns should not pretend they produced a visible reply.
   *
   * We use `Date.now()` for the final assistant timestamp because it is the
   * closest thing to "the visible turn is fully done and back in the user's
   * hands".
   */
  pi.on("agent_end", async (event, ctx) => {
    /**
     * No `currentTurn` means we have nothing to measure.
     * This can happen if the runtime resumed mid-conversation or if a command
     * path never produced a normal user->assistant turn.
     */
    if (!currentTurn) return;

    const userMessage = event.messages.find((message) => message.role === "user");
    const assistantMessages = event.messages.filter((message) => message.role === "assistant");
    const hasVisibleAssistantReply = assistantMessages.some((message) => messageContainsVisibleAssistantText(message));
    const status: TurnStatus = hasVisibleAssistantReply ? "completed" : "aborted";

    const userTimestamp = userMessage?.timestamp ?? currentTurn.userTimestamp;
    const assistantTimestamp = status === "completed" ? Date.now() : undefined;
    const totalDurationMs = assistantTimestamp !== undefined
      ? Math.max(0, assistantTimestamp - userTimestamp)
      : undefined;

    const replyStartTimestamp = hasVisibleAssistantReply
      ? (currentTurn.replyStartTimestamp ?? currentTurn.assistantStartTimestamp)
      : undefined;
    const replyStartDurationMs = replyStartTimestamp !== undefined
      ? Math.max(0, replyStartTimestamp - userTimestamp)
      : undefined;

    /**
     * Persist only what the visible transcript row actually renders.
     *
     * If future UI needs the absolute reply-start clock time, we can add it
     * later. For now the smaller payload keeps history cleaner.
     */
    const details: TurnTimingDetails = {
      version: 1,
      userTimestamp,
      assistantTimestamp,
      totalDurationMs,
      replyStartDurationMs,
      status,
    };

    scheduleTimingRowAppend(pi, ctx, details);

    currentTurn = undefined;
    activeTui?.requestRender();
  });
}
