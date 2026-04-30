# skills-bridge

Pi extension that auto-discovers Claude Code plugin skills from `plugins/*/skills/` directories and registers them as pi skills. One install bridges all 21 plugin skills into pi without restructuring the repo.

## What it does

The Diversio team has 21 Claude Code skills (`release-manager`, `monty-code-review`, `backend-atomic-commit`, etc.) in the shared repo. Claude Code and Codex users see them automatically. Pi users don't — pi only discovers skills from `~/.pi/agent/skills/` and `pi-packages/*/skills/`, not from `plugins/*/skills/`.

This extension bridges that gap. It uses pi's `resources_discover` hook to scan the plugins directory and register skill paths. One `pi install` per team member, then `/reload`, and all 21 skills appear.

**Context safety:** The extension only exposes skill names + descriptions (~5-10KB total) at startup. Full `SKILL.md` bodies load on demand when a skill is invoked. No context bloat.

## Install

**Global (recommended for worktree-heavy teams):**

```bash
# From the monolith root
pi install "$PWD/agent-skills-marketplace/pi-packages/skills-bridge"
```

**Project-local (for single-repo teams):**

```bash
# From the monolith root
pi install -l ./agent-skills-marketplace/pi-packages/skills-bridge
```

Then restart pi or run `/reload` in an existing session.

## How it finds the skills

The extension uses three-tier resolution to find the `agent-skills-marketplace` root:

1. **`PI_SKILLS_PATH` env var** (highest priority) — explicit session-level override. The extension uses this path and skips everything else.
2. **`~/.config/pi/skills-bridge.json` config file** — persistent per-developer config with `skillsPath` and optional `additionalPaths`.
3. **Cwd walk-up** (fallback) — walks up from the working directory looking
   for a `plugins/` directory (repo-agnostic) or an
   `agent-skills-marketplace/plugins/` child (monolith submodule convenience).

For most developers in the monolith, tier 3 works automatically. No config needed.

### Config file

For developers who keep skills at a non-standard path or want extra skill sources:

```bash
mkdir -p ~/.config/pi
```

Create `~/.config/pi/skills-bridge.json`:

```json
{
  "skillsPath": "/absolute/path/to/agent-skills-marketplace",
  "additionalPaths": [
    "/another/checkout/agent-skills-marketplace",
    "/path/to/experimental-skills"
  ]
}
```

- `skillsPath` — primary skills root (optional; falls through to cwd walk-up if absent)
- `additionalPaths` — extra skills roots to also scan (optional)
- Both fields are optional; an empty file `{}` means "use cwd walk-up only"
- The config file lives outside the package repo, so updating the repo never overwrites local config
- When `PI_SKILLS_PATH` env var is set, the config file is ignored (env var is an explicit override)

## Verify

After installing and restarting pi, check that skills appear:

1. Type `/skill:<tab>` in pi — you should see `release-manager`, `monty-code-review`, `backend-atomic-commit`, and others
2. Try `/skill:release-manager` — it should load the full release workflow instructions

To verify discovery without restarting pi, run this standalone test:

```bash
cd /path/to/monolith
node -e "
const { existsSync, readdirSync, statSync } = require('node:fs');
const { join } = require('node:path');
function findSkillDirs(root, depth=0) {
  const results = [];
  if (depth > 5) return results;
  let entries;
  try { entries = readdirSync(root); } catch { return results; }
  for (const entry of entries) {
    const full = join(root, entry);
    let isDir;
    try { isDir = statSync(full).isDirectory(); } catch { continue; }
    if (!isDir) continue;
    if (existsSync(join(full, 'SKILL.md'))) results.push(full);
    results.push(...findSkillDirs(full, depth+1));
  }
  return results;
}
const pluginsDir = 'agent-skills-marketplace/plugins';
const plugins = readdirSync(pluginsDir);
let total = 0;
for (const p of plugins) {
  const sd = join(pluginsDir, p, 'skills');
  if (!existsSync(sd)) continue;
  const found = findSkillDirs(sd);
  total += found.length;
}
console.log('Skills discovered:', total);
"
```

## Skills bridged

The extension discovers all 21 skills from these plugins:

`release-manager`, `monty-code-review`, `backend-atomic-commit`, `backend-pr-workflow`, `plan-directory`, `backend-ralph-plan`, `pr-description-writer`, `process-code-review`, `bruno-api`, `code-review-digest-writer`, `mixpanel-analytics`, `clickup-ticket`, `github-ticket`, `repo-docs-generator`, `visual-explainer`, `dependabot-remediation`, `terraform-atomic-commit`, `terraform-pr-workflow`, `login-cta-attribution-skill`, `monolith-review-orchestrator`, `frontend`

## Team setup

Each team member runs one command:

```bash
# In the monolith root
pi install "$PWD/agent-skills-marketplace/pi-packages/skills-bridge"
```

Then `/reload` (or restart pi). Skills appear immediately.

### Worktree behavior

Global install (without `-l`) persists across all git worktrees. If you use `scripts/create_worktree.py`, you only need to install once in the main monolith checkout.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Skills don't appear after `/reload` | Extension can't find skills root | Check `PI_SKILLS_PATH` or verify `agent-skills-marketplace/plugins/` exists |
| "Skill name collision" warnings | Same skill registered from multiple sources | Check if the skill exists in both `~/.pi/agent/skills/` and the skills root |
| Extension causes pi startup error | TypeScript syntax error in extension | Check pi startup logs |
| Skills appear but `/skill:name` doesn't load content | SKILL.md structure issue | Verify the skill directory follows `plugins/<name>/skills/<skill>/SKILL.md` |
| Submodule not initialized | `git submodule update --init` hasn't been run | Run `git submodule update --init agent-skills-marketplace` |

## Rollback

```bash
# Find the installed package path
pi list

# Remove it
pi remove /path/to/agent-skills-marketplace/pi-packages/skills-bridge

# Restart pi or /reload
```

The config file at `~/.config/pi/skills-bridge.json` is not affected by install/remove — it's a separate per-developer file. Delete it manually if you want to remove all traces.

## Updating

When new skills are added or the extension is updated:

```bash
# Remove and reinstall to pick up the latest extension code
pi remove /path/to/agent-skills-marketplace/pi-packages/skills-bridge
pi install /path/to/agent-skills-marketplace/pi-packages/skills-bridge
# Then /reload
```
