# `dependabot.yml` Review Checklist

Use this checklist during `triage` before alert planning.

## Quick Detection

```bash
REPO="${REPO:-$(gh repo view --json nameWithOwner --jq '.nameWithOwner')}"
DEFAULT_BRANCH="$(gh repo view "$REPO" --json defaultBranchRef --jq '.defaultBranchRef.name')"

if [ -f .github/dependabot.yml ]; then
  echo "local config present"
else
  echo "local config missing"
fi

gh api "repos/$REPO/contents/.github/dependabot.yml" >/dev/null 2>&1 \
  && echo "remote config present on default branch ($DEFAULT_BRANCH)" \
  || echo "remote config missing on default branch ($DEFAULT_BRANCH)"
```

## Required Checks

- `version: 2` exists.
- `updates:` includes a backend lane (`uv` for `uv` repos, or repo-appropriate ecosystem).
- `updates:` includes a frontend lane (`npm` ecosystem for npm/yarn/pnpm repos).
- Each update entry has:
  - `directory`
  - `target-branch`
  - `schedule`
  - `open-pull-requests-limit`
- Security grouping is configured:
  - `groups.<name>.applies-to: security-updates`
  - broad `patterns` coverage (usually `*`).
- `target-branch` matches the actual integration branch strategy.
- `directory` paths exist in the repo.

## Optional but Recommended

- `cooldown` for version-update churn control.
- `versioning-strategy: increase-if-necessary`.
- Label policy consistency across dependency PRs.

## Red Flags (`[BLOCKING]`)

- No `dependabot.yml`.
- Wrong branch targeting (Dependabot opening PRs against a non-used branch).
- Missing security grouping where security PR volume is high.
- Broad `ignore` rules that suppress critical security updates.
- Directory paths that do not exist.
