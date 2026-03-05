# Harness Principles

This file extends `SKILL.md` with the design rules behind the repo-docs skill.

Primary inspiration:
- OpenAI, February 11, 2026: https://openai.com/index/harness-engineering/

## Source Model

The repo-docs skill should optimize for execution, not literary completeness.

Use this layered model:

1. `README.md`
   - Human-first orientation, install, quickstart, and project purpose.
   - Should point to `AGENTS.md` for agent navigation and deeper repo docs.
2. `AGENTS.md`
   - Canonical entrypoint for agents.
   - Short routing map with key commands, boundaries, and links to deeper docs.
3. Topic docs
   - Versioned repo-local files for architecture, gates, runbooks, specs, and
     plans.
4. Tooling
   - Linters, wrappers, CI, and tests that enforce the most important rules.

## Repository Legibility Rules

A repo is "legible to agents" when:

- An agent can discover the correct commands without guessing.
- Architectural boundaries are explicit and local.
- Repeated failure modes are written down close to the code.
- Plans and specs are committed, not trapped in chat history.
- The docs layout makes it obvious where to add new durable knowledge.

## AGENTS.md Rules

`AGENTS.md` should not be the whole handbook.

Prefer these sections:

- What this repo is
- How to navigate the docs
- Commands that actually work
- Non-negotiable invariants and gates
- Directory-scoped guidance or links
- How to update the harness when you learn something

Avoid these anti-patterns:

- Huge architecture essays better suited for `docs/architecture/`
- Long runbooks better suited for `docs/runbooks/`
- Plan details that belong in `docs/plans/`
- Duplicated content already covered by topic docs

## Topic Doc Heuristics

Create focused docs when there is enough stable detail to justify them.

Recommended categories:

- `docs/architecture/`
  - System boundaries, request/data flows, ownership seams, integration maps.
- `docs/quality/`
  - Pre-commit, CI, type gates, test strategy, recurring lint failures,
    required wrappers, golden rules.
- `docs/runbooks/`
  - Development setup, release/deploy checklists, debugging, incident response.
- `docs/specs/`
  - Product or technical specs that define intended behavior.
- `docs/plans/`
  - Execution plans, migration plans, staged rollouts, follow-up work.

Use existing repo conventions when present; do not force `docs/` if the repo
already has a clear equivalent such as `design/`, `adr/`, or `runbooks/`.

## Mechanical Enforcement Rule

If a rule matters enough to repeat, it likely matters enough to encode.

Prioritize:

1. Tooling or CI enforcement.
2. Wrapper commands with clear error messages.
3. A focused doc page linked from `AGENTS.md`.
4. Free-form prose only when the above are not practical yet.

Examples:

- Repeated lint failures -> document in `docs/quality/gates.md`, then add or
  improve wrapper commands.
- Repeated architecture violations -> document boundaries in
  `docs/architecture/overview.md`, then add CI or lint checks if possible.
- Repeated migration mistakes -> add a migration runbook and link it from
  `AGENTS.md`.

## Canonicalization Heuristics

When docs are messy:

- Keep `AGENTS.md` as the canonical entrypoint.
- Move deep detail into focused docs.
- Normalize `CLAUDE.md` to `@AGENTS.md`.
- Remove stale package-manager or wrapper examples.
- Prefer current CI and wrapper behavior over old prose.
- Add missing docs only where they reduce future rediscovery cost.

## Review Questions

Before finishing, ask:

- Can a new agent find the right command path in under 30 seconds?
- Are the highest-cost failures documented or enforced?
- Does `AGENTS.md` point to the right places instead of duplicating them?
- Do the docs make future plans/specs discoverable inside the repo?
- Did we reduce future guesswork, or just generate more text?
