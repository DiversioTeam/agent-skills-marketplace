# Case studies

Four projects from October 2026. They look nothing alike, which is why the
method is general. Names are left out on purpose; the shapes, numbers and
lessons are what carry over. Providers are named where they were used; see
[providers](providers.md) for what changes with others.

## 1. A UI component library

**Goal:** a designer describes a change in plain words and gets clickable
before/after pages, then a private live preview, then a draft PR.

**Shape:** one repo, Node + pnpm, private packages on GitHub Packages,
Storybook, a paid per-snapshot visual testing service.

**Built:**
- One environment: Custom network (defaults + the preview host's API); a
  setup script pinning Node and pnpm (binary swap, checksum).
- Three network secrets: package registry read; preview deploy token, scoped
  by path prefix; an access service token (two custom headers) so the
  session can open its own previews.
- Cloudflare Pages previews behind Cloudflare Access (company email domain;
  service auth for the session).
- `CLAUDE.md` = `@AGENTS.md`; a repo skill with explore / preview / save
  levels, plain intake and a reply shape.
- A generator turning one story into one self-contained artifact page in
  about 5 s.

**Measured:** idea → before/after pages about 3½ min; tweak about 1 min;
"save it" → test, 426 passing tests, live preview and draft PR about 9 min.

**Lessons:** setup runs outside the clone; pin everything; scope secrets by
path; clickable pages beat screenshots; push once (visual testing costs per
build); the PR connector adds an attribution footer; Codex could not clone
the private repo.

## 2. A parent repo with product submodules and remote sandboxes

**Goal:** anyone (customer support, PMs, engineers) asks about one of two
products, and the agent reads code, runs the product in a remote sandbox
with a database, debugs, changes code, shows screenshots and saves a draft
PR.

**Shape:** a parent repo whose product repos are submodules; a sandbox
provider (Crafting) reached through a CLI that logs in inside the VM; sandbox
workloads on their own hosts.

**Built:**
- Two environments, identical except a variable naming the product and
  their own login token (an environment variable, because the CLI login
  registers an SSH key and keeps a session in the VM).
- A non-admin service account; tokens minted straight into the password
  manager.
- Setup script: pinned CLI, SSH→HTTPS rewrite, a user-level `CLAUDE.md` and
  a bootstrap command as the fallback.
- SessionStart hook: remote-only, partial submodule checkouts for attached
  repos, CLI sign-in, relay set-up, a status written as instructions.
- Helper scripts: a relay through the egress proxy, a safe sandbox summary,
  an edit-here-run-there sync with guards, sign-in for screenshots with
  synthetic users and tokens in mode-600 files.
- A repo skill with plain-language, saving and shared-sandbox references.

**Measured:** a sandbox ready in 2–5 minutes (a test build took 137 s).

**Lessons:** multi-repo sessions skip hooks; only attached repos are
reachable; some CLIs bypass the proxy; never print a minted token; the
classifier blocks acting as real users, by design; the end-of-turn check
needs a scripted answer; persona runs find what probes do not.

## 3. An MCP server over a read-only SaaS API

**Goal:** operations staff type "QC <item id>" and get every discrepancy
against house rules, plus a report link.

**Shape:** Python + uv, an MCP server, a third-party REST API that must
never be written to, and a desktop-era design (installer, password-manager
credential modes, its own LLM step).

**Built:**
- `.mcp.json` at the root (`uv run --frozen python <server>`).
- An "auth via proxy" flag so the client sends no `Authorization` header and
  a Bearer network secret on the API host supplies it.
- A read-only HTTP session that refuses non-GET, with a test.
- Removed the server-side AI step, desktop tooling and credential modes.
- Compact tool results; MCP instructions ordered hard rules → workflow →
  reporting rules → stop on ambiguity → publish the report as an artifact.

**Lessons:** the session's agent is the AI, so delete the project's own LLM
calls; keep tool results small; outputs must be artifacts; the code guard
does not stop `curl`, token scopes do; a plain prompt with no hints is the
final test.

## 4. An internal staff website

**Goal:** non-engineers (often HR and operations) change the internal site
from claude.ai/code: describe a change, see it, say "publish".

**Shape:** a static docs site with one command for every check (page lint,
secret and name scans, tests, build, link check, phone-width screenshots),
Cloudflare Pages, a custom domain whose DNS is outside Cloudflare.

**Built:**
- One environment: Custom network (defaults + GitHub release hosts,
  `nodejs.org`, the preview hosts); a setup script pinning Node, pnpm, the
  check runner and `gh`, checksum-verified; no secrets in variables; one
  network secret, an access service token for the preview hosts.
- A script turning the real built page into a draft artifact (refusing
  restricted pages) and one printing the branch's preview link.
- The publishing gate: a gate-rules script, a request script, a deploy
  workflow that verifies and ships, an approval page behind sign-in
  ([publishing](publishing.md)).
- Site sign-in through an OIDC app, because the access proxy cannot sit in
  front of a domain whose DNS lives elsewhere.
- A repo skill: the loop (understand → find → edit → check → show → iterate
  → publish), reply shape *What I changed* / *See it* / *Your call*, a
  "Never" list, approval words.

**Measured:** previews ready 2–4 minutes after a push; publish 3–6 minutes.

**Lessons:** network secrets never go to GitHub; the GitHub proxy refuses
commit-status writes; sessions refuse to forge approvals, so make "done"
honest; artifacts are not private on a shared account; only new sessions see
environment changes; the local agent's safety check needs human clicks for
grants, credentials, merges and approvals.

## What to carry to the next project

The decision table, the change record, the secret handling, the never-fail
setup and hook, the user-level fallback, probe → diagnose → fix → retest,
persona runs, honest publishing, and the private people guide.
