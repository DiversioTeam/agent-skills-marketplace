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

## Base Branch Detection

```bash
# Detect the base branch — defaults to the repo's default branch.
# Override by setting BASE_BRANCH before invoking (e.g., BASE_BRANCH=release).
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name')"
fi
```

---

## Step 0: Merge Conflict Check

Before running any other gate, verify the branch can merge cleanly.

```bash
gh pr view --json mergeable,mergeStateStatus
```

- `MERGEABLE` → no conflicts ✅
- `CONFLICTING` → must resolve before anything else
- `UNKNOWN` → GitHub hasn't computed it yet (recent push)

If `CONFLICTING` or `UNKNOWN`, check locally:

```bash
# Fetch and attempt merge (always merge, never rebase)
git fetch origin release
git merge origin/$BASE_BRANCH --no-edit --no-ff
```

### If merge fails with "unrelated histories"

This happens in shallow clones (CI, fresh worktrees) where git doesn't
have the common ancestor. Unshallow to fetch the full history, then retry
with a normal merge:

```bash
# Unshallow the repo to get full history (fetches the common ancestor)
git fetch --unshallow origin 2>/dev/null || true

# Retry with a normal merge — histories should now be related
git merge origin/$BASE_BRANCH --no-edit --no-ff
```

**Do NOT use `--allow-unrelated-histories`** — if the merge still fails
after unshallowing, the branches are genuinely unrelated and forcing it
would create a broken merge. Stop and investigate.

### If merge succeeds but has conflicts

```bash
# List conflicting files
git diff --name-only --diff-filter=U

# Resolve each conflict, then:
git add <resolved-files>
git commit --no-edit
```

### Check if branch is behind release

```bash
git fetch origin release
git merge-base --is-ancestor HEAD origin/$BASE_BRANCH && echo "up to date" || echo "⚠️ branch behind release — merge before pushing"
```

**Always merge, never rebase.** Rebasing rewrites history and can silently
lose merge fixes, drop migration ordering, or create duplicate commits.

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
  .bin/ruff format $(git diff --name-only origin/$BASE_BRANCH...HEAD --diff-filter=ACMRT | grep '\.py$')
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
.bin/ty check $(git diff --name-only origin/$BASE_BRANCH...HEAD --diff-filter=ACMRT | grep '\.py$')
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
git diff --name-only origin/$BASE_BRANCH...HEAD -- '*/migrations/*.py' \
  | grep -v '__init__' \
  | awk -F'/migrations/' '{print $1}' \
  | sort | uniq -c | sort -rn
```

### If any app has more than one new migration

**First, check if these migrations have already been pushed and shared:**

```bash
# Have these migrations been pushed to the remote branch?
git log --oneline origin/<branch> -- '*/migrations/*.py' | head -5
```

**If NOT yet pushed** (safe to squash):
1. Identify the last migration BEFORE the branch's first new one:
   ```bash
   ls <app>/migrations/ | grep '^0' | sort | tail -5
   ```
2. Delete only the branch-specific migration files.
3. Run `.bin/django makemigrations <app>` to regenerate a single migration.
4. Run `.bin/ruff check --fix` and `.bin/ruff format` on the new file.
5. **Critically**: verify the new migration contains ALL operations from the deleted ones:
   ```bash
   git diff --cached -- '*/migrations/*.py'  # Review the squashed migration
   ```
6. Verify with `.bin/django migrate --check` (no pending changes).

**If ALREADY pushed** (do NOT delete — others may have applied them):
- Don't squash. The cost of breaking other environments outweighs the benefit.
- Flag as `[SHOULD_FIX]` for next time — squash before pushing.
- Exception: if you're the only one on this branch and can coordinate, squash + force-push is acceptable.

### Special cases — do NOT squash

- **Data migrations with `RunPython`**: these can't be auto-regenerated by
  `makemigrations`. If you delete them, you lose the data migration logic.
  Either: (a) manually merge the operations into one migration file, or
  (b) leave them separate and accept the multiple migration.
- **Dependent migrations**: if migration 0009 adds a field and migration
  0010 uses it, they can be squashed but you must verify the operations
  are in the correct order in the regenerated migration.

**Flag**: `[SHOULD_FIX]` — multiple migrations for same app should be
squashed into one before pushing. `[BLOCKING]` if the squash would
lose data migration logic or break a dependency chain.

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
.bin/pytest $(git diff --name-only origin/$BASE_BRANCH...HEAD --diff-filter=ACMRT | grep 'tests/.*\.py$')
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
  ruff:      .bin/ruff format $(git diff --name-only origin/$BASE_BRANCH...HEAD --diff-filter=ACMRT | grep '\.py$')
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
