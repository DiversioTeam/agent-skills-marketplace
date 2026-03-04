---
description: Pytest-only hardening lane using monty-code-review (dangerous test patterns with wrong/correct fixes).
---

Use your `monty-code-review` Skill in **pytest test-hardening lane**.

Scope and execution rules:
- Review pytest files only (`test_*.py`, `*_test.py`, `tests/**/*.py`).
- Default to changed-files-only scope (base branch diff + staged/unstaged/untracked).
- If no pytest files are in scope, return out-of-scope and stop.
- Run full-repo scan only if explicitly requested (`--all` or `scope all`).

Review focus:
- Dangerous silent-pass and false-confidence patterns.
- Include wrong/correct replacement snippets.
- Prioritize findings from `skills/monty-code-review/references/pytest-dangerous-patterns.md`.

Output requirements:
- Findings table with `Severity`, `Pattern`, `File:Line`, `Detector`, `Risk`, and `Safe Fix`.
- Severity tags: `[BLOCKING]`, `[SHOULD_FIX]`, `[NIT]`.
- Keep fixes minimal and behavior-preserving.
