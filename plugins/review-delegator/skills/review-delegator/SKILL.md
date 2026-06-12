---
name: review-delegator
description: >
    Review delegator. Runs monty-v2's core analysis (intent,
    branch enumeration, adversarial inputs), then delegates specialized
    checks to focused sub-skills in parallel for deep coverage. Compiles
    findings into a single review. Use for PRs that touch 5+ files or
    multiple subsystems where a single-skill review would miss systemic issues.
user-invocable: true
argument-hint: '[--quick] [--deep] [--self-review]'
allowed-tools: [Bash, Read, Edit]
---

# Review Delegator

Delegates a multi-skill code review by running monty-v2's core analysis,
then delegating specialized checks to focused sub-skills. Each sub-skill
handles ONE concern deeply, making it much harder to miss the patterns
that a monolithic review overlooks.

## When to Use

- PR touches **5+ files** or multiple subsystems
- PR involves **contract changes** (new fields, changed signatures)
- PR has been through **multiple review rounds** with recurring findings
- Reviewer feedback history shows **lifecycle parity, admin form, or merge
  drift issues** were caught late
- **`--deep`** mode: any PR where correctness-critical code is touched

For simple 1-2 file bugfixes, use `/monty-v2-code-review:code-review` directly.

## Architecture

```
Review Delegator
├── Phase 1-3: monty-v2 core (understand, enumerate, adversarial)
├── Phase 4 (delegated): Sub-skills in parallel
│   ├── /contract-propagation-check:check ← P10, P17, P18
│   ├── /merge-drift-check:check        ← P22, P24, P25
│   ├── /historical-data-check:check    ← P14, P16, P23
│   ├── /test-quality-check:check       ← P1, P12, P19, P20
│   └── /gate-runner:run                ← ruff, ty, imports, migrate
├── Phase 5-6: monty-v2 (bias check, blind-spot sweep)
└── Phase 8: Compile & write review
```

Each sub-skill returns findings tagged with `[BLOCKING]`, `[SHOULD_FIX]`, `[NIT]`.
The delegator compiles all findings into a single review document.

---

## Step 1: Understand the PR

```bash
# Basic PR info
gh pr view --json number,title,url,headRefName,body,baseRefName

# Detect the base branch — defaults to the PR's target branch.
# Override by setting BASE_BRANCH before invoking.
if [ -z "$BASE_BRANCH" ]; then
  BASE_BRANCH="$(gh pr view --json baseRefName --jq '.baseRefName')"
fi

# Files changed
git diff --name-only origin/$BASE_BRANCH...HEAD

# Diff size
git diff --stat origin/$BASE_BRANCH...HEAD
```

Classify the PR:
- **Size**: small (1-2 files), medium (3-10 files), large (10+ files)
- **Type**: bugfix, feature, refactor, migration, chore
- **Risk areas**: models, admin, services, API, migrations, config

---

## Step 2: Run monty-v2 Core (Phases 1-3)

Run monty-v2's first three phases to understand intent, enumerate branches,
and check adversarial inputs:

```
/monty-v2-code-review:code-review Phase 1-3 only
```

This gives you:
- What problem is being solved
- Every branch in every changed function
- Input combination gaps
- Test coverage map for each branch

Hold these results — they'll be incorporated into the final review.

---

## Step 3: Delegate Specialized Checks (Parallel)

Based on the PR classification, delegate to the relevant sub-skills.
Run them in parallel — each focuses on ONE concern:

### Always run (Tier 1 checks — highest-recurring missed patterns)

These sub-skills MUST be invoked for EVERY PR with 3+ files or any
correctness-critical change. Skip only for trivial 1-2 file changes
with no helpers, admin, models, or config changes.

```
/contract-propagation-check:check
```
Covers: P10 (change propagation), P17 (lifecycle parity), P18 (admin
three-layer surface). Greps ALL consumers of every changed function,
model field, and utility. Verifies lifecycle parity at every stage.

```
/merge-drift-check:check
```
Covers: P22 (merge drift), P24 (unrelated file regression), P25 (PR
description drift). Checks pyproject.toml/uv.lock, WhiteLabel assets,
fixture regression, and PR description accuracy.

```
/gate-runner:run
```
Covers: ruff_pr_diff.sh, ty check, local_imports_pr_diff.sh, migration
squash check. Runs the exact CI gate sequence.

### Run when relevant

```
/historical-data-check:check
```
Run when: migrations, config import/export, data processing, field
constraints, or sentinel values are touched. Covers: P14, P16, P23.

```
/test-quality-check:check
```
Run when: new tests added, test assertions changed, or CI tolerance
adjustments made. Covers: P1, P12, P19, P20.

### Delegation Completion Gate

Each sub-skill has its own completion gate. Before moving to Step 4, verify:

```text
☐ /contract-propagation-check:check returned with evidence (not "looks fine")
☐ /merge-drift-check:check returned with evidence (not "no drift found")
☐ /gate-runner:run returned with pass/fail for each gate
☐ /historical-data-check:check returned (if applicable)
☐ /test-quality-check:check returned (if applicable)
```

**If any sub-skill returned without evidence, re-invoke it.** "No findings"
is only acceptable when accompanied by specific evidence (e.g., line citations,
grep result counts, lifecycle stage checklist).

---

## Step 4: Run monty-v2 Remaining Phases (4-6)

After sub-skills return findings, run monty-v2's per-file analysis and
bias check. **Skip Phase 7 (blind-spot sweep)** — Tier 1 checks are
already handled by the delegated sub-skills. Only run Phase 7 Tier 3
checks inline if any remain unaddressed.

```
/monty-v2-code-review:code-review Phases 4-6 only
```

This covers:
- Phase 4: Per-file analysis (correctness, types, performance, migrations)
- Phase 5: Unchanged code impact (consumer obligation — P10 already covered
  by contract-propagation-check, but Phase 5 adds the centralization
  obligation check: "does every old inline pattern now call the new helper?")
- Phase 6: Bias check (mandatory for self-review)

---

## Step 5: Compile Findings

Merge all findings from all sources. Deduplicate — the same issue
found by both monty-v2 and a sub-skill should appear once.

### Deduplication rules
- Same file, same line, same issue class → keep the more detailed version
- Same issue class across different files → flag as a **systemic pattern**
  (stronger signal than isolated occurrences)

### Systemic patterns
When the same finding appears in 2+ sub-skills or 2+ files, flag it as a
**systemic pattern** in the review summary:

```
[SYSTEMIC] Lifecycle parity: the new <helper> is applied at <stage1>
and <stage2> but missed at <stage3>, <stage4>, <stage5> across 3 files.
```

Systemic patterns are always `[BLOCKING]`.

---

## Step 6: Write Review

Structure the final review:

1. **Summary** — what changed, review mode used, sub-skills invoked
2. **What's great** — 3-7 bullets with file references
3. **Findings** — grouped by file, then by severity:
   - `[BLOCKING]` file:line — explanation + fix
   - `[SHOULD_FIX]` file:line — explanation + fix
   - `[NIT]` file:line — explanation
   - `[SYSTEMIC]` — pattern found across multiple files/skills
4. **Branch Coverage** — from Phase 2
5. **Sub-Skill Reports** — one section per invoked sub-skill, summarizing findings
6. **Test Gaps** — what's covered, what's missing
7. **Unchanged Code Impact** — affected callers
8. **Verdict** — approve/request changes, quantified

---

## Modes

### Default (medium/large PRs)
Run all of the above. Sub-skills: always contract-propagation + merge-drift +
gate-runner; conditionally historical-data + test-quality.

### --quick
For small PRs (1-4 files). Skip sub-skills, run monty-v2 quick-pass directly.
Only invoke sub-skills if monty-v2 quick-pass flags a Tier 1 concern.

```
/monty-v2-code-review:code-review quick-pass
```

### --deep
For security-sensitive, data-migration, or multi-tenant boundary PRs.
Run ALL sub-skills + monty-v2 deep-coverage mode (load per-lens-checklist.md
and full blind-spot-patterns.md).

```
/contract-propagation-check:check
/merge-drift-check:check
/historical-data-check:check
/test-quality-check:check
/gate-runner:run
/monty-v2-code-review:code-review deep-coverage
```

### --self-review
Same as default but Phase 6 (bias check) is mandatory and runs first.
Bias check findings are listed before all other findings.

---

## Rules

- **No AI signatures** — review must look like a human wrote it.
- **Parallel by default** — sub-skills run in parallel when possible.
- **Deduplicate** — same finding from multiple sources appears once.
- **Flag systemic** — patterns across files/skills are stronger signals.
- **Sub-skills are focused** — each handles ONE concern. Don't ask
  contract-propagation-check to also check formatting.
- **Tier 1 checks are mandatory** — P17, P23, P22, P18, P10 are the
  highest-recurring missed patterns. Never skip them.

---

## Example Prompts

> `/review-delegator`
> Full review of current branch's PR.

> `/review-delegator --quick`
> Fast review for a small PR.

> `/review-delegator --deep`
> Deep review for a security-sensitive or multi-tenant PR.

> `/review-delegator --self-review`
> Self-review before pushing — bias check runs first.
