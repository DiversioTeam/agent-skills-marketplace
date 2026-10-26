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

A transcript must cover the branch's current HEAD. In repositories that have
enabled it, local-ci runs `agent-session check` as a required step; rollout is
per repository, not automatic. The plugin's Claude Code hook blocks
`gh pr create` and body edits without a link or declaration. Never work
around either check; never fake a link.

The `agent-session` command (a shim in `~/.local/bin`, installed and kept
current by the plugin's SessionStart hook, the Pi extension, or
`install-codex-hook`; by hand: `python3 <skill>/scripts/agent_session.py
install-shim`) runs this skill's CLI. Standard library Python 3.9+, same under
Claude Code, Pi, and Codex.

```bash
S="<this skill>/scripts/agent_session.py"   # `python3 "$S" …` is the same as `agent-session …`
```

## When local-ci Reports `agent-session:`

The failure starts with `agent-session: missing`, `stale`, `unlinked`, or
`unverified` and prints the exact `fix:` command. Run it: usually
`agent-session share --repo <root> [--pr N]`, which renders, publishes,
rewrites the PR body's `## Agent sessions` section with the new link, and
deletes the upload it supersedes. Then run local-ci again. On a branch's first
publish, `share` stops with exit code 3 for the review below; continue with
`--yes` after the developer agrees. `unverified` means gh could not read the
PR: fix `gh auth`, then rerun.

A repo opts in with one step in `.local-ci.toml` (see
`references/local-ci-step.md`).

## Workflow

Run from the repository (any worktree) on the PR's branch, after the last
commit you are about to push: the transcript records the commits it covers
(base..HEAD) and its name carries `h<HEAD12>`, so new commits make it stale.

1. **Find (optional).** `python3 "$S" find [--pr N]` lists Claude Code, Pi,
   and Codex sessions that ran on this branch, linked this PR, or mention the branch or
   PR URL, with their subagents and teammates. Add a missing one with `--session ID`, drop one with
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
   directly and remember the developer's choices (dropped turns, included
   outputs, `--session`/`--exclude`/`--whole`); `--reset-choices` forgets them.
   If the PR body cannot be updated, `share` fails and keeps the old page.
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
- **Pi:** sessions in `~/.pi/agent/sessions/`, following the active path of
  each session tree (abandoned branches are counted, not shown). A Pi session
  belongs to the branch when it ran in a worktree that has the branch checked
  out, mentions the branch while running in this repository, or mentions the
  PR from anywhere. The `agent-session` Pi package guards PR
  create and edit like the Claude Code hook.
- **Codex:** rollouts in `$CODEX_HOME/sessions/` (default `~/.codex`), matched
  by the `git.branch` and repository Codex records, or a worktree on the
  branch, or a mention. Subagent rollouts attach to their parent thread, from
  where their own work starts. Reasoning is encrypted and never shown.
  `python3 "$S" install-codex-hook` adds the same PR guard to Codex's
  `hooks.json` (Codex asks the developer to trust it).
