---
name: repo-docs-generator
description: "Generate repository harness docs: a short AGENTS.md map, README.md, CLAUDE.md stub, and repo-local docs that make the codebase legible to agents."
allowed-tools: Bash Read Edit Write Grep Glob
argument-hint: "[path] (e.g., /path/to/repo or . for current directory)"
---

# Repository Documentation Generator Skill

Build repository docs as an engineering harness, not a prose dump.

This skill is aligned with OpenAI's February 11, 2026 harness-engineering
article:
- `AGENTS.md` should be a short routing map, not a giant manual.
- Detailed knowledge should live in versioned, repo-local docs.
- Repeated failures should become harness improvements: docs, wrappers, CI,
  lints, or clearer error messages.
- The goal is agent legibility and higher-quality autonomous work.

## When to Use This Skill

- A repo has weak, stale, or missing agent-facing documentation.
- `AGENTS.md` has become a long dumping ground instead of a navigation layer.
- Engineers or agents keep rediscovering the same commands, constraints, or
  failure modes.
- You want to canonicalize `CLAUDE.md` into a minimal `@AGENTS.md` stub.
- You want repo docs that improve execution speed, not just onboarding prose.

## Core Model

Treat documentation as a layered harness:

1. `README.md` is human-first quickstart and orientation.
2. `AGENTS.md` is the canonical agent entrypoint and routing map.
3. Topic-specific docs under `docs/` (or an equivalent repo-local location)
   hold the durable details.
4. `CLAUDE.md` is a minimal pointer that sources `AGENTS.md`.
5. Tooling and CI enforce the highest-value constraints mechanically.

Important nuance:
- `AGENTS.md` is the canonical entrypoint.
- The source of truth for a topic can live in a linked doc such as
  `docs/quality/gates.md` or `docs/architecture/overview.md`.
- `CLAUDE.md` must not carry unique behavioral rules.

## Required Outcomes

Every run should leave the repo with a clear harness shape:

- `AGENTS.md`
  - Short, scannable, and command-heavy.
  - Explains what the repo is, where important docs live, how to run key
    commands, and which constraints are non-negotiable.
  - Usually targets roughly 80-180 lines unless the repo is genuinely tiny.
- `README.md`
  - Preserves human-authored content.
  - Points readers to `AGENTS.md` and any major docs directories.
- `CLAUDE.md`
  - Minimal `@AGENTS.md` stub only.
- `docs/` (or existing equivalent)
  - Add or normalize topic-specific docs when the repo complexity warrants it.
  - Prefer a few focused docs over one giant file.

## Generate Mode

Use `/repo-docs:generate` when creating or rebuilding the harness from scratch.

### Generate Workflow

1. Discover actual behavior
   - Read existing `README.md`, `AGENTS.md`, `CLAUDE.md`, and any existing
     `docs/` indexes first.
   - Inspect manifests, wrappers, CI, pre-commit, scripts, Makefiles, and test
     commands.
   - Identify recurring failure modes, architectural boundaries, and the active
     type gate (`ty`, then `pyright`, then `mypy`, unless repo docs/CI differ).

2. Choose the smallest useful harness footprint
   - Tiny repo: `README.md`, `AGENTS.md`, `CLAUDE.md` may be enough.
   - Normal product repo: add focused docs for architecture, quality gates, and
     runbooks.
   - Complex monorepo: add per-domain docs and keep each `AGENTS.md` scoped to
     its directory.

3. Write docs in the right layer
   - Put stable commands, navigation, and "where truth lives" in `AGENTS.md`.
   - Put deep architecture, policies, plans, and runbooks in topic docs.
   - Keep diagrams optional; include them only when they clarify boundaries or
     flows better than prose and code references.

4. Encode the harness gap
   - If the repo repeatedly fails on the same issue, document the fix path and
     recommend or add mechanical enforcement when reasonable.
   - Prefer wrapper commands, lint messages, CI checks, and dedicated docs over
     repeating the same free-form instructions.

## Canonicalize Mode

Use `/repo-docs:canonicalize` when docs already exist but are stale or badly
structured.

### Canonicalize Goals

- Shrink oversized `AGENTS.md` files into routing maps.
- Move durable detail into focused repo-local docs.
- Remove stale commands and replace them with current wrappers and gates.
- Merge any valuable `CLAUDE.md` content into `AGENTS.md` or topic docs.
- Normalize every `CLAUDE.md` to a minimal stub.

### Canonicalize Rules

1. Analyze the actual repo before changing docs.
2. Use `--dry-run` first or pause for human confirmation before broad,
   ambiguous, or repo-wide reshaping.
3. Preserve valuable human-written content, but relocate it if it lives in the
   wrong layer.
4. Prefer `docs/quality/`, `docs/architecture/`, `docs/runbooks/`,
   `docs/plans/`, or existing equivalents over bloating `AGENTS.md`.
5. If `.pre-commit-config.*`, CI jobs, or wrappers define the real workflow,
   those must be reflected in the docs.
6. For Python repos, document the active type gate and treat `ty` as mandatory
   when configured.
7. Record recurring failure modes as explicit "golden rules" or gate docs.

## Recommended Artifact Shapes

Use the smallest structure that matches the repo:

- Small repo
  - `README.md`
  - `AGENTS.md`
  - `CLAUDE.md`
- Medium repo
  - `README.md`
  - `AGENTS.md`
  - `CLAUDE.md`
  - `docs/architecture/overview.md`
  - `docs/quality/gates.md`
  - `docs/runbooks/development.md`
- Complex repo or monorepo
  - Top-level `README.md`, `AGENTS.md`, `CLAUDE.md`
  - Per-domain docs such as `docs/architecture/`, `docs/quality/`,
    `docs/runbooks/`, `docs/specs/`, `docs/plans/`
  - Subdirectory `AGENTS.md` files only where scope genuinely diverges

## What Good Output Looks Like

The skill should optimize for:

- Fast "first 5 minutes" comprehension by an agent.
- Commands that actually work.
- Clear doc routing instead of duplicated prose.
- Explicit architectural boundaries and quality gates.
- A place for plans, specs, and recurring lessons to accumulate in-repo.
- Fewer rediscovered failures during later autonomous work.

## Important Rules

1. Read existing docs before writing anything.
2. Do not treat a giant `AGENTS.md` as success.
3. Preserve README content; enhance rather than replace.
4. Keep `CLAUDE.md` as a pointer only.
5. Prefer ASCII if you add diagrams.
6. Never guess commands or tech stack details; verify them.
7. If the repo already has a good docs hierarchy, improve it instead of
   replacing it with your preferred layout.
8. If you find repeated review or lint failures, turn them into docs or
   enforceable checks.

## Output Shape

Report work in this structure:

```text
## Documentation Updated

Repository: /path/to/repo
Harness shape: [small | medium | complex]

Files updated:
- AGENTS.md - [created/updated/trimmed]
- README.md - [created/updated/preserved]
- CLAUDE.md - [normalized]
- docs/... - [created/updated as needed]

Harness upgrades:
- [commands documented]
- [quality gates documented]
- [architecture/runbook docs added]
- [stale patterns removed]

Open follow-ups:
- [optional mechanical enforcement or missing docs]
```

## References

Load only what you need:

- `references/harness-principles.md`
  - Core policy, migration heuristics, and harness design rules.
- `references/generate-and-canonicalize-playbook.md`
  - Discovery commands, canonicalization steps, and stale-pattern checks.
- `references/templates.md`
  - Templates for `AGENTS.md`, `CLAUDE.md`, `README.md`, and topic docs.
