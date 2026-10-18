---
name: cloud-agent-onboarding
description: "Make a repository work in hosted cloud coding agents (Claude Code on the web, Codex cloud): assess, environment, secrets, repo instructions, cloud tests, people guide."
allowed-tools: Bash Read Glob Grep Edit Write
---

# Cloud Agent Onboarding

Use when someone wants a project to work in a hosted cloud agent session
(claude.ai/code cloud environments, Codex cloud at chatgpt.com/codex) so that
people, technical or not, can ask in plain words and the cloud agent does the
work. Also use to audit or repair an existing cloud setup, or to learn the
platform facts before advising on one.

Not for: running a single cloud session for a task (just do the task), CI/CD
pipelines, or remote-sandbox operations on their own (in this marketplace,
`crafting-sandboxes`).

The knowledge here comes from four real projects done in October 2026
(see [case studies](references/case-studies.md)). It names the providers we
use by default (GitHub, 1Password, Cloudflare, Crafting, our own check
runner) and, for each, what changes with another one
([providers](references/providers.md)). Use it as is with those defaults, or
swap any block. Platform facts drift fast:
re-read the official pages in [platforms](references/platforms.md) at the
start of every project and note what changed.

## Example prompts

- "Make `<org>/<repo>` usable from Claude Code on the web for designers." → `assess`
- "Add a network secret for our private npm registry to the cloud environment." → `access`
- "Our cloud sessions fail before Claude starts; fix the setup script." → `environment`
- "Let staff publish page edits from a cloud session with an approver for code changes." → `publish`
- "Run the engineer probe against the new environment and report a table." → `test`
- "Audit our existing cloud setup against this skill." → `audit`
- "How do Claude cloud and Codex cloud differ for secrets?" → `learn`

## The shape of every project

```
Person ─ opens claude.ai/code or chatgpt.com/codex, picks environment + repo
  ▼
Cloud environment (built in the vendor UI)   setup script · network · variables · secrets
  ▼
VM clones the repo → repo-side start-up       SessionStart hook · .mcp.json · user-level fallback
  ▼
Agent reads instructions                      CLAUDE.md → AGENTS.md → repo skill
  ▼
Outside systems (optional)                    private registries · APIs · CLIs · previews
  ▼
Outputs people can open                       artifacts · previews behind sign-in · draft PRs · gated publish
```

Four layers to build, in order: **access** (non-human credentials), **the
cloud environment**, **the repo** (hook, skill, helper scripts), **the people
guide**. Plus records the whole way through.

## Who does what

This split is the most important thing to repeat. The local agent (you, on an
engineer's machine) does the technical work; the human does anything that
involves a credential or an outward decision.

| Step | Agent | Human |
| --- | --- | --- |
| Sign in to vendor sites | Opens the sign-in page in its own browser and waits | Signs in, says "done" |
| Create a token | Opens the token page pre-filled, reads the scopes back off the page | Picks expiry, clicks Create |
| Store a token | Proposes the vault item name and fields | Stores it (or the agent pipes it straight into the vault, never printing it) |
| Add a network secret | Fills name, host, path prefix, header; leaves Value empty | Pastes the value, clicks Add, then Save |
| Push, PR, labels, deploys to new places, closing PRs | Asks first | Approves; merges |
| Accept risks (broad tokens, public endpoints, shared logins) | Writes them down | Accepts them in writing |
| Grant access, store credentials, merge without review, approve a release | Fills the form, stops before the last button | Clicks it |

The local agent's own safety check blocks that last row even when the human
says "go ahead"; plan those steps as human clicks from the start instead of
rephrasing around the block.

## Rules that always apply

- **Secret values never pass through the agent's context.** Not in prompts,
  argv, shell history, terminal output, files, screenshots, or the repo.
  Never screenshot a dialog that holds a pasted value; read its length. When a
  value must move, the human pastes it or a script reads it from stdin and
  prints only `length` and a `sha256` prefix. If a value leaks, revoke it at
  once and record the leak.
- **Never `env`, `printenv`, or "show" config that may hold secrets** without
  filtering values out. CLIs print tokens; never let a mint command write to
  the terminal.
- **One browser, its own profile, small steps.** Never attach to or close a
  browser or tab that belongs to the user or another session, and stop if
  someone is typing in the tab you are about to use. Never call
  `browser.close()` on a CDP-attached browser.
- **Ask before outward actions**: pushes, PRs, closing PRs, labels, deploys to
  new places, sharing artifacts beyond private.
- **Synthetic data only** in fixtures, test prompts, screenshots, guides,
  branch names and commits.
- **Keep a numbered change record** for every state-changing action, written
  in the same session, with pre-state and read-back verification
  ([records](references/rollout-and-records.md#change-record)).
- Follow the target repo's own rules (attribution, branch, review, CI). Cloud
  tools add attribution footers on their own; plan to remove them.

## Router

Pick the lane from the request (`$ARGUMENTS` of the command) and load only
its references. Default lane for a new project: `assess`.

| Lane | When | Read |
| --- | --- | --- |
| `assess` | New project, or "can this work in the cloud?" | [platforms](references/platforms.md), [providers](references/providers.md), [assess](references/assess.md) |
| `access` | Tokens, service accounts, secrets vs variables | [credentials](references/credentials.md) |
| `environment` | Create or change the vendor environment, setup script, network | [environment](references/environment.md), [browser automation](references/browser-automation.md) |
| `repo` | Hook, user-level fallback, instructions, repo skill, MCP, helper scripts | [repo setup](references/repo-setup.md), [outputs](references/outputs.md) |
| `publish` | People should ship from a session, with or without an approver | [publishing](references/publishing.md), [outputs](references/outputs.md) |
| `test` | Probe, diagnose, retest, persona runs | [testing](references/testing.md), [browser automation](references/browser-automation.md) |
| `rollout` | People guide, handover, risks, rollback, memory | [rollout and records](references/rollout-and-records.md) |
| `audit` | Check an existing setup against this skill | [checklist](references/checklist.md), then the lanes it flags |
| `learn` | Explain the platforms or the method; no changes | [platforms](references/platforms.md), [providers](references/providers.md), [gotchas](references/gotchas.md), [case studies](references/case-studies.md) |

[Providers](references/providers.md) maps each building block (cloud agent,
code host, password manager, CI secrets, registries, previews and access
control, remote sandboxes, checks) to our default and its alternatives; read
it in `assess` and whenever a lane names a specific vendor.
[Gotchas](references/gotchas.md) is the consolidated failure table; skim it
before any lane that changes state. [Templates](references/templates.md) holds
the prompts, setup script and hook skeletons, change record and vault-item
shapes.

## The method, end to end

1. **Read the platform docs** (links in [platforms](references/platforms.md)).
   Record anything that contradicts this skill in the change record and in
   your final report.
2. **Decide before building** ([assess](references/assess.md#decide-first)):
   which vendor and plan, who signs in, which single repo sessions start on,
   what the agent needs outside the VM, what data it can see, where outputs
   and saved work go, who accepts the risks. Ask the owner only the questions
   whose answers change the build, with a recommendation each.
3. **Start a worktree and the change record** before touching anything.
   Capture pre-state read-only.
4. **Audit laptop assumptions** in the repo and **inventory outside systems**
   read-only ([assess](references/assess.md#laptop-assumptions)).
5. **Create access**: non-human accounts with the narrowest role, one token
   per environment, minted into the vault, proven with a throwaway `HOME`
   ([credentials](references/credentials.md)). Choose network secret vs
   variable per credential.
6. **Build the environment**: pinned, logged, always-`exit 0` setup script
   that installs tools only; custom network allow-list plus the package
   manager defaults; variables for non-secret flags and placeholders
   ([environment](references/environment.md)). Read every save back.
7. **Make the repo ready**: `CLAUDE.md` = `@AGENTS.md`; a remote-only,
   always-`exit 0` SessionStart hook; a user-level fallback written by the
   setup script; a repo skill in `.claude/skills/` (and `.agents/skills/` for
   Codex); allow-listed helper scripts for anything the agent would otherwise
   improvise; `.mcp.json` if there is an MCP server; outputs people can open
   ([repo setup](references/repo-setup.md), [outputs](references/outputs.md)).
   If people ship from sessions, the session only *requests* publishing and a
   workflow it does not control verifies and ships
   ([publishing](references/publishing.md)). Push to the branch sessions will
   clone.
8. **Test in real cloud sessions**: environment check → secret control
   (project vs default environment) → engineer probe → diagnose → fix → retest
   → rehearsal → persona runs → wrong starts → approval paths. Always compare
   against a known answer, check evidence outside the chat, and use a fresh
   session after every environment or skill change
   ([testing](references/testing.md)).
9. **Tune instructions from what sessions really did**, one row per observed
   behaviour; re-run the exact failing prompt plus one persona run after each
   change.
10. **Roll out**: a private people guide built from a real persona run with
    synthetic data; maintainer doc; risks accepted in writing; rollback list;
    token expiries; memory note ([rollout](references/rollout-and-records.md)).

## Stop conditions

Stop and ask when:

- the plan or vendor cannot do what the design needs (for example no network
  secrets on the account's plan, or the vendor cannot clone the repo);
- a credential would need broader scope than the owner agreed;
- a step would write to production, shared templates, or another person's
  resources;
- a test would use real customer or employee data;
- the platform behaves differently from this skill in a way that changes the
  design (record it, then propose the change).

Never work around a vendor safety classifier or approval prompt. The person's
mode switch (for example Auto → Accept edits) is the approval; switch back
afterwards.

## Completion evidence

Report, with read-backs rather than intentions:

- decisions and who made them; risks and who accepted them;
- every credential: purpose, scope, where stored (vault item name), where used
  (environment and secret name), expiry, `length`/`sha256` prefix match;
- environment settings read back (setup script hash, allow-list, variable
  names only);
- repo changes: branch, commits, PR links, and what loads in a session
  (hook output, skill, MCP tool count);
- each cloud test: session id, prompt file, result versus the known answer,
  what was created and deleted (read back);
- the people guide link (private) and maintainer doc path;
- open items, token expiry dates, and anything in the platform docs that
  differed from this skill.

Never claim a cloud behaviour works from local tests alone: proxy,
permission and classifier behaviour only show up in real cloud sessions.
