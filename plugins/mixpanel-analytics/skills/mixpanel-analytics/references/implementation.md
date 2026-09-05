# Implement An Optimo Event

Read the current operating guide and
[non-regression contract](non-regression-contract.md) first. The old raw-ID,
cron-schema, package-root export, and internal-helper mock templates were
removed deliberately; copy a current neighboring producer, not historical code.

## Define The Fact

Complete: “When **event** changes, **audience** will decide **action** using
**metric**.” Reuse an existing event when a safe property already answers it.
Specify one authority, person scope, actor/subject meanings, bounded properties,
and treatment of duplicate, late, automated, impersonated, or excluded events.

## Make The Smallest Contract Change

1. Reuse/add the event constant and bounded values in
   `optimo_analytics/constants.py`. Preserve the established event naming;
   do not encode worker execution style in a new event name.
2. Define the strict property schema in `schemas.py`, with meaningful field
   descriptions and the current UUID/nullability rules. Shared identity and
   provenance are boundary-owned, not caller fields.
3. Register schema, origin, and person scope together in `registry.py` using
   the actual registry API in this checkout. Delivery remains post-commit.
4. Add/reuse a named producer in the explicit domain module (`auth.py`,
   `survey.py`, `risk.py`, `hris.py`, or `map.py`). A new producer module needs
   a deliberate architecture-allowlist update and its test—not a bypass.
5. Accept the persisted domain object or approved locator plus only facts that
   cannot be recovered from it. Reload and validate state; derive identity via
   `MixpanelEventIdentity`, tenant, subject, channels, and join keys internally.
6. Wire the real business transition to that producer with an explicit domain
   import. Do not call private delivery from feature code or automatically
   re-export helpers through `service/__init__.py`.
7. Keep analytics failure non-blocking and logs free of private payload/error
   text. Use the existing shared boundary instead of creating a second client.

For auth attribution changes, read the current login attribution module and
`optimo_analytics/docs/LoginCTA_AttributionTestingGuide.md`. Update session
fields, login/logout declarations, and `include_from_session` together.
A session field alone does not prove it reaches the emitted event.

## Prove The Change

Choose cases from the non-regression contract for the affected domain. At
minimum, test the actual caller and business result through the real producer
and schema to the mocked external SDK boundary. Execute captured commit
callbacks and assert the exact identity/properties, not just “called once”.
Include relevant rejection, rollback, retry/idempotency, and transport-failure
cases. Preserve architecture checks. Use `mocker`; do not mock the helper or
transition under test. Pure schema checks need no database unless the tested
application invariant requires it.

Run repository-owned lint/format, type gate (`ty` → `pyright` → `mypy`, with
configured `ty` mandatory), focused caller/contract tests, and required wider
validation. Detect wrappers/configuration rather than copying an old Django
configuration name or assuming all tests live under `optimo_analytics/tests/`.

Update the operating guide when authority, coverage, properties, or rollout
requirements change. Report exactly what was tested and what still needs
operator approval, staging receipts, identity inspection, or dashboard work.
Never send production test events or enable a project as an implementation
shortcut. `--dry-run` stops at the proposed changes and verification plan.
