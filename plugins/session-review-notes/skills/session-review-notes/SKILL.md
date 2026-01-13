---
name: session-review-notes
description: "Upsert a single PR comment that serves as an AI session ledger (human steering, deltas, tests) across Codex + Claude Code. Not a PR description."
tools: [Bash, Read, Write, Grep, Glob]
allowed-tools: Bash Read Write Grep Glob
---

# Session Review Notes Skill

## When to Use This Skill

Use this skill at the end of an AI-assisted coding session (Codex or Claude Code) when you want to:

- Give reviewers the **intent and rationale** that a diff/PR alone can’t capture.
- Make “prompt requests” practical by summarizing **how the human steered** the work.
- Highlight **what to review** (risks, tricky areas, assumptions, tradeoffs).
- Post a **single, auto-updating PR comment** (create-or-update) that stays scannable.

This is **not** a replacement for a PR description:
- Use `pr-description-writer` for the PR body (narrative, diagrams, full test plan).
- Use `session-review-notes` for a single upserted comment that tracks **human steering across sessions** and avoids the “latest minor session” trap.

## Inputs / Assumptions

- You are in an active chat that includes the session’s conversation history.
- If the work involves a git repo, you can access it via `Bash`.
- You have GitHub CLI (`gh`) installed and authenticated for the target repo.
- If you can’t reliably infer the PR, base branch, or commit range, ask the user.

## Architecture (Hybrid: LLM + Deterministic Script)

This skill is intentionally **hybrid**:

- **LLM responsibility (high-level narrative only):** produce a small JSON payload capturing intent, human steering, decisions, tests, and reviewer hotspots.
- **Script responsibility (invariants, no exceptions):** create-or-update the single PR comment, preserve/merge the session log, compute PR facts + delta, apply redaction, and talk to GitHub via `gh api`.

Use the deterministic script:
- `scripts/upsert-pr-comment.py`

## Payload JSON (LLM-Owned)

The script consumes a **small JSON payload** containing only human narrative (it will compute PR facts + delta itself).

Minimum recommended shape:

```json
{
  "intent": "1–2 sentences: what we were trying to do and why",
  "risk": "Low/Medium/High + 1-liner justification",
  "tests_summary": "Short, evidence-based summary (or 'None recorded')",
  "pr_scope_bullets": ["PR-wide changes, not just this chat"],
  "hotspots": ["Where reviewers should focus / risks"],
  "prompts": "Optional. Minimal prompts-to-reproduce (redacted).",
  "session_label": "Short label for this session entry",
  "human_steering": ["Constraints, clarifications, reversals, corrections"],
  "decisions": ["Tradeoffs chosen + why"],
  "delta_narrative": "Short: what changed since prior update",
  "tests_markdown": "- [ ] pytest ...\\n- [x] ruff ... (pass)",
  "notes": "Anything reviewers should know (uncertainties, follow-ups)"
}
```

Rules:
- Keep `pr_scope_bullets` and `hotspots` scannable (short bullets, no diffs).
- `tests_markdown` must be **GitHub task list** markdown. The script treats `[x]` as **self-reported**, not verified, and will render it explicitly as such.
- Redact secrets/tokens, customer PII, and internal URLs (the script also redacts as a safety net).

## Comment Identity (Distinct + Idempotent)

This skill must ensure **only one** such comment exists per PR by using a hidden marker that you can search for and update:

```text
<!-- diversio:session-review-notes -->
```

Rules:
- The marker must appear **once near the top** of the comment body.
- Before posting, search existing PR comments for the marker:
  - If found, **update** that comment (do not add another).
  - If multiple are found, update the **most recently updated** one and call out the duplication as a follow-up.

## Multi-Session Support (Codex + Claude Code)

This skill assumes a PR may be produced across **multiple agent sessions**, possibly in **different tools** (Codex and Claude Code).

Principle: the PR comment is a **living ledger** with two layers:
- **PR scope (always regenerated):** derived from the full PR diff so it never “forgets” earlier work.
- **Session log (cumulative):** each run adds (or updates) a session entry capturing **human steering** and the **delta since the prior update**.

## Session Selection (Human-Readable)

Sometimes you need to backfill earlier work (e.g., several Codex + Claude Code sessions happened but only the final session is open right now).

If you can’t confidently identify which sessions matter:

1. Generate a short, human-readable list of recent sessions for this project (tool, session ID, timestamp, branch, first-prompt snippet).
   - Prefer the helper described in `references/transcripts.md`.
2. Ask the user to pick the relevant session IDs (and optionally give each a 1-line label).
3. Only then, selectively open/scan those transcript files to extract **human steering** + **tests run** (never paste transcripts verbatim; redact secrets).

If transcript access is not available (sandbox / remote environment), fall back to asking the user to run:
- `codex resume` / `codex resume --all`
- `claude --resume`

and share the chosen session IDs.

## Avoiding the “Latest Minor Session” Trap

Never let a tiny follow-up session overwrite the narrative:
- The visible “What changed” section must reflect the **entire PR diff**, not just the current chat.
- The most recent session should be logged as a **delta** plus a new (or updated) session entry.

## Workflow

1. **Resolve the target PR**
   - Prefer `--pr auto` (PR for current branch) or accept a PR URL/number.
   - If there is no PR, ask the user for the PR number or URL (stop until you have it).

2. **If multi-session/backfill is needed, enumerate sessions**
   - Use the helper described in `references/transcripts.md` to show a short table.
   - Ask the user which session IDs to include (Codex + Claude Code may both be involved).

3. **Write the payload JSON (LLM-owned content only)**
   - Keep it short and structured (no walls of text).
   - Do not claim tests ran unless you have evidence.
   - Redact secrets/tokens/PII/internal URLs.

4. **Run the deterministic upsert script**
   - It finds/updates the single comment (by marker), merges session entries, computes delta via GitHub compare, redacts, and posts.
   - Use `--dry-run` to preview without posting.

5. **Return**
   - Output only the comment URL (and do not re-print the entire comment body unless asked).

## Output Format (Markdown)

The script renders a single GitHub-flavored Markdown comment body in this shape (keep it scannable and keep the markers intact):

````markdown
<!-- diversio:session-review-notes -->
<!-- diversio:session-review-notes:state {"schema":2,"base":"<baseRefName>","head":"<headRefOid>","prev_head":"<prior_head_or_null>","rev":<n>,"sessions_total":<n>,"codex":<n>,"claude":<n>,"included_sessions":[{"tool":"codex","id":"..."},{"tool":"claude","id":"..."}],"sessions_sha256":"<sha256>","repair_count":<n>,"last_repair_at":"<ISO8601>","generator":"session-review-notes","generator_version":"<ver_or_null>","last_updated":"<ISO8601>"} -->

<div align="center">

## SESSION REVIEW NOTES
<sub>Single upserted PR comment • cumulative across Codex + Claude Code sessions</sub>

</div>

> [!IMPORTANT]
> This comment is **updated**, not duplicated. Re-run `/session-review-notes:generate` to update it. Please do not create a second “SESSION REVIEW NOTES” comment.

### Summary

| Field | Value |
| --- | --- |
| **Intent** | <1–2 sentences> |
| **PR coverage** | `<baseRefName>...<headRefOid_short>` |
| **PR size** | <files changed + additions/deletions + commits> |
| **Sessions** | `<n> (Codex×<n>, Claude×<n>)` |
| **Latest delta** | <short stat since prior update (or “n/a — first entry”)> |
| **Risk** | Low / Medium / High |
| **Tests** | <Latest update summary; refer to session log for earlier runs> |

<details>
<summary><strong>What changed (full PR diff)</strong></summary>

- <high-level change area 1>
- <high-level change area 2>

</details>

<details>
<summary><strong>Hotspot map (deterministic)</strong></summary>

| Area | Files | + | - |
| --- | ---: | ---: | ---: |
| `src/` | 7 | 220 | 45 |

</details>

<details>
<summary><strong>Review hotspots / risks</strong></summary>

- <what reviewers should focus on>

</details>

<details>
<summary><strong>Latest delta (since prior update)</strong></summary>

- <small, scannable diffstat-style bullets; don’t paste diffs>

</details>

<details>
<summary><strong>Provenance / integrity</strong></summary>

- PR scope: GitHub diff `<baseRefName>...<headRefOid_short>`
- Delta: compare `<prev_head_short>...<headRefOid_short>`
- Generator: `session-review-notes` schema=2 rev=<n>

</details>

<details>
<summary><strong>Session log (cumulative)</strong> <sub>(newest first)</sub></summary>

<!-- diversio:session-review-notes:sessions:start -->
<!-- diversio:session-review-notes:entry {"tool":"<codex|claude>","session_id":"<id>","created_at":"<ISO8601>"} -->
<details>
<summary><strong><YYYY-MM-DD HH:MM TZ></strong> • <Codex|Claude Code> • <short label></summary>

**Human steering**
- <clarification / constraint / correction>

**Delta**
- <what changed since prior update; keep it short>

**Key decisions**
- <decision + why>

**Tests (this session)**
- [ ] <test command> (not run)
- [x] <test command> (pass)

**Notes**
- <anything a reviewer should know (tradeoffs, uncertainties, follow-ups)>

</details>

<!-- diversio:session-review-notes:sessions:end -->
</details>

<details>
<summary><strong>Prompts (optional, redacted)</strong></summary>

```text
<minimal prompts someone could re-run to reproduce; redact secrets/PII/URLs>
```

</details>

---

<sub>Last updated: <YYYY-MM-DD HH:MM TZ> • No secrets/tokens/credentials in this comment</sub>
````

## Posting / Updating the Comment (Deterministic Script)

Use the bundled script `scripts/upsert-pr-comment.py`. It:
- finds the existing comment by marker (or creates it),
- merges the session log safely,
- computes PR facts + delta via GitHub compare,
- redacts secrets/PII/URLs,
- updates the comment with merge/verify retries to avoid lost updates.

### Usage

From a **Codex Skill install** (inside the skill directory):

```bash
python3 scripts/upsert-pr-comment.py --tool codex --session-id auto --pr auto --payload payload.json
```

From **Claude Code** (plugin install):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/session-review-notes/scripts/upsert-pr-comment.py" --tool claude --session-id auto --pr auto --payload payload.json
```

Preview only (no GitHub write):

```bash
python3 scripts/upsert-pr-comment.py --dry-run --tool codex --session-id auto --pr auto --payload payload.json
```

Payload from stdin:

```bash
python3 scripts/upsert-pr-comment.py --tool codex --session-id auto --pr auto --payload - < payload.json
```

### Style Rules

- **Never** paste raw secrets/tokens/credentials (including `Authorization:` headers, API keys, cookies, JWTs, or `gh` auth tokens).
- Do not include customer PII. Redact aggressively.
- Prefer **specificity over verbosity**:
  - Mention modules, directories, and concepts.
  - Avoid listing every file unless the change is tiny.
- If you didn’t run tests, say so plainly (don’t imply).
- If you are uncertain about a claim, mark it as **(uncertain)** and explain why.
