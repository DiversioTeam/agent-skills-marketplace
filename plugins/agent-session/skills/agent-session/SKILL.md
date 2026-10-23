---
name: agent-session
description: "Attach the redacted agent session transcript to a Diversio PR: find, render, review, publish, link."
allowed-tools: Bash Read Write Edit
---

# Agent Session Transcripts

Every DiversioTeam PR carries a link to the agent sessions that produced it:
the developer's prompts, the agent's replies, tool calls with their inputs and
outputs, and subagent and agent-team teammate transcripts. The page is
redacted, rendered as one script-free HTML file, and published to Diversio
Internal Share (staff only, behind Cloudflare Access). A PR no agent worked on
says so with `No agent session: <reason>` instead.

This is not optional. A transcript must cover the branch's current HEAD:
local-ci's `agent-session` check (in every Diversio repo's required
`local/verify`) fails when it does not, and the plugin's Claude Code hook
blocks `gh pr create` and body edits without a link or declaration. Never
work around either; never fake a link.

Script (standard library Python 3.10+, works under Claude Code, Pi, and Codex):

```bash
S="<this skill>/scripts/agent_session.py"   # e.g. ${CLAUDE_PLUGIN_ROOT}/skills/agent-session/scripts
```

## When local-ci Reports `agent-session:`

The failure starts with `agent-session: missing`, `agent-session: stale`, or
`agent-session: unlinked` and prints the exact command to run. Run it. It is
`python3 "$S" share --repo <root> [--pr N]`, which renders, publishes, rewrites
the PR body's `## Agent sessions` section with the new link, and deletes the
upload it supersedes. Then run local-ci again. If it is the branch's first
publish, `share` stops with exit code 3 for the review below; continue with
`--yes` after the developer agrees.

## Workflow

Run from the repository (any worktree) on the PR's branch, after the last
commit you are about to push: the transcript records the commits it covers
(base..HEAD) and its name carries `h<HEAD12>`, so new commits make it stale.

1. **Find (optional).** `python3 "$S" find [--pr N]` lists sessions that ran
   on this branch, linked this PR, or mention the branch or PR URL, with their
   teammates. Add a missing one with `--session ID`, drop one with
   `--exclude ID`, keep a whole session with `--whole ID` (on `share` too).
2. **Share.** `python3 "$S" share [--pr N] --open` finds the PR with `gh`
   when `--pr` is omitted, writes the preview to
   `~/.agent/sessions/<repo>-<branch>/`, and prints coverage and a redaction
   summary (counts by kind, never values).
3. **Review with the developer (first publish on a branch).** Show the summary
   and preview path and say plainly: *the page includes your own prompts word
   for word and is visible to all Diversio staff.* Ask once. Offer
   `--drop-turn N` (repeatable) and `--include-output N` (a withheld
   prod/staging output, only when the developer asks; credentials never).
   With a yes, run `share ... --yes`. Later republishes on the branch publish
   directly, keeping the same choices you pass.
4. **Result.** The page is uploaded with `cloudflared access` (first use opens
   a browser sign-in); the developer is the uploader and can delete it. The
   publish is recorded in `~/.agent/sessions/published.jsonl` (local-ci reads
   it before a PR exists). With an open PR, its body's `## Agent sessions`
   section now holds the newest link; without one, `share` prints the section
   to put in the body (`update-body BODY.md --link URL` writes it into a file).

For a branch no agent worked on: `python3 "$S" declare-none "reason"` records
it and writes `No agent session: <reason>` into the PR body.

## What Gets Redacted

Read [references/redaction.md](references/redaction.md) for the full list and
its limits. In short: secret shapes (the same ones Courage redacts), exact
values from the repo's `.env*` files and secret-named environment variables,
auth headers, cookies, OAuth codes, JWTs, URL credentials, customer emails and
phone numbers, outputs that look like rows of personal data, outputs of
commands that print credentials, reads of credential files, and output from
DB, shell, or Django access to prod or staging hosts. Long texts are clipped,
thinking is never included, and images are dropped. Courage checks the page
again after upload.

Redaction is best effort. If the preview shows anything sensitive that slipped
through, drop the turn and tell the developer; record the miss so the patterns
improve.

## Agents

- **Claude Code:** sessions in `~/.claude/projects/`, with subagents and agent
  team teammates from each session's `subagents/` folder. The hook in this
  plugin enforces the link.
- **Pi and Codex:** session parsing for `~/.pi/agent/sessions/` and
  `~/.codex/sessions/` follows in the next release; until then, publish the
  Claude Code sessions involved, or declare `No agent session: <reason>` and
  name the agent in the reason. local-ci's check still applies.
