# Minimal `dependabot.yml` Template (Backend + Frontend)

Use this when `.github/dependabot.yml` is missing or clearly outdated.

This template is intentionally minimal for February 2026 best practices:
- one backend lane (`uv`)
- one frontend lane (`npm` ecosystem for npm/yarn/pnpm repos)
- grouped security updates to reduce PR noise
- controlled version-update churn (`open-pull-requests-limit`, `cooldown`)

```yaml
version: 2
updates:
  - package-ecosystem: "uv"
    directory: "/"
    target-branch: "main"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "05:00"
      timezone: "UTC"
    open-pull-requests-limit: 10
    versioning-strategy: "increase-if-necessary"
    groups:
      backend-security:
        applies-to: security-updates
        patterns:
          - "*"
    cooldown:
      default-days: 3
      semver-major-days: 14
      semver-minor-days: 5
      semver-patch-days: 2

  - package-ecosystem: "npm"
    directory: "/frontend"
    target-branch: "main"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "05:15"
      timezone: "UTC"
    open-pull-requests-limit: 10
    versioning-strategy: "increase-if-necessary"
    groups:
      frontend-security:
        applies-to: security-updates
        patterns:
          - "*"
    cooldown:
      default-days: 3
      semver-major-days: 14
      semver-minor-days: 5
      semver-patch-days: 2
```

Notes:
- Replace both `target-branch` values with your real integration branch.
- For frontend, keep `package-ecosystem: "npm"` even if using Yarn or pnpm.
- `cooldown` affects version updates only; security updates continue normally.
- If the repo has only backend or only frontend, remove the unused update block.
- If security signal is incomplete for `uv`-only repos, keep this config and add
  CI enforcement (for example `pip-audit`) until dependency coverage is complete.
