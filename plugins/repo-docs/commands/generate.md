---
description: "Generate repository harness docs: short AGENTS.md map, README.md, CLAUDE.md stub, and repo-local docs that make the codebase legible to agents."
---

Use your `repo-docs-generator` Skill in **generate** mode.

This mode follows the harness model described in OpenAI's February 11, 2026
article:
- https://openai.com/index/harness-engineering/

Analyzes the target repository to:
- Identify actual commands, wrappers, CI, and quality gates
- Build `AGENTS.md` as a short routing map instead of a giant manual
- Preserve and refresh `README.md` for human readers
- Normalize or create `CLAUDE.md` as a minimal `@AGENTS.md` stub
- Add focused repo-local docs under `docs/` when complexity warrants it
- Capture recurring failure modes as docs or explicit follow-up harness work

**Arguments:**
- `[path]` - Path to repository (defaults to `.` for current directory)

**Examples:**
```bash
/repo-docs:generate              # Current directory
/repo-docs:generate /path/to/repo
/repo-docs:generate ~/projects/my-app
```

**Output:**
- AGENTS.md: Concise agent entrypoint and doc index
- README.md: Human quickstart plus pointers to deeper docs
- CLAUDE.md: Minimal file that sources AGENTS.md
- docs/*: Architecture, quality, runbook, spec, or plan docs as needed

See the SKILL.md and references for the harness workflow, doc layering rules,
and optional ASCII diagram guidance.
