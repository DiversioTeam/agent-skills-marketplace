# Platforms

Facts checked against official docs on **2026-10-17**, plus what three pilots
observed. Where docs and observation disagree, both are given: trust what a
probe session shows today, and record the difference. Re-read these pages at
the start of every project.

## Read first

Claude Code on the web:

- https://code.claude.com/docs/en/claude-code-on-the-web (sessions, sharing, hand-off)
- https://code.claude.com/docs/en/cloud-environments (image, setup script, network, variables, secrets)
- https://code.claude.com/docs/en/web-quickstart (start-up order, GitHub setup)
- https://code.claude.com/docs/en/claude-projects (Projects, `/mnt/project-files`)
- https://code.claude.com/docs/en/settings#settings-in-cloud-sessions
- https://code.claude.com/docs/en/hooks, https://code.claude.com/docs/en/skills, https://code.claude.com/docs/en/mcp
- https://code.claude.com/docs/llms.txt for anything new

Codex cloud (the old `developers.openai.com/codex/...` URLs now redirect to
`learn.chatgpt.com/docs/...`):

- https://learn.chatgpt.com/docs/environments/cloud-environments (current flow)
- https://learn.chatgpt.com/docs/environments/cloud-environment (Legacy flow)
- https://learn.chatgpt.com/docs/cloud and https://learn.chatgpt.com/docs/cloud/internet-access
- https://learn.chatgpt.com/docs/agent-configuration/agents-md
- https://learn.chatgpt.com/docs/build-skills
- https://learn.chatgpt.com/docs/third-party/github.md
- https://github.com/openai/codex-universal (Legacy base image)

## Side by side

| | Claude Code on the web | Codex cloud |
| --- | --- | --- |
| Where | claude.ai/code; `claude --cloud "task"` from the CLI (`--remote` is a deprecated alias) | chatgpt.com/codex ("Work in > Cloud"); `codex cloud exec --env <ID> "task"` (experimental CLI) |
| Plans (docs) | Pro, Max, Team; Enterprise with premium or Claude Code seats. Not for ZDR, HIPAA or CMEK orgs; an org IP allowlist breaks it | Plus, Pro, Business, Enterprise/Edu |
| VM | Fresh Ubuntu 24.04 x86_64, about 4 vCPU / 16 GB / 30 GB. Image cannot be replaced | Current: 2 vCPU / 8 GiB on Plus, 4 vCPU / 16 GiB / 32 GiB on paid business plans. Legacy: `codex-universal` image |
| Preinstalled | Python + pip, poetry, uv, ruff, mypy, pytest; Node 20/21/22 in `/opt/nodeNN` (22 on PATH); npm, yarn, pnpm, bun; Ruby, PHP, JDK 21, Go, Rust, GCC/Clang; Docker; PostgreSQL 16 and Redis 7 installed but not running; gh, jq, yq, rg. `check-tools` prints versions. No .NET | Legacy image: Python 3.10–3.14, Node 18/20/22, Rust, Go, Swift, Ruby, PHP, JDK 11–25, bun, bazel; versions chosen with `CODEX_ENV_*` / "Set package versions" |
| Repos | One or more in the selector; repo hooks, settings and `.mcp.json` apply **only in single-repo sessions** | Current flow supports several repos |
| Start-up order | Docs: clone → setup script → network applied → agent. Setup must exit 0 or the session fails | Legacy: container → checkout → setup (or maintenance script on cached resume) → internet settings → agent. Current: Codex proposes an install script and a "start skill"; you test and **publish** the environment; tasks run on a copy of the published state |
| Setup caching | Files snapshot if setup ends in about 5 min; rebuilt when the script or allowed hosts change, or after about 7 days. Not re-run when an idle VM resumes | Legacy: up to 12 h, invalidated when scripts, variables or secrets change; "Reset cache"; shared across the workspace on business plans. Current: republish to change |
| Lifetime | Idle VM pauses after minutes (files kept), can be reclaimed; reopening restores the conversation, not processes. Environment and `.claude/settings.json` changes reach **new** sessions only | Task VM state recoverable up to 7 days (current) |
| Variables | `.env` format; readable by every user of the environment; re-read only when the VM is restored or rebuilt | Passed to programs for the whole task |
| Secrets | **Network secrets**: proxy injects a header (Bearer or custom) by host, `*.` wildcards; the value never enters the VM. Never attached to GitHub, the Anthropic API or public registries (npm, jsr, PyPI, crates, Go). **Not available during the setup script** | Current: network secrets as placeholders, substituted by the proxy for allowed HTTPS:443 destinations during setup and tasks; saving one adds its hosts to the allowlist; a personal vault for per-user values in shared environments. Legacy: secrets **only during setup**, removed before the agent phase |
| Network | None / Trusted (default, long allowlist) / Full / Custom (your list, optionally plus defaults). GitHub, MCP connectors, network-secret hosts and the Anthropic API bypass the allowlist. All traffic through a security proxy | Agent-phase internet **off by default**; setup always has internet. Presets: package managers, custom only, all (Legacy: none / about 71 common-dependency domains / all). Optional GET/HEAD/OPTIONS-only. Egress IPs published; Tailscale supported |
| GitHub inside the VM | Separate proxy; `GH_TOKEN` reads `proxy-injected`; only attached repos reachable (others 403). **GraphQL blocked**, so `gh pr` / `gh issue` fail; use `gh api repos/...`. Branch deletes and tag pushes rejected. Observed: **commit-status writes refused for every token** (403 "Write access to this GitHub API path is not permitted through this proxy"; the App has `statuses: read`), and network secrets are never added to GitHub hosts | Not documented in detail |
| Instructions | Repo `CLAUDE.md`, `.claude/rules`, `.claude/skills`, agents, commands; skills enabled on the claude.ai account. **Not** `~/.claude/*` from your machine; a setup script can write `~/.claude/CLAUDE.md` | `AGENTS.override.md` → `AGENTS.md` → fallbacks, root down to the working directory, one per directory, 32 KiB limit. Skills in `.agents/skills` (working dir up to root), `~/.agents/skills`, `/etc/codex/skills`; repo skills work in cloud, local personal skills are not synced |
| Plugins / MCP | Repo `enabledPlugins` / `extraKnownMarketplaces` are **not installed**. claude.ai connectors work everywhere; `.mcp.json` in single-repo sessions (loaded with no approval prompt in our pilot). Projects can add plugins in project settings | Not verified |
| Hooks | SessionStart runs on every start and resume, local and cloud; guard with `CLAUDE_CODE_REMOTE=true`; 600 s default timeout; single-repo only | No equivalent; use setup and maintenance scripts |
| Outputs | Diff view with inline comments; Create PR (full, draft, or GitHub compose); artifacts; auto-fix can watch a PR for CI failures and review comments (needs the GitHub App) | Diff, commit, open a PR; `codex cloud diff/apply <ID>` locally; `@codex review` on GitHub (P0/P1 only); other `@codex` mentions start Legacy tasks |
| Attribution | Commits carry a `Claude-Session:` trailer and PR bodies the session URL (setting `attribution.sessionUrl` turns this off); the GitHub connector's `create_pull_request` added "Generated by Claude Code" | Not documented |
| Hand-off to local | `claude --teleport [id]` or `/teleport` (clean tree, same repo and account); `claude -p "msg" --cloud <id>` sends a follow-up; CLI → cloud is one-way | `codex cloud apply <ID>` |
| Sharing | Team/Enterprise sessions Private or Team; Pro/Max Private or Public. Org-shared environments: Owners create them (variables only, no secrets at the time of the pilots); members see them read-only | Environment "Only me" or workspace; sharing shares the setup, not others' tasks |
| Private repos | Claude GitHub App on the repo (org-owner approval) or a `/web-setup` token; SAML SSO orgs need a reconnect; a token without `workflow` scope fails pushes touching workflow files | "Connect GitHub"; org approval steps not documented. GitLab and GitHub Enterprise Server not supported |
| Projects (Claude) | Beta, Pro/Max, one owner, not shareable; uploads under `/mnt/project-files`; GitHub App on every repo | n/a |

## Where docs and the pilots disagree

| Topic | Docs (2026-10-17) | Observed (2026-10-13 to 10-17) | Do this |
| --- | --- | --- | --- |
| Setup script and the clone | Runs after the clone; working directory not documented | In all three pilots the script ran **outside** the clone (cwd `/home/user`, no `package.json` / `pyproject.toml`); a bare `uv sync` or `pnpm install` failed or did nothing | Never depend on the cwd or repo files in setup. Install tools; do repo installs in the hook or let the agent do them. If you must, find the clone first and `|| true` |
| Network secret scoping | Host only, with `*.` wildcards | The form offered a **path prefix**; `/client/v4/accounts/` on `api.cloudflare.com` fixed a broken upload | Use a path prefix where the form offers one; otherwise check that tools with their own auth headers still work |
| Secrets on Team/Enterprise | Team members can add one host at a time; Enterprise needs org-admin role | Team plan lacked network secrets for us; shared org environments had variables only | Check the account's plan in the UI before designing around secrets |
| Branch names | Not in official docs | `claude/<words>` assigned by the platform | Do not prescribe another convention in the skill |
| Commit statuses from a session | Not mentioned | Refused through the GitHub proxy whatever the token | Record check results in a commit; a CI workflow verifies and posts the status ([publishing](publishing.md)) |
| Codex repo access | "Connect GitHub" | "repository authentication for <org>/<repo> failed" even with the org-wide Codex app installed | Verify cloning in a throwaway task before building anything for Codex |

## Not verified (look before relying on them)

- Claude: the clone path and setup-script cwd; path matching for network
  secrets in the docs.
- Codex: setup script user and cwd; `codex/` branch prefix; MCP and plugins
  in cloud tasks; GitHub org approval steps; whether the Legacy "secrets only
  during setup" rule still applies in the current environment model (the
  current docs say network secrets work during tasks); whether a setup-written
  `~/.codex/AGENTS.md` or `~/.agents/skills` loads in cloud tasks.
- `codex cloud` flags come from `codex cloud --help` on codex-cli 0.163.0
  (experimental, no `--branch` flag), not from a docs page.

## Designing for both vendors

- One canonical `AGENTS.md`; `CLAUDE.md` = `@AGENTS.md`.
- One skill, available at `.claude/skills/<name>/` and `.agents/skills/<name>/`
  (a copy or a symlink; check that each vendor follows symlinks in a probe).
- Setup scripts that install tools only, pinned, logged and `exit 0`, so the
  same file works in both (Codex Legacy splits it into setup and maintenance).
- Keep credentials header-shaped where possible: both vendors now inject
  network secrets at the proxy. Codex Legacy is the exception (setup only).
- Expect agent-phase internet to be off on Codex unless you turn it on, and
  restrict it to the hosts the workflow needs.
- Test each vendor separately with the same probe prompt; record per-vendor
  results.
