# Session Transcripts (Codex + Claude Code)

This skill primarily relies on the **live chat context** plus the **PR diff**.
However, for multi-session work (especially across **Codex + Claude Code**), it’s useful to know where each tool stores session transcripts and how to enumerate them.

**Important:** transcripts often contain sensitive content (customer details, internal links, secrets pasted by accident). Treat them like production logs and **never paste them verbatim into GitHub**.

---

## Human-Readable Session Picker (Recommended)

If the agent can’t reliably discover which past sessions matter, generate a **short, human-readable list** and choose the relevant session IDs.

### Option A: Use the helper script (prints a Markdown table)

From the marketplace repo checkout:

```bash
python3 plugins/session-review-notes/skills/session-review-notes/scripts/list-sessions.py --project "$PWD" --limit 15
```

From a Codex skill install (typical path):

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
python3 "$CODEX_HOME/skills/session-review-notes/scripts/list-sessions.py" --project "$PWD" --limit 15
```

From Claude Code (plugin install):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/session-review-notes/scripts/list-sessions.py" --project "$PWD" --limit 15
```

The output includes:
- tool (`codex` / `claude`)
- session ID
- last-active time (relative)
- branch (Claude, when available)
- a short snippet of the first user prompt (redacted)

### Option B: Use the built-in interactive pickers

From the project directory:

- Codex: `codex resume` (or `codex resume --all` to include other directories)
- Claude Code: `claude --resume` (you can type to search)

When you’ve picked sessions, share just the **session IDs** (and optionally a 1-line label per session).

---

## Codex (OpenAI)

### Find / resume past sessions (built-in)

- Resume with an interactive selector:
  - `codex resume`
- Include sessions from outside the current working directory:
  - `codex resume --all`

### Current session ID

- Inside a running Codex interactive session, use:
  - `/status`

Codex prints the current conversation’s session ID via `/status`.

### Better-than-guessing: `notify` (optional)

Codex can be configured to invoke an external program after each turn via `notify` (advanced config). The JSON payload includes a thread/session identifier plus working directory.

If you want fully reliable “current session ID” capture without asking the user to run `/status`, configure `notify` to write the latest `{thread-id, cwd, timestamp}` to a local file your scripts can read.

### Where transcripts live (files)

Codex stores sessions under `$CODEX_HOME` (defaults to `~/.codex`) and writes session files under:

- `$CODEX_HOME/sessions/` (files under date-based subfolders)

Codex can also persist a transcript stream to a `history.jsonl` file via config (`history.persistence`).

### Practical: list the most recent session files

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
ls -t "$CODEX_HOME/sessions"/*/*/*/*.jsonl | head
```

### Practical: search across all Codex sessions

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
rg -n "agent-skills-marketplace" "$CODEX_HOME/sessions"
```

Good search keys:
- repo path fragments (`work/diversio/…`)
- branch names
- PR numbers
- commit SHAs

---

## Claude Code (Anthropic)

### Find / resume past sessions (built-in)

Claude’s CLI supports:
- An interactive session picker:
  - `claude --resume`
- Continue the most recent conversation:
  - `claude --continue`
- Resume a specific session:
  - `claude -r "<session-id>"`

### Current session ID + transcript path (most reliable)

Claude Code can pass `session_id` and `transcript_path` to a status line command/script (as JSON on stdin).

This is the most robust way to identify **the current session’s transcript file** without guessing based on timestamps.

### Where transcripts live (files)

In practice, Claude Code maintains transcript files on disk. Exact folder layout may change, so prefer `transcript_path` from status line / hooks when available.

- `~/.claude/history.jsonl` (an index/metadata log used for resume/continue flows)
- `~/.claude/projects/<normalized-project-path>/*.jsonl` (per-project session transcripts)

Some sessions also have a folder named after the session ID containing sub-agent transcripts, e.g.:

- `~/.claude/projects/<normalized-project-path>/<session-id>/subagents/*.jsonl`

### Practical: list recent session transcripts for one project

```bash
PROJECT_KEY="-Users-<you>-path-to-your-repo"
ls -t "$HOME/.claude/projects/$PROJECT_KEY"/*.jsonl | head
```

### Practical: search across all Claude Code sessions

```bash
rg -n "agent-skills-marketplace" "$HOME/.claude/projects"
```

---

## Recommended Pattern for This Skill (Don’t Overfit to Chat Logs)

To avoid missing earlier sessions or over-weighting the last “minor” session:

1. Use the **PR diff** as the canonical “What changed (full PR diff)” scope.
2. Use session transcripts only to enrich the **session log entries** (human steering + tests run).
3. Persist prior session entries in the single PR comment (the comment becomes your cross-tool session ledger).
