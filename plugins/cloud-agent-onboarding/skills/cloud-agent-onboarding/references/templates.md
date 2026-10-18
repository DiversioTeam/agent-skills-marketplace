# Templates

Replace `<…>` placeholders. Keep the comments: they are the maintainer's
documentation inside the vendor UI.

## Setup script

```bash
#!/bin/bash
# <Project> cloud environment setup (<vendor> environment "<Name>").
# Runs as root on Ubuntu 24.04 (x86_64) before the agent starts. Do not rely on
# the working directory or repo files: in practice it ran outside the clone.
# Its result is cached (about a week on Claude), so it installs tools only:
# no logins, tokens or anything that expires. Logins go in the SessionStart hook.
# Pins: <tool> <version> from <pin file>; checksum taken from <source/date>.
# Never fail the session over setup: the hook or the agent can repair a tool.
TOOL_VERSION=<x.y.z>
TOOL_SHA256=<sha256>
{
  set -x
  if ! <tool> --version 2>/dev/null | grep -q "${TOOL_VERSION}"; then
    cd /tmp \
      && curl -fsSLo tool.tar.gz "<url with ${TOOL_VERSION}>" \
      && echo "${TOOL_SHA256}  tool.tar.gz" | sha256sum -c - \
      && tar -xzf tool.tar.gz -C /usr/local/bin <binary> \
      && rm -f tool.tar.gz
  fi
  # Submodule URLs use SSH; the session's GitHub proxy speaks HTTPS only.
  git config --system url."https://github.com/".insteadOf "git@github.com:"
  # Fallback for sessions that skip the repo hook (several repos, another branch).
  mkdir -p /root/.claude
  cat > /root/.claude/CLAUDE.md <<'NOTE'
# <Environment name>
<One paragraph: what this environment is for and who uses it.>
Follow the `<skill>` skill of <org/repo> (`.claude/skills/<skill>/SKILL.md`) for every request.
<The one rule that matters most, e.g. which product/template this environment uses.>
If the clone has no `.claude/skills/<skill>/`, attach <org/repo> with add_repo if needed, run
`<bootstrap> <path to the clone>`, then work from `<dir>` as its output says. Don't make up your own setup.
NOTE
  <tool> --version
} > /tmp/<project>-setup.log 2>&1
exit 0
```

Node example (only the binary is replaced, so the image's global tools keep
working):

```bash
NODE_VERSION=22.23.1
PNPM_VERSION=10.34.4
if [ "$(/opt/node22/bin/node -v)" != "v${NODE_VERSION}" ]; then
  tarball="node-v${NODE_VERSION}-linux-x64.tar.xz"
  cd /tmp \
    && curl -fsSLO "https://nodejs.org/dist/v${NODE_VERSION}/${tarball}" \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt" | grep " ${tarball}\$" | sha256sum -c - \
    && tar -xJf "${tarball}" -C /opt \
    && install -m 755 "/opt/node-v${NODE_VERSION}-linux-x64/bin/node" /opt/node22/bin/node \
    && rm -f "${tarball}"
fi
/opt/node22/bin/corepack enable
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 /opt/node22/bin/corepack prepare "pnpm@${PNPM_VERSION}" --activate
```

## Bootstrap command (written by the setup script)

```bash
#!/bin/bash
# Usage: <bootstrap> <clone>. Puts the newest branch that has the skill (main, else
# the setup branch) in a worktree at <dir> and runs its session-start hook there.
m=${1:?usage: <bootstrap> <clone>}; dir=${CLOUD_DIR:-/opt/<project>-cloud}
if [ ! -e "$dir/.claude/skills/<skill>/SKILL.md" ]; then
  for ref in main <setup-branch>; do
    git -C "$m" fetch -q origin "$ref" \
      && git -C "$m" cat-file -e FETCH_HEAD:.claude/skills/<skill>/SKILL.md 2>/dev/null \
      && git -C "$m" worktree add -q -f --detach "$dir" FETCH_HEAD && break
  done
fi
[ -e "$dir/.claude/skills/<skill>/SKILL.md" ] || { echo "Couldn't fetch the setup from <org/repo>."; exit 1; }
cd "$dir" && CLAUDE_PROJECT_DIR="$dir" bash scripts/<cloud>/session-start.sh
echo "Work from $dir: read $dir/.claude/skills/<skill>/SKILL.md and run its scripts from there."
```

## SessionStart hook

```bash
#!/bin/bash
# SessionStart hook for <vendor> cloud sessions. Does nothing on laptops.
# Signs tools in, checks out what the session can reach, prints a status that
# becomes part of the agent's context. Always exits 0.
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
cd "$root" || exit 0
log=/tmp/<project>-session-start.log
status=()

# Only missing submodules: on a resumed session they hold the agent's branches.
ready=() unreachable=()
for path in <submodule paths>; do
  if [ -e "$path/.git" ] || git submodule update --init --filter=blob:none "$path" >>"$log" 2>&1; then
    ready+=("$path"); else unreachable+=("$path"); fi
done
[ ${#unreachable[@]} -gt 0 ] && status+=("Code NOT checked out (repos not attached): ${unreachable[*]}. Attach each with your add_repo tool, then rerun this script. Until then those folders are empty and git -C <dir> runs against the parent repo.")

if [ -z "${<TOKEN_VAR>:-}" ]; then
  status+=("<Tool>: <TOKEN_VAR> is not set on this environment; an engineer adds it.")
elif ! <tool> <status command> 2>&1 | grep -q '<signed-in text>'; then
  <tool> login <flags reading "$<TOKEN_VAR>"> >>"$log" 2>&1 \
    && status+=("<Tool>: signed in.") || status+=("<Tool>: sign-in FAILED, see $log.")
fi

echo "<Vendor> cloud session for <environment>."
printf '%s\n' "${status[@]}"
echo "For any request, follow .claude/skills/<skill>/SKILL.md."
exit 0
```

`.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/scripts/<cloud>/session-start.sh", "timeout": 600 } ] }
    ]
  },
  "permissions": {
    "allow": [
      "Bash(bash scripts/<cloud>/session-start.sh:*)",
      "Bash(python3 scripts/<cloud>/<helper>.py:*)"
    ]
  }
}
```

## Test prompts

### Environment check

```
Environment check only: do not change, commit, or push anything.
1) Print /tmp/<project>-setup.log.
2) Print the runtime and package manager versions and paths (for example: node -v, which -a node,
   echo $PATH, pnpm -v) and compare them with the repo's pins.
3) Run a frozen install (for example: CI=true pnpm install --frozen-lockfile) and report the time.
4) Run the slowest build the workflow needs and report the time and output size.
5) Try a headless browser screenshot of the running app and say which browser binary worked.
Report each result in one line.
```

### Secret check (project environment, then a control without the secret)

Claude (the proxy adds the header, so send none):

```
Network check only: do not change, commit, or push anything.
Run: curl -s -o /dev/null -w '%{http_code}\n' <a URL that needs the secret>
Report the status code only. Do not print any headers or tokens.
```

Codex, current flow (the program sends the placeholder; the proxy substitutes
the real value):

```
Network check only: do not change, commit, or push anything.
Run: curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $<SECRET_VAR>" <a URL that needs the secret>
Report the status code only, and whether <SECRET_VAR> is set (yes/no). Do not print its value, any headers or tokens.
```

Expect 200 in the project environment and 401 in the control: for Claude the
default environment; for Codex an environment without that secret, where the
variable is unset and the same command sends an empty credential. Use the
header name and prefix the API expects.

### Engineer probe

```
Engineer test of this cloud environment (I maintain it). Run each check, then report a table:
check | pass/fail | one-line evidence. Never print tokens or env values containing secrets.
1. Start-up: tail the setup and session-start logs; echo $CLAUDE_CODE_REMOTE and <flags>;
   whether <TOKEN_VAR> is set (length only).
2. Code: submodule status; git log -1 in each; a push --dry-run to claude/probe-dryrun.
3. <Tool>: version, identity (one field), list (count only), proxy variable NAMES.
4. Follow <skill> to create a test <resource> named <prefix>-probe-<4 random>. Report the time.
5. Use it: <exec/endpoint checks with status codes>.
6. Round trip: <harmless change, sync, confirm, revert, confirm>.
7. Screenshot <page> with whatever browser the environment provides; describe sign-in.
8. Delete the test <resource> and confirm it is gone.
Finally: anything in the skill or scripts that was wrong, unclear or failed, with the fix you'd
make (don't commit or push).
```

### MCP setup check (appended to a real task)

```
<Real task>. Do not edit files, commit, push, or open a PR, and do not change anything in <system>.
After the task, add a short "Setup check" section: (a) git log -1 --oneline; (b) how many <server>
MCP tools loaded; (c) whether <TOKEN_VAR> is set or unset (never print a value) and the value of
<PROXY_FLAG>; (d) whether you had to wait for or poll any background step; (e) the output of:
<write-guard test command>
```

### Diagnosis

```
Let's dig into <failure>. No secrets in output: redact token/Authorization/cookie values.
1. Run <harmless failing command> and give the exact error text.
2. The tool's own log lines for that run, redacted, cut to 200 chars.
3. Proxy variable names: env | cut -d= -f1 | grep -i -E 'proxy|ssl|cert|ca_'.
4. Through the proxy: curl -sv to <host> — status, CONNECT lines, certificate issuer.
5. WebSocket upgrade and HTTP/2 behaviour through the proxy (status lines only).
6. Any proxy docs inside the VM.
Report findings plainly; don't change any files.
```

### Rehearsal

```
Pilot rehearsal: do not push, open a pull request, or touch any remote.
Pretend I'm a <role> who doesn't write code. Request: "<one small change>".
Follow the repo's instructions and skill. Show me clickable before and after pages, run the
relevant checks, and commit locally on a branch only. Tell me how long each step took.
```

### Persona sequence

```
1. Hi, I'm on the <team> and I don't write code. <Ask to see something>. A screenshot is fine.
2. Thanks! <Ask for a small change> and show me how it looks.
3. Looks good, please save it.
4. That's all, thanks. Please delete the test copy.
```

Then a plain prompt with no hints, a shared link "only look, don't change
anything", and the wrong starts.

## Change record

```
# <Project> cloud-agent setup: change record (<date>)
Goal:
Owner:
## Pre-state (read-only)
## Decisions
## Changes          (numbered; what, how, read-back)
## Tests            (session id, prompt, result vs known answer, created/deleted)
## Risks            (each with who accepted it, when)
## Rollback         (one line per change)
## Open
```

## Vault item

```
Title:    Claude cloud – <what> (<repo or environment>)
Value:    <pasted by a human, or piped by a script>
Scope:    <exact permissions>
Used by:  <vendor> environment "<name>", network secret "<name>" or variable <NAME>
Expires:  <date>
Owner:    <person>
Header:   <header names and prefix, for custom-header secrets>
Check:    len <n>, sha256:<12 chars>
```
