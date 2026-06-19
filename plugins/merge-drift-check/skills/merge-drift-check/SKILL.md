---
name: merge-drift-check
description: >
    Audit for merge resolution drift: pyproject.toml/uv.lock version regression,
    WhiteLabel asset regression, fixture type cleanup regression, config constant
    regression, lockfile/yarn.lock internal consistency, build artifact drift,
    and PR description accuracy. Returns findings tagged [BLOCKING]/[SHOULD_FIX].
user-invocable: true
allowed-tools: [Bash, Read]
---

# Merge Drift Check

Focused sub-skill that detects silent regressions from merge resolution.
Covers monty-v2 blind-spot checks P22, P24, and P25.

## Base Branch Detection

```bash
# Detect the base branch — defaults to the PR's target branch when a PR exists.
# Override by setting BASE_BRANCH before invoking if needed.
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh pr view --json baseRefName --jq '.baseRefName' 2>/dev/null)"
fi
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name')"
fi
```

**This skill is NOT done until you have:**
- Compared pyproject.toml version against origin/$BASE_BRANCH (not just `git diff`)
- Audited EVERY file outside the feature area that differs from $BASE_BRANCH
- Checked WhiteLabel assets, fixture types, config constants explicitly
- Checked lockfile/yarn.lock for internal inconsistency (2026 extension)
- Checked build artifacts (conftest, type stubs) for regression (2026 extension)
- Verified PR description migration/file references match reality

---

## Step 1: Version Metadata Drift (P22)

The #1 silent regression: `pyproject.toml` and `uv.lock` moving backwards.

```bash
# Check if pyproject.toml version is being downgraded vs release
git diff origin/$BASE_BRANCH...HEAD -- pyproject.toml | grep -E '^[-+].*version'

# Check if uv.lock differs from release
git diff --stat origin/$BASE_BRANCH...HEAD -- uv.lock
```

If `pyproject.toml` shows a version downgrade (e.g., `2026.04.29` → `2026.04.28`):
- `[BLOCKING]` — restore release version: `git checkout origin/$BASE_BRANCH -- pyproject.toml && uv lock`
- This is release metadata, not feature behavior. Merging it regresses the package version.

If `uv.lock` differs without a corresponding `pyproject.toml` change:
- `[SHOULD_FIX]` — the lockfile should only change when dependencies or version change.

---

## Step 2: Unrelated File Regression (P24)

Check ALL files outside the feature area for silent drift:

```bash
# Full stat diff against release
git diff --stat origin/$BASE_BRANCH...HEAD

# Focus on files that should NOT change in this PR
# (everything outside the feature's app directories)
```

### Specific regression patterns to check

**WhiteLabel assets:**
```bash
git diff origin/$BASE_BRANCH...HEAD -- dashboardapp/utility/white_label.py
```
Does the branch revert hard-coded prod S3 URLs that release replaced with
`settings.DASHBOARD_URL`-based dynamic URLs? `[BLOCKING]` if yes.

**Fixture type regression:**
```bash
git diff origin/$BASE_BRANCH...HEAD -- dashboardapp/tests/test_models.py
```
Does the branch revert typed fixtures or helpers that release cleaned up?
`[SHOULD_FIX]` if yes — `ty` will fail CI on the regressed file.

**Config constant regression:**
```bash
git diff origin/$BASE_BRANCH...HEAD -- */constants.py */settings.py
```
Does the branch change config defaults, feature flags, or environment
settings that release intentionally set? `[BLOCKING]` if the change is
unrelated to the feature.

**Test utility regression:**
```bash
git diff origin/$BASE_BRANCH...HEAD -- */tests/conftest.py */tests/utils.py
```
Does the branch remove or change shared test utilities that other tests
depend on? `[BLOCKING]` if breakage is likely.

**Lockfile/yarn.lock internal consistency (2026 extension):**
```bash
# Check yarn.lock for entries with mismatched version numbers (common merge artifact)
git diff origin/$BASE_BRANCH...HEAD -- yarn.lock | grep -E '^[-+].*version:' | head -20

# Check if any lock entry was downgraded (e.g., "version: 2.1.5" to "version: 2.1.4")
# This is drift from merge resolution, not an intentional change
git diff origin/$BASE_BRANCH...HEAD -- yarn.lock | grep -B5 '^-.*version: [0-9]'
```
If yarn.lock shows internal inconsistency (PR#1800 real case: `@nodelib/fs.scandir`
version changed from `2.1.5` to `2.1.4`), it is `[BLOCKING]` — regenerate cleanly.

**Build artifact / conftest regression (2026 extension):**
```bash
# Check conftest.py files for type-behavior changes that can break CI
git diff origin/$BASE_BRANCH...HEAD -- '*/tests/conftest.py' | grep -E '^[-+].*job=|CSVImportResult|OptimoHRIS'

# Check package.json for unintended dependency version changes
git diff origin/$BASE_BRANCH...HEAD -- package.json
```
If conftest.py fixtures change constructor signatures in ways that `ty`
flags (PR#3081 real case: `CSVImportResult(job=None, ...)` → `ty` flags
`invalid-argument-type`), flag as `[BLOCKING]` — fix the type before merge.

---

## Step 3: PR Description Accuracy (P25)

Verify the PR description matches the actual branch:

```bash
# Get PR body
gh pr view --json body --jq '.body'

# List actual migration files on this branch
git diff --name-only origin/$BASE_BRANCH...HEAD -- '*/migrations/*.py' | grep -v __init__
```

Check:
1. **Migration references** — does the PR body mention migration X but the
   branch has migration Y? `[SHOULD_FIX]` if mismatched.
2. **File references** — does the PR body reference files that don't exist
   on this branch? `[SHOULD_FIX]` if stale.
3. **Numbered lists / checklists** — do they match the current branch state?

---

## Step 4: File Count Anomaly Detection

```bash
# Full file list
CHANGED=$(git diff --name-only origin/$BASE_BRANCH...HEAD)
echo "$CHANGED" | wc -l

# Feature-area files (the files the PR is SUPPOSED to touch)
# Define this based on the PR title/description
FEATURE_FILES=$(echo "$CHANGED" | grep -E '<app>/|utils/')

# Files outside the feature area
echo "$CHANGED" | grep -v -E '<app>/|utils/|tests/'
```

If files outside the feature area differ from release:
- Audit each one individually
- Flag any that are NOT intentional changes

---

## Step 5: Output

```text
Merge Drift Check
=================
Branch: <branch>
PR: #<number>

Version metadata:
  - pyproject.toml: <release_version> vs <branch_version> — [OK/REGRESSION]
  - uv.lock: <N> lines changed — [OK/EXCESSIVE/REGRESSION]

Unrelated file audit:
  - WhiteLabel: [clean/REGRESSION] <details>
  - Fixtures: [clean/REGRESSION] <details>
  - Config: [clean/REGRESSION] <details>
  - Tests: [clean/REGRESSION] <details>

PR description accuracy:
  - Migration refs: [accurate/MISMATCH] <details>
  - File refs: [accurate/STALE] <details>

Findings:
  [BLOCKING] <file>:<line> — <description>
  [SHOULD_FIX] <file>:<line> — <description>
```

### Completion Gate

```text
☐ pyproject.toml version compared against origin/$BASE_BRANCH (actual values, not just diff)
☐ uv.lock diff-stat reviewed — lock churn must be intentional
☐ yarn.lock checked for internal inconsistency when present
☐ WhiteLabel assets checked for dynamic URL vs hardcoded S3 regression
☐ Fixture files checked for type cleanup regression (ty will fail CI)
☐ conftest/build-artifact regressions checked when touched
☐ Config constants checked for unintended changes
☐ Every file outside feature area audited — not skipped as "probably fine"
☐ PR description migration references match actual migration filenames on branch
```

---

## Rules

- **Version moves forward only** — any version downgrade is `[BLOCKING]`.
- **Files outside feature area get extra scrutiny** — if they differ from
  release, they must be intentional and necessary.
- **PR description must match reality** — stale references confuse operators.
