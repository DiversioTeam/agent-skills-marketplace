# skills-bridge

Selects marketplace skill roots for Pi using an environment override, developer
config, or the current checkout. Pi itself scans the selected
`plugins/*/skills/` directories and loads skills on demand.

## Why keep the bridge?

Native Pi already supports nested skill directories through `--skill`, skill
settings, and package manifests. The bridge adds **root selection**, not a
separate skill loader:

- `PI_SKILLS_PATH` for a session override.
- A persistent primary root and additional roots in developer config.
- Automatic selection of the marketplace in the current monolith/worktree.

Pi lists skill names, descriptions, and file locations in the initial model
context. Full instructions load on demand through native skill behavior. Claude Code
`commands/` wrappers are not registered as Pi commands.

## Install

From the monolith root:

```bash
pi install "$PWD/agent-skills-marketplace/pi-packages/skills-bridge"
```

For project-local installation, add `-l`. Restart Pi or run `/reload` afterward.
The marketplace root package already includes this extension; do not also
install the standalone package alongside it.

A global install persists across worktrees, but **the selected skill checkout
still depends on the rules below**. Starting outside a matching checkout does
not automatically select the extension's own checkout.

## Root selection

1. **`PI_SKILLS_PATH`**: a non-empty value overrides config and ancestor discovery,
   including `additionalPaths`. A nonexistent override returns no skills; it
   never silently switches to another checkout.
2. **Developer config**: `$XDG_CONFIG_HOME/pi/skills-bridge.json`, or
   `~/.config/pi/skills-bridge.json` when that variable is unset/empty.
   An existing `skillsPath` wins; if absent or
   nonexistent, ancestor discovery supplies the primary root. Malformed config
   warns and falls back. Missing/unreadable config also falls back.
3. **Ancestor discovery**: walk upward from Pi's event cwd. At each ancestor,
   prefer `agent-skills-marketplace/plugins/` over a direct `plugins/` directory.
   The nearest matching ancestor wins. Missing candidates are skipped; other
   inspection errors warn and stop automatic selection rather than silently
   choosing a different checkout. Explicit `additionalPaths` still contribute.

Config `additionalPaths` supplement the primary root unless the environment
variable is set. Nonexistent extra paths warn and are skipped; normalized
identical roots are scanned once. Discovery runs again on `/reload`.

Use absolute paths. Every bridge root must contain a `plugins/` directory:

```json
{
  "skillsPath": "/path/to/agent-skills-marketplace",
  "additionalPaths": ["/path/to/another-marketplace"]
}
```

Both fields are optional. `{}` means ancestor discovery only. An existing root
without readable `plugins/` contributes no skills and emits a warning.

## Native discovery and compatibility

Since **0.0.3**, the bridge returns plugin `skills/` directories rather than
recursively locating individual `SKILL.md` files. Pi owns recursive discovery,
ignore rules, skill-root boundaries, and name collisions.

Discovery inside those directories follows these native rules:

- Hidden directories, `node_modules`, and ignored paths are no longer exposed by
  the custom scanner. Filtering applies within each supplied plugin `skills/`
  root; ignore files above that root are not inherited.
- As before, a skill-root boundary stops discovery of nested fixtures as
  separate skills; Pi now enforces that boundary.
- The bridge's old recursion-depth limit is gone.
- Native root-level Markdown skills with valid frontmatter can also load.

Validated with Pi **0.70.6** (the CI pin) and **0.85.1**. Root-selection precedence
is unchanged; no user settings or config files are migrated.

For ordinary skill collections without `plugins/`, use native Pi settings or
`--skill /path/to/skills` instead. For one fixed marketplace checkout, a package
manifest can use `"pi": {"skills": ["plugins/*/skills"]}` without a bridge. Do not add that
alongside this bridge as an interchangeable fallback: same-name skill selection
can favor the fixed package and defeat checkout-specific overrides.

## Verify

From the marketplace root:

```bash
PI_TEST_BINARY="$(command -v pi)" \
  pnpm --config.verify-deps-before-run=false --dir pi-packages/skills-bridge test

printf '{"id":"cmds","type":"get_commands"}\n' | \
  PI_OFFLINE=1 PI_SKILLS_PATH="$PWD" pi --mode rpc --no-session \
    --no-context-files --no-extensions -e ./pi-packages/skills-bridge \
    --no-prompt-templates --no-skills
```

Inspect returned commands with `source: "skill"`. This tests actual Pi discovery,
not a second hand-written scanner. Tests require Node 24 and Pi on PATH; set
`PI_TEST_BINARY` to test another installed Pi binary. The command above captures
the shell's Pi before pnpm adds dependency binaries to PATH. They use temporary roots
and offline RPC discovery, including a reload that switches configured
checkouts, without invoking skills or changing user settings.

See the [plugin catalog](../../docs/plugins/catalog.md) for available skills.

## Troubleshooting and updates

- No skills: check the selected root contains `plugins/<plugin>/skills/` and the
  monolith submodule is initialized. Outside a matching checkout, set an explicit
  root or use native skill settings.
- Missing previously exposed skills: check native ignore rules and whether the
  files live in hidden/dependency directories.
- Wrong checkout or name collisions: inspect returned skill source paths; avoid
  loading the same skill names through both native fixed paths and the bridge.
- Local-path installs read the checkout directly. After changing it, `/reload`
  is sufficient; remove/reinstall is not required.

To remove the standalone package:

```bash
pi list
pi remove /path/to/agent-skills-marketplace/pi-packages/skills-bridge
```

Restart or `/reload`. The separate developer config is left untouched.
