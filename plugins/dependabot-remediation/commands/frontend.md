---
description: "Frontend Dependabot remediation for triage, execution, and remediation release summary."
argument-hint: "[triage | execute | release] [--repo owner/repo] [--base-branch <name>] [--config-only] [--write-config] [--dry-run]"
---

Use your `dependabot-remediation` Skill in **frontend** mode.

Select one action via `$ARGUMENTS`:
- `triage` – Review/create `.github/dependabot.yml`, then build PR/alert triage matrix.
- `execute` – Run close/recreate/merge/manual-remediation flow.
- `release` – Generate remediation release summary (`integration -> production`).

Guardrails:
- Keep decisions evidence-based (PR state, checks, lockfile coverage).
- Scope PR triage to the frontend base branch (repo default unless overridden).
- Treat missing/invalid `dependabot.yml` as `[BLOCKING]` unless you can create a valid minimal config.
- Do not close high/medium alert coverage without replacement path.
- Re-check alerts after execution and report residual risk.
