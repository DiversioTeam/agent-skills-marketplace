# The cloud environment

Built in the vendor UI. Drive it with [browser automation](browser-automation.md)
and read every save back.

## Before creating it

- The repo (and every submodule's repo) is covered by the vendor's GitHub
  app. On Claude, add the repo on the new-session screen first (the repo
  picker is a combobox; click the option).
- Branch protection on the integration branches: PR required, approving
  review, required checks.
- Decide one environment or several. Near-identical environments that differ
  by one variable (`APP_PRODUCT=<product-a>|<product-b>`) and their own token let
  you revoke one without the other, and let the skill derive defaults.

## Claude form fields

| Field | What to put | Notes |
| --- | --- | --- |
| Name | What people will pick: `Design system`, `<Product>`, `Survey QC` | Obvious to a non-engineer |
| Network access | **Custom**, with **Also include default list of common package managers** ticked | Custom blocks everything not listed. Trusted is a long default list; Custom keeps the surface small |
| Allowed domains | Only the hosts the workflow needs, one per line, Enter after each so it becomes a chip | Find the list by running the tool once through a logging proxy locally, or from its errors in a probe session |
| Network secrets | One per API host (see [credentials](credentials.md)) | Values cannot be viewed or edited after saving |
| Setup script | See below | Its result is cached |
| Environment variables | `.env` format: non-secret flags and placeholders | Readable by every user and by the agent; never secrets unless the design requires an in-VM login, recorded as a risk |

Examples of allow-lists:

```
# Remote sandboxes (Crafting: API, workloads, product URLs, CLI downloads)
sandboxes.cloud
*.sandboxes.cloud
*.sandboxes.run
storage.googleapis.com
# Cloudflare previews
api.cloudflare.com
# Tool downloads in setup (GitHub release assets, Node)
github.com
objects.githubusercontent.com
release-assets.githubusercontent.com
nodejs.org
# The session opening its own previews (with an Access service-token secret)
<project>.pages.dev
*.<project>.pages.dev
# A SaaS API (read-only token as a network secret)
api.<vendor>.com
```

Examples of variables:

```
APP_PRODUCT=<product-a>
<VENDOR>_AUTH_VIA_PROXY=1
CLOUDFLARE_ACCOUNT_ID=<account id>
CLOUDFLARE_API_TOKEN=set-by-network-secret
COREPACK_ENABLE_DOWNLOAD_PROMPT=0
SANDBOX_LOGIN_TOKEN=
```

Do not block a CLI's self-update with a variable when its server rejects old
versions (turning off the sandbox CLI's upgrade broke it).

## The setup script

Facts that shape it (see [platforms](platforms.md) for the current wording):

- Runs as **root** on Ubuntu 24.04 x86_64 before the agent starts.
- Its **working directory is not the repo**. Docs say it runs after the
  clone, but in all three pilots it ran outside it (`/home/user`), and bare
  `uv sync` / `pnpm install` failed or did nothing. A failing setup script
  fails the whole session before the agent starts.
- Its result is **cached** (about a week on Claude), so anything that expires
  (logins, tokens, session cookies) must not happen here.
- Network secrets are **not available** during it on Claude.

Principles:

1. **Install tools, not dependencies.** Hard-code version pins with a comment
   saying where they come from (`.nvmrc`, `packageManager`). Let the hook or
   the agent run the repo's install once the repo is there.
2. **Verify downloads** with checksums. When the vendor publishes none, hash
   the download once and record the date in a comment.
3. **Replace narrowly.** The image had Node 22.22.0, below the repo's engines
   range; replacing only the `node` binary in `/opt/node22/bin` kept the
   image's global tools working. Corepack left alone picked the newest pnpm
   major and crashed, so pin and activate the exact version.
4. **Log everything** to `/tmp/<project>-setup.log`, so a probe session can
   print it.
5. **Always `exit 0`.** The agent can repair a missing tool; a failed setup
   blocks every session.
6. **Rewrite SSH remotes** system-wide when submodules use them:
   `git config --system url."https://github.com/".insteadOf "git@github.com:"`.
7. **Write the user-level fallback** (`/root/.claude/CLAUDE.md` and a
   bootstrap command) for sessions that start the wrong way
   ([repo setup](repo-setup.md#3-a-fallback-for-sessions-that-start-the-wrong-way)).

If a repo-dependent pre-install really helps (big dependency trees), find the
clone first and never let it fail:

```bash
repo=$(find / -maxdepth 5 \( -path /proc -o -path /sys \) -prune -o -name <marker-file> \
  -path '*/<RepoName>/<marker-file>' -print 2>/dev/null | head -1)
if [ -n "$repo" ]; then (cd "$(dirname "$repo")" && <install command>) || true; fi
```

Expect it to be a no-op on some platforms; the hook or `uv run --frozen` in
`.mcp.json` installs anything missing on first use. Add dev extras
(`--extra dev`) if engineers need test tools in sessions: without them
`uv run pytest` fell back to a system pytest and failed collection.

Full skeleton in [templates](templates.md#setup-script).

### Updating the setup script

1. Edit the file in the repo (the repo copy is the source of truth).
2. Replace the environment's script from the file
   (`cdp fill-field <Env> "<marker line>" setup.sh`, set up as in
   [browser automation](browser-automation.md#pick-a-browser-driver)).
3. Read it back (`cdp field-hash <Env> "<marker line>"`) and compare with
   `printf '%s' "$(cat setup.sh)" | shasum -a 256` (the stored text loses its
   final newline).
4. Only **new** sessions pick it up (old sessions keep the old environment
   and the old `.claude/settings.json`); changing the script invalidates the
   cache. Start a fresh session to test every change.
5. List the setup script in the maintainer doc's rotation table, so whoever
   changes the repo copy also re-pastes it.

## Codex setup and maintenance scripts

- **Current flow**: Codex proposes an install script and a start skill from
  the repo, you test and **publish** the environment, and every task starts
  from a copy of the published state. Changes need a republish and a new
  task.
- **Legacy flow**: a setup script for a fresh container and a maintenance
  script for cached resumes; each runs in its own Bash session, so `export`
  does not carry over (write to `~/.bashrc` or use environment settings).
  Secrets exist only during setup.
- Agent-phase internet is **off by default**. Turn it on with the narrowest
  preset (package managers, or a custom list), optionally GET/HEAD/OPTIONS
  only.
- `AGENTS.md` is where Codex looks for lint and test commands; keep them
  there and current.
- Verify that Codex can clone the repo in a throwaway task before building
  anything else for it.

## After saving

Reopen the environment and read back each field (hash the setup script, list
variable names only, list allowed hosts and secret names). Record it in the
change record. Then run the environment check prompt
([testing](testing.md#1-environment-check)).
