---
description: "Audit and fix existing repo docs: trim AGENTS.md into a routing map, move deep detail into repo-local docs, and normalize CLAUDE.md to a stub."
---

Use your `repo-docs-generator` Skill in **canonicalize** mode.

This mode follows the harness model described in OpenAI's February 11, 2026
article:
- https://openai.com/index/harness-engineering/

Default to `--dry-run` or a human confirmation checkpoint before broad,
ambiguous, or repo-wide reshaping. Recursive canonicalization is high-impact
steer-mode work, not blind queue-mode work.

Recursively processes every directory with AGENTS.md and/or CLAUDE.md to:

1. **Analyze** actual code/tooling behavior (uv, .bin/*, CI jobs)
2. **Compare** existing docs against reality
3. **Shrink** oversized AGENTS.md files into short routing maps
4. **Move** durable detail into focused repo-local docs (`docs/quality/`,
   `docs/architecture/`, `docs/runbooks/`, etc.)
5. **Merge** valuable CLAUDE.md content into AGENTS.md or the right topic doc
6. **Encode** quality gates and common failure modes so agents stop
   rediscovering them
7. **Normalize** CLAUDE.md to minimal stub (`@AGENTS.md`)

**Arguments:**
- `[path]` - Path to repository (defaults to `.` for current directory)

**Flags:**
- `--dry-run` - Preview changes without applying them

**What gets fixed:**

| Stale Pattern | Current Pattern |
|---------------|-----------------|
| `pip install -r requirements.txt` | `uv sync` |
| `poetry install` / `poetry run` | `uv sync` / `uv run` |
| `python manage.py` | `.bin/django` or `uv run python manage.py` |
| `pytest` | `.bin/pytest` or `uv run pytest` |
| giant AGENTS.md handbook | short AGENTS.md map + focused topic docs |

**End state:**
- All AGENTS.md files are short, current, and act as canonical entrypoints
- Deep detail lives in focused repo-local docs instead of bloated AGENTS files
- All CLAUDE.md files are identical minimal stubs:
  ```markdown
  @AGENTS.md

  ---

  ## Notes
  This `CLAUDE.md` intentionally sources `AGENTS.md`...
  ```
- No directory has divergent specs between the two files

**Examples:**
```bash
/repo-docs:canonicalize              # Current directory
/repo-docs:canonicalize /path/to/repo
/repo-docs:canonicalize --dry-run    # Preview only
```

See the SKILL.md and references for the full canonicalization workflow.
