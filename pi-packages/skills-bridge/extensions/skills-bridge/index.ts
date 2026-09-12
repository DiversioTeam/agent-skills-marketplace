import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";

interface BridgeConfig {
  skillsPath?: string;
  additionalPaths?: string[];
}

function loadBridgeConfig(): BridgeConfig | null {
  const configHome = process.env.XDG_CONFIG_HOME || join(homedir(), ".config");
  const configPath = join(configHome, "pi", "skills-bridge.json");
  let raw: string;
  try {
    raw = readFileSync(configPath, "utf8");
  } catch {
    return null;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    console.warn(`[skills-bridge] Invalid JSON in ${configPath}: ${error instanceof Error ? error.message : String(error)}. Falling through to cwd walk-up.`);
    return null;
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    console.warn(`[skills-bridge] Config at ${configPath} must be a JSON object. Falling through to cwd walk-up.`);
    return null;
  }
  const fields = parsed as Record<string, unknown>;
  const config: BridgeConfig = {};
  if (fields.skillsPath !== undefined) {
    if (typeof fields.skillsPath === "string" && fields.skillsPath.trim()) {
      config.skillsPath = fields.skillsPath.trim();
    } else {
      console.warn("[skills-bridge] Config skillsPath must be a non-empty string. Ignoring.");
    }
  }
  if (fields.additionalPaths !== undefined) {
    if (!Array.isArray(fields.additionalPaths)) {
      console.warn("[skills-bridge] Config additionalPaths must be an array. Ignoring.");
    } else {
      config.additionalPaths = [];
      for (const path of fields.additionalPaths) {
        if (typeof path === "string" && path.trim()) config.additionalPaths.push(path.trim());
        else console.warn(`[skills-bridge] Skipping invalid additionalPaths entry: ${JSON.stringify(path)}`);
      }
    }
  }
  return config;
}

function getSkillRootFromAncestors(startDirectory: string): string | null {
  let directory = resolve(startDirectory);
  for (let depth = 0; depth < 64; depth++) {
    // Prefer the monolith's marketplace over a generic plugins/ at the same ancestor.
    for (const root of [join(directory, "agent-skills-marketplace"), directory]) {
      const plugins = join(root, "plugins");
      try {
        if (statSync(plugins).isDirectory()) return root;
      } catch (error) {
        const errorCode = (error as NodeJS.ErrnoException).code;
        if (errorCode === "ENOENT" || errorCode === "ENOTDIR") continue;
        console.warn(`[skills-bridge] Cannot inspect ${plugins} (${errorCode ?? String(error)}). Stopping ancestor discovery.`);
        return null;
      }
    }
    const parent = resolve(directory, "..");
    if (parent === directory) break;
    directory = parent;
  }
  return null;
}

function getSkillRoots(cwd: string): string[] {
  const environmentPath = process.env.PI_SKILLS_PATH?.trim();
  // An explicit environment override must never fall back to a different checkout.
  if (environmentPath) {
    const root = resolve(environmentPath);
    if (existsSync(root)) return [root];
    console.warn(`[skills-bridge] PI_SKILLS_PATH is set but path doesn't exist: ${root}. Skipping skills discovery.`);
    return [];
  }
  const config = loadBridgeConfig();
  const roots: string[] = [];
  if (config?.skillsPath) {
    const root = resolve(config.skillsPath);
    if (existsSync(root)) roots.push(root);
    else console.warn(`[skills-bridge] Config skillsPath doesn't exist: ${root}. Falling through to cwd walk-up.`);
  }
  if (!roots.length) {
    const root = getSkillRootFromAncestors(cwd);
    if (root) roots.push(root);
  }
  for (const path of config?.additionalPaths ?? []) {
    const root = resolve(path);
    if (!existsSync(root)) {
      console.warn(`[skills-bridge] Config additionalPaths entry doesn't exist: ${root}. Skipping.`);
      continue;
    }
    if (!roots.includes(root)) roots.push(root);
  }
  return roots;
}

function getPluginSkillPaths(root: string): string[] {
  const plugins = join(root, "plugins");
  let names: string[];
  try {
    names = readdirSync(plugins);
  } catch {
    console.warn(`[skills-bridge] Cannot read plugins/ directory at ${plugins}. Skipping this skills root.`);
    return [];
  }
  const paths: string[] = [];
  for (const name of names) {
    const directory = join(plugins, name, "skills");
    try {
      if (statSync(directory).isDirectory()) paths.push(directory);
    } catch {
      // Missing or unreadable plugin skill directories do not block other plugins.
    }
  }
  return paths;
}

export default function (pi: ExtensionAPI) {
  pi.on("resources_discover", async (event) => {
    // Pi owns recursive discovery, ignore rules, skill boundaries, and name collisions.
    const skillPaths = getSkillRoots(event.cwd).flatMap(getPluginSkillPaths);
    if (skillPaths.length) return { skillPaths };
  });
}
