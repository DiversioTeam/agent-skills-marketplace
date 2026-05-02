/**
 * ## Image Model Router Extension
 *
 * ### Problem
 * A text-only model like DeepSeek V4 Pro can't process images.  If you paste a
 * screenshot or reference `@path/to/diagram.png`, the model either ignores the
 * image or errors.  You need a **vision-capable model** to describe the image
 * first, then hand the description back to your main model as text.
 *
 * ### What this extension does
 *
 * ```
 * ┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
 * │  You paste   │     │  Extension      │     │  Vision model    │
 * │  an image    │────▶│  intercepts     │────▶│  (Codex / GPT /  │
 * │              │     │  the prompt     │     │   Claude / etc.) │
 * └──────────────┘     └─────────────────┘     └────────┬─────────┘
 *                                                       │
 *                                          text description of the image
 *                                                       │
 * ┌──────────────┐     ┌─────────────────┐              │
 * │  Main model  │◀────│  Description    │◀─────────────┘
 * │  (DeepSeek)  │     │  injected as    │
 * │  responds    │     │  user message   │
 * └──────────────┘     └─────────────────┘
 * ```
 *
 * ### Three entry points for images
 *
 * 1. **User input**   – pasted images, `@path/to/file.png` references
 *    → intercepted via pi's `input` event
 * 2. **Tool results** – the `read` tool returns image data for a file
 *    → intercepted via pi's `tool_result` event
 * 3. **Model response** – the model replies *"I can't see images"*
 *    → detected via pi's `agent_end` event and flagged
 *
 * ### Routing modes per model
 *
 * | Mode    | User input                          | Tool results                  |
 * |---------|-------------------------------------|-------------------------------|
 * | `auto`  | Route silently, no prompt           | Route silently                |
 * | `ask`   | Show a TUI dialog (the default)     | Route silently (model blocks) |
 * | `never` | Send images to the model as-is      | Send images to the model      |
 *
 * > *Why do tool results always route silently?*  When the LLM calls `read`
 * > on a file, it's blocked waiting for the tool result.  Showing a dialog
 * > during that wait is bad UX — the model times out.  We route instead.
 *
 * ### Self-correcting fallback chain
 *
 * The extension remembers which vision model *actually worked* last time
 * (`lastSuccessfulVision*`).  That model is tried **first** on every
 * subsequent call, ahead of the user's explicit "Always route" choice.
 *
 * ```
 * Run 1: GPT-5.1 Codex (explicit choice)  → fails (no API key)
 *        GPT-5.3 Codex (fallback)          → succeeds ✓
 *        → GPT-5.3 recorded as lastSuccessful
 *
 * Run 2: GPT-5.3 Codex (lastSuccessful)   → succeeds immediately ✓
 *        GPT-5.1 Codex (explicit choice)   → never reached
 * ```
 *
 * If GPT-5.1 later gets its API key fixed and succeeds, it becomes the
 * new `lastSuccessful` and moves back to the front.  The ordering
 * self-corrects without user intervention.
 *
 * ### Settings
 *
 * Run **`/image-router`** at any time to open the TUI settings panel.
 * Preferences are saved to `~/.pi/agent/image-router.json` and survive
 * restarts, new sessions, and worktrees.
 *
 * Environment variables for the default vision model:
 * ```
 * IMAGE_ROUTER_VISION_PROVIDER=openai-codex
 * IMAGE_ROUTER_VISION_MODEL=codex-1
 * ```
 * If not set, the extension auto-detects the first vision-capable model.
 */

import type { ExtensionAPI, ExtensionContext } from "@mariozechner/pi-coding-agent";
import { DynamicBorder, getAgentDir, getSettingsListTheme } from "@mariozechner/pi-coding-agent";
import {
	complete,
	type ImageContent,
	type Message,
	type Model,
	type TextContent,
} from "@mariozechner/pi-ai";
import {
	Container,
	type SelectItem,
	SelectList,
	type SettingItem,
	SettingsList,
	Text,
} from "@mariozechner/pi-tui";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * How the extension should behave for a specific main-model when images appear.
 *
 * ```
 * "auto"  ──▶ route silently, never ask
 * "ask"   ──▶ show a TUI prompt (the default when nothing is saved)
 * "never" ──▶ don't route; let the model deal with raw images
 * ```
 */
type RoutingMode = "auto" | "ask" | "never";

/**
 * Per-model routing preference.
 *
 * Stored keyed by `"provider/modelId"` inside `RouterPreferences.modelPrefs`.
 *
 * `visionProvider` / `visionModelId` — the user's explicitly chosen vision
 * model for this main model (set when they pick "Always route").
 *
 * `lastSuccessfulVision*` — which vision model actually worked last time.
 * Used to reorder the candidate list so known-good models are tried first
 * on subsequent calls.  Updated automatically after every successful route.
 */
interface ModelPreference {
	mode: RoutingMode;
	visionProvider?: string;
	visionModelId?: string;
	lastSuccessfulVisionProvider?: string;
	lastSuccessfulVisionModelId?: string;
}

/**
 * Top-level preferences persisted to `~/.pi/agent/image-router.json`.
 *
 * ```
 * RouterPreferences
 * ├── modelPrefs           per-model routing decisions
 * ├── defaultVision*       fallback vision model when per-model is unset
 * ├── detectResponses      whether to scan for "I can't see images" replies
 * └── version              schema version (written for future migrations;
 *                          ignored on read — loader accepts any version)
 * ```
 */
interface RouterPreferences {
	modelPrefs: Record<string, ModelPreference>;
	defaultVisionProvider?: string;
	defaultVisionModelId?: string;
	detectResponses: boolean;
	version: 1;
}

/**
 * Returned by the routing-prompt TUI dialog.
 *
 * `route` tells the caller whether to proceed with routing.
 * `rememberMode` is set when the user chose "Always" or "Never" so the
 * caller can persist that preference.
 */
interface RoutingDecision {
	route: boolean;
	visionProvider?: string;
	visionModelId?: string;
	rememberMode?: RoutingMode;
}

/**
 * Returned by `describeImagesWithFallback()`.
 *
 * `failures` lists every model that was tried and why it failed.
 * Empty when the first candidate succeeds; useful for debugging when
 * fallback was needed.
 */
interface DescriptionResult {
	description: string;
	visionModel: Model;
	failures: string[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Preferences file path: `~/.pi/agent/image-router.json`.
 *
 * Using a file (not `pi.appendEntry`) so preferences survive across
 * completely new pi sessions.  Session-based persistence only survives
 * within the same session branch — a fresh `/new` or new pi instance
 * loses everything, including `lastSuccessfulVision*`.
 */
const PREFS_FILE = join(getAgentDir(), "image-router.json");

const VISION_PROVIDER_ENV = process.env["IMAGE_ROUTER_VISION_PROVIDER"];
const VISION_MODEL_ID_ENV = process.env["IMAGE_ROUTER_VISION_MODEL"];

/** Base defaults.  Env-vars are captured at load time. */
const DEFAULTS: RouterPreferences = {
	modelPrefs: {},
	defaultVisionProvider: VISION_PROVIDER_ENV,
	defaultVisionModelId: VISION_MODEL_ID_ENV,
	detectResponses: true,
	version: 1,
};

/**
 * System prompt used when describing images from **user input** (pasted /
 * `@path`).  The goal is a *thorough* description because the main model
 * will reason about the image based solely on this text.
 */
const DESCRIPTION_SYSTEM_PROMPT = [
	"You are an image description assistant embedded in a coding agent.",
	"Describe the attached image(s) in thorough detail so that a developer",
	"who cannot see the image can fully understand its contents.",
	"",
	"Focus on:",
	"- What is shown (UI screenshots, diagrams, error messages, code, etc.)",
	"- Text content visible in the image (transcribe exactly if legible)",
	"- Layout, structure, and relationships between elements",
	"- Colors, icons, or visual indicators that carry meaning",
	"- Any technical details a developer would need",
	"",
	"Output ONLY the description — no preamble, no meta-commentary.",
].join("\n");

/**
 * System prompt used when describing images from **tool results** (e.g. the
 * `read` tool returning a PNG).  Tool-result descriptions appear inline
 * inside tool-result blocks, so we keep them short to avoid bloating the
 * LLM context window.
 *
 * The vision model also receives the user's most recent question as context
 * so it can focus its description on what the user actually cares about
 * (colors, layout, text content, etc.) rather than giving a generic summary.
 */
const TOOL_RESULT_DESCRIPTION_SYSTEM_PROMPT = [
	"You are an image description assistant embedded in a coding agent.",
	"Another model asked you to describe an image.  Summarize it concisely.",
	"",
	"You will receive the user's original question as context.  Tailor your",
	"description to answer what the user is asking about.  Examples:",
	"- User asks about colors → list specific hex values or color names",
	"- User asks about layout → describe the spatial arrangement",
	"- User asks 'what does this say?' → transcribe the visible text",
	"- User asks 'what's wrong?' → point out error states or anomalies",
	"",
	"Requirements:",
	"- Be concise — the description appears inline in a tool result",
	"- Prioritize what the user asked about over unrelated details",
	"- Keep the answer under 120 words when possible",
	"",
	"Output ONLY the description — no preamble, no meta-commentary.",
].join("\n");

/**
 * Regex patterns that a model might say when it received an image it can't
 * process.  We scan assistant messages for these after every turn (unless
 * `detectResponses` is off).
 *
 * Examples matched:
 *   "I cannot see the image you attached"
 *   "I'm a text-only model and can't process images"
 *   "I don't have vision capabilities"
 */
const CANT_SEE_IMAGE_PATTERNS = [
	/i cannot see/i,
	/i can't see/i,
	/i don't have vision/i,
	/i('m| am) (a )?text[- ]only/i,
	/i( can|'m )not (process|view|see|analyze|handle|read) (the |this )?image/i,
	/i don'?t support image/i,
	/i('m| am) unable to (view|see|process|analyze) (the )?image/i,
	/unable to (view|see|process) (the )?image/i,
	/no vision capabilit/i,
	/cannot process image/i,
];

/**
 * Model-name patterns that indicate a model is vision-capable even when its
 * metadata does not explicitly list `input: ["text", "image"]`.
 *
 * These are tested against **model identity only** (id + name, NOT provider)
 * to avoid false positives from provider names like "my-claude-proxy".
 */
const OPENAI_VISION_MODEL_PATTERNS = [
	/\bcodex\b/i,
	/\bgpt-5\b/i,
	/\bgpt-4\.1\b/i,
	/\bgpt-4o\b/i,
	/\bgpt-o3\b/i,
	/\bo3\b/i,
	/\bo4-mini\b/i,
	/\bgpt-image-1\b/i,
];

// ---------------------------------------------------------------------------
// State persistence
// ---------------------------------------------------------------------------

/**
 * In-memory preferences.  Mutated directly by handlers; persisted to
 * `~/.pi/agent/image-router.json` via `savePreferences()`.
 *
 * ## Why a file, not `pi.appendEntry()`?
 *
 * `pi.appendEntry()` writes to the **current Pi session** (a `.jsonl`
 * file).  That survives restarts when you *resume* a session, but a
 * completely new session (fresh `/new` or new pi instance) starts with
 * an empty branch — all persisted state is gone.
 *
 * For image-router this is a serious problem: the `lastSuccessfulVision*`
 * field records which vision model actually works, so the extension
 * stops retrying broken models.  If that resets on every new session,
 * the user sees the same GPT-5.1 → GPT-5.3 fallback dance every time.
 *
 * File-based persistence (`~/.pi/agent/image-router.json`) survives
 * ALL sessions, restarts, worktrees, and even pi upgrades.
 */
let preferences: RouterPreferences = { ...DEFAULTS, modelPrefs: {} };

/**
 * Build a stable key for a model: `"provider/modelId"`.
 *
 * Uses `indexOf("/")` + `slice` (not `split`) when parsing keys back
 * because model IDs can themselves contain slashes (e.g. OpenRouter
 * model ID `"anthropic/claude-3.5-sonnet"`).
 */
function modelKey(provider: string, modelId: string): string {
	return `${provider}/${modelId}`;
}

function modelKeyFromModel(m: Model): string {
	return modelKey(m.provider, m.id);
}

function getModelPref(prefs: RouterPreferences, m: Model): ModelPreference | undefined {
	return prefs.modelPrefs[modelKeyFromModel(m)];
}

function setModelPref(
	prefs: RouterPreferences,
	m: Model,
	pref: ModelPreference,
): void {
	prefs.modelPrefs[modelKeyFromModel(m)] = pref;
}

/**
 * Persist current preferences to `~/.pi/agent/image-router.json`.
 *
 * ## Why synchronous?
 *
 * The settings dialog calls `savePreferences()` on every ←→ value
 * change.  Async writes (`writeFile`) would race — multiple rapid
 * changes could interleave, causing data loss.  `writeFileSync`
 * guarantees each write completes before the next begins.
 *
 * The file is tiny (< 1 KB) so blocking the event loop for a
 * synchronous disk write is negligible.
 */
function savePreferences(): void {
	try {
		if (!existsSync(getAgentDir())) mkdirSync(getAgentDir(), { recursive: true });
		writeFileSync(PREFS_FILE, JSON.stringify(preferences, null, 2), "utf-8");
	} catch (err) {
		console.error("image-router: failed to save preferences:", err);
	}
}

/**
 * Load preferences from the JSON file.
 *
 * Called once when the extension starts (synchronous in the async factory).
 *
 * ## Upgrade compatibility
 *
 * The `version` field exists for future schema migrations but the loader
 * does NOT gate on it.  It always loads whatever JSON is on disk, fills
 * in `DEFAULTS` for any missing fields, and only falls back to defaults
 * when the file is completely unparseable (corrupt, not JSON, etc.).
 *
 * This means:
 * - Adding a new optional field → old files load fine (spread + defaults)
 * - Bumping the version number → old files still load (version is ignored
 *   on read; only used if we add explicit migration logic later)
 * - File is corrupt → safe fallback to defaults, no crash
 */
function loadPreferencesSync(): RouterPreferences {
	try {
		const data = readFileSync(PREFS_FILE, "utf-8");
		const parsed = JSON.parse(data);
		// Merge whatever we got with defaults — missing fields get default
		// values, unknown future fields are silently preserved via the spread.
		return {
			...DEFAULTS,
			...parsed,
			modelPrefs: parsed.modelPrefs ? { ...parsed.modelPrefs } : {},
		};
	} catch {
		// File doesn't exist (first run) or is corrupt — use defaults
	}
	return { ...DEFAULTS, modelPrefs: {} };
}

// ---------------------------------------------------------------------------
// Vision model resolution
// ---------------------------------------------------------------------------

/**
 * Human-readable label used in notifications and settings: `"openai/gpt-4o"`.
 */
function modelLabel(model: Model): string {
	return `${model.provider}/${model.name ?? model.id}`;
}

/**
 * Searchable text built from **model id + name only** (not provider).
 *
 * Why exclude the provider?  Earlier versions used `modelSearchText()` which
 * included `${model.provider}`, causing false-positive heuristic matches on
 * provider names like `"my-claude-proxy"`.  `modelIdentityText` fixes that.
 */
function modelIdentityText(model: Model): string {
	return `${model.id} ${model.name ?? ""}`.toLowerCase();
}

/**
 * Does the model *explicitly* declare image support in its metadata?
 *
 * This is the most reliable signal.  When `true`, we skip all heuristics.
 */
function modelAdvertisesImageInput(model: Model): boolean {
	return model.input?.includes("image") ?? false;
}

/**
 * Is this model likely able to process images?
 *
 * Used ONLY for fallback-model discovery in `getVisionCandidates`.
 * The active-model check (`currentModelSupportsImages`) uses only
 * explicit metadata — heuristics could false-match a text-only proxy
 * whose name happens to contain "codex" or "claude".
 *
 * ## Detection layers
 *
 * ```
 * modelLooksVisionCapable(model)
 * ├── model.input includes "image"?  ──yes──▶ true  (fast, reliable)
 * └── no
 *     ├── OpenAI pattern match?       ──yes──▶ true  (Codex, GPT-4o, etc.)
 *     ├── anthropic + "claude"?       ──yes──▶ true  (provider-scoped)
 *     ├── google + "gemini"?          ──yes──▶ true  (provider-scoped)
 *     ├── "claude" in identity?       ──yes──▶ true  (catch-all)
 *     └── "gemini" in identity?       ──yes──▶ true  (catch-all)
 *                                        └──▶ false
 * ```
 *
 * The provider-scoped checks (`anthropic + claude`, `google + gemini`)
 * require both the provider name AND the model identity to match, preventing
 * a provider named `"not-anthropic"` from matching just because it proxies a
 * model with `"claude"` in its name.
 *
 * The catch-all checks are a safety net for providers that serve Claude or
 * Gemini models under a different provider name.
 */
function modelLooksVisionCapable(model: Model): boolean {
	if (modelAdvertisesImageInput(model)) return true;

	const identity = modelIdentityText(model);
	const provider = model.provider.toLowerCase();

	if (OPENAI_VISION_MODEL_PATTERNS.some((pattern) => pattern.test(identity))) {
		return true;
	}
	if (provider.includes("anthropic") && /\bclaude\b/i.test(identity)) return true;
	if (provider.includes("google") && /\bgemini\b/i.test(identity)) return true;
	if (/\bclaude\b/i.test(identity)) return true;
	if (/\bgemini\b/i.test(identity)) return true;

	return false;
}

/**
 * Priority score for ranking vision-model candidates.
 *
 * Higher = tried earlier.  Base score is 1000 for models that explicitly
 * advertise image input, 0 otherwise.  Bonuses use `else-if` (exclusive
 * tiers) because a single model can't belong to multiple families.
 *
 * ```
 * Codex          +500  = 1500  (top tier — user's preferred)
 * GPT-5/4.1/4o   +450  = 1450
 * Claude         +400  = 1400
 * Gemini         +350  = 1350
 * GPT-image-1    +250  = 1250
 * unknown        +0    = 1000  (advertises image input but no bonus)
 * ```
 */
function visionPriorityScore(model: Model): number {
	const text = modelIdentityText(model);
	let score = modelAdvertisesImageInput(model) ? 1000 : 0;

	if (/\bcodex\b/i.test(text)) score += 500;
	else if (/\bgpt-5\b|\bgpt-4\.1\b|\bgpt-4o\b|\bo3\b|\bo4-mini\b/i.test(text)) score += 450;
	else if (/\bclaude\b/i.test(text)) score += 400;
	else if (/\bgemini\b/i.test(text)) score += 350;
	else if (/\bgpt-image-1\b/i.test(text)) score += 250;

	return score;
}

/**
 * Build an ordered list of vision-model candidates to try.
 *
 * ## Candidate ordering (first to last)
 *
 * ```
 * 1. Last-successful model              (auto-remembered after each route)
 * 2. Explicit per-model vision model    (user set via "Always route")
 * 3. Caller-provided preferred model    (from routing-prompt choice)
 * 4. Default vision model               (env var or /image-router setting)
 * 5. All available vision models        (sorted by priority score)
 * ```
 *
 * Deduplication is done by model key so the same model never appears twice.
 *
 * The `lastSuccessful` slot (1) outranks the explicit per-model choice.
 * When the explicit choice works, it becomes the `lastSuccessful` on the
 * next call and retains the top slot.  When it fails and a different model
 * succeeds, the working model takes slot 1 and the broken choice drops to
 * slot 2 — so the extension stops wasting time on known-broken models.
 */
function getVisionCandidates(
	ctx: ExtensionContext,
	pref?: ModelPreference,
	preferredModel?: Model,
): Model[] {
	const candidates: Model[] = [];
	const seen = new Set<string>();

	const pushCandidate = (model: Model | undefined) => {
		if (!model) return;
		if (!modelLooksVisionCapable(model)) return;
		const key = modelKeyFromModel(model);
		if (seen.has(key)) return;
		seen.add(key);
		candidates.push(model);
	};

	// 1. Last model that actually worked for this main model
	if (pref?.lastSuccessfulVisionProvider && pref?.lastSuccessfulVisionModelId) {
		pushCandidate(
			ctx.modelRegistry.find(
				pref.lastSuccessfulVisionProvider,
				pref.lastSuccessfulVisionModelId,
			),
		);
	}

	// 2. Per-model explicit choice
	if (pref?.visionProvider && pref?.visionModelId) {
		pushCandidate(ctx.modelRegistry.find(pref.visionProvider, pref.visionModelId));
	}

	// 3. Caller's preferred model (from routing prompt)
	pushCandidate(preferredModel);

	// 4. Global default
	if (preferences.defaultVisionProvider && preferences.defaultVisionModelId) {
		pushCandidate(
			ctx.modelRegistry.find(
				preferences.defaultVisionProvider,
				preferences.defaultVisionModelId,
			),
		);
	}

	// 5. All other vision-capable models, sorted by priority
	const available = [...ctx.modelRegistry.getAvailable()]
		.filter((model) => modelLooksVisionCapable(model))
		.sort((a, b) => {
			const scoreDelta = visionPriorityScore(b) - visionPriorityScore(a);
			if (scoreDelta !== 0) return scoreDelta;
			return modelLabel(a).localeCompare(modelLabel(b));
		});

	for (const model of available) pushCandidate(model);

	return candidates;
}

/**
 * Convenience: return the *first* candidate from `getVisionCandidates`.
 * Used when we only need to display a model name (routing prompt, etc.).
 */
function findVisionModelForPref(
	ctx: ExtensionContext,
	pref?: ModelPreference,
): Model | undefined {
	return getVisionCandidates(ctx, pref)[0];
}

/**
 * Does the **currently active** model support images?
 *
 * Only checks explicit metadata (`model.input.includes("image")`).
 * Name heuristics are NOT used here — they're only for fallback model
 * discovery in `getVisionCandidates`.  A text-only model whose name
 * happens to match a vision family must still go through routing.
 */
function currentModelSupportsImages(ctx: ExtensionContext): boolean {
	return ctx.model ? modelAdvertisesImageInput(ctx.model) : false;
}

/**
 * Record which vision model succeeded so future candidate lists try it earlier.
 *
 * Called after every successful `describeImagesWithFallback()`.
 *
 * Creates a preference entry with mode `"ask"` if none exists yet — this is
 * the default mode, so functionally equivalent to having no entry but with
 * the bonus of `lastSuccessfulVision*` being recorded.
 */
function rememberSuccessfulVisionModel(
	ctx: ExtensionContext,
	visionModel: Model,
): void {
	if (!ctx.model) return;

	const pref = getModelPref(preferences, ctx.model) ?? { mode: "ask" as RoutingMode };
	setModelPref(preferences, ctx.model, {
		...pref,
		lastSuccessfulVisionProvider: visionModel.provider,
		lastSuccessfulVisionModelId: visionModel.id,
	});
}

// ---------------------------------------------------------------------------
// Image description
// ---------------------------------------------------------------------------

/**
 * Call a vision model with one or more images and get back a text description.
 *
 * The `systemPrompt` tells the model *how* to describe (thorough vs. concise).
 * The `contextHint` is optional extra context appended to the user message
 * (e.g. the user's original text, or the tool/file path).
 *
 * Only the `systemPrompt` is sent as a system message; the user message
 * contains just `contextHint` + images.  This avoids duplicating the system
 * prompt inside the user message, which wasted ~100 tokens per call.
 */
async function describeImages(
	visionModel: Model,
	auth: { apiKey: string; headers?: Record<string, string> },
	images: ImageContent[],
	contextHint: string,
	systemPrompt: string,
	signal?: AbortSignal,
): Promise<string> {
	const content: (TextContent | ImageContent)[] = [];
	if (contextHint.trim()) {
		content.push({ type: "text", text: contextHint });
	}
	content.push(...images);

	const userMessage: Message = {
		role: "user",
		content,
		timestamp: Date.now(),
	};

	const response = await complete(
		visionModel,
		{
			systemPrompt,
			messages: [userMessage],
		},
		{ apiKey: auth.apiKey, headers: auth.headers, signal },
	);

	const description = response.content
		.filter((c): c is TextContent => c.type === "text")
		.map((c) => c.text)
		.join("\n")
		.trim();

	if (!description) {
		throw new Error("Vision model returned an empty description");
	}

	return description;
}

/**
 * Resolve the API key and headers for a vision model.
 *
 * `options.notify` (default `true`) controls whether a missing-key error
 * notification is shown.  Set to `false` inside fallback loops where
 * individual "missing key" warnings would be noisy.
 */
async function resolveVisionAuth(
	ctx: ExtensionContext,
	visionModel: Model,
	options?: { notify?: boolean },
): Promise<{ apiKey: string; headers?: Record<string, string> } | undefined> {
	const auth = await ctx.modelRegistry.getApiKeyAndHeaders(visionModel);
	if (!auth.ok || !auth.apiKey) {
		if (options?.notify !== false) {
			ctx.ui.notify(
				`No API key for vision model ${visionModel.provider}/${visionModel.id}`,
				"error",
			);
		}
		return undefined;
	}
	return { apiKey: auth.apiKey, headers: auth.headers };
}

/**
 * Describe images using a **fallback chain** of vision models.
 *
 * ```
 * describeImagesWithFallback(images, hint)
 * │
 * ├── getVisionCandidates()  →  [codex-1, gpt-4o, claude-sonnet-4, …]
 * │
 * └── for each candidate:
 *       ├── resolve auth  ──no key──▶ skip, record failure, next
 *       └── call describeImages()
 *             ├── success ▶ return { description, visionModel, failures }
 *             └── error   ▶ record failure, next
 *
 * If all candidates fail: throw with aggregated error message.
 * ```
 *
 * ## Why a fallback chain?
 *
 * A single vision model can be unavailable for many reasons:
 * - API key not configured for that provider
 * - Rate-limited or temporarily down
 * - Model deprecation / name change
 *
 * Iterating through candidates means the extension keeps working as long as
 * *any* vision-capable model is reachable.
 *
 * ## Notifications
 *
 * - One announcement when the first candidate is attempted.
 * - If fallback *actually occurs* (≥1 prior failure), a notification tells
 *   the user which model was used and suggests `/image-router` to pin a
 *   preferred model.
 * - Individual "missing API key" warnings are suppressed inside the loop;
 *   only the aggregated outcome is shown.
 */
async function describeImagesWithFallback(
	ctx: ExtensionContext,
	images: ImageContent[],
	contextHint: string,
	pref?: ModelPreference,
	preferredModel?: Model,
	options?: { announce?: string; systemPrompt?: string },
): Promise<DescriptionResult> {
	const candidates = getVisionCandidates(ctx, pref, preferredModel);
	if (candidates.length === 0) {
		throw new Error("No vision-capable model available");
	}

	const failures: string[] = [];
	let announced = false;
	const systemPrompt = options?.systemPrompt ?? DESCRIPTION_SYSTEM_PROMPT;

	for (const candidate of candidates) {
		// Announce once with the first candidate attempted
		if (!announced && options?.announce) {
			ctx.ui.notify(
				`${options.announce} via ${modelLabel(candidate)}…`,
				"info",
			);
			announced = true;
		}

		// Suppress individual "no key" errors — the fallback summary covers them
		const auth = await resolveVisionAuth(ctx, candidate, { notify: false });
		if (!auth) {
			failures.push(`${modelLabel(candidate)}: missing API key`);
			continue;
		}

		try {
			const description = await describeImages(
				candidate,
				auth,
				images,
				contextHint,
				systemPrompt,
				ctx.signal,
			);

			// Only notify when fallback actually kicked in (prior candidates failed)
			if (failures.length > 0) {
				ctx.ui.notify(
					`Image routing used ${modelLabel(candidate)} after ${failures.length} fallback ${failures.length === 1 ? "attempt" : "attempts"}. Set a custom fallback model with /image-router.`,
					"info",
				);
			}
			return { description, visionModel: candidate, failures };
		} catch (err) {
			const message = err instanceof Error ? err.message : String(err);
			failures.push(`${modelLabel(candidate)}: ${message}`);
		}
	}

	throw new Error(`All vision models failed: ${failures.join("; ")}`);
}

// ---------------------------------------------------------------------------
// Smart detection: model responses
// ---------------------------------------------------------------------------

/**
 * Does this text contain a phrase like "I can't see images"?
 *
 * Used by `agent_end` to detect models that claim image support in their
 * metadata but reply with an error when actually given images.
 */
function messageSaysCannotSeeImages(text: string): boolean {
	return CANT_SEE_IMAGE_PATTERNS.some((p) => p.test(text));
}

// ---------------------------------------------------------------------------
// TUI: Routing prompt dialog
// ---------------------------------------------------------------------------

interface PromptChoice {
	value: string;
	label: string;
	description: string;
}

/**
 * Show the user a TUI dialog asking what to do with images.
 *
 * ```
 * ┌─────────────────────────────────────────────┐
 * │  Image Routing                               │
 * │                                              │
 * │  deepseek-v4-pro doesn't support images.     │
 * │  2 image(s) detected in your input.          │
 * │                                              │
 * │  ✓  Route this time                          │
 * │  ✓  Always route for this model              │
 * │  →  Send images anyway                       │
 * │  ✗  Never route for this model               │
 * │                                              │
 * │  ↑↓ navigate  •  enter select  •  esc cancel │
 * └─────────────────────────────────────────────┘
 * ```
 *
 * The "Route this time" / "Always route" choices only appear when at least
 * one vision-capable model is available.  Otherwise the user can only
 * choose "Send anyway" or "Never route".
 *
 * Returns a `RoutingDecision` — the caller applies the choice and saves
 * preferences if `rememberMode` is set.
 */
async function showRoutingPrompt(
	ctx: ExtensionContext,
	currentModel: Model,
	visionModel: Model | undefined,
	imageCount: number,
): Promise<RoutingDecision> {
	const modelName = currentModel.name ?? currentModel.id;
	const visionName = visionModel
		? `${visionModel.provider}/${visionModel.name ?? visionModel.id}`
		: "(none available)";

	const choices: PromptChoice[] = [];

	// Route-options are only meaningful when a vision model exists
	if (visionModel) {
		choices.push({
			value: "route-once",
			label: "✓  Route this time",
			description: `Describe image(s) with ${visionName}`,
		});
		choices.push({
			value: "route-always",
			label: "✓  Always route for this model",
			description: `Remember: always route to ${visionName}`,
		});
	}

	choices.push(
		{
			value: "send-anyway",
			label: "→  Send images anyway",
			description: "Let the model try (may fail)",
		},
		{
			value: "never",
			label: "✗  Never route for this model",
			description: "Skip routing, don't ask again",
		},
	);

	const result = await ctx.ui.custom<PromptChoice | null>(
		(tui, theme, _kb, done) => {
			const container = new Container();

			container.addChild(new DynamicBorder((s) => theme.fg("accent", s)));

			container.addChild(
				new Text(
					theme.fg("accent", theme.bold("  Image Routing")),
				),
			);
			container.addChild(new Text(""));

			container.addChild(
				new Text(
					`  ${theme.fg("warning", modelName)} doesn't support image input.`,
				),
			);
			container.addChild(
				new Text(
					`  ${imageCount} image(s) detected in your input.`,
				),
			);
			container.addChild(new Text(""));

			const items: SelectItem[] = choices.map((c) => ({
				value: c.value,
				label: c.label,
				description: c.description,
			}));

			const selectList = new SelectList(items, Math.min(items.length, 6), {
				selectedPrefix: (text) => theme.fg("accent", text),
				selectedText: (text) => theme.fg("accent", text),
				description: (text) => theme.fg("muted", text),
				scrollInfo: (text) => theme.fg("dim", text),
				noMatch: (text) => theme.fg("warning", text),
			});

			selectList.onSelect = (item) => {
				const choice = choices.find((c) => c.value === item.value);
				done(choice ?? null);
			};
			selectList.onCancel = () => done(null);

			container.addChild(selectList);
			container.addChild(new Text(""));
			container.addChild(
				new Text(
					theme.fg("dim", "  ↑↓ navigate  •  enter select  •  esc cancel"),
				),
			);

			container.addChild(new DynamicBorder((s) => theme.fg("accent", s)));

			return {
				render(width: number) {
					return container.render(width);
				},
				invalidate() {
					container.invalidate();
				},
				handleInput(data: string) {
					selectList.handleInput(data);
					tui.requestRender();
				},
			};
		},
	);

	if (!result) {
		return { route: false }; // user pressed escape
	}

	switch (result.value) {
		case "route-once":
			return {
				route: true,
				visionProvider: visionModel?.provider,
				visionModelId: visionModel?.id,
			};
		case "route-always":
			return {
				route: true,
				visionProvider: visionModel?.provider,
				visionModelId: visionModel?.id,
				rememberMode: "auto",
			};
		case "send-anyway":
			return { route: false };
		case "never":
			return { route: false, rememberMode: "never" };
		default:
			return { route: false };
	}
}

// ---------------------------------------------------------------------------
// TUI: Settings dialog
// ---------------------------------------------------------------------------

/**
 * Open the settings panel via `/image-router`.
 *
 * ## Why `SettingsList`?
 *
 * Pi's built-in `SettingsList` component handles ALL keyboard input
 * correctly across terminals — arrow keys, Enter, Escape, everything.
 * Earlier versions of this extension tried custom TUI components with
 * manual keyboard handling and consistently broke on different terminals.
 * `SettingsList` just works.
 *
 * ## Controls
 *
 * - **Enter / Space** — cycle the selected setting's value
 * - **↑↓** — navigate between settings
 * - **Esc** — close the panel
 *
 * ## What you can configure
 *
 * - **Default vision model** — which model to use when no per-model
 *   preference is set.  `(auto-detect)` means the extension picks the
 *   first available vision-capable model.
 * - **Detect responses** — whether to scan assistant messages for
 *   "I can't see images" and show a warning notification.
 * - **Per-model routing** — `auto` (route silently), `ask` (show a
 *   prompt), or `never` (send images as-is).  Shows `(last: ...)` when
 *   a `lastSuccessfulVision*` is recorded, confirming the self-correcting
 *   fallback is working.
 *
 * Changes are persisted immediately to `~/.pi/agent/image-router.json`.
 */
async function showSettingsDialog(
	ctx: ExtensionContext,
): Promise<void> {
	const knownModels = new Map<string, { provider: string; id: string; name: string }>();

	if (ctx.model) {
		const key = modelKeyFromModel(ctx.model);
		knownModels.set(key, {
			provider: ctx.model.provider,
			id: ctx.model.id,
			name: ctx.model.name ?? ctx.model.id,
		});
	}

	for (const key of Object.keys(preferences.modelPrefs)) {
		if (!knownModels.has(key)) {
			const slash = key.indexOf("/");
			const provider = key.slice(0, slash);
			const id = key.slice(slash + 1);
			knownModels.set(key, { provider, id, name: id });
		}
	}

	const visionModels = ctx.modelRegistry
		.getAvailable()
		.filter((m) => modelLooksVisionCapable(m))
		.map((m) => `${m.provider}/${m.id}`);

	const visionModelValues = visionModels.length > 0
		? ["(auto-detect)", ...visionModels]
		: ["(none available)"];

	const currentDefaultVision = preferences.defaultVisionProvider && preferences.defaultVisionModelId
		? `${preferences.defaultVisionProvider}/${preferences.defaultVisionModelId}`
		: "(auto-detect)";

	const items: SettingItem[] = [
		{
			id: "defaultVision",
			label: "Default vision model",
			currentValue: currentDefaultVision,
			values: visionModelValues,
		},
		{
			id: "detectResponses",
			label: 'Detect "can\'t see images" responses',
			currentValue: preferences.detectResponses ? "on" : "off",
			values: ["on", "off"],
		},
	];

	for (const [key, info] of knownModels) {
		const pref = preferences.modelPrefs[key];
		const lastUsed = pref?.lastSuccessfulVisionProvider && pref?.lastSuccessfulVisionModelId
			? ` (last: ${pref.lastSuccessfulVisionProvider}/${pref.lastSuccessfulVisionModelId})`
			: "";
		items.push({
			id: `model:${key}`,
			label: `${info.name}${lastUsed}`,
			currentValue: pref?.mode ?? "ask",
			values: ["auto", "ask", "never"],
		});
	}

	await ctx.ui.custom((tui, theme, _kb, done) => {
		const container = new Container();

		container.addChild(new DynamicBorder((s) => theme.fg("accent", s)));
		container.addChild(new Text(theme.fg("accent", theme.bold("  Image Router"))));
		container.addChild(new Text(""));

		const settingsList = new SettingsList(
			items,
			Math.min(items.length + 2, 20),
			getSettingsListTheme(),
			(id, newValue) => {
				if (id === "defaultVision") {
					if (newValue === "(auto-detect)") {
						preferences.defaultVisionProvider = undefined;
						preferences.defaultVisionModelId = undefined;
					} else if (newValue === "(none available)") {
					// No vision models registered — keep current setting
				} else {
						const slash = newValue.indexOf("/");
						preferences.defaultVisionProvider = newValue.slice(0, slash);
						preferences.defaultVisionModelId = newValue.slice(slash + 1);
					}
				} else if (id === "detectResponses") {
					preferences.detectResponses = newValue === "on";
				} else if (id.startsWith("model:")) {
					const mk = id.slice("model:".length);
					preferences.modelPrefs[mk] = {
						...preferences.modelPrefs[mk],
						mode: newValue as RoutingMode,
					};
				}
				savePreferences();
			},
			() => done(undefined),
		);

		container.addChild(settingsList);
		container.addChild(new Text(""));
		container.addChild(new Text(theme.fg("dim", "  enter/space to change  •  esc to close")));
		container.addChild(new DynamicBorder((s) => theme.fg("accent", s)));

		return {
			render(width: number) {
				return container.render(width);
			},
			invalidate() {
				container.invalidate();
			},
			handleInput(data: string) {
				settingsList.handleInput(data);
				tui.requestRender();
			},
		};
	});

	ctx.ui.notify("Image router preferences updated", "success");
}


function formatDescription(description: string, imageCount: number): string {
	return imageCount === 1
		? `[Image described by vision model:\n${description}\n]`
		: `[${imageCount} images described by vision model:\n${description}\n]`;
}

/**
 * Split a content array into text blocks and image blocks.
 *
 * Used by the `tool_result` handler to separate the original text (which we
 * preserve) from the image blocks (which we replace with descriptions).
 */
function partitionContent(
	content: readonly (TextContent | ImageContent)[],
): { textBlocks: TextContent[]; imageBlocks: ImageContent[] } {
	const textBlocks: TextContent[] = [];
	const imageBlocks: ImageContent[] = [];
	for (const block of content) {
		if (block.type === "text") textBlocks.push(block);
		else imageBlocks.push(block);
	}
	return { textBlocks, imageBlocks };
}

// ---------------------------------------------------------------------------
// Extension entry point
// ---------------------------------------------------------------------------

export default async function (pi: ExtensionAPI) {
	// ## Startup: load preferences before anything else
	//
	// `pi.appendEntry()` is session-scoped — it doesn't survive fresh
	// sessions.  We use a file instead.  `loadPreferencesSync()` reads
	// `~/.pi/agent/image-router.json` synchronously before any handlers
	// register, so preferences (including `lastSuccessfulVision*`) are
	// available from the very first user input.
	//
	// The factory is `async` even though loading is synchronous — this
	// is harmless and leaves the door open for async init in the future.
	preferences = loadPreferencesSync();

	// ── Command: /image-router ────────────────────────────────────────

	pi.registerCommand("image-router", {
		description: "Configure image model routing preferences",
		handler: async (_args, ctx) => {
			await showSettingsDialog(ctx);
		},
	});

	// ── Handler 1: User input ─────────────────────────────────────────
	//
	// Fires for pasted images and @path references.  Guard clauses exit
	// early when there's nothing to do:
	//
	//   1. No images?                          — skip
	//   2. Our own injected message?           — skip (recursion guard)
	//   3. Current model supports images?      — skip (native handling)
	//   4. No active model?                    — skip (shouldn't happen)
	//   5. Preference is "never"?              — skip (user opted out)
	//
	// Then the handler branches on the saved routing mode:
	//
	//   "auto"  → describeImagesWithFallback → replace prompt → handled
	//   "ask"   → showRoutingPrompt → if route: describe → replace → handled
	//                                  if not route: continue (let through)
	//
	// After a successful route, `rememberSuccessfulVisionModel()` updates
	// the candidate ordering so the model that worked is tried first next
	// time.

	pi.on("input", async (event, ctx) => {
		if (!event.images?.length) return { action: "continue" };
		if (event.source === "extension") return { action: "continue" };
		if (currentModelSupportsImages(ctx)) return { action: "continue" };
		if (!ctx.model) return { action: "continue" };

		const currentModel = ctx.model;
		const existingPref = getModelPref(preferences, currentModel);

		if (existingPref?.mode === "never") return { action: "continue" };

		// ── Auto mode: route silently ──────────────────────────────
		if (existingPref?.mode === "auto") {
			try {
				const { description, visionModel } = await describeImagesWithFallback(
					ctx,
					event.images,
					event.text,            // user's original text as context hint
					existingPref,
					undefined,
					{ announce: `Describing ${event.images.length} image(s)` },
				);
				rememberSuccessfulVisionModel(ctx, visionModel);
				savePreferences();
				const replacementText = event.text.trim()
					? `${formatDescription(description, event.images.length)}\n\n${event.text}`
					: formatDescription(description, event.images.length);

				pi.sendUserMessage(replacementText);
			} catch (err) {
				const msg = err instanceof Error ? err.message : String(err);
				ctx.ui.notify(`Image description failed: ${msg}`, "error");
				const fallback = event.text.trim()
					? `[Image(s) could not be described: ${msg}]\n\n${event.text}`
					: `[Image(s) could not be described: ${msg}]`;
				pi.sendUserMessage(fallback);
			}
			return { action: "handled" };
		}

		// ── Ask mode (default): show TUI prompt ────────────────────
		// In headless/RPC contexts there is no TUI — fall back to auto.
		if (!ctx.hasUI) {
			// Re-run as auto mode
			try {
				const { description, visionModel: vm } = await describeImagesWithFallback(
					ctx, event.images, event.text, existingPref, undefined,
					{ announce: `Describing ${event.images.length} image(s)` },
				);
				rememberSuccessfulVisionModel(ctx, vm);
				savePreferences();
				pi.sendUserMessage(event.text.trim()
					? `${formatDescription(description, event.images.length)}\n\n${event.text}`
					: formatDescription(description, event.images.length));
			} catch (err) {
				const msg = err instanceof Error ? err.message : String(err);
				ctx.ui.notify(`Image description failed: ${msg}`, "error");
				const fallback = event.text.trim()
					? `[Image(s) could not be described: ${msg}]\n\n${event.text}`
					: `[Image(s) could not be described: ${msg}]`;
				pi.sendUserMessage(fallback);
			}
			return { action: "handled" };
		}

		const visionModel = findVisionModelForPref(ctx, existingPref);
		const decision = await showRoutingPrompt(
			ctx,
			currentModel,
			visionModel,
			event.images.length,
		);

		// Persist "Always"/"Never" if the user chose to remember
		if (decision.rememberMode) {
			setModelPref(preferences, currentModel, {
				mode: decision.rememberMode,
				visionProvider: decision.visionProvider,
				visionModelId: decision.visionModelId,
			});
			savePreferences();
		}

		if (!decision.route) {
			return { action: "continue" }; // user chose "send anyway" or cancelled
		}

		// Resolve which vision model the user picked
		const chosenVisionModel = (decision.visionProvider && decision.visionModelId)
			? ctx.modelRegistry.find(decision.visionProvider, decision.visionModelId)
			: visionModel;

		try {
			const { description, visionModel: successfulModel } = await describeImagesWithFallback(
				ctx,
				event.images,
				event.text,
				existingPref,
				chosenVisionModel,
				{ announce: `Describing ${event.images.length} image(s)` },
			);
			rememberSuccessfulVisionModel(ctx, successfulModel);
			savePreferences();
			const replacementText = event.text.trim()
				? `${formatDescription(description, event.images.length)}\n\n${event.text}`
					: formatDescription(description, event.images.length);

			pi.sendUserMessage(replacementText);
			ctx.ui.notify(
				`Image(s) described by ${successfulModel.name ?? successfulModel.id}`,
				"success",
			);
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			ctx.ui.notify(`Image description failed: ${msg}`, "error");
			const fallback = event.text.trim()
				? `[Image(s) could not be described: ${msg}]\n\n${event.text}`
				: `[Image(s) could not be described: ${msg}]`;
			pi.sendUserMessage(fallback);
		}

		return { action: "handled" };
	});

	// ── Handler 2: Tool results ───────────────────────────────────────
	//
	// Fires when any tool returns content that includes image blocks.
	// In practice this is always the `read` tool reading a PNG / JPEG.
	//
	// Unlike user input, we cannot show a dialog here because the LLM is
	// blocked waiting for the tool result.  So we route silently whenever
	// existingPref is not "never".
	//
	// ## Why extract the user's question?
	//
	// Without the user's question, the vision model has no idea *why*
	// it's describing the image.  It gives a generic summary like
	// "a dashboard with purple gradient" — which is useless when the
	// user asked "what specific colors are used here?"
	//
	// By walking the conversation branch backward to find the most
	// recent user message and appending it to the context hint, the
	// vision model can tailor its description:
	//
	//   User: "what colors are used here?"
	//     → Vision model lists hex values: `#7c69bd, #6a55b4, …`
	//
	//   User: "what does this error say?"
	//     → Vision model transcribes the error text verbatim
	//
	//   User: "is the layout broken?"
	//     → Vision model describes misalignments or overlaps
	//
	// This eliminates the frustrating pattern where DeepSeek receives
	// a generic description, can't answer the user's question, and
	// falls back to writing Python to re-analyze the image.

	pi.on("tool_result", async (event, ctx) => {
		const { textBlocks, imageBlocks } = partitionContent(event.content);
		if (imageBlocks.length === 0) return;
		if (currentModelSupportsImages(ctx)) return;
		if (!ctx.model) return;

		const currentModel = ctx.model;
		const existingPref = getModelPref(preferences, currentModel);

		if (existingPref?.mode === "never") return;

		try {
			// Build a context hint that includes the user's original question.
			// Without this the vision model has no idea *why* it's describing
			// the image and gives a generic summary that may miss what the user
			// actually cares about (colors, specific text, layout, etc.).
			let contextHint = `Tool "${event.toolName}" returned ${imageBlocks.length} image(s).`;
			const input = event.input as Record<string, unknown> | undefined;
			if (input && typeof input === "object" && "path" in input) {
				contextHint += ` File: ${String(input.path)}`;
			}

			// Pull the most recent user message so the vision model knows what
			// the user is asking about (colors? layout? error messages? etc.).
			const branch = ctx.sessionManager.getBranch();
			for (let i = branch.length - 1; i >= 0; i--) {
				const entry = branch[i];
				if (entry.type === "message" && entry.message.role === "user") {
					const text = typeof entry.message.content === "string"
						? entry.message.content
						: (entry.message.content as TextContent[])
							?.filter((c) => c.type === "text")
							.map((c) => c.text)
							.join(" ") ?? "";
					if (text.trim()) {
						contextHint += `\n\nUser's question: """\n${text.trim()}\n"""\n\nDescribe the image with the user's question in mind.`;
					}
					break;
				}
			}

			const { description, visionModel } = await describeImagesWithFallback(
				ctx,
				imageBlocks,
				contextHint,
				existingPref,
				undefined,
				{
					announce: `Describing ${imageBlocks.length} image(s) from ${event.toolName} result`,
					systemPrompt: TOOL_RESULT_DESCRIPTION_SYSTEM_PROMPT,
				},
			);
			rememberSuccessfulVisionModel(ctx, visionModel);
			savePreferences();

			// Replace image blocks with a single text description block,
			// preserving any original text blocks from the tool result.
			const replacementBlock: TextContent = {
				type: "text",
				text: formatDescription(description, imageBlocks.length),
			};

			ctx.ui.notify(
				`Image(s) from ${event.toolName} described by ${visionModel.name ?? visionModel.id}`,
				"success",
			);

			return { content: [...textBlocks, replacementBlock] };
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			ctx.ui.notify(`Image description failed: ${msg}`, "error");
			const errorBlock: TextContent = {
				type: "text",
				text: `[Image(s) could not be described: ${msg}]`,
			};
			return { content: [...textBlocks, errorBlock] };
		}
	});

	// ── Handler 3: Response detection ─────────────────────────────────
	//
	// After every agent turn, scan the assistant's messages for phrases
	// like "I can't see images".  If detected and the model isn't already
	// configured for routing, show a one-time notification suggesting
	// `/image-router`.
	//
	// This catches models that *claim* image support in metadata but
	// actually can't process images (e.g. a proxy that strips images).

	pi.on("agent_end", async (event, ctx) => {
		if (!preferences.detectResponses) return;
		if (!ctx.model) return;

		const existingPref = getModelPref(preferences, ctx.model);
		if (existingPref?.mode === "auto" || existingPref?.mode === "never") {
			return; // already configured — no need to nag
		}

		let detected = false;
		for (const msg of event.messages) {
			if (msg.role !== "assistant") continue;
			const texts = typeof msg.content === "string"
				? msg.content
				: (msg.content as Array<{ type: string; text?: string; thinking?: string }>)
					?.filter((c) => c.type === "text" && typeof c.text === "string")
					.map((c) => c.text!)
					.join(" ") ?? "";
			if (messageSaysCannotSeeImages(texts)) {
				detected = true;
				break;
			}
		}

		if (!detected) return;

		ctx.ui.notify(
			"It looks like this model can't process images. Use /image-router to configure automatic routing.",
			"warning",
		);
	});
}
