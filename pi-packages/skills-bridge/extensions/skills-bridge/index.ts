/**
 * skills-bridge
 * ============
 *
 * PROBLEM: The Diversio team has 21 agent skills (release-manager,
 * monty-code-review, backend-atomic-commit, etc.) in the shared
 * agent-skills-marketplace repo. These skills follow the agentskills.io
 * standard — each is a directory with a SKILL.md file. Claude Code and
 * Codex discover them automatically because those tools scan
 * `plugins/* /skills/` directories. Pi users don't — pi only discovers
 * skills from `~/.pi/agent/skills/` and `pi-packages/* /skills/`, not
 * from `plugins/* /skills/`. The result: half the team can't see these
 * skills in pi.
 *
 * WHAT THIS EXTENSION DOES: It bridges that gap. Using pi's
 * `resources_discover` extension hook (the official mechanism for extensions
 * to contribute skill paths), it scans the `plugins/* /skills/` directory
 * tree under a skills root and registers every discovered `SKILL.md`
 * directory as a pi skill. One `pi install`, then `/reload`, and all 21
 * skills appear.
 *
 * HOW IT WORKS — high-level flow:
 *
 *   pi starts up
 *     │
 *     ├─ fires "resources_discover" event
 *     │     │
 *     │     ├─ 1. RESOLVE skills roots        (where are the skills?)
 *     │     │     ├─ env var PI_SKILLS_PATH? → use it, skip everything else
 *     │     │     ├─ ~/.config/pi/skills-bridge.json? → use skillsPath
 *     │     │     └─ neither → walk up from cwd looking for a plugins/ dir
 *     │     │                   (repo-agnostic: checks for plugins/ directly
 *     │     │                    AND for agent-skills-marketplace/plugins/)
 *     │     │
 *     │     ├─ 2. DISCOVER skills under each root
 *     │     │     └─ scan plugins/* /skills/ recursively for SKILL.md dirs
 *     │     │
 *     │     └─ 3. RETURN skillPaths to pi
 *     │           └─ pi loads each skill (name + description only, per progressive disclosure)
 *     │
 *     └─ pi is ready. User types /skill:release-manager → full SKILL.md loads on demand.
 *
 * CONTEXT SAFETY: This extension does NOT load full SKILL.md content. It only
 * tells pi where the skill directories are. Pi's built-in progressive
 * disclosure model handles the rest: at startup, only the skill's `name` and
 * `description` (from SKILL.md YAML frontmatter) enter the system prompt
 * (~5-10KB total for 21 skills). The full SKILL.md body only loads when the
 * user explicitly invokes the skill via `/skill:name`. No context bloat.
 *
 * DEPENDENCIES: None beyond Node.js built-ins and pi's ExtensionAPI.
 * The package has zero npm dependencies — everything uses `node:fs`, `node:os`,
 * and `node:path`. This means zero `npm install` step after `pi install`.
 *
 * CONFIG FILE: Separate from both the extension code and pi's settings.json.
 * Lives at ~/.config/pi/skills-bridge.json (XDG convention). Reason:
 * pi manages its own settings.json (pi install, pi config). Writing custom keys
 * there risks pi overwriting them. A separate XDG config file is:
 *   - Never touched by pi tooling
 *   - Never committed to version control (lives in home directory)
 *   - Survives extension package updates (the extension repo changes don't
 *     overwrite it)
 *
 * RESOLUTION ORDER — why this specific priority:
 *
 *   PI_SKILLS_PATH env var               ← "I know exactly what I want"
 *         │ (if not set)
 *   ~/.config/pi/skills-bridge.json      ← "I want persistent config"
 *         │ (if skillsPath not set)
 *   cwd walk-up                          ← "Just find it automatically"
 *
 * The env var is highest priority because it's an explicit, session-level
 * override. Setting it means "use this exact path, ignore everything else."
 * This is why additionalPaths from config are NOT merged when the env var is
 * set — the developer made a deliberate choice to override.
 *
 * The config file is second because it's a persistent preference that survives
 * terminal restarts. The cwd walk-up is the fallback that works automatically
 * for anyone with a monolith checkout containing a plugins/ directory.
 *
 * ADDITIONAL PATHS: Why are they separate from skillsPath?
 * A developer might want skills from two sources simultaneously:
 *   - The team's primary skills root (skillsPath)
 *   - Their personal experimental skills (additionalPaths)
 * Both are scanned and their skills are merged. This is useful for testing new
 * skills before they're merged into the team skills root.
 *
 * SKILL DISCOVERY: Why recursive + depth-limited?
 * The plugin layout is plugins/<plugin>/skills/<skill>/SKILL.md.
 * That's 3 levels deep. Some plugins have nested skills (e.g., plan-directory
 * has both plan-directory/ and backend-ralph-plan/ under skills/). A flat
 * read of skills/ would miss nested skill directories. Recursive scanning
 * finds them all. The depth limit of 5 prevents infinite recursion from
 * symlink loops or unusual structures while giving enough headroom for
 * nested skill groupings.
 *
 * WHY ONLY plugins/* /skills/ AND NOT commands/?
 * Claude Code's commands/*.md files are thin wrappers that delegate to skills.
 * For example, `commands/review-prs.md` contains `/skill:monolith-review-orchestrator`.
 * Pi has its own command system (`/skill:name` and extensions' `registerCommand`).
 * The skill content itself is what matters — commands are a Claude Code UX
 * convention. Bridging commands would duplicate functionality pi already has.
 */

import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

// =========================================================================
// NAVIGATION — this file is ~700 lines. Jump to:
//   § loadConfig()              — reads ~/.config/pi/skills-bridge.json
//   § findSkillRoots()           — three-tier resolution logic
//   § walkUpFindSkillRoot()      — cwd walk-up with visual trace
//   § findSkillDirs()            — recursive SKILL.md discovery
//   § discoverSkills()           — scans plugins/* /skills/ layout
//   § export default function    — extension entry point (resources_discover)
// =========================================================================

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * Shape of the per-developer config file at ~/.config/pi/skills-bridge.json.
 *
 * Both fields are optional:
 *   - skillsPath: primary skills root. When absent, falls through to
 *     cwd walk-up. When present, use this as the primary root and skip walk-up.
 *   - additionalPaths: extra skills roots scanned alongside the primary.
 *     Always merged (unless env var is set, which overrides everything).
 *     Useful for personal skill collections or testing checkouts.
 *
 * An empty file {} is valid and means "use cwd walk-up only."
 */
interface BridgeConfig {
  skillsPath?: string;
  additionalPaths?: string[];
}

// ---------------------------------------------------------------------------
// Config loading
// ---------------------------------------------------------------------------

/**
 * Read and parse the XDG config file.
 *
 * PATH: ~/.config/pi/skills-bridge.json
 *   (respects $XDG_CONFIG_HOME if set, falls back to ~/.config)
 *
 * WHY A SEPARATE FILE AND NOT pi's settings.json?
 *   pi's settings.json is managed by pi itself (pi install, pi config,
 *   pi remove). Writing custom keys there risks pi overwriting them on future
 *   updates. A separate file under ~/.config/pi/ follows XDG conventions
 *   and is never touched by pi tooling. The file also lives outside the
 *   extension repo, so updating the repo never overwrites local config.
 *
 * ERROR HANDLING STRATEGY:
 *   Every error is non-fatal. If the file doesn't exist, return null and
 *   fall through to cwd walk-up. If the JSON is malformed, log a warning
 *   and return null. If individual fields are wrong types, log a warning
 *   for that field and continue parsing the rest. The extension must never
 *   crash pi because of a bad config file — a developer's hand-edited typo
 *   shouldn't prevent pi from starting.
 *
 * RETURN:
 *   BridgeConfig on success (may be empty {}), null on missing/invalid file.
 */
function loadConfig(): BridgeConfig | null {
  // Resolve config directory per XDG spec.
  // $XDG_CONFIG_HOME/pi/skills-bridge.json, or ~/.config/pi/...
  const configHome = process.env.XDG_CONFIG_HOME || join(homedir(), ".config");
  const configPath = join(configHome, "pi", "skills-bridge.json");

  // ---- Read the file ----
  // sync is fine here: we're in startup, this file is ~100 bytes, and we
  // need the result before we can continue discovery.
  let raw: string;
  try {
    raw = readFileSync(configPath, "utf8");
  } catch {
    // File doesn't exist or permission denied — not an error.
    // Most developers will never create this file; cwd walk-up handles them.
    return null;
  }

  // ---- Parse JSON ----
  // Catch JSON.parse errors separately from file-read errors so we can
  // give a specific warning message that helps the developer fix their typo.
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    console.warn(
      `[skills-bridge] Invalid JSON in ${configPath}: ` +
        `${err instanceof Error ? err.message : String(err)}. ` +
        `Falling through to cwd walk-up.`,
    );
    return null;
  }

  // ---- Validate top-level shape ----
  // Must be a plain object. Arrays (valid JSON) and primitives (also valid)
  // are not meaningful config files for us.
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    console.warn(
      `[skills-bridge] Config at ${configPath} must be a JSON object. ` +
        `Falling through to cwd walk-up.`,
    );
    return null;
  }

  const obj = parsed as Record<string, unknown>;
  const config: BridgeConfig = {};

  // ---- skillsPath ----
  // Primary skills root. When set, this replaces cwd walk-up.
  // When absent or empty, walk-up handles discovery automatically.
  if (obj.skillsPath !== undefined) {
    if (typeof obj.skillsPath !== "string" || obj.skillsPath.trim().length === 0) {
      console.warn(
        `[skills-bridge] Config skillsPath must be a non-empty string. Ignoring.`,
      );
    } else {
      config.skillsPath = obj.skillsPath.trim();
    }
  }

  // ---- additionalPaths ----
  // Extra skills roots scanned alongside the primary.
  // Typical use: a developer keeps personal/experimental skills in a separate
  // checkout and wants them available alongside the team skills root.
  // Each entry that is a non-empty string is kept; everything else is warned
  // and skipped (so one bad entry doesn't discard all the good ones).
  if (obj.additionalPaths !== undefined) {
    if (!Array.isArray(obj.additionalPaths)) {
      console.warn(
        `[skills-bridge] Config additionalPaths must be an array. Ignoring.`,
      );
    } else {
      const paths: string[] = [];
      for (const item of obj.additionalPaths) {
        if (typeof item === "string" && item.trim().length > 0) {
          paths.push(item.trim());
        } else {
          console.warn(
            `[skills-bridge] Skipping non-string additionalPaths entry: ` +
              `${JSON.stringify(item)}`,
          );
        }
      }
      config.additionalPaths = paths;
    }
  }

  return config;
}

// ---------------------------------------------------------------------------
// Skills root resolution
// ---------------------------------------------------------------------------

/**
 * Resolve the ordered set of skills root directories.
 *
 * This is the central decision function: "where are the skills?"
 * It implements a three-tier priority system so that:
 *   - A developer who needs a one-off override can set an env var.
 *   - A developer with a persistent non-standard layout can set a config file.
 *   - Everyone else gets automatic discovery via cwd walk-up.
 *
 * THREE-TIER RESOLUTION:
 *
 *   Tier 1 — PI_SKILLS_PATH env var
 *     When set, this is the ONLY skills root. Config file and cwd
 *     walk-up are both ignored. additionalPaths from config are also NOT
 *     merged — the developer made an explicit choice to override. If they
 *     want env-var + extra paths, they should use the config file instead.
 *     If the path doesn't exist, we warn and return empty (graceful skip).
 *
 *   Tier 2 — Config file skillsPath
 *     When set (and env var is not), this becomes the primary root.
 *     additionalPaths from config are merged in alongside it.
 *     If the path doesn't exist, we warn and fall through to cwd walk-up —
 *     a stale config entry shouldn't leave you with no skills.
 *
 *   Tier 3 — Cwd walk-up
 *     The automatic fallback. Walks up from the current directory checking
 *     two things at each ancestor: (a) does this directory itself have a
 *     plugins/ subdirectory? (b) does it have an agent-skills-marketplace/
 *     child with plugins/? This makes no-config discovery work for any
 *     checkout with the right layout, not just the monolith submodule.
 *
 * DEDUPLICATION:
 *   Identical resolved paths only appear once. Node's path.resolve()
 *   normalizes paths (trailing slashes, . and .. segments), so the simple
 *   string comparison results.includes(resolved) is sufficient.
 *
 * RETURN: Array of absolute paths to skills root directories.
 *   Empty array means "no skills root found — skip silently."
 */
function findSkillRoots(cwd: string): string[] {
  // ---- Tier 1: env var (highest priority) ----
  // A developer who sets PI_SKILLS_PATH is saying "use this exact
  // skills root." We respect that by skipping all other discovery.
  const envPath = process.env.PI_SKILLS_PATH?.trim();
  if (envPath) {
    const resolved = resolve(envPath);
    if (!existsSync(resolved)) {
      console.warn(
        `[skills-bridge] PI_SKILLS_PATH is set but path doesn't exist: ` +
          `${resolved}. Skipping skills discovery.`,
      );
      return [];
    }
    return [resolved];
  }

  // ---- Load config (may be null if file missing or invalid) ----
  const config = loadConfig();
  const results: string[] = [];

  // ---- Tier 2: config file skillsPath ----
  // The developer's persistent preference. We validate that the path exists
  // before using it — a config that pointed at an old checkout that was
  // deleted shouldn't silently fail.
  if (config?.skillsPath) {
    const resolved = resolve(config.skillsPath);
    if (existsSync(resolved)) {
      results.push(resolved);
    } else {
      console.warn(
        `[skills-bridge] Config skillsPath doesn't exist: ${resolved}. ` +
          `Falling through to cwd walk-up.`,
      );
    }
  }

  // ---- Tier 3: cwd walk-up (automatic fallback) ----
  // Only runs when no primary root was found via config. This handles:
  //   - Developers who never created a config file (the common case)
  //   - Developers whose config skillsPath pointed at a nonexistent path
  // Walk-up always uses the event's cwd (pi's working directory), not
  // process.cwd(), because they could differ in forked sessions.
  if (results.length === 0) {
    const walked = walkUpFindSkillRoot(cwd);
    if (walked) {
      results.push(walked);
    }
  }

  // ---- Merge additionalPaths (only when env var is NOT set) ----
  // additionalPaths supplement the primary root. They're useful for:
  //   - Personal skill collections (experimental skills)
  //   - Multiple monolith checkouts (different branches, different submodule states)
  //   - Testing new skills before merging to the team skills root
  // Each path is validated; bad ones are warned and skipped individually
  // so one typo doesn't discard all additional paths.
  if (config?.additionalPaths && config.additionalPaths.length > 0) {
    for (const raw of config.additionalPaths) {
      const resolved = resolve(raw);
      if (!existsSync(resolved)) {
        console.warn(
          `[skills-bridge] Config additionalPaths entry doesn't exist: ` +
            `${resolved}. Skipping.`,
        );
        continue;
      }
      // Deduplicate: if the same skills root is already in results
      // (e.g., from config skillsPath or cwd walk-up), don't scan twice.
      if (!results.includes(resolved)) {
        results.push(resolved);
      }
    }
  }

  return results;
}

/**
 * Walk up the directory tree looking for a skills root.
 *
 * A "skills root" is any directory that contains a `plugins/` subdirectory
 * (the Claude Code plugin layout). We check two things at each ancestor:
 *
 *   1. Does this directory itself have a plugins/ subdirectory?
 *      → repo-agnostic: works for any checkout with the right layout.
 *      If you run pi inside agent-skills-marketplace/ itself, it's found
 *      immediately.
 *
 *   2. Does this directory have an agent-skills-marketplace/ child with
 *      a plugins/ subdirectory inside it?
 *      → monolith submodule convenience: the team's primary layout where
 *      agent-skills-marketplace is a git submodule at the monolith root.
 *
 * Check 1 runs first so that a direct match (the cwd IS a skills root)
 * wins over an indirect match via a submodule path.
 *
 * HOW IT WORKS — visual trace from a monolith checkout:
 *
 *   cwd = /work/monolith/backend/
 *
 *   iteration 0: check /work/monolith/backend/plugins/ → no
 *                check /work/monolith/backend/agent-skills-marketplace/plugins/ → no
 *                → go up to /work/monolith/
 *
 *   iteration 1: check /work/monolith/plugins/ → no
 *                check /work/monolith/agent-skills-marketplace/plugins/ → YES!
 *                → return /work/monolith/agent-skills-marketplace
 *
 * This works from ANY depth inside the monolith.
 *
 * WHY WALK UP AND NOT JUST CHECK <cwd>/agent-skills-marketplace?
 *   A developer might start pi from backend/ or frontend/. Checking only
 *   one level would miss it. Walking up handles all depths.
 *
 * WHY THE 64-ITERATION LIMIT?
 *   Prevents infinite loops if there's a symlink cycle or unusual filesystem
 *   layout. 64 levels up from any reasonable directory reaches the filesystem
 *   root on any OS. The loop also checks parent === current to detect when
 *   we've reached the root (resolve("/..") === "/").
 *
 * WHAT IT RETURNS:
 *   The absolute path to the skills root (the directory that contains the
 *   plugins/ directory, either directly or via agent-skills-marketplace/).
 *   This is NOT the plugins/ directory itself — discoverSkills() finds
 *   plugins/ under the returned root.
 *
 * RETURN: Absolute path to skills root, or null if not found.
 */
function walkUpFindSkillRoot(startDir: string): string | null {
  const monolithSubmodule = "agent-skills-marketplace";
  let current = resolve(startDir);

  for (let depth = 0; depth < 64; depth++) {
    // ---- Check 1: does <current>/plugins/ exist? (repo-agnostic) ----
    // The current directory IS a skills root if it directly contains
    // a plugins/ subdirectory with the Claude Code plugin layout.
    const directPlugins = join(current, "plugins");
    if (existsSync(directPlugins) && statSync(directPlugins).isDirectory()) {
      return current;
    }

    // ---- Check 2: does <current>/agent-skills-marketplace/plugins/ exist? ----
    // The monolith keeps agent-skills-marketplace as a git submodule.
    // This is the team's most common layout, so we check for it as a
    // convenience. Other submodule/repo names work via env var or config.
    const submoduleDir = join(current, monolithSubmodule);
    const subPluginsDir = join(submoduleDir, "plugins");
    if (existsSync(subPluginsDir) && statSync(subPluginsDir).isDirectory()) {
      return submoduleDir;
    }

    // Go up one level. resolve("..") on the root returns the root,
    // so this won't loop forever even without the depth limit.
    const parent = resolve(current, "..");
    if (parent === current) break; // reached filesystem root
    current = parent;
  }

  return null;
}

// ---------------------------------------------------------------------------
// Skill discovery
// ---------------------------------------------------------------------------

/**
 * Recursively find all directories under `root` that contain a SKILL.md file.
 *
 * HOW IT WORKS — visual trace:
 *
 *   skills/
 *   ├── plan-directory/
 *   │   ├── SKILL.md              ← FOUND (plan-directory is a skill)
 *   │   ├── references/
 *   │   │   └── some-guide.md     ← ignored (no SKILL.md)
 *   │   └── backend-ralph-plan/
 *   │       ├── SKILL.md          ← FOUND (backend-ralph-plan is a skill)
 *   │       └── references/
 *   └── pr-description-writer/
 *       └── SKILL.md              ← FOUND
 *
 * A directory IS a skill directory if it directly contains a SKILL.md file.
 * Once a skill directory is found, recursion STOPS at that boundary — Pi's
 * skill loader treats that directory as the skill root, so we must not
 * expose subdirectories (fixtures, templates, examples, vendored data) as
 * separate top-level skills. Sibling skills (like plan-directory and
 * backend-ralph-plan under the same skills/ directory) are still discovered
 * because the parent directory is not a skill directory itself.
 *
 * WHY RECURSIVE AND NOT FLAT?
 *   A flat read of the skills/ directory would only find plan-directory/.
 *   It would miss backend-ralph-plan/ which is a sibling skill directory
 *   (not nested inside plan-directory/). Recursive scanning catches all
 *   sibling skills under plugins/<plugin>/skills/. This is necessary
 *   because the agentskills.io standard allows skill directories anywhere
 *   under skills/, not just at the top level.
 *
 * BUT: recursion STOPS at a discovered skill boundary. Subdirectories
 *   inside a skill (references/, templates/, examples/) are never
 *   descended into. This prevents accidental registration of fixture
 *   or vendored SKILL.md files as separate top-level skills.
 *
 * WHY DEPTH LIMIT OF 5?
 *   The current plugin layout is:
 *     plugins/<plugin>/skills/<skill>/SKILL.md  = depth 3
 *   With nesting (plan-directory/skills/backend-ralph-plan/):
 *     plugins/<plugin>/skills/<skill>/<nested-skill>/SKILL.md = depth 4
 *   The limit of 5 provides headroom for deeper nesting while preventing
 *   infinite recursion from symlink loops or unusual directory structures.
 *
 * ERROR HANDLING:
 *   readdirSync and statSync are wrapped in try/catch. If a directory is
 *   unreadable (permission error, broken symlink), we skip it and continue
 *   with the rest. A single inaccessible directory shouldn't prevent the
 *   rest of the skills from being discovered.
 *
 * RETURN: Array of absolute paths to directories containing SKILL.md.
 */
function findSkillDirs(root: string, depth = 0): string[] {
  // Depth guard: prevents infinite recursion from symlink cycles.
  if (depth > 5) return [];

  const results: string[] = [];
  let entries: string[];

  // If we can't read the directory (permissions, doesn't exist, etc.),
  // just return what we have so far. Don't crash.
  try {
    entries = readdirSync(root);
  } catch {
    return results;
  }

  for (const entry of entries) {
    const full = join(root, entry);

    // Skip non-directories (files, symlinks to files, etc.).
    // We only care about directories because skills are directories
    // containing SKILL.md.
    let isDir: boolean;
    try {
      isDir = statSync(full).isDirectory();
    } catch {
      // Broken symlink, permission error, etc. Skip.
      continue;
    }
    if (!isDir) continue;

    // KEY CHECK: a directory is a skill directory if it contains SKILL.md.
    // This is the agentskills.io standard — the file must exist and be
    // named exactly "SKILL.md" (case-sensitive).
    if (existsSync(join(full, "SKILL.md"))) {
      results.push(full);
      // Skill root boundary — Pi's skill loader treats a SKILL.md directory
      // as the skill root and stops there. Do not recurse inside a discovered
      // skill: fixtures, templates, examples, or vendored content with their
      // own SKILL.md files must not be exposed as separate top-level skills.
      continue;
    }

    // Recurse into non-skill directories to discover nested skills.
    // This handles sibling skills under plugins/<plugin>/skills/ (e.g.,
    // plan-directory and backend-ralph-plan are siblings, not nested).
    results.push(...findSkillDirs(full, depth + 1));
  }

  return results;
}

/**
 * Discover all skill directories under a skills root's plugins/ tree.
 *
 * A "skills root" is any directory containing a `plugins/` subdirectory
 * with Claude Code-style plugin folders underneath. For example:
 *   /Users/alice/work/monolith/agent-skills-marketplace  ← skills root
 *   /Users/alice/work/monolith/agent-skills-marketplace/plugins/ ← plugins
 *   .../plugins/monty-code-review/skills/monty-code-review/ ← skill dir
 *
 * This function bridges the Claude Code plugin layout to pi's skill model.
 *
 * CLAUDE CODE LAYOUT (what exists):
 *   agent-skills-marketplace/
 *   └── plugins/
 *       ├── monty-code-review/          ← plugin (Claude Code install unit)
 *       │   ├── .claude-plugin/
 *       │   │   └── plugin.json
 *       │   ├── skills/
 *       │   │   └── monty-code-review/  ← skill dir (contains SKILL.md)
 *       │   │       └── SKILL.md
 *       │   └── commands/               ← Claude Code only (we skip these)
 *       │       └── code-review.md
 *       ├── backend-release/
 *       │   └── skills/
 *       │       └── release-manager/    ← skill dir (different name than plugin!)
 *       │           └── SKILL.md
 *       └── plan-directory/
 *           └── skills/
 *               ├── plan-directory/     ← skill dir
 *               │   └── SKILL.md
 *               └── backend-ralph-plan/ ← nested skill dir
 *                   └── SKILL.md
 *
 * PI SKILL MODEL (what we produce):
 *   Returns paths like:
 *     /path/to/plugins/monty-code-review/skills/monty-code-review
 *     /path/to/plugins/backend-release/skills/release-manager
 *     /path/to/plugins/plan-directory/skills/plan-directory
 *     /path/to/plugins/plan-directory/skills/backend-ralph-plan
 *
 * Pi then reads SKILL.md from each path and extracts name + description
 * from the YAML frontmatter. The skill name comes from the SKILL.md
 * frontmatter, NOT from the directory name (though by convention they match).
 *
 * WHAT WE SKIP AND WHY:
 *   - commands/ directories — these are Claude Code UX wrappers. They
 *     contain slash-command definitions like `/monty-code-review:code-review`
 *     that delegate to skills. Pi has its own `/skill:name` invocation
 *     system, so these aren't needed.
 *   - .claude-plugin/ directories — Claude Code package manifests.
 *     Not relevant to pi.
 *   - references/, scripts/, assets/ — loaded on demand by pi when a
 *     skill is invoked (progressive disclosure). We don't need to register
 *     these separately; pi discovers them relative to the skill directory.
 *
 * ERROR HANDLING:
 *   If plugins/ doesn't exist or can't be read, we warn and return empty.
 *   Individual plugin directories that lack a skills/ subdirectory are
 *   silently skipped (some plugins might only have commands, no skills).
 *   Plugin directories that can't be read are also silently skipped.
 *
 * RETURN: Array of absolute paths to skill directories (containing SKILL.md).
 */
function discoverSkills(skillsRoot: string): string[] {
  const pluginsDir = join(skillsRoot, "plugins");

  // The root might not have a plugins/ directory (e.g., if the
  // path points to a different kind of repo). Warn and skip.
  if (!existsSync(pluginsDir)) {
    console.warn(
      `[skills-bridge] No plugins/ directory found at ${pluginsDir}. ` +
        `Skipping this skills root.`,
    );
    return [];
  }

  // Read the list of plugin directories. Each subdirectory of plugins/
  // is a Claude Code plugin that MAY contain skills.
  let pluginNames: string[];
  try {
    pluginNames = readdirSync(pluginsDir);
  } catch {
    console.warn(
      `[skills-bridge] Cannot read plugins/ directory at ${pluginsDir}.`,
    );
    return [];
  }

  const skillDirs: string[] = [];

  for (const pluginName of pluginNames) {
    // Claude Code plugins store skills under plugins/<plugin>/skills/.
    // We check for this specific path — if it doesn't exist, this plugin
    // has no skills to bridge (it might be commands-only, or a non-plugin
    // directory like a README).
    const skillsDir = join(pluginsDir, pluginName, "skills");

    if (!existsSync(skillsDir)) continue;

    // Double-check it's actually a directory, not a file named "skills".
    let isDir: boolean;
    try {
      isDir = statSync(skillsDir).isDirectory();
    } catch {
      continue;
    }
    if (!isDir) continue;

    // Recursively discover skill directories under this plugin's skills/.
    // findSkillDirs handles nested skills (like plan-directory containing
    // backend-ralph-plan).
    const found = findSkillDirs(skillsDir);
    skillDirs.push(...found);
  }

  return skillDirs;
}

// ---------------------------------------------------------------------------
// Extension entry point
// ---------------------------------------------------------------------------

/**
 * Pi extension entry point.
 *
 * This is the function pi calls when loading the extension. It receives the
 * ExtensionAPI object and uses it to subscribe to lifecycle events.
 *
 * We subscribe to exactly ONE event: `resources_discover`. This is the
 * canonical pi extension hook for contributing skill paths. It fires after
 * `session_start` so we have access to the working directory.
 *
 * WHY resources_discover AND NOT settings.json?
 *   pi's settings.json supports `"skills": ["~/.claude/skills"]` but that
 *   only works for flat skill directories. This layout uses a nested
 *   plugin structure (plugins/* /skills/) that the flat path setting can't
 *   express. resources_discover gives us full control to walk the directory
 *   tree and return exactly the right paths.
 *
 * FLOW:
 *   1. pi fires "resources_discover" with the current working directory
 *   2. We resolve skills roots (env var → config → walk-up)
 *   3. We discover skill directories under each root
 *   4. We return { skillPaths: [...] } to pi
 *   5. Pi loads each skill (name + description only, per progressive disclosure)
 *
 * When no skills root is found (no roots, or roots with no skills), we return
 * undefined. Pi continues normally as if the extension wasn't there. This is
 * important: a missing skills root shouldn't prevent pi from starting.
 *
 * We use an async handler because pi requires all `resources_discover`
 * handlers to be async (they can return promises). Our code is synchronous
 * internally, but the async wrapper satisfies pi's contract.
 */
export default function (pi: ExtensionAPI) {
  pi.on("resources_discover", async (event) => {
    // Step 1: Where are the skills?
    //   Empty array = nowhere. We return undefined (graceful skip).
    const roots = findSkillRoots(event.cwd);
    if (roots.length === 0) {
      return;
    }

    // Step 2: What skills are in each skills root?
    //   Collect all skill directory paths across all roots.
    //   Multiple roots are supported (e.g., team skills root + personal
    //   skills root via additionalPaths). All skills from all roots are
    //   merged into one flat list.
    const allSkillDirs: string[] = [];

    for (const root of roots) {
      const skillDirs = discoverSkills(root);
      allSkillDirs.push(...skillDirs);
    }

    // Step 3: Tell pi about the discovered skills.
    //   Pi handles name-collision warnings (if a skill exists in both
    //   ~/.pi/agent/skills/ and the skills root).
    //   Pi handles progressive disclosure (only name + description at
    //   startup, full SKILL.md on demand).
    if (allSkillDirs.length === 0) {
      return;
    }

    return {
      skillPaths: allSkillDirs,
    };
  });
}
