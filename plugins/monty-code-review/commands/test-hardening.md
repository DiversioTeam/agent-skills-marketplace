---
description: Pytest-only hardening lane using monty-code-review (dangerous test patterns with wrong/correct fixes).
---

Use your `monty-code-review` Skill in **pytest test-hardening lane**.

Scope and execution rules:
- Use `.bin/pytest-file-selector` as the single source of truth for file selection.
  - Default (no args): changed-files-only scope (branch diff + staged + unstaged + untracked).
  - `--all`: full-repo scan (opt-in only).
  - `--base <ref>`: override base branch (strict — exits 1 if ref is invalid).
  - Exit 1 on unresolvable base or branch-diff failure (fail-closed).
- If the script outputs zero files, return out-of-scope and stop.
- Do NOT build your own file list — always delegate to this script.

Review focus:
- Dangerous silent-pass and false-confidence patterns.
- Include wrong/correct replacement snippets.
- Prioritize findings from `skills/monty-code-review/references/pytest-dangerous-patterns.md`.

Output requirements:
- Findings table with `Severity`, `Pattern`, `File:Line`, `Detector`, `Risk`, and `Safe Fix`.
- Severity tags: `[BLOCKING]`, `[SHOULD_FIX]`, `[NIT]`.
- Keep fixes minimal and behavior-preserving.
