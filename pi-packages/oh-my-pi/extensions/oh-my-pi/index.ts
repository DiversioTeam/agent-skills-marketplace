import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import cmuxNotifyExtension from "./cmux-notify.ts";
import cmuxSplitExtension from "./cmux-split.ts";
import cmuxWorkspaceExtension from "./cmux-workspace.ts";

/**
 * oh-my-pi entrypoint
 *
 * Mental model:
 * - `cmux-notify.ts` watches Pi lifecycle events and sends native cmux notifications.
 * - `cmux-split.ts` adds commands for opening split panes.
 * - `cmux-workspace.ts` adds commands for opening workspace tabs.
 *
 * We keep the three concerns separate so future maintainers can change one area
 * (for example, notification wording) without having to reason about pane or
 * workspace launching code at the same time.
 */
export default function (pi: ExtensionAPI) {
  cmuxNotifyExtension(pi);
  cmuxSplitExtension(pi);
  cmuxWorkspaceExtension(pi);
}
