---
name: dependabot-remediation
description: "Plan and execute backend and frontend Dependabot remediation with wave-based sequencing, resolver validation, and post-merge closure checks."
allowed-tools: Bash Read Edit Write Glob Grep
argument-hint: "[backend <triage|execute-wave <N>|release> | frontend <triage|execute|release>] [--repo owner/repo] [--base-branch <name>] [--config-only] [--write-config]"
---

# Dependabot Remediation Skill

## When to Use This Skill

Use this skill when a repository has open Dependabot security alerts and you
need a deterministic remediation flow with clear evidence and rollback paths.

Use it for:
- Python backend remediation waves (for example `uv` + `pyproject.toml` repos).
- JavaScript/TypeScript frontend remediation waves (`npm`, `yarn`, or `pnpm`).
- Mixed remediation periods where backend and frontend flows must stay explicit
  and separate.

## Modes

- `backend <triage|execute-wave <N>|release>`:
  - `triage`: Review/create `dependabot.yml`, then build backend alert inventory and wave plan.
  - `execute-wave <N>`: Execute one backend wave with strict gates.
  - `release`: Validate closure and prepare backend remediation release summary.
- `frontend <triage|execute|release>`:
  - `triage`: Review/create `dependabot.yml`, then build frontend PR/alert triage matrix.
  - `execute`: Execute frontend close/recreate/merge/manual flow.
  - `release`: Create frontend release summary for remediation changes.

## Shared Invariants

1. Query live GitHub Dependabot alerts before proposing changes.
2. Do not claim remediation success until post-merge alert re-check passes.
3. Keep wave boundaries atomic and reversible.
4. Report blockers explicitly with severity tags.
5. If checks were not run, state that explicitly.

Severity tags:
- `[BLOCKING]` cannot proceed safely
- `[SHOULD_FIX]` high-value correction before merge
- `[NIT]` optional improvement

## Shared Baseline

Before backend or frontend execution:

```bash
git status -sb
git branch --show-current
gh auth status
```

If GitHub auth is missing or token lacks alert permissions, stop with `[BLOCKING]`.

## Dependabot Config Gate (runs during `triage`)

Before backend/frontend alert triage, validate repository configuration:

1. Detect repo + default branch via `gh repo view`.
2. Check `.github/dependabot.yml`:
   - If missing: propose minimal config using
     `references/dependabot-yml-minimal-template.md`.
   - If `--write-config` is set: create `.github/dependabot.yml`.
3. If present: review with
   `references/dependabot-yml-review-checklist.md`.
4. Surface `[BLOCKING]` config gaps that invalidate remediation claims.

If `--config-only` is set, stop after config create/review + CI policy advice.

## Backend Workflow

### 1. Triage (`backend triage`)

Goal: produce deduplicated advisory inventory plus executable waves.

Required workflow:
1. Run Dependabot config gate (review existing config or scaffold minimal config).
2. Fetch all open Dependabot alerts with pagination.
3. Filter to backend scope (backend ecosystems and/or backend manifest paths).
4. Deduplicate by `package + GHSA + first_patched_version`.
5. Classify each advisory as direct vs transitive.
6. Trace transitive root constraints before proposing targets.
7. Validate proposed upgrades via resolver checks before finalizing waves.

Primary references:
- `references/backend-github-dependabot-cli.md`
- `references/backend-wave-plan-template.md`
- `references/dependabot-yml-minimal-template.md`
- `references/dependabot-yml-review-checklist.md`
- `references/dependency-review-ci-policy-template.md`

### 2. Execute One Wave (`backend execute-wave <N>`)

Execution rules:
- Only execute the requested wave.
- Do not silently include packages from other waves.
- Keep lock/export artifacts consistent with repository policy.

Backend validation gates must include:
- Lock consistency (`uv lock --check` or repo equivalent)
- Lint gates (repo wrappers if present)
- Active Python type gate with precedence:
  - `ty` first
  - `pyright` second
  - `mypy` third
- Targeted tests for touched dependency surfaces

If `ty` is configured (`[tool.ty]`, `ty.toml`, `.bin/ty`, or CI usage), treat it
as mandatory and blocking.

### 3. Release / Closeout (`backend release`)

After waves merge:
1. Re-query open Dependabot alerts and re-apply backend scope filter.
2. Report residual backend advisories by severity/package.
3. Summarize merged wave PRs and validation status.
4. Provide additional-wave plan for any residual backend alerts.

## Frontend Workflow

### 1. Triage (`frontend triage`)

Goal: classify open bot PRs and alerts into actionable lanes.
Always scope PR inventory to the frontend base branch (auto-detect from
`gh repo view ... defaultBranchRef` unless overridden) so backend Dependabot
PRs are not mixed into the matrix.

Required workflow:
1. Run Dependabot config gate (review existing config or scaffold minimal config).
2. Build PR and alert inventory scoped to frontend base branch.
3. Classify each PR as `actionable`, `obsolete`, or `stale-but-recreate`.
4. Identify alert gaps with no PR coverage and mark manual remediation candidates.

Classification classes:
- `actionable`
- `obsolete`
- `stale-but-recreate`

References:
- `references/frontend-triage-matrix.md`
- `references/dependabot-yml-minimal-template.md`
- `references/dependabot-yml-review-checklist.md`
- `references/dependency-review-ci-policy-template.md`

### 2. Execute (`frontend execute`)

Execution policy:
1. Close obsolete PRs with explicit rationale comments.
2. Recreate stale-but-relevant PRs using `@dependabot recreate`.
3. Merge actionable PRs in security-first order once checks pass.
4. If alerts remain without bot PR coverage, run manual remediation branch flow.
5. Re-check open alerts and report residual risk.

References:
- `references/frontend-triage-matrix.md`
- `references/frontend-manual-remediation-playbook.md`

### 3. Release (`frontend release`)

Generate remediation release summary for integration branch -> production branch:
- Included remediation PRs
- Diff scope and validation context
- Alert status at release-cut time

Reference:
- `references/frontend-release-pr-template.md`

## Output Shape

### Backend Modes Output

Always return:
1. `Current State`
2. `Dependabot Config Status` (existing/reviewed or created/proposed)
3. `Backend Scope Filter` (ecosystem/path rules used)
4. `Deduplicated Alert Inventory`
5. `Root-Cause Dependency Paths`
6. `Proposed Waves` or `Wave Execution Summary`
7. `Validation Gates`
8. `Risks and Rollback`
9. `Next Actions`

### Frontend Modes Output

Always return:
1. `Inventory`
2. `Dependabot Config Status` (existing/reviewed or created/proposed)
3. `Triage Matrix`
4. `Execution Summary`
5. `Risk Snapshot`
6. `Next Actions`

## Guardrails

- Never merge backend and frontend remediation into the same wave branch unless
  explicitly requested.
- Never force push remediation branches unless explicitly requested.
- Never include unrelated file changes in manual remediation PRs.
- Never close high/medium alert PR coverage without replacement path.
- Never claim sustainable remediation unless `dependabot.yml` is reviewed or created.
