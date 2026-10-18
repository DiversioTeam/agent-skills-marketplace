# Assess the project

Do this read-only. The first assessment is a starting point; on the component
library every early assumption (no live preview, Chromatic as the visual loop) changed
later.

## Decide first

Answer these with the owner before building. Every later step depends on
them. Ask only the ones whose answer changes the build, each with a
recommendation.

| Question | Why it matters | Example answer |
| --- | --- | --- |
| Which vendor and plan? | Claude network secrets need a plan that offers them (Pro/Max at the time; Team/Enterprise had shared environments without secrets). Codex environments are per workspace. Check [platforms](platforms.md). | One claude.ai account with network secrets; Codex parked until it can clone the repo |
| Who signs in? | A shared login means one environment and one secret serve everyone, but everyone sees every session, artifact and variable, and shares usage limits. Seats mean per-person environments or org-shared ones. | Decided by the owner, trade-offs recorded |
| Which repo does a session start on? | Claude repo hooks do not run in multi-repo sessions. One parent repo with submodules keeps sessions single-repo and gives the agent the whole system. | The parent repo alone, or the project repo alone |
| What does the agent need outside the VM? | Decides credentials, allowed hosts and helper scripts. | A private package registry; a preview host; remote sandboxes; a SaaS API |
| How does each outside system authenticate? | Static header → network secret. Login inside the VM (CLI session, SSH key) → environment variable plus hook. See [credentials](credentials.md). | Both kinds |
| Does it write to outside systems? | A network secret is attached to **every** matching request, including a `curl` the agent improvises. Only token scopes really limit writes. | The SaaS API: read-only token plus a code guard |
| What data can the agent see? | Shapes "data stays there" rules, screenshots and guides. | Dev snapshots and synthetic users only |
| Where do outputs go? | The VM is deleted; people cannot open its paths. | Private artifacts, private previews, draft PRs |
| Where does saved work go? | Protect main branches; nothing ships from a session. | `claude/<words>` branches, draft PRs, an engineer merges |
| One environment or several? | One token per environment, so each can be revoked alone. A variable can name the product. | Two near-identical environments, one per product |
| Who uses it? | Non-engineers need plain-language rules, a reply shape and a people guide. | Engineers, PMs, designers, customer success |
| Who accepts the risks? | Broad tokens, public endpoints, shared logins. | The owner, in writing, in the change record |

## Project facts to collect

| Fact | Why |
| --- | --- |
| Runtime and package-manager pins (`.nvmrc`, `packageManager`, `.python-version`, `pyproject.toml`) | Cloud images ship their own versions; the setup script must pin |
| Private registries or packages | Each needs a read-only network secret |
| Build time and output size | An artifact is one page up to 16 MB; larger needs hosting |
| What gives visual feedback today (Storybook, Chromatic, screenshots) | Paid per-snapshot tools and seat-gated links do not work for everyone |
| Where full validation runs (CI, a local check runner) | Cloud PRs may need to say "needs an engineer" |
| Where the rules live (`CLAUDE.md`, `AGENTS.md`, docs) | Claude cloud reads `CLAUDE.md`; Codex reads `AGENTS.md`; stale legacy files mislead sessions |
| What "shipping" means (package release, deploy) | Keep production deploys out of the cloud environment |
| Whether the vendor's GitHub app covers the repo **and every submodule's repo** | Sessions can only reach attached or installed repos |
| Branch protection on the target branches | Saved work must go through review |

## Laptop assumptions

Search the repo for each and note the cloud fix.

| Look for | Example seen | Cloud fix |
| --- | --- | --- |
| How it is launched | MCP server registered in a desktop app's config by an installer | Commit `.mcp.json` at the repo root with a command that works from a fresh clone (`uv run --frozen …`, `npx --yes …`) |
| Where credentials come from | `.env`, a password-manager CLI or SDK, `--auth-method` flags | Read env vars only; let a network secret supply the header |
| Code that sets its own `Authorization` header | `Client(access_token=...)` | An "auth via proxy" flag that sends **no** header, so the proxy's header is used |
| The project's own LLM calls with an API key | A background "AI interpretation" job needing `ANTHROPIC_API_KEY` | Delete it: the session's agent is the AI. Return structured results and let it explain them |
| Files read from the user's disk | A "drop zone" folder | Uploads, or Claude Projects' `/mnt/project-files` (Projects only) |
| Files written for the user to open | `reports/*.html` | Publish as a private artifact and reply with the link |
| Huge tool outputs | A tool returning ~74,000 characters | Compact summary in the result; full data on disk behind another tool |
| Desktop-only tooling | `setup.sh`, `.bat` installers, zip packagers | Delete with their tests |
| Writes to outside systems | Nothing intended, nothing preventing it | A read-only HTTP session that refuses non-GET, a test that fails if a write gets through, and a read-only token |
| SSH remotes | Submodule URLs `git@github.com:…` | Rewrite to HTTPS (`url.insteadOf`); the session's GitHub proxy speaks HTTPS |
| Services the project needs (database, Redis, queues) | A local Postgres | Fixtures, SQLite or in-memory fakes, or a remote sandbox via a CLI. Probe what the image can run before promising anything |
| Tools that ignore `HTTPS_PROXY` | A CLI connecting straight to workload hosts | Expect `403` from the egress gateway; a local relay that tunnels through the proxy with `CONNECT` |

Probe that an MCP server starts headless over stdio with no token in the
environment:

```bash
(printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'; sleep 6) \
| env -u <TOKEN_VAR> timeout 30 <server command>
```

## Inventory outside systems (read-only)

Before creating anything, learn what is there and what could leak. For any
provider, list: org settings (with secret-looking lines filtered out),
existing non-human accounts, templates or project definitions, running
resources and who owns them, and data snapshots. Example with Crafting's
`cs` CLI:

```bash
cs org show -o yaml | grep -viE 'token|secret|key'   # settings without secret-looking lines
cs org service-account list                          # existing non-human accounts
cs template list -o yaml                             # what products exist
cs sandbox list                                      # who has what running
cs snapshot list -o json                             # which data copies exist
```

The same questions for others: `gh api orgs/<org>/installations`, `vercel
project ls`, `coder templates list`, the cloud console's IAM and secrets
pages.

What to look for, and what each finding changes:

- A template or config that talks to a real provider (SMS, email, payments)
  → default to a variant that does not.
- Third-party keys in plain template or config variables → the skill forbids
  printing them and a helper prints a safe summary instead.
- Endpoints protected only by the product's own login → a risk for the owner
  to accept or fix.
- A shared, approved dev data snapshot → the recommended data choice.

Save definitions locally only when needed (scratch directory), never paste
them anywhere.

## What the result looks like

A short assessment in the change record: the decision table filled in, the
facts table, the laptop-assumption fixes, the outside-system inventory, and a
verdict per user group ("works for small changes; needs previews for
designers; Codex blocked on repo access").
