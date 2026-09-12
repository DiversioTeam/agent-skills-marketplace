# Templates

Use only the sections needed by the actual repo; these are not a minimum size
or a required directory tree. Verify safety claims before filling permission
placeholders; see [model guidance](model-guidance.md).

## AGENTS.md Template

````markdown
# AGENTS.md

## What This Repo Is

<One short paragraph on purpose and shape.>

## How To Navigate This Repo

- Start here for commands and repo-wide rules.
- Use `<architecture doc>` when changing service boundaries.
- Use `<quality doc>` to choose the gates required for the changed area.
- Use `<deployment runbook>` when preparing an authorized deployment.

## Commands

```bash
<verified command>
<verified command>
<verified command>
```

## Non-Negotiable Rules

- <hard invariant>
- <hard invariant>
- <hard invariant>

## Completion And Permissions

- <Requested outcome and required verification; omit redundant generic advice.>
- <Verified safe local actions allowed without repeated approval.>
- <Actions needing separate authorization; name targets and side effects.>

## Keep The Harness Fresh

- If a failure repeats, update docs or tooling.
- If a command changes, update this file and the linked source doc.
- If a new durable workflow appears, add a focused doc instead of expanding
  this file indefinitely.
````

## CLAUDE.md Template

```markdown
@AGENTS.md

---

## Notes

This `CLAUDE.md` intentionally sources `AGENTS.md` so that requirements,
commands, and agent behavior have a single canonical entrypoint in this repo.
```

## README.md Addition

Add a short note near the top:

```markdown
> For agent-oriented commands, repo rules, and deeper project docs, see
> [AGENTS.md](./AGENTS.md).
```

## docs/quality/gates.md Template

````markdown
# Quality Gates

## Required Commands

```bash
<pre-commit command>
<test command>
<type-check command>
```

## Active Type Gate

- <ty | pyright | mypy>
- Why it is the active gate in this repo

## Common Failures

- <failure mode> -> <how to avoid it>
- <failure mode> -> <how to avoid it>

## CI Notes

- <job name> verifies <scope>
- <job name> verifies <scope>
````

## docs/architecture/overview.md Template

```markdown
# Architecture Overview

## Main Components

- `<component>` - <responsibility>
- `<component>` - <responsibility>

## Boundaries

- `<boundary>` must not depend on `<boundary>`
- `<boundary>` owns `<data or behavior>`

## Main Flows

1. <request or job flow>
2. <request or job flow>

## Useful Code References

- `<path>` - <why it matters>
- `<path>` - <why it matters>
```
