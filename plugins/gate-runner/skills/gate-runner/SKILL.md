---
name: gate-runner
description: >
    Run the exact CI gate sequence on the current branch: ruff_pr_diff.sh,
    ty check, local_imports_pr_diff.sh, and migration squash check. Reports
    pass/fail for each gate with actionable fix commands. Returns findings
    tagged [BLOCKING]/[SHOULD_FIX].
user-invocable: true
allowed-tools: [Bash, Read, Glob, Grep]
---

# Gate Runner

Focused sub-skill that runs the exact CI gate sequence and reports results.
Does NOT fix issues — it diagnoses what gates fail and provides the exact
commands to fix them.

---

## Step 0: Merge Conflict Check

Before running any other gate, verify the branch can merge cleanly.

```bash
gh pr view --json mergeable,mergeStateStatus
```

- `MERGEABLE` → no conflicts ✅
- `CONFLICTING` → must resolve before anything else
- `UNKNOWN` → GitHub hasn't computed it yet (recent push)

If `CONFLICTING`, stop. Don't run other gates — fix conflicts first:

```bash
# Pull and attempt merge
git pull origin release --no-rebase

# If conflicts, list them
git diff --name-only --diff-filter=U

# Resolve, then:
git add <resolved-files>
git commit --no-edit
```

Also check if the branch is behind release (needs a merge to pick up new
migrations, lockfile changes, etc.):

```bash
git fetch origin release
git merge-base --is-ancestor HEAD origin/release && echo "up to date" || echo "⚠️ branch behind release — merge before pushing"
```

**Flag**: `[BLOCKING]` — cannot proceed if branch has conflicts or is
significantly behind release.

---

## Step 1: ruff_pr_diff.sh

The #1 CI failure pattern. Runs `ruff check` and `ruff format --check` on
the union of branch diff + local changes:

```bash
./.security/ruff_pr_diff.sh
```

**If it fails:**
- The output will show exactly which files need formatting.
- Fix command:
  ```bash
  .bin/ruff format $(git diff --name-only origin/release...HEAD --diff-filter=ACMRT | grep '\.py$')
  ```
- Re-run until clean: `./.security/ruff_pr_diff.sh`

**Flag**: `[BLOCKING]` — CI will be red until this passes.

---

## Step 2: local_imports_pr_diff.sh

Ensures all imports use top-level module paths (no local relative imports
in production code):

```bash
./.security/local_imports_pr_diff.sh
```

**If it fails:**
- Fix command: replace relative imports with absolute imports.
- Example: `from .models import Foo` → `from app.models import Foo`

**Flag**: `[BLOCKING]` — CI will be red until this passes.

---

## Step 3: ty check

Run the active type checker on changed Python files:

```bash
# On all changed Python files
.bin/ty check $(git diff --name-only origin/release...HEAD --diff-filter=ACMRT | grep '\.py$')
```

**If it fails:**
- Fix each reported error in the changed file.
- Common pitfalls:
  - Ruff ARG002 fix (prefix `_`) can break `ty` if method signature must
    match parent class (e.g., Django admin methods).
  - Type narrowing needed for optional fields.
- Re-run until clean.

**Flag**: `[BLOCKING]` — CI runs `ty` and will fail.

---

## Step 4: Migration Squash Check

Check if the branch introduced multiple migrations for the same app:

```bash
# Find new migration files on this branch vs release
git diff --name-only origin/release...HEAD -- '*/migrations/*.py' \
  | grep -v '__init__' \
  | awk -F'/migrations/' '{print $1}' \
  | sort | uniq -c | sort -rn
```

**If any app has more than one new migration:**
1. Identify the last migration BEFORE the branch's first new one.
2. Delete only the branch-specific migration files.
3. Run `.bin/django makemigrations` to regenerate a single migration.
4. Run `.bin/ruff check --fix` and `.bin/ruff format` on the new file.
5. Verify with `.bin/django migrate --check`.

**Flag**: `[SHOULD_FIX]` — multiple migrations for same app should be
squashed into one for clean merge history.

---

## Step 5: Optional / Conditional Gates

### Django system checks
```bash
./.security/gate_cache.sh --gate django-system-check --scope index -- uv run python manage.py check --fail-level WARNING
```

Run when models, migrations, or admin registrations are changed.
**Flag**: `[BLOCKING]` if system checks fail.

### Targeted pytest (for risky changes)
```bash
.bin/pytest $(git diff --name-only origin/release...HEAD --diff-filter=ACMRT | grep 'tests/.*\.py$')
```

Run when core logic is changed. **Flag**: `[SHOULD_FIX]` if tests fail.

---

## Step 6: Output

```text
Gate Runner
===========
Branch: <branch>

merge conflict:     ✅ MERGEABLE / ❌ CONFLICTING — <N files>
release sync:       ✅ up to date / ⚠️ behind release
ruff_pr_diff:       ✅ PASS / ❌ FAIL — <N> file(s) need formatting
local_imports:      ✅ PASS / ❌ FAIL — <N> import(s) to fix
ty check:           ✅ PASS / ❌ FAIL — <N> error(s) in <M> file(s)
migration squash:   ✅ OK (1 per app) / ⚠️ <N> migrations for <app>
django checks:      ✅ PASS / ❌ FAIL / ⏭️ SKIPPED
targeted pytest:    ✅ PASS (<N> passed) / ❌ FAIL / ⏭️ SKIPPED

Fix commands:
  conflicts: git pull origin release --no-rebase
  ruff:      .bin/ruff format $(git diff --name-only origin/release...HEAD --diff-filter=ACMRT | grep '\.py$')
  ty:        .bin/ty check <files>
  squash:    .bin/django makemigrations <app>

Overall: ✅ ALL GREEN / ❌ <N> GATES FAILING
```

---

## Rules

- **Read-only by default** — this skill diagnoses, it does not fix.
  Fixes should be applied by the calling skill (pr-review-fix,
  commit-and-reply, or review-delegator).
- **ruff_pr_diff.sh is the #1 CI failure** — always run it first and
  treat failures as `[BLOCKING]`.
- **Cache-aware** — when `gate_cache.sh` is available, use it for
  deterministic checks to avoid re-running identical computations.
- **Scoped by default** — run on changed files only, not the whole repo,
  unless the CI gate requires full-repo scope.
