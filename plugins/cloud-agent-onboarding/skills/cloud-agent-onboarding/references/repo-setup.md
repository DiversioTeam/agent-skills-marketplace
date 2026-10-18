# Repo setup

Cloud sessions only know what is in the repo they cloned (plus anything the
environment's setup script wrote to the machine). They do not install
marketplace plugins. Everything the cloud agent must follow has to live in
the repo or be written by the setup script.

## 1. Make the rules load

- **Claude** cloud sessions load `CLAUDE.md` (not `AGENTS.md` directly), repo
  skills from `.claude/skills/`, `.claude/settings.json` (hooks,
  permissions) and `.mcp.json`.
- **Codex** reads `AGENTS.md` (nearest file wins, nested files refine) and
  repo skills from `.agents/skills/`. Check [platforms](platforms.md) for the
  current lookup rules.
- Make `AGENTS.md` canonical and `CLAUDE.md` a stub that sources it:

  ```markdown
  @AGENTS.md

  ---

  ## Notes

  This `CLAUDE.md` intentionally sources `AGENTS.md` so that requirements,
  commands, and agent behavior have a single canonical entrypoint in this repo.
  ```

- Legacy instruction files mislead sessions. One repo had a 1,858-line
  `CLAUDE.md` with stale facts (old framework versions, an auto-publishing
  release that no longer existed). Map every section against `AGENTS.md` and
  the code (a read-only subagent works well), move true-but-unwritten rules
  into focused docs, fix stale facts, check every relative link.
- Add the repo's attribution rule to `AGENTS.md` explicitly. Cloud tools add
  footers on their own anyway; see [outputs](outputs.md#pull-requests).
- Point `AGENTS.md` (and so `CLAUDE.md`) at the repo skill for the cloud
  workflow, so every agent finds it.

## 2. The SessionStart hook (Claude)

Repo-side start-up. Wire it in `.claude/settings.json` and allow-list the
helper scripts so sessions do not stop for approval on routine calls
(skeletons in [templates](templates.md#sessionstart-hook)).

Design points:

- **Guard**: `[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0`. It does
  nothing on laptops, so the repo files are harmless.
- **Logins go here, not in the setup script** (the setup result is cached;
  anything that expires breaks later sessions).
- **Dependencies can go here** (the repo exists now). Keep it fast or run it
  in the background; the session waits for the hook.
- **Submodules**: check out only the missing ones, as partial clones
  (`--filter=blob:none`), so a resumed session keeps the agent's work
  branches. A session's GitHub access covers **only the repos attached to
  it**; tell the agent to attach the rest (`add_repo`) and rerun the hook.
  Until then the submodule folder is empty and `git -C <dir>` **silently runs
  against the parent repo**. Say so in the status.
- **Print a short status; stdout becomes part of the agent's context.** Write
  it as instructions: "Code NOT checked out because these repos aren't
  attached… attach each one with add_repo, then rerun …"; "Signed in as …";
  "For any request, follow `.claude/skills/<name>/SKILL.md`."
- **Always `exit 0`** and log to `/tmp/<project>-session-start.log`. A broken
  step is reported, never allowed to block the session.
- **Safe to rerun.** The agent reruns it after attaching repos.
- Allow-list entries match the **bare command**: tell the agent to run each
  allowed script from the repo root as its own command (no `cd …;`, no pipe),
  or it stops for approval.
- Do not trust a CLI's status command's exit code (`cs login --status` exits
  0 when signed out); grep its output.

Repo hooks **do not run in multi-repo Claude sessions**. Codex has no
equivalent hook; use its setup and maintenance scripts (see
[environment](environment.md#codex-setup-and-maintenance-scripts)).

## 3. A fallback for sessions that start the wrong way

Real users pick the wrong branch, attach several repos, or pick the other
product's environment. In the parent-repo project, a user started with two repos on
`main`: no hook (multi-repo) and no skill (not on `main` yet), so the agent
improvised and built a sandbox from the wrong template.

Fix from the setup script, which runs whatever was picked:

- Write a **user-level `~/.claude/CLAUDE.md`** (for root, `/root/.claude/CLAUDE.md`).
  It loads in every session. It says what the environment is for, the rule
  that matters most (which template or product), and: "If the repo clone has
  no skill folder, run `<bootstrap> <clone>` and work from `<dir>`. Don't make
  up your own setup."
- Install a **bootstrap command** that fetches `main`, else the setup branch,
  whichever has the skill, as a worktree in a fixed directory, then runs the
  hook there.
- Verify by reproducing the wrong start exactly.

Generic lesson: keep critical rules in a user-level file written by the
setup script. Repo files only reach sessions that start the way you expect.
For Codex, the equivalent is `~/.codex/AGENTS.md` written by the setup script
(verify against [platforms](platforms.md)).

## 4. The repo skill

Lives in the repo: `.claude/skills/<name>/SKILL.md` plus `references/*.md`;
mirror or symlink into `.agents/skills/<name>/` for Codex. Name it for the
job people come for (`design-system-experiments`, `edit-internal-website`).

Writing principles that worked:

- **State the audience first.** "The person may be an engineer, PM, designer
  or customer success. You do all the technical work and never ask them to
  run a command or read code unless they ask."
- **Say what the agent has**: the repos, environment variables that matter,
  signed-in CLIs, helper scripts, and what to say when the hook reported a
  failure ("I can read the code but can't start a test copy right now; an
  engineer needs to fix this environment").
- **Match work to the request** in a table: understand → answer from code; see
  or try → run it and show; change → edit, run, check, show; keep → only on
  "save it".
- **Levels for non-engineers**: explore (clickable pages, default) → preview
  (private live link) → save (draft PR, only when asked). Never push people
  past exploration.
- **Ask once, only about consequential choices, with a recommendation**
  ("Should the test copy start with recent dev data (recommended), an empty
  database, or a specific snapshot?"). Everything else gets a default.
- **List what needs an explicit yes**: replacing a database, deleting
  resources, switching a shared resource's branches, discarding someone's
  work, acting in someone else's resource.
- **One "Rules that always apply" block**: no secrets in the open, data stays
  where it is, never production, draft PRs only, no attribution lines.
- **A reply shape**: *Look at* / *What I found or changed* / *What is
  simulated* / *Saved* / *Next question*. And a failure shape: what happened,
  what is safe, what is next.
- **Saving is a separate, explicit step**; iterations do not commit or push.
  Push once at save time (some pushes cost money, for example Chromatic
  builds).
- **Real numbers**: "usually ready in 2–5 minutes (a test build took 137 s)".
  The agent then sets expectations correctly.
- **Name each trap where the agent will hit it**: the 403 fix next to the
  command that gets it; the PR-footer cleanup next to "open draft PRs".
- **Don't prescribe tools the environment may not have**: "preview and review
  your own work with whatever browser or screenshot tool your environment
  provides".
- **Plain words** in a reference file: "test copy", not "sandbox"; "saved for
  review", not "pushed"; one question at a time with 2–4 choices; never ask
  people to pick files, branches, props or test strategies.
- **Failures**: "Never tell the person about a failure you can fix." Retry
  once, then say what it means for them in one line; never try other
  credentials to get around a refusal. No file paths, commands, branch names,
  error output or jargon unless they ask.
- **Approval words**: list what counts as a yes ("publish", "put it live")
  and what does not ("looks good, but…", "I'll check with <person>"); see
  [publishing](publishing.md#instructions-for-the-session).
- **A "Never" list** for paths that need an approver (code, workflows, agent
  rules, dependencies, security docs, access lists), checked by a script, not
  only by the agent.
- **Answer the likely questions** in the reference: "Who can see this?", "Can
  I undo it?", "Can you change the design?".
- **Data safety**: if a person pastes what looks like real employee or
  customer data, do not repeat it, commit it, or screenshot it; use made-up
  examples and say so.

## 5. Helper scripts

Write small, allow-listed scripts for anything the agent would otherwise
improvise each session. Patterns from the remote-sandbox project:

| Need | Script pattern |
| --- | --- |
| A tool ignores `HTTPS_PROXY` and gets `403` from the egress gateway | A local relay: map the hostnames to 127.0.0.1 and tunnel through the proxy with `CONNECT`, reading TLS SNI. TLS stays end to end |
| Show a remote resource without its secrets | A summary script that prints only safe fields |
| Edit in the VM, run remotely | A sync script with guards: refuse a stale base (the first version overwrote 74 files), refuse to overwrite edits it did not make, base64-encode remote commands when the transport cannot carry newlines |
| Screenshots of an app that needs sign-in | Create synthetic `claude-test-<role>@example.com` users and mint app tokens into a mode-600 browser storage file; never print them. Use the product's audited read-only impersonation only after the person approves |

The rule for all of them: **tokens and links go into mode-600 files, never
into the terminal**, and a script prints only what the agent should say.

## 6. MCP servers

- Commit `.mcp.json` at the repo root with a command that works from a fresh
  clone and installs what it needs on first use:

  ```json
  { "mcpServers": { "<name>": { "command": "uv", "args": ["run", "--frozen", "python", "mcp-server/server.py"] } } }
  ```

- In single-repo Claude sessions it loaded **without an approval prompt**.
  Verify the tool count in a probe session.
- Put the operating rules in the server's `instructions` (every session
  receives them) and a `next_step` string in each tool result, in this order:
  hard rules (for example read-only) → required workflow → strict reporting
  rules (never re-grade, drop or soften a finding; extra observations listed
  separately) → hard stop on ambiguity (ask, never guess) → how to deliver
  outputs (publish the report unchanged as a private artifact).
- **Keep tool results small.** Over the size limit, results spill to a file the
  session must read in chunks. Return counts, every failure and warning in
  full, skip reasons and file paths; put bulk data behind another tool;
  return a path and size instead of HTML.
- Enforce "never write" in code at the HTTP session level (not one helper),
  with a test that fails if a write gets through. It only covers the
  project's own code; token scopes are the real guarantee.

## 7. Docs and pushing

- Update every doc for the cloud reality (README, `AGENTS.md`, architecture,
  setup guide, `.env.example`, diagrams). Describe only the current system;
  delete sections for removed features.
- A maintainer doc in the repo: how a session starts, the environments table,
  token rotation, updating the setup script, how to check a change, rollback.
- Push to the branch sessions will clone. **A session only sees the skill,
  hook and scripts on the branch picked**, so test on the feature branch until
  it is merged, and expect `main` sessions to need the fallback until then.
- Normal review applies to every repo change, including the skill: separate
  worktree, no attribution, ask before pushing or opening the PR, run the
  repo's CI, answer and resolve every review thread.
