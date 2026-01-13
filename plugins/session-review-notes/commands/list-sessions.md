---
description: List recent Codex + Claude Code sessions for this project (human-readable) so you can choose which ones to include.
argument-hint: "[--limit=<n>] [--scan=<n>] [--tool=all|codex|claude] [--project=<path>]"
---

Use your `session-review-notes` Skill to produce a **human-readable session picker** for this project.

User arguments: `$ARGUMENTS`

Requirements:
- Print a **Markdown table** of recent sessions for the current project with:
  - tool (`codex` / `claude`)
  - session ID
  - last-active time (relative)
  - start time (local)
  - branch (if available)
  - a short first-prompt snippet (redacted)
- Redact secrets/tokens and URLs in the snippet.
- After the table, ask the user which session IDs to include for backfilling the PR comment.

Implementation note:
- Prefer using the helper described in `skills/session-review-notes/references/transcripts.md` (it includes a script-based picker).
- In Claude Code, run:
  - `python3 "${CLAUDE_PLUGIN_ROOT}/skills/session-review-notes/scripts/list-sessions.py" --project "$PWD" --limit 15`
  - If `CLAUDE_PLUGIN_ROOT` is unavailable, run from a marketplace checkout:
    - `python3 plugins/session-review-notes/skills/session-review-notes/scripts/list-sessions.py --project "$PWD" --limit 15`
