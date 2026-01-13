# Handoff (2026-01-13): `session-review-notes` Skill / Plugin (Codex + Claude Code)

I’m building a cross-platform **Agent Skill** + **Claude Code plugin** that upserts **exactly one** PR comment: a “session ledger” capturing **human steering**, **full-PR scope**, **delta since last update**, and **tests actually run** across **multiple Codex + Claude Code sessions**.

You’re an expert LLM engineer who knows Codex + Claude Code deeply. You don’t have access to my repo, so I’m including everything you need to reason about the design and help me harden it. I’m explicitly asking for **implementation guidance**, **failure-mode hardening**, and **creative/UI feedback**.

---

## 0) Agent Skills Standard (so we’re aligned)

This repo follows the **Agent Skills standard**: a Skill is a directory with `SKILL.md` (YAML frontmatter + instructions) plus optional `references/`, `scripts/`, etc. The same Skill can be installed into Codex.

This repo also includes **Claude Code plugin** metadata:
- Marketplace: `.claude-plugin/marketplace.json`
- Plugin manifest: `plugins/<plugin>/.claude-plugin/plugin.json`
- Slash commands: `plugins/<plugin>/commands/*.md`
- Skill + scripts: `plugins/<plugin>/skills/<skill-name>/...`

Codex consumes the **Skill directory** via installation into `$CODEX_HOME/skills/<skill-name>/...`.

---

## 1) What I’m building (and what it’s not)

### What it is

`session-review-notes`:
- Upserts **one** PR comment (create-or-update; never duplicates).
- Comment is a **mini database** + human narrative:
  1) **PR scope** (regenerated from PR diff every run, so it never “forgets” early work)
  2) **Session log** (cumulative entries per session across Codex + Claude)

### What it is not

It is not the PR description. It’s intentionally smaller and more operational:
- `pr-description-writer` = PR body narrative + diagrams + full test plan.
- `session-review-notes` = one upserted comment answering “how did the human steer the agent”, plus deltas and tests.

---

## 2) My opinionated architecture (hybrid, deterministic merge)

I’m following the “hybrid” recommendation:
- **LLM writes only narrative payload JSON** (intent, steering, decisions, tests, hotspots).
- **Deterministic script owns invariants**:
  - single-comment upsert
  - comment schema + markers
  - session entry identity + merging/dedup
  - PR machine facts (base/head, diffstat)
  - delta computation (previous head → current head)
  - redaction on everything going to GitHub
  - concurrency handling (merge → patch → verify → retry)

This is meant to permanently eliminate “LLM drift” failure modes: marker deletion, duplicate comments, overwritten ledgers, implied tests, etc.

---

## 3) Repo layout (everything relevant)

```text
plugins/session-review-notes/
  .claude-plugin/plugin.json
  commands/
    generate.md
    list-sessions.md
  skills/session-review-notes/
    SKILL.md
    references/
      transcripts.md
    scripts/
      list-sessions.py
      upsert-pr-comment.py
```

---

## 4) PR comment “database schema” (markers + state)

The comment is uniquely identified by a marker near the top:

```md
<!-- diversio:session-review-notes -->
```

Hidden state (single-line JSON):

```md
<!-- diversio:session-review-notes:state {"schema":2,"base":"main","head":"<sha>","prev_head":"<sha-or-null>","rev":3,"sessions_total":5,"codex":2,"claude":3,"included_sessions":[{"tool":"codex","id":"..."},{"tool":"claude","id":"..."}],"last_updated":"2026-01-13T07:48:00-05:00"} -->
```

Session log region is *inside* the wrapper details (canonical layout):

```md
<details>
<summary><strong>Session log (cumulative)</strong> <sub>(newest first)</sub></summary>

<!-- diversio:session-review-notes:sessions:start -->
...entries only...
<!-- diversio:session-review-notes:sessions:end -->

</details>
```

Each session entry has a hidden per-entry marker (for dedupe/update safety):

```md
<!-- diversio:session-review-notes:entry {"tool":"claude","session_id":"<id>","created_at":"<ISO8601>"} -->
<details>
<summary>...</summary>
...
</details>
```

---

## 5) End-to-end flow (how it runs)

### Claude Code (plugin install)

- Commands the user runs:
  - `/session-review-notes:list-sessions`
  - `/session-review-notes:generate`

My command docs call the scripts via `${CLAUDE_PLUGIN_ROOT}` (documented by Anthropic as the plugin root directory). This is a key thing I want you to sanity-check. Docs: `CLAUDE_PLUGIN_ROOT` env var in Claude Code plugins.  
https://docs.anthropic.com/en/docs/claude-code/plugins#environment-variables

### Codex (Skill install)

- Install Skill:
  - Use Codex skill installer (repo/path install) and restart Codex.
- Run:
  - Generate payload JSON (LLM)
  - Run `python3 scripts/upsert-pr-comment.py ...`

---

## 6) Handling multi-session + “latest minor session trap”

The big trap I’m trying to avoid:
- A tiny follow-up session overwrites intent and makes reviewers think that small delta is “the work”.

My hard rule:
- **PR scope summary is always regenerated from PR diff**
- **Newest session writes only a delta narrative and a session entry**

This means:
- Even if a user only runs the Skill from a “minor cleanup” session, the comment still describes the entire PR.

---

## 7) Session discovery problem (my current approach)

### What I can do today (best-effort)

I have `scripts/list-sessions.py` to print a **human-readable session picker** (Markdown table) and ask the user which sessions to include.

How it works:
- It resolves the “project root” via `git rev-parse --show-toplevel` (fallback to `--project` path).
- Codex: scans `$CODEX_HOME/sessions/**/*.jsonl` and extracts:
  - session id, cwd, timestamps, first meaningful user prompt snippet (redacted)
- Claude Code: scans `$CLAUDE_HOME/projects/.../*.jsonl` (and falls back to scanning all projects if the derived project key isn’t found) and extracts:
  - sessionId, cwd, gitBranch, timestamps, first meaningful user prompt snippet (redacted)

Key: it’s **human-in-the-loop**. If I can’t safely choose sessions, I show a table and let the user choose. That’s how I avoid the “most recent minor session trap” in multi-tool/multi-session scenarios.

### The gap / what I want your help with

I’m not happy relying on filesystem scanning forever. I want stable, officially supported hooks where possible:

#### Claude Code (best option)

Claude Code status line scripts get JSON on stdin including `session_id` and `transcript_path`. Docs:  
https://docs.anthropic.com/en/docs/claude-code/statusline

My idea: ship an **optional** tiny script that users can set as status line to write `{session_id, transcript_path, cwd}` into a predictable file, so `--session-id auto` can be 100% reliable (no guessing).

Question for you: can/should this be done via plugin-provided hooks/config, or must it be user-configured?

#### Codex (possible option)

OpenAI Codex supports `notify`: after each response, Codex can run a program with a JSON payload that includes a thread/session id and cwd. Docs:  
https://developers.openai.com/codex/config-advanced/#notifications

My idea: optionally configure `notify` to write `{thread-id, cwd, timestamp}` to a file, so “current session id” doesn’t require `/status` and doesn’t require scanning sessions.

Question for you: is this the “right” direction, and is the payload stable enough to depend on?

---

## 8) The deterministic upsert script (how it works)

File: `plugins/session-review-notes/skills/session-review-notes/scripts/upsert-pr-comment.py`

Behavior:
0) Validate + normalize the payload JSON (treat it as untrusted input; enforce types/lengths; downgrade tests to self-reported unless evidence).
1) Resolve PR (`--pr auto|number|url`), fetch PR metadata (base/head/additions/deletions/commits).
2) Find existing comment by marker, select most recently updated.
3) Fetch existing comment body and extract markers/state/session block (self-heal when needed).
4) Extract prior `head` from state marker; compute delta via compare endpoint:
   - `GET /repos/{owner}/{repo}/compare/{prev_head}...{head_sha}`
5) Merge session entries between markers; dedupe by per-entry meta marker key `(tool, session_id)`.
6) Render comment:
   - Distinct centered title
   - `[!IMPORTANT]` callout about “single upserted comment”
   - Summary table (Intent / PR coverage / PR size / sessions / delta / risk / tests)
   - Everything else collapsed under `<details>`
7) Redact:
   - Tokens (GitHub PATs, gh tokens, `sk-*`, AWS keys, private key blocks, Slack tokens)
   - URLs (allowlist GitHub host + PR host; replace others with `[URL]`)
   - home directory path → `~`
8) Update comment with bounded merge retries:
   - fetch latest → merge → patch → fetch+verify (rev/hash + entry presence) → retry if needed
9) Print comment URL only.

If you want to sanity-check a few implementation choices, here are the key invariants I’m enforcing:
- markers never change
- session entries must include the per-entry marker
- session log markers are inside wrapper (migration supported for older format)
- the script is the only writer to GitHub

---

## 9) Payload JSON (LLM-owned content)

The script expects a JSON payload containing human narrative only (no machine facts needed; it computes those).

Fields I’m using:
- `intent` (string)
- `risk` (string)
- `tests_summary` (string)
- `pr_scope_bullets` (array of strings)
- `hotspots` (array of strings)
- `prompts` (string, optional)
- `session_label` (string)
- `human_steering` (array of strings)
- `decisions` (array of strings)
- `delta_narrative` (string)
- `tests_markdown` (string, GitHub task list markdown)
- `notes` (string)

I’m explicitly trying to avoid overlap with PR description:
- I keep `pr_scope_bullets` short and scannable, and everything is under `<details>`.
- No “full narrative”; that’s PR body.

---

## 10) What I want from you (questions)

Please be opinionated and practical—tell me what you would actually ship.

### A) Claude Code specifics
1) Is `${CLAUDE_PLUGIN_ROOT}` the correct/robust way to reference plugin scripts from slash commands (in real projects)? Any gotchas on Windows?
2) Status line JSON includes `session_id` and `transcript_path`. Should I implement an optional status line helper script to write current session metadata to disk for 100% reliable `--session-id auto`?
3) Is there a better official way to list sessions than scanning `~/.claude/projects`? (CLI flags? a “list sessions” command?)

### B) Codex specifics
1) For “current session id”: is `notify` the best official hook-like mechanism, or is there a more direct API?
2) Is `history.jsonl` / `history.persistence` the right source for listing sessions without scanning `$CODEX_HOME/sessions`? (I currently scan sessions.)
3) Any stable, official metadata fields I should rely on for session pickers?

### C) Multi-tool correlation
1) What’s the best way to correlate “these sessions belong to this PR” without reading full transcripts?
   - I’m currently using: cwd within repo + timestamps + optional branch + optional PR URL/commit SHA grep.
2) Would you store `included_sessions` in the comment state (I do) so future updates can preserve a stable set even on different machines?
3) How would you handle a team scenario where multiple devs run updates from different machines (and don’t share transcript histories)?

### D) GitHub comment correctness / merge
1) Is `gh api` REST the best choice, or should I switch to GraphQL for comment enumeration/search?
2) If the comment is manually edited and markers are broken:
   - should I self-heal (rebuild the wrapper) silently, or should I add a visible warning in the comment?
3) Concurrency:
   - Is ETag/If-Match enough? Would you add a “rev” compare or checksum to detect stomped merges?

### E) Security & redaction
1) Are my regex patterns sufficient, or would you add more? (JWTs? OAuth bearer tokens? cookies?)
2) URL policy:
   - should I strip all URLs always, or allow only GitHub URLs?
3) Any known “gotchas” where tool output can leak secrets (e.g., `gh auth status`) and how you’d guardrail the LLM from pasting it?

### F) UX / information design
1) How would you make the comment even more skimmable without losing trustworthiness?
   - I’m using banner + summary table + everything else collapsed.
2) Would you add a deterministic “hotspot map” table (top dirs by churn) computed from compare/file stats?
3) How would you make “Tests” impossible to misread (e.g., `[x]` only with evidence)?

---

## 11) My next steps (unless you suggest otherwise)

1) Optional: implement **Claude status line helper** to persist `{session_id, transcript_path}` for reliable `--session-id auto`.
2) Optional: implement **Codex notify helper** to persist `{thread-id, cwd}` for reliable `--session-id auto`.
3) Add a deterministic “hotspot map” table (compare stats → top dirs).
4) Decide on backfill ordering:
   - current behavior inserts new entries at top; for “backfill” this may mis-order entries.
   - I could sort session entries by meta `created_at` (if you recommend it).

---

## 12) Key upstream docs I used (for your quick reference)

- Claude Code plugins: `CLAUDE_PLUGIN_ROOT` env var  
  https://docs.anthropic.com/en/docs/claude-code/plugins#environment-variables
- Claude Code status line: `session_id` and `transcript_path`  
  https://docs.anthropic.com/en/docs/claude-code/statusline
- OpenAI Codex advanced config: `notify` payload  
  https://developers.openai.com/codex/config-advanced/#notifications
- OpenAI Codex config reference: `history.persistence` / `history.jsonl`  
  https://developers.openai.com/codex/config-reference/
