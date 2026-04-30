import type { ExtensionAPI, ExtensionCommandContext } from "@mariozechner/pi-coding-agent";
import {
  buildPiCommand,
  buildShellCommand,
  isInsideCmux,
  openWorkspace,
} from "./cmux-core.ts";

/**
 * Workspace tab commands
 *
 * UX recommendation:
 * - Workspace tabs are not the default recommendation for quick helper work.
 * - In v1, opening a workspace tab switches focus immediately.
 * - They are best when the user wants a stronger boundary than a split pane:
 *   a named lane, a longer-running task, or something worth revisiting later.
 *
 * Why this file exists separately from split panes:
 * - Workspace tabs are a different cmux concept with different UX tradeoffs.
 * - Future readers should be able to adjust tab-specific behavior without
 *   wading through split-pane logic.
 */

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Parse optional `--name` arguments for workspace commands.
 *
 * We support two human-friendly forms:
 *
 * 1. Quoted multi-word titles
 *    /omp-workspace --name "Auth Review" review the login flow
 *
 * 2. Unquoted titles separated from the remaining prompt/command with ` -- `
 *    /omp-workspace --name Auth Review -- review the login flow
 *
 * Why not use a full CLI parser?
 * - Pi command handlers receive one plain string.
 * - These two forms cover the common cases while staying easy to explain in docs.
 */
function parseNamedArgs(args: string): { title?: string; rest: string; error?: string } {
  const trimmed = args.trim();
  if (!trimmed.startsWith("--name")) return { rest: args };

  let remainder = trimmed.slice("--name".length).trimStart();
  if (!remainder) {
    return { rest: "", error: "Missing workspace title after --name" };
  }

  let title = "";
  if (remainder.startsWith('"') || remainder.startsWith("'")) {
    const quote = remainder[0];
    const endIndex = remainder.indexOf(quote, 1);
    if (endIndex === -1) {
      return { rest: "", error: `Unterminated ${quote} quote in --name title` };
    }
    title = remainder.slice(1, endIndex).trim();
    remainder = remainder.slice(endIndex + 1).trim();
  } else {
    const delimiterIndex = remainder.indexOf(" -- ");
    if (delimiterIndex >= 0) {
      title = remainder.slice(0, delimiterIndex).trim();
      remainder = remainder.slice(delimiterIndex + 4).trim();
    } else {
      const firstSpace = remainder.indexOf(" ");
      if (firstSpace === -1) {
        title = remainder.trim();
        remainder = "";
      } else {
        title = remainder.slice(0, firstSpace).trim();
        remainder = remainder.slice(firstSpace + 1).trim();
      }
    }
  }

  if (!title) {
    return { rest: remainder, error: "Workspace title after --name cannot be empty" };
  }

  return { title, rest: remainder };
}

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------

/**
 * Open a new workspace tab with a fresh Pi session.
 */
async function openPiInWorkspace(
  pi: ExtensionAPI,
  ctx: ExtensionCommandContext,
  args: string,
  title?: string,
): Promise<{ ok: true; workspaceRef: string } | { ok: false; error: string }> {
  return openWorkspace(pi, {
    cwd: ctx.cwd,
    name: title,
    command: buildPiCommand(ctx.cwd, {
      prompt: args.trim().length > 0 ? args : undefined,
    }),
  });
}

/**
 * Open a new workspace tab with one arbitrary shell command.
 */
async function openShellInWorkspace(
  pi: ExtensionAPI,
  ctx: ExtensionCommandContext,
  args: string,
  title?: string,
): Promise<{ ok: true; workspaceRef: string } | { ok: false; error: string }> {
  if (!args.trim()) {
    return {
      ok: false,
      error: "A shell command is required. Use /omp-workspace-command <command> or /omp-workspace-command --name \"My Tab\" <command>",
    };
  }
  return openWorkspace(pi, {
    cwd: ctx.cwd,
    name: title,
    command: buildShellCommand(ctx.cwd, args.trim()),
  });
}

function ensureInsideCmux(ctx: ExtensionCommandContext): boolean {
  if (!isInsideCmux()) {
    ctx.ui.notify("This command must be run from inside a cmux surface", "warning");
    return false;
  }
  return true;
}

function registerPiWorkspaceCommand(
  pi: ExtensionAPI,
  name: string,
  description: string,
) {
  pi.registerCommand(name, {
    description,
    handler: async (args, ctx) => {
      if (!ensureInsideCmux(ctx)) return;

      const parsed = parseNamedArgs(args);
      if (parsed.error) {
        ctx.ui.notify(`cmux workspace failed: ${parsed.error}`, "error");
        return;
      }

      const result = await openPiInWorkspace(pi, ctx, parsed.rest, parsed.title);
      if (result.ok) {
        ctx.ui.notify(
          parsed.title
            ? `Opened new workspace tab "${parsed.title}" with Pi`
            : "Opened new workspace tab with Pi",
          "info",
        );
      } else {
        ctx.ui.notify(`cmux workspace failed: ${result.error}`, "error");
      }
    },
  });
}

function registerShellWorkspaceCommand(
  pi: ExtensionAPI,
  name: string,
  description: string,
) {
  pi.registerCommand(name, {
    description,
    handler: async (args, ctx) => {
      if (!ensureInsideCmux(ctx)) return;

      const parsed = parseNamedArgs(args);
      if (parsed.error) {
        ctx.ui.notify(`cmux workspace failed: ${parsed.error}`, "error");
        return;
      }

      const result = await openShellInWorkspace(pi, ctx, parsed.rest, parsed.title);
      if (result.ok) {
        ctx.ui.notify(
          parsed.title
            ? `Opened new workspace tab "${parsed.title}" with shell command`
            : "Opened new workspace tab with shell command",
          "info",
        );
      } else {
        ctx.ui.notify(`cmux workspace failed: ${result.error}`, "error");
      }
    },
  });
}

/**
 * Register the workspace-tab command surface.
 *
 * Canonical commands use readable `omp-<slug>` names.
 * Short mnemonic aliases remain for faster typing.
 *
 * Canonical:
 * - `omp-workspace`
 * - `omp-workspace-command`
 *
 * Aliases:
 * - `ompw`, `ompwr`
 */
function registerWorkspaceCommands(pi: ExtensionAPI) {
  registerPiWorkspaceCommand(
    pi,
    "omp-workspace",
    "Open a new cmux workspace tab with a fresh Pi session in the current cwd. This switches focus to the new workspace tab.",
  );
  registerPiWorkspaceCommand(
    pi,
    "ompw",
    "Alias for /omp-workspace",
  );

  registerShellWorkspaceCommand(
    pi,
    "omp-workspace-command",
    "Open a new cmux workspace tab and run an arbitrary shell command in the current cwd. This switches focus to the new workspace tab.",
  );
  registerShellWorkspaceCommand(
    pi,
    "ompwr",
    "Alias for /omp-workspace-command",
  );
}

// ---------------------------------------------------------------------------
// Extension
// ---------------------------------------------------------------------------

export default function cmuxWorkspaceExtension(pi: ExtensionAPI) {
  registerWorkspaceCommands(pi);
}
