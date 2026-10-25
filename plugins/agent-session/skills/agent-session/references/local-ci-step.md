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
- Without a PR, the local record must have a publish for this branch and
  HEAD, or a no-agent declaration for this branch. Declarations are not
  HEAD-bound; do not leave one in place after an agent contributes.
- A required PR lookup that fails is `unverified`, never a pass.
- Before asking GitHub, it passes as `skipped (<why>)` for a cloud session
  (`CLAUDE_CODE_REMOTE` set), HEAD on an integration branch (`main`, `master`,
  `dev`, `release`, `release/...`, etc.), or a detached HEAD an `origin`
  integration branch already contains (deploy triggers, release candidates).
- After a successful PR lookup, it also skips a promotion/release PR from
  `promote/`, `releases/`, etc. into an integration branch, or a bot's PR.

Output starts with `agent-session: ok|skipped|missing|stale|unlinked|unverified` and,
on failure, gives the `fix:` command. Agents act on that line.

For a repository whose local-ci planner emits the step list, add the same
command to the planner's applicable plans instead of assuming a static TOML
step will be included. Verify the generated plan contains `agent-session`;
no local-ci-runner change or GitHub Actions enforcement job is needed.

Order on a branch: commit, push, `agent-session share`, then `local-ci run`
(local-ci posts statuses to the pushed commit).
