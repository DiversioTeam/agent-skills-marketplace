---
description: Generate comprehensive AGENTS.md, README.md, and CLAUDE.md documentation for a repository.
---

Use your `repo-docs-generator` Skill in **generate** mode.

Analyzes the target repository to:
- Identify tech stack (Python, JS/TS, Java, Go, Rust, Terraform, etc.)
- Understand architecture patterns
- Detect quality gates (pre-commit, linters/formatters, template tooling) and
  document them so agents don’t rediscover failures at commit time
- Create ASCII architecture diagrams (standard ASCII only, no Unicode)
- Preserve existing documentation content
- Generate three standardized files: AGENTS.md, README.md, CLAUDE.md

**Arguments:**
- `[path]` - Path to repository (defaults to `.` for current directory)

**Examples:**
```bash
/repo-docs:generate              # Current directory
/repo-docs:generate /path/to/repo
/repo-docs:generate ~/projects/my-app
```

**Output:**
- AGENTS.md: Comprehensive architecture docs with ASCII diagrams
- README.md: Enhanced with architecture overview (preserves existing)
- CLAUDE.md: Minimal file that sources AGENTS.md

See the SKILL.md for detailed workflow and ASCII diagram standards.
