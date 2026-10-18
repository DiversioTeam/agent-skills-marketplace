# Credentials

## Network secret or environment variable?

| | Network secret (Claude) | Environment variable (Claude or Codex) | Codex secret |
| --- | --- | --- | --- |
| How it works | The egress proxy adds a header to requests matching a host and, optionally, a path prefix | A plain `NAME=value` in the VM | Available to setup scripts only (check [platforms](platforms.md)) |
| Can the agent read it? | No. The value never enters the VM | **Yes**, and so can every user of the environment | Not during the agent phase |
| Fits | HTTP APIs with a static header: package registries, REST APIs, Cloudflare API, Access service tokens | Tools that log in and keep state in the VM: CLI logins, SSH keys, token exchanges | Fetching private dependencies during setup |
| Examples | `npm.pkg.github.com`, `api.cloudflare.com` (path `/client/v4/accounts/`), Access-protected preview hosts, a SaaS API host | A sandbox CLI login token | Not used |

**Prefer a network secret whenever the tool works with a header.** Use a
variable only when the login has to happen inside the VM, and write the
exposure into the risks.

Network secret facts that bit us:

- It is attached to **every** matching request, from any process. A code-level
  read-only guard does not stop `curl`; only token scopes do.
- **Scope by host and path prefix.** An unscoped `api.cloudflare.com` secret
  overwrote Wrangler's own short-lived upload JWT on `/client/v4/pages/assets/*`
  (HTTP 403, error 8000013). The fix was the path prefix `/client/v4/accounts/`.
  Test that tools with their own auth headers still work.
- Some tools refuse to start without a token variable (Wrangler). Set a
  placeholder variable (`CLOUDFLARE_API_TOKEN=set-by-network-secret`); the
  proxy replaces the header.
- Code that builds its own `Authorization` header must be able to send none
  (an "auth via proxy" flag), or it crashes looking for a token or sends a
  blank header that competes with the proxy's.
- Custom headers work: change the default `Authorization` row's header name
  and clear the prefix (for example `CF-Access-Client-Id`), then **Add header**
  for a second one (`CF-Access-Client-Secret`).
- Saved secrets are write-only: they cannot be viewed or edited. To change
  one, delete and re-add it, which means the human pastes again.
- Hosts and path prefixes only register when you press Enter and they become
  chips.
- After **Add**, you still have to click **Save changes** on the environment
  dialog.

## Where each kind of secret belongs

| The secret is used by | It lives in |
| --- | --- |
| A cloud session, sending to a non-GitHub host | A network secret |
| A cloud session, for a GitHub host | Nowhere: network secrets are never added to GitHub hosts, and the GitHub proxy refuses some writes whatever the token. Sessions use the vendor's GitHub app |
| The deployed site or app | The hosting platform's **production** secrets. Never preview secrets: a branch preview runs that branch's code |
| The deploy | A CI environment secret |
| Never | Cloud environment variables (unless an in-VM login requires it, recorded as a risk), the repo, the chat, a screenshot |

## Non-human identity

Create a bot or service account with the **narrowest role the system
offers**. If the system cannot scope it, write the limits into the repo skill
and record the risk for the owner.

```bash
cs org service-account create claude-cloud --display-name "Claude cloud"   # Crafting example
```

Every PR a cloud session opens is authored by the GitHub user connected to
the vendor account, whoever typed the request. Say so in the people guide.

## The six-step pattern (web-created tokens)

1. **Agent opens the token page pre-filled** and verifies the scopes by
   reading the page, not by trusting the URL. Example:
   `https://github.com/settings/tokens/new?scopes=read:packages&description=Claude%20cloud%20-%20GitHub%20Packages%20read%20(<repo>)`.
2. **Human picks the expiry and clicks Create.** The agent stays on another
   tab while a one-time value is on screen, never screenshots it, and checks
   only the tab URL afterwards.
3. **Human stores it in the vault** under the agreed name; the agent proposes
   the name and fields (scope, used by, expiry, owner).
4. **Agent opens the environment → Add secret** and fills everything except
   the value.
5. **Human pastes the value** and clicks **Add**, then **Save changes**. (Or
   the agent clicks them after the human says "added", without reading the
   field.)
6. **Agent tests** in the project environment (expect success) and in the
   default environment (expect failure): 200 versus 401 proves the secret
   works and that nothing else grants access.

## CLI-minted tokens: mint straight into the vault

The first attempt with a sandbox CLI **printed the token** into the agent's output (an
error branch echoed it). It was revoked within a minute and recorded. The
pattern that worked: mint into a shell variable, pipe a JSON item into
the password manager's CLI, print only length and a hash prefix. Shown with
1Password's `op`; any CLI that reads the item from stdin works the same way
([providers](providers.md#password-manager)).

```bash
set -euo pipefail
mint_and_store () {
  local label="$1" tok
  tok=$(<mint command> 2>/dev/null | tr -d '\r\n ')
  [ ${#tok} -ge 20 ] || { echo "mint failed for $label"; return 1; }
  TOK="$tok" LABEL="$label" python3 - <<'PY' | op item create --vault <Vault> --format json - >/dev/null
import json, os
print(json.dumps({
  "title": f"Claude cloud – <what> ({os.environ['LABEL']})",
  "category": "API_CREDENTIAL",
  "fields": [
    {"id": "credential", "type": "CONCEALED", "label": "credential", "value": os.environ["TOK"]},
    {"id": "notesPlain", "type": "STRING", "purpose": "NOTES", "label": "notesPlain",
     "value": "Purpose, scope, expiry, how to revoke. Paste into the vendor UI only."}
  ]
}))
PY
  echo "stored $label (len ${#tok}, sha256:$(printf '%s' "$tok" | shasum -a 256 | cut -c1-12))"
}
```

Read a stored value only to pipe it on:
`op item get "<title>" --vault <Vault> --fields credential --reveal | <consumer reading stdin>`.

Record the length and sha256 prefix in the change record. They let you match
the vault, the environment and a later revocation without ever showing the
value.

## Prove the credential in isolation

Use a throwaway `HOME` so your own CLI login is untouched and nothing is left:

```bash
H=$SCRATCH/cli-home; rm -rf "$H"; mkdir -p "$H"
TOK=$(op item get "<title>" --vault <Vault> --fields credential --reveal | tr -d '\r\n')
HOME=$H <cli> login -t "$TOK" 2>&1 | sed -E 's/[A-Za-z0-9+\/=._-]{30,}/<redacted>/g' | tail -3
HOME=$H <cli> whoami
HOME=$H <cli> logout; rm -rf "$H"
```

This is where you learn what the login really does. `cs login -t` swapped the
token for an 8-day session **and registered an SSH key** on the account,
which is why it had to be a variable plus a hook, not a network secret.

## Rules

- **One token per environment**, so either can be revoked alone.
- Expiry is a trade-off: an expired token silently breaks every session.
  Choose deliberately, record it, put rotation steps in the maintainer doc,
  and set a reminder for each expiry date.
- **Naming**, so anyone finding a token can tell what it is for: vault item
  `Claude cloud – <what> (<repo or env>)`; network secret `<what> (<repo>)`;
  token name in the service `Claude cloud - <what> (<repo>)`.
- Narrowest scopes: `read:packages` only for registries; one permission
  ("Pages: Edit") for deploy tokens; read-only scopes for APIs the agent must
  not change. Confirm scopes in the issuing service's UI, and record what you
  could not confirm.
- **When a token's power grows** (a status note becomes an approval signal),
  issue a new one rather than promoting one that was ever exposed.
- Write one-time setup scripts to be idempotent, print no secrets, and skip
  (with a clear message) steps the available token is not allowed to do: an
  engineering Cloudflare token could not create or list service tokens (403),
  so that step became a human click and the script accepted the new token's
  ID on re-run. Pipe generated secrets from a mode-600 temp file (or
  `openssl rand … |`) straight into the consumer, then delete the file.
- Service name limits bite: GitHub fine-grained token names max out at 40
  characters.
- Never production keys. Never put a secret in the environment variables box
  unless the design requires an in-VM login, and then record the exposure.
