# The local-ci Step

Read when: adding the agent-session check to a repository's `.local-ci.toml`,
or debugging that step.

Add one step. It is an ordinary command; local-ci only runs it and reports
pass or fail, so a failure fails the required `local/verify`.

```toml
[[steps]]
id = "agent-session"
name = "Agent session transcript"
# A published, redacted transcript must cover HEAD (see the agent-session skill).
command = ["sh", "-c", "command -v agent-session >/dev/null || { echo 'agent-session: missing (the agent-session command is not installed)'; echo 'fix: claude plugin install agent-session@diversiotech (or the Codex/Pi skill), start a session once, then run local-ci again'; exit 1; }; exec agent-session check"]
github_context = "local/agent-session"
```

`agent-session check` reads git, `gh` (the branch's open PR) and
`~/.agent/sessions/published.jsonl` itself:

- With an open PR, its body must link a page named `-h<HEAD12>-` for HEAD, or
  say `No agent session: <reason>`.
- Without a PR, the local record must have a publish (or a declaration) for
  this branch and HEAD.
- A PR lookup that fails is `unverified`, never a pass.

Output starts with `agent-session: ok|missing|stale|unlinked|unverified` and,
on failure, gives the `fix:` command. Agents act on that line.

Order on a branch: commit, push, `agent-session share`, then `local-ci run`
(local-ci posts statuses to the pushed commit).
