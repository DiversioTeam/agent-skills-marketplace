# Optimo Mixpanel Non-Regression Contract

Source: [current operating guide](https://github.com/DiversioTeam/Django4Lyfe/blob/dev/docs/analytics/optimo-mixpanel/README.md).
Rationale: [backend #3203](https://github.com/DiversioTeam/Django4Lyfe/pull/3203)
and [frontend #579](https://github.com/DiversioTeam/Optimo-Frontend/pull/579).
This is a review checklist, not a second runtime schema or rollout ledger.
Re-read the live guide and affected code for exact APIs and environment status.

## Identity And Tenant Boundaries

- `$user_id` is always `OptimoUser.uuid`; an account-only user needs no invented
  employee. Employee-first backend history uses `OptimoEmployee.uuid` as
  `$device_id` with no permanent user until the persisted link exists.
- The first real linked backend outcome sends both IDs after validating the
  canonical relationship and tenant in both directions. A database link alone
  does not invent an event. In-memory Slack/Teams authorization mappings are
  not evidence for a permanent identity merge.
- Backend `MixpanelEventIdentity` owns reserved fields. The SDK `distinct_id`
  argument is empty when reserved person IDs exist; explicit organization
  automation uses `org_<organization_uuid>`. No raw person-ID fallback ladder,
  backend `identify()`, or `alias()`.
- Browser SDK anonymous keys stay independent. Frontend auth middleware calls
  `identify(user.uuid)`; it never copies an employee UUID into browser identity.
- Reset before switching effective users, including entering/leaving
  impersonation. Check persisted SDK `$user_id` as well as in-memory state.
  If reset fails, do not identify the next user or continue tracking.
- Logout clears credentials, analytics identity, and user-scoped state even
  when the server logout request fails. Token refresh preserves `session_id`;
  a real new login or effective-user change starts a new session.
- Never reassign an already-merged employee/user pair without an explicit
  analytics data-repair plan. A bad permanent merge is not fixed by a filter.

## Authority, Actors, And Impersonation

- Backend owns authentication and durable business outcomes; frontend owns
  authenticated browser interactions. No duplicate frontend session-start,
  survey-completion, or recommendation-completion receipts.
- `actor_user_id`, `actor_employee_id`, `subject_employee_id`, and
  `manager_employee_id` are distinct. A subject's account link does not prove
  authentication. Public employee receipts can merge identity while leaving
  `actor_user_id` and role empty.
- System events may have a subject but never invent a human actor or role.
  Integration user actions declare `interaction_channel`; without a real
  token-backed Optimo session, `session_id` is null, not fabricated.
- Preserve the exact trusted `impersonation` boolean on every event. The target
  remains the flagged event's person, not the support actor. Unknown actor IDs
  stay empty. Skip impersonated profile updates, not the event itself.
- Schedule creation requires server-owned `originated_from_impersonation` as
  a separate argument and persists it in the schedule field. Strip same-named
  client JSON. Downstream system receipts inherit this origin; a later real
  manager action uses that manager's current authenticated context.

## Producers, Schemas, And Delivery

- Feature code calls named domain producers. Only the allowed producers reach
  the private backend delivery primitive; preserve the architecture test.
  Import the explicit domain module, not a dependency-heavy package root.
- Producers reload persisted objects, derive tenant/identity/subject/join keys,
  and reject contradictory state. Do not add overloads taking those derived
  columns as caller arguments. Queue payloads are locators, not event payloads.
- Registry entries bind one strict schema, origin, and person scope. Shared
  fields are injected after schema validation, not overridden by caller JSON.
  Reject conflicting tenant/subject IDs or scope before outbound delivery.
- All receipts release after transaction commit; rollback releases none.
  Without an active transaction, delivery can occur immediately. Failure in
  analytics must never roll back the valid product transition.
- Frontend exact runtime schemas also derive property types. Feature code uses
  named producers in `trackEvents.ts`, never low-level service imports, SDK
  options, identity controls, or caller-selected deduplication settings.
- Missing context follows the actual nullable schema contract. Do not blindly
  replace missing UUIDs with empty strings or duplicate shared schema fields.

## Privacy And Time

- No public tokens, token hashes, secrets, personal names/emails/phones,
  comments, free-form provider/exception text, or raw dynamic URLs. Use bounded
  failure categories and registered private route templates. Public/auth and
  unknown routes emit no frontend page-view events.
- Keep `organization_name` only where approved, never in logs. Validation
  failures log safe event/failure classifications, not rejected payload values.
- Backend uses `ip=0`; frontend disables IP enrichment and respects Do Not
  Track. Do not replace impersonation collection with blanket opt-out.
- Use canonical UUID strings for IDs, bounded enums for closed values, stable
  machine-format recommendation codes, and bounded risk levels—not exact scores.
- One canonical millisecond `time` represents the named outcome. Do not restore
  `is_cron_job`, `cron_execution_timestamp`, parallel cron schemas, or redundant
  delivered/completed timestamps. A background worker is not automatically CRON.

## Domain Regressions To Test When Touched

| Area | Required evidence |
|---|---|
| Survey delivery and steps | Reload assignment/schedule; derive tenant, employee, survey, delivery channel, join keys, question membership/order, percentage, and elapsed values. Reject missing schedule/channel mismatch. No unsupported `question_type` field. |
| Completion | Reload the saved response and verify redundant assignment/employee/tenant/survey links. Derive response UUID, duration, and completion time. |
| Cross-channel funnel | Separate `delivery_channel` from `response_channel`; join on assignment UUID, never token/hash. Do not interpret missing channel coverage as zero. |
| Started | Slack/Teams use a single-winner not-started → in-progress transition. Double-clicks, reminders, and retries resume without duplicate receipts. |
| Abandonment | Hourly sweep and lazy expired-link paths compete for one locked open → expired transition. Only one emits; terminal assignments stay unchanged. Sweep uses `response_channel=unknown`, expiry time, and a bounded per-run cap. Database expiry still works with analytics disabled. |
| Risk | Queue only the response UUID; reload latest persisted answers. Legacy enqueue-time timestamps must not reject legitimate answer edits; wrong employee/survey relationships still fail. Emit actual worker outcome time and bounded levels/categories. |
| HRIS | Reload saved job and minimized initiating-user context; verify tenant and terminal state. Use measured duration and actual outcome time, not initiating-request time. |
| Recommendations | Keep code, definition UUID, plan UUID, manager, and subject separate. Backend owns completed/dismissed outcomes with explicit channel; only web has a real session. Auto-resolve/expire emit once under concurrent retries. |
| SMS duration | Start time is interactive-session creation, not finalization; completion duration must not collapse to zero. |
| Reminders | Numbering starts at one, including direct-send fallback before its sent-mail row is logged. |
| CTA auth | Session schema, login/logout schema declarations, and `include_from_session` agree, including `magic_link_action` and platform attribution. Test attributed and plain auth paths. |
| Browser lifecycle | No session-ended/tab-closed/tab-reopened KPIs. Early video exit requires started playback and explicit in-app dismissal, not unload/pagehide/sendBeacon. |

## Tests And Rollout

- Use `mocker` for new/changed backend analytics tests, not new `monkeypatch` or
  `unittest.mock.patch`. Exercise real models, callers, producers, schemas, and
  transitions; mock only outbound SDK/provider/queue/navigation boundaries.
- Execute captured Django commit callbacks for caller assertions. Assert both
  business outcome and exact emitted contract, absence on rollback, and safe
  behavior on delivery failure. Never hide assertions behind `if mock.called`.
- Keep pure schema/registry tests free of unnecessary database setup. Preserve
  backend producer and frontend restricted-import architecture checks.
- Confirm Simplified ID Merge in the actual target project before setting
  `OPTIMO_MIXPANEL_IDENTITY_CONTRACT=simplified_v1` or
  `VITE_MIXPANEL_IDENTITY_CONTRACT=simplified_v1`. These acknowledgements do not
  change the remote project mode. A populated Legacy/Original project needs a
  new empty Simplified project, not an assumed in-place conversion.
- For identity changes, authorized staging proof covers employee-before-account,
  linked user, account-only user, two independent browsers joining the same
  user, effective-user reset, automation, impersonation, and absent public data.
- Production is read-only during validation. Recheck regional enablement and
  record cutover boundaries; never freeze CA/EU/frontend rollout claims here.
- Dashboard readiness additionally requires observed events, Lexicon ownership,
  privacy/freshness definitions, verified charts, and `impersonation=false`
  in normal reports. Code deployed is not proof of telemetry enabled.
