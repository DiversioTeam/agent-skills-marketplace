---
name: mixpanel-analytics
description: "Implement or review Optimo Mixpanel events without regressing identity, tenant safety, producer ownership, privacy, or post-commit delivery. Use for Django optimo_analytics and its cross-channel callers."
allowed-tools: Bash Read Edit Write Glob Grep
---

# Optimo Mixpanel Analytics

Use for adding or changing backend events, reviewing analytics, or checking a
backend/frontend contract. For frontend implementation, also load the frontend
skill's analytics lane; this skill does not replace repository frontend gates.

## Start With Current Evidence

1. Read the target repo's `AGENTS.md` and
   `docs/analytics/optimo-mixpanel/README.md`, especially the engineering
   contract, code map, tests, and current rollout state.
2. Read `optimo_analytics/AGENTS.md`, current schemas, registry, identity helper,
   named producer, real callers, and their tests for the affected domain.
3. Load [references/non-regression-contract.md](references/non-regression-contract.md).
   It records the guardrails introduced by backend PR #3203 and companion
   frontend #579; do not resurrect the older implementation templates.
4. Use the current operating guide and runtime code over historical PR rollout
   claims. If the local guide is absent, fetch the canonical guide below. If
   code and guide disagree, report the conflict before an identity or delivery
   change; never silently restore the old behavior.

Canonical guide:
https://github.com/DiversioTeam/Django4Lyfe/blob/dev/docs/analytics/optimo-mixpanel/README.md

Historical rationale:
https://github.com/DiversioTeam/Django4Lyfe/pull/3203

## Modes

- `/mixpanel-analytics:implement`: follow
  [references/implementation.md](references/implementation.md). `--dry-run`
  produces a proposal only, without editing files or sending events.
- `/mixpanel-analytics:review`: follow
  [references/review.md](references/review.md). Default to staged changes;
  support an explicit PR/branch, `all`, or `file:path`. Inspect only; do not
  apply fixes or publish review comments without authorization.

## Non-Negotiables

- Permanent human `$user_id` is `OptimoUser.uuid`. The backend employee
  `$device_id` is an independent anonymous merge key, never a browser key.
  Only the canonical persisted same-tenant relationship may join them.
- Feature callers use named producers with persisted domain objects or
  approved locators. They never choose reserved identity or call private
  delivery. Producers reload state and derive tenant, subject, and join keys.
- One fact has one authority: backend owns authentication and durable outcomes;
  frontend owns authenticated browser interactions. Public survey pages emit
  no frontend Mixpanel events under the current contract.
- Register one strict schema, origin, and person scope. Delivery is always
  post-commit and fire-and-forget; analytics failure cannot undo business work.
- Keep actor, subject, employee, manager, session, and assignment meanings
  separate. Preserve trusted `impersonation` on every event; never identify
  the impersonated target as the support actor.
- No tokens or token hashes, personal content, raw routes, provider/exception
  text, rendered recommendation titles, or exact risk scores. Disable IP
  enrichment; normal reports filter `impersonation=false`.
- Do not reintroduce `is_cron_job`, `cron_execution_timestamp`, or cron schema
  variants. Use registered origin/person scope and one real occurrence `time`.
- Identity delivery fails closed unless the target project's Simplified ID
  Merge mode is verified and its exact `simplified_v1` acknowledgement is set.
  Never enable telemetry or mutate Mixpanel projects just to make tests pass.

## Type Gate Detection

Read repository typing docs and use its wrappers. Detect `ty`, then `pyright`,
then `mypy`; configured `ty` is mandatory and blocking. Touched files must pass,
without blanket suppressions or "baseline acceptable" exceptions. Run the
repository's required wider gates before claiming merge readiness.

## Completion

Report event authority, affected producer/callers, identity and privacy checks,
regression cases run, repository gate results, and remaining blockers.
Distinguish implemented, tested, staging-observed, governed, and dashboard-ready.
Tests do not prove remote identity merges, enablement, or regional coverage.
Use only authorized staging validation; keep production read-only during
validation and never report real credentials or personal payloads.
