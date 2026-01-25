---
description: Audit and fix existing AGENTS.md/CLAUDE.md files - make AGENTS.md canonical, normalize CLAUDE.md to minimal stubs.
---

Use your `repo-docs-generator` Skill in **canonicalize** mode.

Recursively processes every directory with AGENTS.md and/or CLAUDE.md to:

1. **Analyze** actual code/tooling behavior (uv, .bin/*, CI jobs)
2. **Compare** existing docs against reality
3. **Merge** valuable CLAUDE.md content into AGENTS.md
4. **Rewrite** AGENTS.md with current commands and patterns
5. **Normalize** CLAUDE.md to minimal stub (`@AGENTS.md` + best-practices note)

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

**End state:**
- All AGENTS.md files are canonical, current, and accurate
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

See the SKILL.md "Canonicalize Mode" section for detailed workflow.
