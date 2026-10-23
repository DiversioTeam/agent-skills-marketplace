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

This is not optional. Courage sets a `courage/agent-session` status on every
PR, and the plugin's Claude Code hook blocks `gh pr create` and body edits
without a link or declaration. Never work around either; never fake a link.

Script (standard library Python 3.10+, works under Claude Code, Pi, and Codex):

```bash
S="<this skill>/scripts/agent_session.py"   # e.g. ${CLAUDE_PLUGIN_ROOT}/skills/agent-session/scripts
```

## Workflow

Run from the repository (any worktree) on the PR's branch.

1. **Find.** `python3 "$S" find [--pr N]` lists sessions that ran on this
   branch, linked this PR, or mention the branch or PR URL, with their
   teammates. The current session should be among them. Add a missing one with
   `--session ID`, drop one with `--exclude ID`, keep a whole session (not
   only matching turns) with `--whole ID`.
2. **Render.** `python3 "$S" render [--pr N] --open` writes the preview to
   `~/.agent/sessions/<repo>-<branch>/` and prints a redaction summary
   (counts by kind, never values).
3. **Review with the developer.** Show the summary and preview path and say
   plainly: *the page includes your own prompts word for word and is visible
   to all Diversio staff.* Ask once whether to publish. Offer:
   - `--drop-turn N` (repeatable) to remove a turn by the number on the page;
   - `--include-output N` to publish a withheld prod/staging output in turn N
     (only when the developer asks; credentials are never included).
   Re-render after any change. Do not publish without a yes.
4. **Publish.** `python3 "$S" publish` uploads with `cloudflared access`
   (first use opens a browser sign-in). It refuses files changed since render.
   The developer becomes the uploader and can delete the page in Internal
   Share.
5. **Link.** Put the printed `## Agent sessions` section in the PR body:
   `python3 "$S" update-body BODY.md --link URL [--link URL2]` replaces an
   existing section or appends one. Then create or edit the PR with
   `--body-file BODY.md`. Check with `python3 "$S" check-body BODY.md`.

Before the PR exists, render without `--pr`; the branch is enough to find the
sessions. When more work lands on the PR, render and publish again and
replace the section's links (Internal Share never overwrites a name, so each
publish gets a fresh one).

For a PR with no agent involvement, write the declaration instead:
`python3 "$S" update-body BODY.md --none "hand-edited config value"`.

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
  name the agent in the reason. Courage's status check still applies.
