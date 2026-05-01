import type { ExtensionAPI, ExtensionCommandContext } from "@mariozechner/pi-coding-agent";
import {
  buildPiCommand,
  buildShellCommand,
  isInsideCmux,
  openSplit,
  type SplitDirection,
} from "@diversioteam/pi-cmux";

/**
 * Split pane commands
 *
 * UX recommendation:
 * - Splits are the default / recommended lane for most quick adjacent work.
 * - They keep the user in the same workspace tab and avoid an immediate focus jump.
 * - Workspace tabs are still useful, but mainly when the task deserves stronger
 *   isolation or a named long-lived lane.
 *
 * Product goal:
 * - Stay tiny and predictable.
 * - One command should do one obvious thing: open a split to the right or down,
 *   then launch either Pi or one shell command.
 *
 * We intentionally keep "fancy" behavior out of this file. Things like shell
 * escaping, caller detection, and split creation live in `@diversioteam/pi-cmux`
 * so this file reads more like a command catalog than a process-management script.
 */

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------

/**
 * Open a fresh Pi session in a new split, preserving the current cwd.
 */
async function openPiInSplit(
  pi: ExtensionAPI,
  ctx: ExtensionCommandContext,
  direction: SplitDirection,
  args: string,
): Promise<{ ok: true } | { ok: false; error: string }> {
  return openSplit(
    pi,
    direction,
    buildPiCommand(ctx.cwd, { prompt: args.trim().length > 0 ? args : undefined }),
  );
}

/**
 * Open one arbitrary shell command in a new split.
 */
async function openShellInSplit(
  pi: ExtensionAPI,
  ctx: ExtensionCommandContext,
  direction: SplitDirection,
  args: string,
): Promise<{ ok: true } | { ok: false; error: string }> {
  if (!args.trim()) {
    return {
      ok: false,
      error: "A shell command is required. Use /omp-split-right-command <command> or /omp-split-down-command <command>",
    };
  }
  return openSplit(pi, direction, buildShellCommand(ctx.cwd, args.trim()));
}

function ensureInsideCmux(ctx: ExtensionCommandContext): boolean {
  if (!isInsideCmux()) {
    ctx.ui.notify("This command must be run from inside a cmux surface", "warning");
    return false;
  }
  return true;
}

function registerPiSplitCommand(
  pi: ExtensionAPI,
  name: string,
  direction: SplitDirection,
  description: string,
  successMessage: string,
) {
  pi.registerCommand(name, {
    description,
    handler: async (args, ctx) => {
      if (!ensureInsideCmux(ctx)) return;
      const result = await openPiInSplit(pi, ctx, direction, args);
      if (result.ok) ctx.ui.notify(successMessage, "info");
      else ctx.ui.notify(`cmux split failed: ${result.error}`, "error");
    },
  });
}

function registerShellSplitCommand(
  pi: ExtensionAPI,
  name: string,
  direction: SplitDirection,
  description: string,
  successMessage: string,
) {
  pi.registerCommand(name, {
    description,
    handler: async (args, ctx) => {
      if (!ensureInsideCmux(ctx)) return;
      const result = await openShellInSplit(pi, ctx, direction, args);
      if (result.ok) ctx.ui.notify(successMessage, "info");
      else ctx.ui.notify(`cmux split failed: ${result.error}`, "error");
    },
  });
}

/**
 * Register the split-pane command surface.
 *
 * Canonical commands use readable `omp-<slug>` names.
 * Short mnemonic aliases remain for faster typing.
 *
 * Canonical:
 * - `omp-split-right`
 * - `omp-split-right-command`
 * - `omp-split-down`
 * - `omp-split-down-command`
 *
 * Aliases:
 * - `ompv`, `ompr`, `omph`, `omphr`
 */
function registerSplitCommands(pi: ExtensionAPI) {
  registerPiSplitCommand(
    pi,
    "omp-split-right",
    "right",
    "Open a new right-side cmux split pane and launch a fresh Pi session in the current cwd",
    "Opened a new right-side cmux split with Pi",
  );
  registerPiSplitCommand(
    pi,
    "ompv",
    "right",
    "Alias for /omp-split-right",
    "Opened a new right-side cmux split with Pi",
  );

  registerShellSplitCommand(
    pi,
    "omp-split-right-command",
    "right",
    "Open a new right-side cmux split pane and run an arbitrary shell command in the current cwd",
    "Opened a new right-side cmux split with shell command",
  );
  registerShellSplitCommand(
    pi,
    "ompr",
    "right",
    "Alias for /omp-split-right-command",
    "Opened a new right-side cmux split with shell command",
  );

  registerPiSplitCommand(
    pi,
    "omp-split-down",
    "down",
    "Open a new down-side cmux split pane and launch a fresh Pi session in the current cwd",
    "Opened a new down-side cmux split with Pi",
  );
  registerPiSplitCommand(
    pi,
    "omph",
    "down",
    "Alias for /omp-split-down",
    "Opened a new down-side cmux split with Pi",
  );

  registerShellSplitCommand(
    pi,
    "omp-split-down-command",
    "down",
    "Open a new down-side cmux split pane and run an arbitrary shell command in the current cwd",
    "Opened a new down-side cmux split with shell command",
  );
  registerShellSplitCommand(
    pi,
    "omphr",
    "down",
    "Alias for /omp-split-down-command",
    "Opened a new down-side cmux split with shell command",
  );
}

// ---------------------------------------------------------------------------
// Extension
// ---------------------------------------------------------------------------

export default function cmuxSplitExtension(pi: ExtensionAPI) {
  registerSplitCommands(pi);
}
