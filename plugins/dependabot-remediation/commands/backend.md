---
description: "Backend Dependabot remediation for triage, wave execution, and release closeout."
argument-hint: "[triage | execute-wave <N> | release] [--repo owner/repo] [--base-branch <name>] [--config-only] [--write-config] [--dry-run]"
---

Use your `dependabot-remediation` Skill in **backend** mode.

Select one action via `$ARGUMENTS`:
- `triage` – Review/create `.github/dependabot.yml`, then build backend-scoped deduplicated alert inventory and wave plan.
- `execute-wave <N>` – Execute one backend remediation wave with strict validation gates.
- `release` – Re-check post-merge closure and produce release/closeout summary.

Guardrails:
- Treat missing/invalid `dependabot.yml` as `[BLOCKING]` unless you can create a valid minimal config.
- Scope alert inventory to backend only (ecosystem/path filter) before deduplication.
- Do not execute more than one wave unless explicitly requested.
- Treat failing quality gates as `[BLOCKING]`.
- Keep lock/export artifacts consistent with repo policy.
