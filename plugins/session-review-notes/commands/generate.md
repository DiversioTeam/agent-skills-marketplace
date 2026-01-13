---
description: Upsert a single PR comment with session review notes (create or update the existing one).
argument-hint: "[--pr=<number|url|auto>] [--session-id=<id|auto>] [--dry-run] [--brief|--full] [--audience=<role>]"
---

Use your `session-review-notes` Skill to upsert a **single, auto-updating PR comment** via a **deterministic script** (hybrid approach):
- You (LLM) write a **payload JSON** (human narrative only).
- The script owns **idempotency, merging, markers, redaction, delta computation, and GitHub upsert**.

User arguments: `$ARGUMENTS`

Interpret flags (when present):
- `--pr=<number|url|auto>`: target PR (default: `auto` for current branch).
- `--session-id=<id|auto>`: session ID for the entry (default: `auto`).
- `--dry-run`: render the final comment body to stdout (do not post to GitHub).
- `--brief`: ~150-250 words, omit prompts section unless crucial.
- `--full`: include prompts-to-reproduce and more detail (still keep it scannable).
- `--audience=<role>`: tailor tone/terminology (e.g., "backend", "frontend", "data", "security", "EM").

Requirements:
- Focus on **what the human did** to steer the session (clarifications, constraints, corrections, tradeoffs).
- Summarize **what changed** at PR scope (don’t paste diffs).
- Avoid the “latest minor session trap”: the visible summary must cover the entire PR, while the newest session is logged as a delta.
- Call out **review hotspots / risks** and **tests actually run** (or explicitly say none were run).
- Redact secrets, tokens, customer PII, and internal URLs.
- Post the output as a PR comment. Only one such comment should exist: **update the existing one** if present (script-enforced).
- If the PR was built across multiple Codex/Claude sessions and you need help identifying them, run `/session-review-notes:list-sessions` first and ask the user which session IDs to backfill.

Implementation (script-driven):
1) Create a JSON payload for the script (human narrative only). Use this shape:
   - `intent`: string
   - `risk`: string (Low/Medium/High + 1-liner)
   - `tests_summary`: string (short summary; treated as self-reported unless you have hard evidence)
   - `pr_scope_bullets`: array of strings (short, PR-wide)
   - `hotspots`: array of strings (review focus / risks)
   - `prompts`: string (optional; redacted)
   - `session_label`: string (short)
   - `human_steering`: array of strings
   - `decisions`: array of strings
   - `delta_narrative`: string (short; what changed since prior update)
   - `tests_markdown`: string (GitHub task-list markdown)
   - `notes`: string
2) Write it to a temp file (or pipe to stdin).
3) Run the upsert script (Claude Code):
   - `python3 "${CLAUDE_PLUGIN_ROOT}/skills/session-review-notes/scripts/upsert-pr-comment.py" --tool claude --session-id <auto|id> --pr <auto|number|url> --payload <path|->`
   - If `CLAUDE_PLUGIN_ROOT` is unavailable, run the script from a marketplace checkout:
     - `python3 plugins/session-review-notes/skills/session-review-notes/scripts/upsert-pr-comment.py --tool claude --session-id <auto|id> --pr <auto|number|url> --payload <path|->`
4) Return a short confirmation with the comment URL (and do not re-print the entire comment body unless asked).
