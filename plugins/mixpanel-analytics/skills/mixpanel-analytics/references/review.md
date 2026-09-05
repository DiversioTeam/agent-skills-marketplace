# Review Optimo Analytics

Read the current operating guide and
[non-regression contract](non-regression-contract.md). Review the real caller
through persisted state, producer, registry, identity, and outbound boundary;
a valid schema alone cannot prove a truthful event.

## Scope

- `staged`: staged changes plus relevant surrounding callers (default).
- `branch` or explicit PR: use the actual PR base or repo-documented base, not
  a hardcoded `release` branch. Distinguish committed and uncommitted changes.
- `all`: current analytics module and its business callers.
- `file:path`: supplied file and affected upstream/downstream contract.

## Review In Risk Order

1. **Identity/tenant safety:** permanent user versus employee/browser merge
   keys, canonical persisted links, cross-tenant rejection, no raw-ID fallback
   or caller-owned reserved identity. Check account-only and public cases.
2. **Authority/provenance:** one emitter per fact, explicit actor/subject,
   trusted impersonation and queued schedule origin. No client overrides or
   fabricated actors, sessions, or integration identity merges.
3. **Privacy:** tokens/hashes, raw routes/errors, personal content, exact risk
   scores, and display titles absent from events and logs; IP enrichment off.
4. **Producer/registry:** named producers reload state; exact schema, origin,
   and person scope agree; conflicting subjects rejected. Preserve private
   delivery and restricted-import architecture checks.
5. **Delivery/time:** post-commit only, none on rollback, safe transport failure,
   real outcome time, no resurrected cron fields or duplicate clocks.
6. **Domain behavior:** select applicable rows in the non-regression contract;
   inspect retries and concurrent transitions, assignment/response joins,
   channel distinctions, risk/HRIS worker authority, CTA flattening, and session
   continuity rather than assuming coverage from an event name.
7. **Tests:** real caller/business behavior and exact outbound receipt, using
   `mocker` only at external boundaries; execute commit callbacks. No mocked
   producer, conditional assertions, or unnecessary DB setup for pure schemas.
8. **Rollout:** actual Simplified project verification, acknowledgements,
   staging evidence, region-specific enablement, and report governance. Tests
   or a historical PR body cannot prove the current production state.

## Findings And Validation

Report scope/base, confirmed findings with `path:line`, broken behavior and
impact, a concrete correction, and relevant missing regression checks.

- `[P0]`: identity merge corruption, tenant leak, or private data exposure.
- `[P1]`: wrong authority/provenance, missing registration, delivery timing,
  or other incorrect receipt behavior. Blocking before merge.
- `[P2]`: coverage or documentation gaps; escalate when they hide a P0/P1 risk.
- `[P3]`: optional improvements, never a substitute for correctness evidence.

List repository lint, type, test, and architecture gate results, distinguishing
passed, failed, and not run. Detect `ty` → `pyright` → `mypy`; configured `ty`
is mandatory. State which staging/identity/dashboard claims remain unverified.
Review mode does not edit code, post comments, enable projects, or send test
events. Offer implement mode for authorized fixes rather than applying them
silently after the report.
