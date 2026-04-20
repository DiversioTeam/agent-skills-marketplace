# E2E Debugging Guide

## Root Cause Debugging (CI Failures)

**Two-pass approach: diagnose FIRST, fix SECOND.** Don't guess at fixes - read the logs.

### Step 1: Get the failure logs

```bash
# Find the failed run
gh run list --branch <branch> --workflow sandbox.yml --limit 5

# Read the failed logs (this is your starting point, always)
gh run view <run-id> --log-failed
```

### Step 2: Categorize the failure

| Category       | Symptoms                                      | Common Fix                                     |
| -------------- | --------------------------------------------- | ---------------------------------------------- |
| **Selector**   | `locator.click: Error: strict mode violation` | Make selector more specific or use `.first()`  |
| **Navigation** | `page.goto: net::ERR_CONNECTION_REFUSED`      | Check baseURL, ensure app is running           |
| **Auth**       | Redirected to login, 401 errors               | Check auth state setup, cookie/token expiry    |
| **Flaky**      | Passes locally, fails in CI intermittently    | Add `waitFor`, check race conditions, timeouts |
| **Config**     | Module not found, env variable undefined      | Check CI env setup, dependency installation    |

### CI-specific gotchas

- CI runs **chromium only** (not Firefox/WebKit) with **2 retries** and **2 workers**
- Sandbox URLs differ from localhost - check `baseURL` in CI config
- CI runs in headless mode - hover/tooltip tests may behave differently
- `__dirname` doesn't work in ESM - use `import.meta.url` instead

---

## Artifact-Based Debugging

**Artifact naming:** `e2e-report-pr-{PR_NUMBER}` (7-day retention)

**What's included:**

- HTML report (always)
- Screenshots (on failure only)
- Video (retained on failure only)
- Traces (on first retry only)

### Step 1: Download artifacts

```bash
# List recent runs for your branch
gh run list --branch <branch> --workflow sandbox.yml --limit 5

# Download the E2E report artifact
gh run download <run-id> -n e2e-report-pr-<PR_NUMBER>
```

### Step 2: Analyze the report

```bash
# Open the HTML report (visual test results with screenshots)
npx playwright show-report ./e2e-report-pr-<PR_NUMBER>

# Analyze a specific trace file (step-by-step execution replay)
npx playwright show-trace ./e2e-report-pr-<PR_NUMBER>/trace.zip
```

### Step 3: Complete debugging workflow

1. **Read logs** - `gh run view <run-id> --log-failed` (always start here)
2. **Download artifacts** - `gh run download <run-id> -n e2e-report-pr-<PR_NUMBER>`
3. **View screenshots** - check the HTML report for failure screenshots
4. **Check traces** - replay the exact browser actions that led to failure
5. **Fix** - apply the fix based on root cause category above
6. **Verify locally** - `yarn test:e2e --grep "test name"` before pushing

---

## Local E2E Testing Against Sandbox

Run E2E tests locally against a Crafting Sandbox before pushing.

### Prerequisites

- **CS CLI** installed (`brew install crafting-dev/tap/cs` or [docs](https://docs.crafting.dev/cli))
- **Authenticated**: `cs login` (one-time setup)

### Step-by-Step

**1. Check CS CLI is ready**

```bash
cs info    # Should show authenticated user and org
```

**2. Find your sandbox name**

```bash
cs sandbox list    # Lists all active sandboxes
# Sandbox name follows pattern: test-{first-two-meaningful-words}
```

**3. Resume if suspended**

```bash
cs sandbox resume test-my-feature    # Resumes and waits until ready
cs sandbox show test-my-feature      # Verify status is RUNNING
```

**4. (Optional) Pin sandbox to prevent auto-suspension**

```bash
cs sandbox pin test-my-feature       # Prevents auto-suspension
# Remember to unpin when done: cs sandbox unpin test-my-feature
```

**5. Set environment variables and run tests**

```bash
export E2E_BASE_URL="https://web--test-my-feature.org.sandboxes.run"
export VITE_API_URL="https://backend--test-my-feature.org.sandboxes.run/optimo/api/v1"
export E2E_TEST_SECRET="<ask team for value>"

# Run tests (chromium only, matching CI)
yarn test:e2e --project=chromium

# Run specific test tags
yarn test:e2e --project=chromium --grep '@critical'
```

**6. View the report**

```bash
yarn test:e2e:report    # Opens HTML report in browser
```

### Troubleshooting

| Issue                          | Symptom                          | Fix                                                                    |
| ------------------------------ | -------------------------------- | ---------------------------------------------------------------------- |
| `cs: command not found`        | CLI not installed                | `brew install crafting-dev/tap/cs`                                     |
| `not authenticated`            | Login expired                    | `cs login`                                                             |
| `sandbox not found`            | Sandbox deleted or never created | Open a PR to trigger sandbox creation                                  |
| Connection refused             | Sandbox suspended                | `cs sandbox resume <name>`                                             |
| 502/503 from backend           | Backend still booting            | Wait 30-60s after resume, check `cs sandbox show <name>`               |
| Auth redirect loop             | Wrong `E2E_BASE_URL`             | Verify URL matches `cs sandbox show` output                            |
| Tests pass locally, fail in CI | Environment differences          | CI uses headless chromium with 2 retries; check sandbox URL in CI logs |

---

## Playwright Configuration Reference

- **Base URL:** `https://localhost:3000`
- **Browsers:** Chromium, Firefox, WebKit, Mobile Chrome (Pixel 5), Mobile Safari (iPhone 12)
- **Retries:** 0 locally, 2 in CI
- **Traces:** On first retry
- **Screenshots:** Only on failure
- **Video:** Retain on failure
- **Timeout:** 30s per test, 5 min global
