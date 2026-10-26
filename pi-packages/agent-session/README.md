# agent-session (Pi package)

The Pi side of the [`agent-session`](../../plugins/agent-session/skills/agent-session/SKILL.md)
skill. Before Pi's `bash` tool runs `gh pr create`, `gh pr edit --body…`, or
`gh api …/pulls` with a body in a DiversioTeam repository, it checks that the
body links an agent session transcript
(`internal-share.diversio.com/session-…html`) or says
`No agent session: <reason>`. Otherwise the call is blocked, and the reason
tells the agent to run the skill's `share` command.

It runs the same `check_pr_hook.py` as the Claude Code plugin's hook, found in
this marketplace checkout or beside `$AGENT_SESSION_CLI`. local-ci's
`agent-session` check is the real gate; this gives earlier feedback.

## Install

```bash
pi install git:github.com/DiversioTeam/agent-skills-marketplace
```

## Test

```bash
node --test pi-packages/agent-session/tests/agent-session.test.mjs
```
