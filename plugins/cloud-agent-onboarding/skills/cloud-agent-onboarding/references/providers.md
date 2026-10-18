# Providers: our defaults and the alternatives

The method does not depend on any one vendor. Each building block below names
the default we use, how to set it up, and what changes with something else.
Pick one row per block for the project and write the choice into the change
record.

The rule behind every block: **the agent never sees a secret value**, every
credential is the narrowest one the provider offers, and every setting is
read back after saving.

## Cloud agent

| | Default | Alternatives |
| --- | --- | --- |
| Product | Claude Code on the web (claude.ai/code) | Codex cloud (chatgpt.com/codex); other hosted agents (for example GitHub Copilot's coding agent, Cursor background agents, Google Jules) |
| What to check | [platforms](platforms.md) | For anything else, answer the same questions before designing: when does setup run and in which directory; is setup cached; which instruction files and skill folders load; can secrets be injected without the agent reading them; how is egress filtered; which repos can a session reach; how does work leave the VM (PR, diff, artifact) |

Design for more than one: canonical `AGENTS.md`, `CLAUDE.md` = `@AGENTS.md`,
the skill in both `.claude/skills/` and `.agents/skills/`, setup scripts that
install tools only, header-shaped credentials.

## Code host

| | Default | Alternatives |
| --- | --- | --- |
| Host | GitHub, with the vendor's GitHub app installed on the org and the repo (and every submodule's repo) selected | GitLab, Bitbucket, self-hosted: Claude can upload a git bundle from the CLI but cannot push back; Codex does not support GitLab or GitHub Enterprise Server (2026-10-17). Expect a manual hand-off |
| Branch protection | Ruleset on the integration branch: PR required, approving review, required status checks | GitLab protected branches and merge request approvals; Bitbucket branch restrictions |
| Bot identity | The vendor's GitHub app authors PRs as the connected GitHub user | A machine user or a GitHub App you own, for anything a CI workflow does |

Creating GitHub tokens without seeing them: open the token page pre-filled
(classic: `https://github.com/settings/tokens/new?scopes=<scopes>&description=<name>`;
fine-grained: Settings → Developer settings → Fine-grained tokens, choose
resource owner, one repository, the exact permissions). Read the ticked
permissions back off the page; the human sets the expiry and clicks
Generate. Fine-grained names are limited to 40 characters. GitHub Packages
(npm) needed a classic token with `read:packages` when we did this; check
whether fine-grained tokens cover it now.

## Password manager

| | Default | Alternatives |
| --- | --- | --- |
| Store | 1Password: one item per token, named after the token in the issuing service, category API Credential, value in a concealed field, notes with scope, where used, expiry, owner | Bitwarden, HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager, Doppler, Infisical |
| Human path | The human copies the value from the vault into the form | Same for any manager |
| Scripted path | `op item create --vault <Vault> -` with a JSON item on stdin; `op item get … --reveal \| <consumer>`; `op read "op://<vault>/<item>/<field>"` | Any CLI that takes the value on **stdin or from a file** works: `vault kv put <path> value=-`, `aws secretsmanager create-secret --name <n> --secret-string file:///dev/stdin`, `bw encode \| bw create item` |

Requirements for any manager: the value never goes in argv (shell history,
process lists); the scripted path prints only length and a sha256 prefix; the
human can always do it by hand instead. Some teams forbid agents from using
the manager's CLI at all; then every value moves by hand, which is fine.

## Secrets for CI and deploys

| | Default | Alternatives |
| --- | --- | --- |
| Where | GitHub Actions **environment** secrets (an environment such as `production`, with protection rules and allowed branches) | CircleCI contexts with security groups; GitLab CI masked and protected variables; Buildkite secrets; your cloud's OIDC federation instead of a stored key |
| How | `gh secret set <NAME> --env <environment> --repo <owner>/<repo>` with the value on stdin (the human pastes it, or a pipe from the vault). `gh secret list --env <environment>` to read back names | The provider's UI or CLI; prefer OIDC (`id-token: write` in GitHub Actions, then a cloud role) so no long-lived key exists |
| Hosting runtime secrets | Cloudflare Pages: `wrangler pages secret put <NAME> --project-name <p>` with the value on stdin, **production only** | Vercel / Netlify environment variables scoped to Production; never expose them to preview builds of arbitrary branches |

The pattern, whatever the provider: secrets the **session** needs are network
secrets in the cloud environment; secrets the **deploy** needs live in CI;
secrets the **running site** needs live in the host's production settings.
None of them go in the repo, the environment variables box, the chat or a
screenshot.

## Private packages

| | Default | Alternatives |
| --- | --- | --- |
| Registry | GitHub Packages (`npm.pkg.github.com`), read-only token as a network secret; a `.npmrc` with only the registry line | Private packages on `registry.npmjs.org`: Claude never attaches network secrets to public registries, so that needs a token variable (recorded as an exposure) or a separate registry host. Artifactory, Nexus, a private PyPI index: network secret per host if it takes a static header |
| Short-lived tokens | n/a | AWS CodeArtifact and similar issue tokens from a login: that needs an in-VM login (variable plus hook) or a pre-fetched token in setup on vendors that allow secrets there |

Test 200 in the project environment and 401 in the default one.

## Previews and access control

| | Default | Alternatives |
| --- | --- | --- |
| Static previews | Cloudflare Pages, one preview project, production branch unused, deploys with `wrangler pages deploy … --branch <alias>` | Vercel, Netlify, AWS Amplify, S3 + CloudFront, GitHub Pages (no access control on public plans) |
| Who can open them | Cloudflare Access: company email domain (Google SSO, or one-time PIN when no identity provider is set up) | Vercel Deployment Protection, Netlify password or SSO protection, an identity-aware proxy (Google IAP, oauth2-proxy), Tailscale for internal-only |
| How the session opens its own preview | An Access **service token** as a network secret: headers `CF-Access-Client-Id` and `CF-Access-Client-Secret` on the preview hosts | Any provider's automation bypass that is a static header (for example Vercel's protection-bypass header) as a network secret on the preview hosts |
| Custom domain sign-in | Access only fronts hostnames in a Cloudflare DNS zone; otherwise the site signs people in itself through an Access SaaS (OIDC) app | Any OIDC provider (Google Workspace, Okta, Entra ID, Auth0) with the same checks: PKCE, state, nonce, JWKS, issuer, audience, expiry, email domain; fail closed |
| Dynamic apps | A host that runs code (Workers, a staging service) or a remote sandbox, behind the same access control | Fly.io, Render, Cloud Run with IAP; pointed at staging or mock data, never production |

Whatever the host: create the project first and use the host name it
actually gives you; restrict previews before the first deploy; protect the
bare domain as well as the wildcard; use a random suffix in preview aliases;
keep production deploys in CI with their own token.

## Running copies of the product

| | Default | Alternatives |
| --- | --- | --- |
| Remote sandboxes | Crafting (`cs` CLI): templates with a database, shared dev snapshots, per-sandbox URLs | Coder, Gitpod, GitHub Codespaces, ephemeral Kubernetes namespaces, a shared staging stack |
| How the session reaches it | A service-account login token as an environment variable; the SessionStart hook logs in; a relay because the CLI bypasses `HTTPS_PROXY` | Whatever the provider's CLI needs. Check: does login happen in the VM (variable plus hook) or is it a static header (network secret)? Does the CLI honour `HTTPS_PROXY`? Does each login register keys you must prune? |
| Without any of these | | Fixtures, SQLite or in-memory fakes; the preinstalled PostgreSQL and Redis in Claude's image (installed, not running) |

## Checks

| | Default | Alternatives |
| --- | --- | --- |
| One command for every check | `local-ci` (our runner), run in the session with GitHub posting off | `make check`, `just check`, `pnpm verify`, `tox`, `pre-commit run --all-files` |
| Who posts the status | A CI workflow that verifies the session's recorded result ([publishing](publishing.md)) | GitHub Actions, CircleCI, GitLab CI running the same command |
| Review | Our review bot plus a human; cloud PRs are drafts | Any required review; the cloud vendor's own PR review features |

Make the one command work on a clean Linux box with only what the setup
script installs.

## Browser automation (for the local agent)

| | Default | Alternatives |
| --- | --- | --- |
| Driver | A separate Chrome with a debug port and [`scripts/cdp.mjs`](../scripts/cdp.mjs) | Playwright MCP; a computer-use tool; Playwright or Puppeteer `connectOverCDP` |

Rules do not change with the driver: own profile, the human signs in, small
steps, never close the user's tabs, never screenshot secrets.

## People guide hosting

| | Default | Alternatives |
| --- | --- | --- |
| Where | A private claude.ai artifact, or our internal share host | The company wiki, an internal docs site, a PDF in the shared drive |

## Change records and memory

| | Default | Alternatives |
| --- | --- | --- |
| Where | A numbered change record in the worktree (`docs/plans/…`) plus an agent memory note | A ticket with a checklist, an ADR, a wiki page; the content matters, not the place |
