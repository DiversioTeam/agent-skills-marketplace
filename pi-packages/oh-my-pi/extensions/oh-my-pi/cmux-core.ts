import { existsSync, realpathSync } from "node:fs";
import { dirname, join } from "node:path";

import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

/**
 * Shared cmux helpers
 *
 * Why this file exists:
 * - `cmux-split.ts`, `cmux-workspace.ts`, and `cmux-notify.ts` all need a few
 *   of the same low-level building blocks.
 * - cmux output is *mixed mode*: some commands return JSON, others still return
 *   plain text. Centralizing the parsing rules here keeps that weirdness in one
 *   place instead of scattering it across command handlers.
 *
 * First principles:
 * - Ask cmux who the caller is instead of guessing.
 * - Build shell commands once, in one place, with strict escaping.
 * - Treat every cmux CLI call like a small RPC boundary that can fail or time out.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SplitDirection = "right" | "down";

export interface CmuxCallerInfo {
  workspace_ref: string;
  surface_ref: string;
}

interface CmuxIdentifyResponse {
  caller?: {
    workspace_ref?: string;
    surface_ref?: string;
  };
}

interface CmuxSplitResponse {
  surface_ref?: string;
}

interface CmuxExecResult {
  ok: boolean;
  stdout: string;
  stderr: string;
  error?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CMUX_TIMEOUT_MS = 5000;
const SPLIT_BOOT_DELAY_MS = 250;

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function parseJson<T>(text: string): T | undefined {
  try {
    return JSON.parse(text) as T;
  } catch {
    return undefined;
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

// ---------------------------------------------------------------------------
// Shell escaping
// ---------------------------------------------------------------------------

/**
 * Escape one shell argument for `sh -lc '...'` style commands.
 *
 * Why so strict?
 * - Split/workspace commands let the user pass free-form prompts and shell text.
 * - A single bad quote can launch the wrong command in the wrong tab.
 *
 * We use classic single-quote shell escaping because it is boring, predictable,
 * and works well for the short command lines we generate here.
 */
export function shellEscape(value: string): string {
  return `'${value.replace(/'/g, `'\\''`)}'`;
}

// ---------------------------------------------------------------------------
// Command builders
// ---------------------------------------------------------------------------

/**
 * Resolve the Pi launcher we should use inside spawned cmux surfaces.
 *
 * Why not just run `pi` and trust PATH?
 * - The current interactive shell usually has Pi on PATH.
 * - A newly respawned cmux pane may not inherit the same shell initialization.
 * - In practice that means `pi` can be available *here* while failing with
 *   `command not found: pi` inside the new split.
 *
 * The most reliable default is: if Pi is running right now, use the `pi`
 * executable sitting next to the current Node binary.
 *
 * Visual model:
 *
 * ```text
 * current Pi session
 *   └─ knows exactly which Node + Pi install is working now
 *        └─ spawned cmux pane should reuse that exact launcher
 *             └─ do not rediscover it from scratch in a weaker environment
 * ```
 *
 * Advanced escape hatch:
 * - `PI_CLI_PATH=/absolute/path/to/pi` forces a specific launcher when needed.
 */
function resolvePiLauncher(): string {
  const explicit = process.env.PI_CLI_PATH?.trim();
  if (explicit) {
    try {
      if (!existsSync(explicit)) {
        return shellEscape(explicit);
      }

      const resolvedExplicit = realpathSync(explicit);
      if (resolvedExplicit.endsWith(".js")) {
        return `${shellEscape(process.execPath)} ${shellEscape(resolvedExplicit)}`;
      }

      return shellEscape(explicit);
    } catch {
      return shellEscape(explicit);
    }
  }

  const siblingCandidate = join(dirname(process.execPath), "pi");
  if (!existsSync(siblingCandidate)) {
    return "pi";
  }

  try {
    const resolvedSibling = realpathSync(siblingCandidate);

    // The common Pi install path is a small `#!/usr/bin/env node` wrapper
    // script. Launching that wrapper can still fail in respawned panes if PATH
    // no longer contains `node`. When the wrapper resolves to a JS entrypoint,
    // call it through the currently running Node binary directly.
    if (resolvedSibling.endsWith(".js")) {
      return `${shellEscape(process.execPath)} ${shellEscape(resolvedSibling)}`;
    }

    return shellEscape(siblingCandidate);
  } catch {
    return "pi";
  }
}

/**
 * Wrap one command in a tiny shell trampoline.
 *
 * Why this helper exists:
 * - cmux panes disappearing instantly feels broken when a launch fails before
 *   the user can read the error.
 * - Respawned cmux panes may not inherit the same PATH as the current Pi
 *   session, so we restore it explicitly before running the real command.
 *
 * Current policy:
 * - normal clean exits are allowed to close the pane
 * - failed launches drop into an interactive shell so the error stays visible
 *
 * We intentionally do not try to keep every successful short-lived command open.
 * Interactive tools already stay open naturally, and forcing a post-success
 * shell fallback was flaky in respawned cmux panes during local testing.
 *
 * Visual model:
 *
 * ```text
 * restore PATH
 *   └─ run real command
 *        ├─ success -> exit normally
 *        └─ failure -> show error -> drop into shell -> let the user inspect it
 * ```
 */
function wrapSpawnedCommand(command: string, notice: string): string {
  const lines = [
    `PATH=${shellEscape(process.env.PATH ?? "")}`,
    "export PATH",
    command,
    "status=$?",
    'if [ "$status" -ne 0 ]; then printf "\\n[oh-my-pi] %s\\n[oh-my-pi] Exit status: %s\\n" ' + shellEscape(notice) + ' "$status"; exec "${SHELL:-/bin/sh}" -i; fi',
    'exit "$status"',
  ];

  return ["exec", "sh", "-lc", shellEscape(lines.join("; "))].join(" ");
}

/**
 * Build the exact shell command we want cmux to run for a fresh Pi session.
 *
 * Design choices:
 * - `cd <cwd>` makes the new pane/tab start in the same directory as the
 *   current Pi session.
 * - We launch Pi by absolute path instead of relying on PATH inside the new
 *   cmux surface.
 * - `--` before the prompt prevents prompts that start with `-` from being
 *   misread as Pi CLI flags.
 * - If Pi fails to start, keep the pane open in a shell so the error is visible
 *   instead of the pane disappearing instantly.
 *
 * Visual model:
 *
 * ```text
 * /omp-split-right review this diff
 *   └─ open split
 *        └─ cd into same cwd
 *             └─ launch Pi with same Node/Pi install as parent session
 *                  └─ pass prompt after `--`
 * ```
 */
export function buildPiCommand(
  cwd: string,
  options?: { sessionFile?: string; prompt?: string },
): string {
  const parts = [resolvePiLauncher()];
  if (options?.sessionFile) {
    parts.push("--session", shellEscape(options.sessionFile));
  }
  const prompt = options?.prompt?.trim();
  if (prompt) {
    parts.push("--", shellEscape(prompt));
  }

  return [
    "cd",
    shellEscape(cwd),
    "&&",
    wrapSpawnedCommand(
      parts.join(" "),
      "Pi failed to stay open. Keeping this pane open for debugging.",
    ),
  ].join(" ");
}

/**
 * Build the exact shell command we want cmux to run for arbitrary shell work.
 *
 * We intentionally route through `sh -lc` instead of trying to split the user's
 * command into argv pieces ourselves. The user asked for "run this shell text",
 * so we preserve normal shell behavior.
 *
 * We currently keep the pane open only on error.
 *
 * Why not keep it open after every successful command?
 * - interactive programs like `top`, `lazygit`, or `npm run dev` naturally stay
 *   open already
 * - some shells launched after a successful non-interactive command immediately
 *   exit again in respawned cmux panes, which creates a flaky UX
 * - the high-value fix is preserving PATH and surfacing failures instead of
 *   pretending every short-lived command should become a persistent shell lane
 *
 * First-principles rule:
 * - use Pi split commands for "open an adjacent AI work lane"
 * - use shell split commands for "run a real terminal program beside me"
 * - prefer long-running or interactive commands when you want the lane to stay
 *   visible after launch
 */
export function buildShellCommand(cwd: string, command: string): string {
  return [
    "cd",
    shellEscape(cwd),
    "&&",
    wrapSpawnedCommand(command, "Command failed. Keeping this pane open for debugging."),
  ].join(" ");
}

// ---------------------------------------------------------------------------
// cmux execution
// ---------------------------------------------------------------------------

/**
 * Execute one cmux CLI command with a small timeout and normalized errors.
 *
 * Why normalize here?
 * - Extension command handlers should talk in product terms like "open split"
 *   and "notify", not in child-process edge cases.
 * - Returning one small `{ ok, stdout, stderr, error }` shape keeps the rest of
 *   the package easy to read.
 */
async function execCmux(pi: ExtensionAPI, args: string[]): Promise<CmuxExecResult> {
  const result = await pi.exec("cmux", args, { timeout: CMUX_TIMEOUT_MS });
  if (result.killed) {
    return {
      ok: false,
      stdout: result.stdout,
      stderr: result.stderr,
      error: "cmux command timed out",
    };
  }
  if (result.code !== 0) {
    return {
      ok: false,
      stdout: result.stdout,
      stderr: result.stderr,
      error: result.stderr.trim() || result.stdout.trim() || `cmux exited with code ${result.code}`,
    };
  }
  return {
    ok: true,
    stdout: result.stdout,
    stderr: result.stderr,
  };
}

// ---------------------------------------------------------------------------
// Caller identification
// ---------------------------------------------------------------------------

/**
 * Fast environment check used for "should we even try cmux?" decisions.
 *
 * This is intentionally cheap and slightly conservative. Interactive commands
 * still call `identifyCaller()` for the real source of truth before opening
 * panes or tabs.
 */
export function isInsideCmux(): boolean {
  return Boolean(
    process.env.CMUX_SOCKET_PATH &&
    process.env.CMUX_WORKSPACE_ID &&
    process.env.CMUX_SURFACE_ID,
  );
}

/**
 * Ask cmux which workspace/surface launched this extension command.
 *
 * Why not trust environment variables alone?
 * - Env vars are useful for a quick "inside cmux?" check.
 * - For actual pane splitting we want cmux itself to tell us the authoritative
 *   workspace/surface refs to operate on.
 */
export async function identifyCaller(
  pi: ExtensionAPI,
): Promise<{ ok: true; caller: CmuxCallerInfo } | { ok: false; error: string }> {
  const result = await execCmux(pi, ["--json", "identify"]);
  if (!result.ok) {
    return { ok: false, error: result.error || "Failed to identify cmux caller" };
  }

  const parsed = parseJson<CmuxIdentifyResponse>(result.stdout);
  const workspaceRef = parsed?.caller?.workspace_ref;
  const surfaceRef = parsed?.caller?.surface_ref;

  if (!workspaceRef || !surfaceRef) {
    return {
      ok: false,
      error: "This command must be run from inside a cmux surface",
    };
  }

  return {
    ok: true,
    caller: { workspace_ref: workspaceRef, surface_ref: surfaceRef },
  };
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

/**
 * Send one native cmux notification.
 *
 * We use cmux's built-in notification system instead of OSC escape sequences
 * because cmux understands focus state, unread badges, and the notification
 * panel. That gives a better "cmux-native" experience.
 */
export async function notify(
  pi: ExtensionAPI,
  title: string,
  subtitle: string,
  body: string,
  options?: { timeout?: number },
): Promise<{ ok: boolean; error?: string }> {
  const args = ["notify", "--title", title, "--subtitle", subtitle, "--body", body];
  const result = await pi.exec("cmux", args, {
    timeout: options?.timeout ?? CMUX_TIMEOUT_MS,
  });

  if (result.killed) {
    return { ok: false, error: "cmux notify timed out" };
  }
  if (result.code !== 0) {
    const error =
      result.stderr.trim() || result.stdout.trim() || `cmux exited with code ${result.code}`;
    return { ok: false, error };
  }

  return { ok: true };
}

// ---------------------------------------------------------------------------
// Split pane
//
// Uses cmux --json new-split and parses the returned surface_ref directly,
// then calls respawn-pane. No polling needed.
// ---------------------------------------------------------------------------

/**
 * Open a new split pane beside the caller and launch one command in it.
 *
 * Why the two-step flow?
 * 1. `cmux --json new-split ...` creates the new surface and tells us its ref.
 * 2. `cmux respawn-pane ... --command` replaces the placeholder shell with the
 *    real Pi or shell command we want.
 *
 * This is simpler and more reliable than polling `list-panes` waiting for a new
 * surface to appear.
 */
export async function openSplit(
  pi: ExtensionAPI,
  direction: SplitDirection,
  command: string,
): Promise<{ ok: true } | { ok: false; error: string }> {
  const callerResult = await identifyCaller(pi);
  if (!callerResult.ok) {
    return callerResult;
  }

  const { workspace_ref: workspaceRef, surface_ref: surfaceRef } = callerResult.caller;

  const splitResult = await execCmux(pi, [
    "--json",
    "new-split",
    direction,
    "--workspace",
    workspaceRef,
    "--surface",
    surfaceRef,
  ]);
  if (!splitResult.ok) {
    return { ok: false, error: splitResult.error || "Failed to create cmux split" };
  }

  const parsed = parseJson<CmuxSplitResponse>(splitResult.stdout);
  const newSurfaceRef = parsed?.surface_ref;
  if (!newSurfaceRef) {
    return {
      ok: false,
      error: `Created split, but could not parse surface_ref from: ${splitResult.stdout.trim().slice(0, 200)}`,
    };
  }

  // Brief delay to let the new surface boot.
  //
  // In practice, `new-split` returns before the new surface is always ready to
  // accept `respawn-pane`. A tiny delay keeps the UX reliable without needing a
  // more complex retry loop.
  await delay(SPLIT_BOOT_DELAY_MS);

  const respawnResult = await execCmux(pi, [
    "respawn-pane",
    "--workspace",
    workspaceRef,
    "--surface",
    newSurfaceRef,
    "--command",
    command,
  ]);
  if (!respawnResult.ok) {
    return {
      ok: false,
      error: respawnResult.error || "Failed to start command in the new split",
    };
  }

  return { ok: true };
}

// ---------------------------------------------------------------------------
// Workspace tab
//
// cmux new-workspace returns plain text "OK workspace:<n>" even with --json.
// We parse the text response rather than assuming JSON.
// ---------------------------------------------------------------------------

export interface OpenWorkspaceOptions {
  cwd: string;
  name?: string;
  command: string;
}

/**
 * Open a new cmux workspace tab and launch one command in it.
 *
 * Important cmux quirk:
 * - `new-workspace` currently returns plain text like `OK workspace:19`
 *   even when `--json` would suggest otherwise.
 * - We therefore parse text here on purpose. This is not an accident.
 */
export async function openWorkspace(
  pi: ExtensionAPI,
  options: OpenWorkspaceOptions,
): Promise<{ ok: true; workspaceRef: string } | { ok: false; error: string }> {
  const args: string[] = ["new-workspace", "--cwd", options.cwd, "--command", options.command];
  if (options.name) {
    args.push("--name", options.name);
  }

  const result = await execCmux(pi, args);
  if (!result.ok) {
    return { ok: false, error: result.error || "Failed to create cmux workspace" };
  }

  // Parse text response: "OK workspace:<n>"
  const match = result.stdout.match(/^OK\s+(workspace:\d+)/m);
  if (!match) {
    return {
      ok: false,
      error: `Created workspace, but could not parse ref from: ${result.stdout.trim().slice(0, 200)}`,
    };
  }

  return { ok: true, workspaceRef: match[1] };
}
