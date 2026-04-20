---
name: frontend-cicd
description: "CI/CD pipeline guidance for React/TypeScript frontends: GitHub Actions workflows, CloudFlare Pages deployment, Crafting Sandboxes, E2E caching, and production release process."
---

# Frontend CI/CD Skill

Pipeline management and debugging guide for frontend CI/CD infrastructure.

---

## Argument Routing

| Argument    | Action                         |
| ----------- | ------------------------------ |
| (none)      | Show pipeline overview         |
| `workflows` | List and explain all workflows |
| `deploy`    | Deployment process guide       |
| `sandbox`   | Crafting Sandbox management    |
| `debug`     | Debug failing CI/CD runs       |
| `release`   | Production release process     |

---

## Pipeline Overview

```
PR Created
  |
  +--> ci.yml: Lint + Type-check + Unit Tests
  +--> deploy.yml: Build + Preview Deploy (PRs to main only)
  +--> sandbox.yml: Create Crafting Sandbox
  |
PR Updated (push)
  |
  +--> ci.yml: Re-run checks
  +--> sandbox.yml: Auto-rebuild (zero CI cost)
  |
PR Approved / /run-tests / run-e2e label
  |
  +--> sandbox.yml: Run E2E tests against sandbox
  |
PR Merged to dev
  |
  +--> deploy.yml: Build + Deploy to staging
  |
Push to main (Release)
  |
  +--> deploy.yml: Build + Deploy to production + Sentry release
```

---

## Workflows

### 1. CI (`ci.yml`)

**Triggers:** PRs to dev/main, push to dev/main

| Job              | Timeout | What It Does                         |
| ---------------- | ------- | ------------------------------------ |
| `lint-typecheck` | 10 min  | `yarn type-check` + `yarn lint`      |
| `unit-tests`     | 15 min  | `vitest --coverage` + PR report      |
| `ci-status`      | -       | Aggregates results, fails if any job fails |

### 2. Deploy (`deploy.yml`)

**Triggers:** Push to main/dev, PRs to main

| Branch/Event   | Deploy To              | Sentry                    |
| -------------- | ---------------------- | ------------------------- |
| Push to `main` | Production             | Full release              |
| Push to `dev`  | Staging                | Deploy record             |
| PR to `main`   | Preview (staging)      | Deploy record             |

### 3. Sandbox (`sandbox.yml`)

**Triggers:** PR events (opened, reopened, synchronize, edited, closed, labeled), PR reviews, comments

| Event                        | Action                          |
| ---------------------------- | ------------------------------- |
| PR opened/reopened           | Create sandbox                  |
| PR synchronize               | Auto-rebuild                    |
| PR edited (BE branch change) | Recreate with new BE branch     |
| Comment `/run-tests`         | Run E2E tests                   |
| Label `run-e2e` added        | Run E2E tests                   |
| PR approved                  | Auto-run E2E tests              |
| PR closed (merged)           | Post-merge validation, delete   |
| PR closed (not merged)       | Delete immediately              |

**Sandbox naming:** `test-{first-two-meaningful-words}` from branch name
**Backend branch:** From PR description `Backend-Branch: name` or defaults to `release`

---

## Crafting Sandbox Management

### Sandbox URLs

```
Frontend: https://web--{sandbox-name}.org.sandboxes.run
Backend:  https://backend--{sandbox-name}.org.sandboxes.run
```

### Triggering E2E Tests

| Method   | How                     | Best For                |
| -------- | ----------------------- | ----------------------- |
| Comment  | `/run-tests` in PR      | Quick one-time test     |
| Label    | Add `run-e2e` label     | Persistent trigger      |
| Approval | Approve the PR          | Auto-runs before merge  |

### Manual Operations

```bash
cs login                              # Authenticate
cs sandbox list                       # List all sandboxes
cs sandbox show test-my-feature       # Show specific sandbox
cs sandbox resume test-my-feature     # Resume suspended sandbox
cs sandbox delete test-my-feature     # Delete sandbox
```

---

## Caching Strategy

| Layer                      | Key                      | Notes                            |
| -------------------------- | ------------------------ | -------------------------------- |
| Yarn packages              | `yarn.lock` hash         | Avoids re-downloading packages   |
| Playwright browsers        | `yarn.lock` hash + OS    | Avoids 200MB browser download    |
| E2E passed marker          | Source hash + grep        | Skips re-running unchanged tests |

### E2E Result Cache

- **Failures are NEVER cached** - only passing runs create entries
- **Any source change invalidates** - even comments in `src/`
- **Bypass:** Comment `/run-tests --force` on PR

### Database Snapshot Restore

Before every E2E run:
- `cs snapshot restore` resets DB to clean state
- Health check loop waits up to 5 min for backend recovery
- Adds ~2-5 min overhead but ensures test isolation

---

## Debugging CI Failures

### Step 1: Identify the Failing Job

```bash
gh run list --limit 10
gh run view {run-id}
gh run view {run-id} --log-failed
```

### Step 2: Common Failures

| Failure                 | Cause                    | Fix                                    |
| ----------------------- | ------------------------ | -------------------------------------- |
| `yarn lint` fails       | ESLint errors/warnings   | Run locally, fix all issues            |
| `yarn type-check` fails | TypeScript errors        | Run locally, fix type issues           |
| Unit tests fail         | Assertion failures       | Run `yarn test` locally                |
| Build fails             | Import errors, env vars  | Check env var availability             |
| Sandbox creation fails  | Crafting API issues      | Check auth token, try `cs sandbox list`|
| E2E tests fail          | Selectors/timing         | Run `yarn test:e2e:debug` locally      |

### Step 3: Reproduce Locally

```bash
yarn lint              # Match CI lint check
yarn type-check        # Match CI type check
yarn test:coverage     # Match CI unit tests
yarn build             # Match CI build
yarn test:e2e:headed   # Debug E2E with visible browser
```

---

## Production Release Process

### Using PR Skill (Recommended)

Use the PR creation skill with `release` argument.

### Manual Process

1. Ensure `dev` is up to date: `git checkout dev && git pull origin dev`
2. Find unreleased PRs: `git log main..dev --grep="Merge pull request" --oneline`
3. Create PR: title `Release [Month] [Day with ordinal] [Year]`, body = bulleted PR links
4. Get approval and merge

---

## Secrets Reference

| Secret               | Used By      | Purpose                          |
| -------------------- | ------------ | -------------------------------- |
| `NPM_TOKEN`         | All builds   | Private package access           |
| `CLOUDFLARE_*`      | deploy.yml   | CloudFlare Pages deployment      |
| `SENTRY_*`          | deploy.yml   | Sentry releases                  |
| `CRAFTING_*`        | sandbox.yml  | Sandbox authentication           |
| `PROD_VITE_*`       | deploy (main)| Production env vars              |
| `DEV_VITE_*`        | deploy (dev) | Dev/staging env vars             |
