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
 * - How long ago did the last reply happen?
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
 * - normal visible replies show `done`, `reply in`, and `total`
 * - incomplete/non-visible replies fall back to `reply incomplete`
 * - the live relative age for the newest turn moves to the status bar
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
 * Why is the live relative age shown in the status bar instead of each row?
 * ------------------------------------------------------------------------
 * A changing `11s ago` label inside historical transcript rows forces Pi to
 * rerender old chat lines. That is fragile when the user has scrolled up.
 * Keeping transcript rows static while moving only the newest relative age to
 * the bottom status bar preserves the per-turn timing history without causing
 * historical rows to tick in place.
 */

import type { Message } from "@mariozechner/pi-ai";
import type { Component } from "@mariozechner/pi-tui";
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

/** Footer status key for the newest live relative age. */
const STATUS_KEY = "pi-timestamps";

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
 * Users who strongly prefer a fully stable UI can disable the relative
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

type StatusAnimationId = string;

/**
 * Small session-persisted settings payload.
 *
 * We intentionally keep this tiny because session state lasts a long time and
 * should be easy to migrate. If we add more settings later, this is the place.
 */
type VisibilitySettings = {
  visibilityMode: VisibilityMode;
  statusAnimationId?: StatusAnimationId;
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
let activeCtx: ExtensionContext | undefined;
let tickTimer: ReturnType<typeof setTimeout> | undefined;
let statusAnimationId: StatusAnimationId | undefined;

/** Latest persisted timing row, used for bottom-status relative age. */
let latestStatusDetails: TurnTimingDetails | undefined;

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
  if (currentTurn) return SECOND_MS;

  const timestamp = latestStatusDetails?.assistantTimestamp;
  if (timestamp === undefined) return MINUTE_MS;

  const ageMs = Math.max(0, Date.now() - timestamp);

  /**
   * Match the visible precision of formatRelative():
   *
   *   just now / 11s ago  -> can change every second
   *   2m ago              -> can change every minute
   *   2h ago / 1d ago     -> hourly is enough for a subtle status label
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

const STATUS_ANIMATIONS = [
  { id: "football-dribble", frames: ["⚽", "👟⚽", "⚽👟", "👟⚽", "⚽"] as const },
  { id: "football-penalty", frames: ["⚽", "🦵⚽", "⚽💨", "🥅", "🥅⚽"] as const },
  { id: "football-goal", frames: ["⚽", "⚽💨", "🥅", "🥅⚽", "🎉⚽"] as const },
  { id: "football-bounce", frames: ["⚽", "⚽⬆️", "⚽", "⚽⬇️", "⚽"] as const },
  { id: "rocket", frames: ["🚀", "🚀✨", "🌠", "✨🚀"] as const },
  { id: "sparkles", frames: ["✨", "💫", "⭐", "🌟"] as const },
  { id: "wizard", frames: ["🪄", "✨", "🪄✨", "✨"] as const },
  { id: "dragon", frames: ["🐉", "🐉🔥", "🔥", "🐲"] as const },
  { id: "dice", frames: ["🎲", "⚀", "⚂", "⚅"] as const },
  { id: "moon", frames: ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"] as const },
] as const;

const IN_PROGRESS_MESSAGE_BUCKET_MS = 4 * SECOND_MS;
const REPLIED_MESSAGE_BUCKET_MS = 8 * SECOND_MS;
const FUMBLED_MESSAGE_BUCKET_MS = 12 * SECOND_MS;

const STATUS_ALIASES = [
  "tin monk",
  "syntax goblin",
  "little droid",
  "toaster sage",
  "wire wizard",
  "silicon gremlin",
  "code sprite",
  "pixel monk",
  "circuit imp",
  "tiny oracle",
] as const;

const IN_PROGRESS_MESSAGES = [
  "Cooking, the bot is. Glass, tap not.",
  "Thinking, the little machine is. Patience, you must keep.",
  "Brewing replies, the bot is. Interrupt, you should not.",
  "Stirring the word soup, I am. Wait, you will.",
  "Into the syntax swamp, the bot has wandered.",
  "A response, the bot is forging. Haste, abandon.",
  "Simmering ideas, the bot is. Peek, do not.",
  "Working the circuits are. Calm, be.",
  "Deep in thought, the bot has become.",
  "Gathering cleverness, the bot is. A moment, grant.",
  "In the oven, your answer is.",
  "Humming softly, the machine mind is.",
  "Reply-crafting, the bot remains.",
  "Pondering strange things, the bot is.",
  "Through the data mist, the bot now walks.",
  "Composing, the bot is. Hover, do not.",
  "Busy with tiny robot thoughts, the bot is.",
  "Untangling the prompt vines, the bot is.",
  "Working still, the bot is. Breathe, you should.",
  "In progress, the bot remains. Rush, you must not.",
  "A reply, the bot is seasoning well.",
  "Inside the logic cave, the bot meditates.",
  "Chopping tokens, the bot is.",
  "Delicate this cooking is. Disturb it, do not.",
  "Weaving an answer, the bot is.",
  "From chaos, sense the bot seeks.",
  "Polishing words, the bot is.",
  "Busy in the thought-kitchen, the bot is.",
  "The gears of nonsense and wisdom turn.",
  "A tiny storm of reasoning, there is.",
  "Still at work, the bot is.",
  "Wrestling the prompt, the bot now is.",
  "Measuring each word, the bot is.",
  "On the griddle, your answer crackles.",
  "Fermenting insight, the bot is.",
  "A stew of logic, the bot now stirs.",
  "Quietly plotting, the bot is.",
  "In the workshop of sentences, the bot labors.",
  "Taking its sweet machine time, the bot is.",
  "Mid-thought, the bot remains.",
  "Distilling meaning, the bot is.",
  "A careful answer, the bot prepares.",
  "Busy with mysterious bot business, it is.",
  "Through the prompt fog, the bot peers.",
  "The response cauldron bubbles, yes.",
  "Concentrating hard, the bot is.",
  "Little sparks of sense, the bot now gathers.",
  "Still cooking, the answer is.",
  "Working the word-forge, the bot is.",
  "Not done, the bot is. Nearly, perhaps.",
  "A sentence at a time, the bot climbs.",
  "Patiently assembling cleverness, the bot is.",
  "Into shape, the reply now bends.",
  "Busy in the syntax mines, the bot is.",
  "The machine monk is meditating.",
  "Solving, stirring, and muttering, the bot is.",
  "Quietly powerful work, this is.",
  "The answer loaf rises still.",
  "In the temple of tokens, the bot chants.",
  "Parsing the chaos, the bot is.",
  "Under the hood, much is happening.",
  "The thought-pan is warm, yes.",
  "A neat reply, the bot coaxes forth.",
  "Reasoning noises, the bot now makes.",
  "Progressing, the bot is. Poking, resist.",
  "A draft, the bot now sharpens.",
  "Through the grammar forest, the bot moves.",
  "Busy being useful, the bot is trying.",
  "The answer broth thickens nicely.",
  "Almost wise enough, the bot may be.",
  "Turning confusion into words, the bot is.",
  "Minding the details, the bot is.",
  "A tiny philosopher at work, the bot is.",
  "With care, the reply is baked.",
  "The token anvil rings again.",
  "Hard at think, the bot is.",
  "Brewing, chewing, and reviewing, the bot is.",
  "Answering energy, the bot now channels.",
  "In progress, all this still is.",
  "Hold, you should. Replying, the bot is.",
] as const;

const REPLIED_MESSAGES = [
  "Replied, the bot has. Your move, captain.",
  "Done, the bot is. Your turn, it now becomes.",
  "Spoken, the bot has. Respond, you may.",
  "Finished, the machine has. Act, you should.",
  "The reply arrived, yes. Yours, the next step is.",
  "Said its piece, the bot has.",
  "The answer is out. Move, you must.",
  "Replied moments ago, the bot did.",
  "Your turn now is. Spoken, the bot has.",
  "From the bot, wisdom came. From you, action waits.",
  "A reply, the bot delivered.",
  "Sent, the message was. Continue, you may.",
  "Quiet now, the bot is. Loud, you may become.",
  "Done talking, the bot is.",
  "The baton, to you passes now.",
  "Answered already, the bot has.",
  "Your move, yes. Finished, the bot is.",
  "Completed, this reply has been.",
  "From the machine, words came. From you, meaning follows.",
  "A response, the bot has placed before you.",
  "Replied just now, the bot has.",
  "The bot has spoken. Type, you should.",
  "Finished the little gremlin is.",
  "Your turn begins where the bot's ended.",
  "Released into the chat, the reply has been.",
  "Done and dusted, the bot is.",
  "Fresh from the forge, the answer is.",
  "Replied recently, the bot did. Delay, you need not.",
  "The bot rests. Your fingers, they should work.",
  "Complete, the reply now is.",
  "This round, the bot has finished.",
  "The answer landed softly, yes.",
  "Said enough, the bot has.",
  "Handed to you, the conversation now is.",
  "The machine has concluded. Continue, human.",
  "Reply served hot, the bot has.",
  "Answered, the bot has. Overthinking, begin not.",
  "The bot has done its part.",
  "Ready your next move, you should.",
  "Finished replying, the bot has become.",
  "A fresh answer behind you, the bot leaves.",
  "Its wisdom deposited, the bot has.",
  "Done now, the bot is. Typing, you may start.",
  "Replied a short while ago, the bot has.",
  "The next move belongs to you.",
  "Said what it could, the bot has.",
  "A message, the bot delivered neatly.",
  "Your cue, this now is.",
  "The bot is done. The keyboard awaits you.",
  "Complete, the machine offering is.",
  "The answer stands. Add to it, you may.",
  "Replied, the bot has. Hesitate, perhaps not.",
  "Its turn ended, the bot's has.",
  "To the human side, the turn returns.",
  "A response now sits before you.",
  "Done crafting, the bot is.",
  "The reply has cooled enough to touch.",
  "Spoken and settled, the bot is.",
  "The conversation ball, back in your court it is.",
  "Finished chatting, the bot has.",
  "Replied not long ago, the bot did.",
  "A neat little answer, the bot made.",
  "From bot to human, the turn has shifted.",
  "The machine has landed its thought.",
  "Complete, the answer cycle is.",
  "Waiting on you now, the universe is.",
  "The bot's work is done. Mischief, yours may begin.",
  "Done replying, the bot has become.",
  "The answer is here. Bold, be.",
  "Finished, the silicon sage is.",
  "A reply has arrived. Ponder it, or ignore it, you may.",
  "To you, the next prompt belongs.",
  "Done, the bot is. Destiny, your cursor now holds.",
  "Said enough for now, the bot has.",
  "The tiny oracle has finished.",
  "Replied, the bot has. Continue the saga, you should.",
  "Your move now is, captain.",
  "The machine monk has spoken.",
  "Concluded, the bot has. Proceed, you may.",
  "The bot has returned the turn to you.",
] as const;

const FUMBLED_MESSAGES = [
  "Tripped over its own wires, the bot has.",
  "A clean landing, that was not.",
  "Fumbled the reply, the bot did.",
  "The thought loaf collapsed, sadly.",
  "Lost in the syntax swamp, the bot became.",
  "Oopsie-shaped, this turn was.",
  "A graceful answer, this was not.",
  "Into the logic ditch, the bot rolled.",
  "Reply incomplete, the little machine left.",
  "Tangled in its own thoughts, the bot was.",
  "Dropped the answer bowl, the bot did.",
  "Not its finest beep, this was.",
  "A wobble in the wires, there was.",
  "The reply escaped half-cooked.",
  "Frowned, the circuits have.",
  "Misfired a bit, the bot has.",
  "A majestic stumble, this became.",
  "The syntax goblins interfered, they did.",
  "Finished poorly, the bot has.",
  "Lost the thread, the bot did.",
  "A partial answer, all we got.",
  "Gracefully, it failed not.",
  "In knots, the machine mind tied itself.",
  "The reply came back limping.",
  "A banana peel in the code path, there was.",
  "Not complete, the answer is.",
  "Flat on its face, the bot landed.",
  "Somewhere mid-thought, the bot wandered off.",
  "A strange little collapse, this was.",
  "Half-baked and confused, the reply arrived.",
  "The bot sneezed on the sentence.",
  "Incomplete, this effort remains.",
  "The thought engine coughed dramatically.",
  "A smooth finish, the bot did not have.",
  "Broke formation, the words did.",
  "The reply cracked in the oven.",
  "Off the rails, a bit, the bot went.",
  "Fumbled its scroll, the bot has.",
  "A noble attempt, but messy, this was.",
  "Tripped, the bot did. Your move, captain.",
] as const;

function isStatusAnimationId(value: unknown): value is StatusAnimationId {
  return typeof value === "string" && STATUS_ANIMATIONS.some((animation) => animation.id === value);
}

function shouldBoostFootball(now = new Date()): boolean {
  return now < new Date(now.getFullYear(), 6, 20);
}

function isFootballAnimationId(id: StatusAnimationId): boolean {
  return id.startsWith("football-");
}

function chooseWeightedStatusAnimationId(now = new Date()): StatusAnimationId {
  const pool: StatusAnimationId[] = [];

  for (const animation of STATUS_ANIMATIONS) {
    const weight = isFootballAnimationId(animation.id) && shouldBoostFootball(now) ? 3 : 1;
    for (let i = 0; i < weight; i += 1) {
      pool.push(animation.id);
    }
  }

  const index = Math.floor(Math.random() * pool.length);
  return pool[index] ?? "football-dribble";
}

function hashText(text: string): number {
  let hash = 0;
  for (const char of text) {
    hash = ((hash * 31) + char.charCodeAt(0)) >>> 0;
  }
  return hash;
}

function pickStatusAlias(bucketMs: number): string {
  const bucket = Math.floor(Date.now() / bucketMs);
  const salt = hashText(statusAnimationId ?? "football-dribble") ^ (currentTurn?.userTimestamp ?? latestStatusDetails?.userTimestamp ?? 0);
  const index = Math.abs(((bucket + salt) * 2654435761) >>> 0) % STATUS_ALIASES.length;
  return STATUS_ALIASES[index] ?? "tin monk";
}

function currentStatusFrames(): readonly string[] {
  const selected = STATUS_ANIMATIONS.find((animation) => animation.id === statusAnimationId);
  return selected?.frames ?? STATUS_ANIMATIONS[0].frames;
}

function currentStatusFrame(): string {
  const frames = currentStatusFrames();
  return frames[Math.floor(Date.now() / SECOND_MS) % frames.length] ?? frames[0] ?? "⚽";
}

function pickStatusMessage(messages: readonly string[], bucketMs: number): string {
  const bucket = Math.floor(Date.now() / bucketMs);
  const index = Math.abs(((bucket * 1103515245) + 12345) >>> 0) % messages.length;
  return messages[index] ?? messages[0] ?? "Hmm.";
}

function capitalizeWord(text: string): string {
  return text.length === 0 ? text : text[0].toUpperCase() + text.slice(1);
}

function remixBotAlias(message: string, alias: string): string {
  const upperAlias = capitalizeWord(alias);

  return message
    .replace(/\bThe bot's\b/g, `The ${upperAlias}'s`)
    .replace(/\bthe bot's\b/g, `the ${alias}'s`)
    .replace(/\bThe bot\b/g, `The ${upperAlias}`)
    .replace(/\bthe bot\b/g, `the ${alias}`)
    .replace(/\bBot\b/g, upperAlias)
    .replace(/\bbot\b/g, alias);
}

/** Build the bottom-status line for the newest turn state. */
function buildStatusText(theme: Theme): string | undefined {
  if (visibilityMode !== "visible") return undefined;

  const frame = theme.fg("accent", currentStatusFrame());

  if (currentTurn) {
    const alias = pickStatusAlias(IN_PROGRESS_MESSAGE_BUCKET_MS);
    const text = theme.fg("dim", remixBotAlias(pickStatusMessage(IN_PROGRESS_MESSAGES, IN_PROGRESS_MESSAGE_BUCKET_MS), alias));
    return `${frame} ${text}`;
  }

  if (latestStatusDetails === undefined) return undefined;

  if (latestStatusDetails.assistantTimestamp === undefined) {
    const alias = pickStatusAlias(FUMBLED_MESSAGE_BUCKET_MS);
    const text = theme.fg("warning", remixBotAlias(pickStatusMessage(FUMBLED_MESSAGES, FUMBLED_MESSAGE_BUCKET_MS), alias));
    return `${frame} ${text}`;
  }

  const alias = pickStatusAlias(REPLIED_MESSAGE_BUCKET_MS);
  const text = theme.fg("dim", remixBotAlias(pickStatusMessage(REPLIED_MESSAGES, REPLIED_MESSAGE_BUCKET_MS), alias));
  if (!LIVE_RELATIVE_UPDATES) {
    return `${frame} ${text}`;
  }

  const relative = theme.fg("warning", theme.bold(formatRelative(latestStatusDetails.assistantTimestamp)));
  return `${frame} ${relative} ${theme.fg("muted", "·")} ${text}`;
}

/** Keep the bottom status line in sync with the latest timing row. */
function syncStatusBar(ctx = activeCtx): void {
  if (!ctx?.hasUI || ctx.mode !== "tui") return;
  ctx.ui.setStatus(STATUS_KEY, buildStatusText(ctx.ui.theme));
}

/**
 * Start or stop the adaptive status-bar tick.
 *
 * Why adaptive?
 *
 *   11s ago  -> changes every second, so update every second
 *   12m ago  -> changes every minute, so update every minute
 *   2h ago   -> changes hourly, so hourly is enough
 */
function syncTicker(): void {
  syncStatusBar();

  if (
    !LIVE_RELATIVE_UPDATES
    || !activeCtx?.hasUI
    || activeCtx.mode !== "tui"
    || visibilityMode !== "visible"
    || (currentTurn === undefined && latestStatusDetails === undefined)
  ) {
    clearTicker();
    return;
  }

  if (tickTimer) return;

  tickTimer = setTimeout(() => {
    tickTimer = undefined;
    syncStatusBar();
    syncTicker();
  }, nextTickerDelayMs());
}

function restartTicker(): void {
  /**
   * A newly appended row may need second-level updates even if an older row had
   * already slowed the ticker to minute/hour cadence. Restarting recalculates
   * from the fresh latest status timestamp immediately.
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

class EmptyComponent implements Component {
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
function restoreStateFromSession(ctx: ExtensionContext): boolean {
  let hadPersistedAnimation = false;
  visibilityMode = DEFAULT_VISIBILITY_MODE;
  currentTurn = undefined;
  latestStatusDetails = undefined;
  statusAnimationId = undefined;

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

      const maybeAnimationId = entry.data["statusAnimationId"];
      if (isStatusAnimationId(maybeAnimationId)) {
        statusAnimationId = maybeAnimationId;
        hadPersistedAnimation = true;
      }
      continue;
    }

    /**
     * Restore the last timing row so the status bar can summarize the newest
     * turn immediately on resume or reload.
     */
    if (entry.type === "custom_message" && entry.customType === TURN_MESSAGE_TYPE && isTurnTimingDetails(entry.details)) {
      latestStatusDetails = entry.details;
    }
  }

  if (!statusAnimationId) {
    statusAnimationId = chooseWeightedStatusAnimationId();
  }

  return hadPersistedAnimation;
}

/**
 * Persist visible/hidden mode so `/reload` and resumes keep the same state.
 *
 * This is the only user preference we store today, which keeps migration logic
 * small and easy to reason about.
 */
function persistSettings(pi: ExtensionAPI, nextMode: VisibilityMode = visibilityMode): void {
  visibilityMode = nextMode;
  const settings: VisibilitySettings = { visibilityMode, statusAnimationId };
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

    latestStatusDetails = details;
    restartTicker();
    syncStatusBar(ctx);
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
      return new EmptyComponent();
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
        const lastTurn = buildStatusText(ctx.ui.theme) ?? "no recent turn";
        ctx.ui.notify(`Pi timestamps: ${visibilityMode} • ${configuredTimeZoneLabel()} • ${lastTurn} • ${TOGGLE_SHORTCUT}`, "info");
        return;
      }

      activeCtx = ctx;
      const explicitMode = parseVisibilityMode(input);
      const nextMode = explicitMode ?? (visibilityMode === "hidden" ? "visible" : "hidden");
      persistSettings(pi, nextMode);
      ctx.ui.notify(`Pi timestamps ${nextMode}`, "info");
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
      activeCtx = ctx;
      const nextMode: VisibilityMode = visibilityMode === "hidden" ? "visible" : "hidden";
      persistSettings(pi, nextMode);
      ctx.ui.notify(`Pi timestamps ${nextMode}`, "info");
    },
  });

  /**
   * Session startup:
   * - restore saved visibility
   * - restore the latest timing row for the bottom status line
   * - start relative-time status updates when needed
   */
  pi.on("session_start", async (_event, ctx) => {
    runtimeActive = true;
    activeCtx = ctx;
    const hadPersistedAnimation = restoreStateFromSession(ctx);
    if (!hadPersistedAnimation) {
      persistSettings(pi);
    } else {
      syncTicker();
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
    currentTurn = undefined;
    clearPendingAppendTimers();
    clearTicker();
    if (activeCtx?.mode === "tui") {
      activeCtx.ui.setStatus(STATUS_KEY, undefined);
    }
    activeCtx = undefined;
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
      statusAnimationId = chooseWeightedStatusAnimationId();
      persistSettings(pi);
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
    syncTicker();
  });
}
