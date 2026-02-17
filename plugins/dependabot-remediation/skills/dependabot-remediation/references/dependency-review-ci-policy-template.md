# Minimal CI Policy Template (Dependency Review + Stack Audit)

Use this after creating/reviewing `.github/dependabot.yml`.

## 1. Required PR Gate: Dependency Review Action

Create `.github/workflows/dependency-review.yml`:

```yaml
name: dependency-review

on:
  pull_request:
    branches: ["main"] # replace with your protected production branch

permissions:
  contents: read

jobs:
  dependency-review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/dependency-review-action@v4
        with:
          fail-on-severity: moderate
          fail-on-scopes: runtime
          comment-summary-in-pr: always
```

Set this workflow as a required status check in branch protection.

## 2. Optional Defense-in-Depth Gate: Package-Manager Audits

Create `.github/workflows/dependency-audit.yml`:

```yaml
name: dependency-audit

on:
  pull_request:
    branches: ["main"] # replace with your protected production branch

permissions:
  contents: read

jobs:
  dependency-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install uv
        uses: astral-sh/setup-uv@v5
      - name: Backend lock check
        run: |
          if [ -f pyproject.toml ] && [ -f uv.lock ]; then
            uv lock --check
          fi
      - name: Frontend audit
        run: |
          if [ -f yarn.lock ]; then
            corepack enable
            yarn npm audit -A -R --severity moderate
          elif [ -f pnpm-lock.yaml ]; then
            corepack enable
            pnpm audit --prod --audit-level moderate
          elif [ -f package-lock.json ]; then
            npm audit --audit-level=moderate
          else
            echo "No Node lockfile found; skipping frontend audit."
          fi
```

If your org already enforces security analysis centrally, keep this lightweight
or remove overlap.
