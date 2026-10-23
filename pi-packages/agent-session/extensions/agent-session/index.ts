import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// The agent-session PR guard for Pi: the same check as the Claude Code plugin's PreToolUse hook
// (plugins/agent-session/skills/agent-session/scripts/check_pr_hook.py), run before Pi's bash tool executes
// `gh pr create`, `gh pr edit --body…`, or `gh api …/pulls` with a body in a DiversioTeam repo. A PR body without an
// agent session transcript link or a "No agent session: <reason>" line is blocked with the fix. local-ci's agent-session
// check stays the gate; this is the early feedback.

const PR_COMMAND = /\bgh\s+(?:pr\s+(?:create|edit)|api\b[^\n]*\/pulls\b)/;

// The hook script ships in the same marketplace checkout; AGENT_SESSION_CLI points elsewhere when installed apart.
export function findHook(environment: NodeJS.ProcessEnv = process.env, here = dirname(fileURLToPath(import.meta.url))): string | undefined {
  const candidates = [
    environment.AGENT_SESSION_CLI ? join(dirname(environment.AGENT_SESSION_CLI), "check_pr_hook.py") : "",
    resolve(here, "../../../../plugins/agent-session/skills/agent-session/scripts/check_pr_hook.py"),
  ].filter(Boolean);
  return candidates.find(candidate => existsSync(candidate));
}

export type Decision = { block: true; reason: string } | undefined;

export function decide(command: string, cwd: string, hook: string | undefined, run = spawnSync): Decision {
  if (!PR_COMMAND.test(command)) return undefined;
  if (!hook) {
    return { block: true, reason: "agent-session: the PR guard cannot find check_pr_hook.py. Install the agent-session skill " +
      "(or set AGENT_SESSION_CLI), then run its share command before creating or editing the PR." };
  }
  const result = run("python3", [hook], { input: JSON.stringify({ tool_input: { command }, cwd }), encoding: "utf8", timeout: 15_000 });
  if (result.status === 2) return { block: true, reason: String(result.stderr || "").trim() };
  // Any other failure of the guard itself leaves the decision to local-ci rather than blocking unrelated work.
  return undefined;
}

// Keep the `agent-session` command (local-ci's step) on PATH and pointing at this checkout's CLI.
export function installShim(hook: string | undefined, run = spawnSync): void {
  if (!hook) return;
  run("python3", [join(dirname(hook), "agent_session.py"), "install-shim", "--quiet"], { encoding: "utf8", timeout: 15_000 });
}

export default function agentSession(pi: ExtensionAPI) {
  const hook = findHook();
  installShim(hook);
  pi.on("tool_call", async (event, context) => {
    if (event.toolName !== "bash") return undefined;
    const command = (event.input as { command?: unknown } | undefined)?.command;
    if (typeof command !== "string") return undefined;
    return decide(command, context.cwd, hook);
  });
}
