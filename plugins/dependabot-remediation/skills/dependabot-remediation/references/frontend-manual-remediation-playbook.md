# Frontend Manual Remediation Playbook

Use this only when no open Dependabot PR covers remaining alerts.

## Toolchain Preflight

```bash
node -v
npm -v || true
yarn -v || true
pnpm -v || true
```

If versions are missing or unexpected, align via project version manager (for example `nvm`, `asdf`, `volta`, `fnm`).

## Branching

```bash
REPO="${REPO:-$(gh repo view --json nameWithOwner --jq '.nameWithOwner')}"
BASE_BRANCH="${BASE_BRANCH:-$(gh repo view "$REPO" --json defaultBranchRef --jq '.defaultBranchRef.name')}"
git checkout "$BASE_BRANCH"
git pull --ff-only origin "$BASE_BRANCH"
git checkout -b chore/dependabot-remediation-remaining-alerts
```

## Edit Scope

Default scope should stay minimal:
- `package.json`
- one lockfile (`yarn.lock` or `package-lock.json` or `pnpm-lock.yaml`)

Avoid unrelated file edits.

## Verification Steps

1. Ensure vulnerable versions are gone:

```bash
yarn why <package>
# or
npm ls <package>
# or
pnpm why <package>
```

2. Run quality gates:

```bash
# choose the repo package manager
yarn lint
# plus repo-required tests/checks
# or
npm run lint
# or
pnpm lint
```

3. Commit narrowly:

```bash
git add package.json
[ -f yarn.lock ] && git add yarn.lock
[ -f package-lock.json ] && git add package-lock.json
[ -f pnpm-lock.yaml ] && git add pnpm-lock.yaml
git commit -m "chore(deps): remediate remaining dependabot alert packages"
```

4. Push and open PR with package-by-package summary.
