## Per-Lens Micro-Checklist

When scanning a file or function, run through these lenses:

1. API surface & naming
   - Do function/method names accurately reflect behavior and scope (especially
     around org/company/year/quarter)?
   - Are parameters and returns typed and documented where non-trivial?
   - Are names specific enough (avoid generic `data`, `obj`, `item` without context)?
   - Are docstrings present for public / non-trivial functions, describing contracts
     and edge cases?

2. Structure & responsibilities
   - Does each function/class do one coherent thing?
   - Are I/O, business logic, formatting, and error handling separated where practical?
   - Are large “kitchen-sink” functions candidates for refactoring into helpers?

3. Correctness & edge cases
   - Do implementations match requirements and comments for all cases?
   - Are edge cases handled (empty inputs, `None`, boundary values, large values)?
   - Are assumptions about external calls (DB, HTTP, queues) explicit and defended?

4. Types & data structures
   - Are types precise (e.g., dataclasses or typed dicts instead of bare tuples)?
   - Are invariants about structure (sorted order, uniqueness, non-empty) documented
     and maintained?
   - Are multi-tenant and time-dimension fields always present and correctly scoped?

5. Control flow & ordering
   - Is control flow readable (limited nesting, sensible early returns)?
   - Are sorting and selection rules deterministic, including ties?
   - Are error paths and “no work” paths clear and symmetric with happy paths
     where appropriate?

6. Performance & resource use
   - Any obvious N+1 database patterns or repeated queries in loops?
   - Any large intermediate structures or per-row external calls that should be batched?
   - Is this code on or near a hot path? If so, is the algorithmic shape sensible?

7. Consistency with codebase / framework
   - Does the code follow existing patterns, helpers, and abstractions instead of
     reinventing?
   - Is it consistent with Django/DRF/Optimo conventions already in this repo?
   - Are shared concerns (logging, permissions, serialization) going through central
     mechanisms?

8. Tests & validation
   - Are there tests covering new behavior, edge cases, and regression paths?
   - Do tests use factories/fixtures rather than hand-rolled graphs where possible?
   - Do tests reflect multi-tenant and time-dimension scenarios where relevant?
   - **Exception:** Django migration files (`*/migrations/*.py`) do not require tests;
     focus test coverage on the models and business logic they represent instead.

9. Harness & legibility
   - Are important repo rules discoverable from `AGENTS.md` and linked docs?
   - If this code depends on subtle invariants, is there an obvious in-repo
     place where that knowledge is documented?
   - Do repeated failure patterns suggest a missing wrapper, lint, CI check, or
     repo-docs update?

10. Migrations & schema changes
   - Does the PR include Django model or migration changes? If so:
     - Avoid destructive changes (dropping fields/tables) in the same deploy where
       running code still expects those fields; prefer a two-step rollout:
       first remove usage in code, then drop the field/table in a follow-up PR once
       no code depends on it.
     - For large tables, avoid adding non-nullable columns with defaults in a single
       migration that will rewrite or lock the whole table; instead:
       - Add the column nullable with no default.
       - Backfill values in controlled batches (often via non-atomic migrations or
         background jobs).
       - Only then, if needed, add a default for new rows.
     - Treat volatile defaults (e.g. UUIDs, timestamps) similarly: add nullable
       column first, backfill in batches, and then set defaults for new rows only.
     - When a single feature has many iterative migrations in one PR, expect the
       author to **regenerate a minimal, final migration set and re-apply it**
       before merge, without touching migrations that are already on production
       branches. Conceptually this means:
       - Identify which migrations were introduced by this PR vs. which already
         exist on the main branch.
       - Migrate back to the last migration **before** the first PR-specific one.
       - Delete only the PR-specific migration files.
       - Regenerate migrations to represent the final schema state.
       - Apply the regenerated migrations locally and ensure tests still pass.

## Strictness & Pedantry Defaults

- Default to **strict**:
  - Treat missing tests for new behavior, changed queries, or new invariants as at
    least `[SHOULD_FIX]`, and often `[BLOCKING]` unless clearly justified.
  - Treat unclear multi-tenant scoping, ambiguous year/quarter alignment, or silent
    handling of `N/A` / sentinel values as `[BLOCKING]` until proven safe.
  - Treat the micro-guidelines in this skill (docstrings, EOF newlines, spacing,
    f-strings, `Decimal` and `timezone.now()`, `transaction.atomic()` usage, etc.)
    as real expectations, not optional suggestions.
- Do not assume every change needs a nit. Report style findings when they
  violate repository policy or expose a repeated maintenance problem; a clean
  review is valid without invented findings.
- Be explicit about “no issues”:
  - When a high-priority dimension truly has no concerns (e.g., tests are excellent),
    say so explicitly in the relevant section.
- If the user explicitly asks for a non-pedantic / quick pass, you may:
  - Keep the same priorities, but omit most `[NIT]` items and focus on
    `[BLOCKING]` / `[SHOULD_FIX]`.
  - State that you are intentionally suppressing most pedantic nits due to the
    requested lighter review.

## Style & Micro-Guidelines to Emphasize

When commenting on code, pay particular attention to:

- Multi-tenancy, time dimensions & data integrity:
  - Always ensure queries and serializers respect tenant boundaries (company/org) and
    do not accidentally cross tenants.
  - Check that year/quarter (and similar keys) are aligned across all related rows
    used together; misalignment is a correctness bug, not just a nit.
  - Handle `N/A` / sentinel values explicitly in calculations and exports; never let
    them silently miscompute or crash.
- APIs, contracts & external integrations:
  - Preserve existing defaults, ranges, and response shapes unless there is a clear,
    intentional contract change.
  - Use consistent status codes and error envelopes across endpoints; avoid one-off
    response formats.
  - Treat external systems (Slack, Salesforce, survey providers, etc.) as unreliable:
    guard against timeouts, malformed responses, and per-row external calls in loops.
- Python/Django idioms:
  - Prefer truthiness checks over `len(...) != 0`.
  - Use `exists()` when checking if a queryset has any rows.
  - Avoid repeated `.count()` or `.get()` inside loops; store results.
  - Prefer using Django reverse relations (e.g., `related_name`, `foo_set`) over
    importing related models solely to traverse relationships.
- Strings & f-strings:
  - Use f-strings for interpolated strings; don’t use f-strings for constants.
  - Prefer `", ".join(items)` over dumping list representations in logs.
  - Keep log messages and errors human-readable and informative.
- Docstrings & formatting:
  - Non-trivial public functions/classes should have imperative, punctuated docstrings
    that explain behavior and important edge cases.
  - Ensure newline at end of file and PEP8-adjacent spacing (around operators,
    after commas).
  - No `print()` debugging or large commented-out blocks in committed code.
  - Avoid commented-out code; if behavior is obsolete, delete it rather than
    commenting it.
- Imports:
  - Keep imports at module top; do not introduce local (function-level) imports as a
    workaround for circular dependencies.
  - When you encounter or suspect circular imports, propose refactors that tease apart
    shared concerns into separate modules or move types into dedicated typing modules,
    rather than using local imports.
  - Group as standard library → third-party → local, and avoid unused imports.
- Dynamic attributes & introspection:
  - Prefer direct attribute access over `getattr()`/`hasattr()` when the attribute is
    part of the normal object interface.
  - Use `getattr()`/`hasattr()` only when truly needed (for generic code or optional
    attributes), and avoid “just in case” usage that hides real bugs.
- Security & privacy:
  - Apply least-privilege principles in serializers, views, and exports; only expose
    fields that are actually needed.
  - Centralize permission checks and audit logging via existing helpers/mixins instead
    of ad-hoc `if user.is_superuser` checks.
  - Avoid logging secrets or sensitive PII; log stable identifiers or redacted values
    instead.
- Exceptions & logging:
  - Prefer specific exceptions over bare `except Exception`.
  - Keep `try` blocks as small as possible; avoid large, catch-all regions that make it
    hard to see what can actually fail.
  - Avoid swallowing exceptions silently; log or re-raise with context where
    appropriate.
  - Log structured, actionable messages; avoid leaking secrets or PII.
  - In `optimo_*` apps, prefer structured logging helpers and typed payloads over
    ad-hoc string logging; avoid hard-coded magic strings and numbers in log records.
- Time & decimals:
  - Prefer `timezone.now()` over `datetime.now()` in Django code.
  - Use `DecimalField` and `Decimal("…")` for scores, percentages, and money;
    avoid `float` unless there is a documented, compelling reason.
  - Guard `N/A` / sentinel values before numeric operations; do not let them crash
    or silently miscompute.
- Types & type hints:
  - Be pedantic about type hints: prefer precise, informative annotations over `Any`
    wherever possible.
  - Avoid string-based type hints (e.g., `"OptimoRiskQuestionBank"`); arrange imports
    and module structure so real types can be referenced directly.
  - Use `TypedDict`, dataclasses, or well-typed value objects instead of `dict[str, Any]`
    or dictionaries used with many different shapes.
  - When a type truly must be more flexible, explain why in a short comment rather
    than silently falling back to `Any`.
- Tests:
  - Expect new or changed behavior to be covered by tests, especially around
    multi-tenant scoping, time dimensions, and edge cases like `N/A` / zero /
    maximum values.
  - Prefer realistic fixtures/factories over toy one-off objects; tests should
    resemble production scenarios where practical.
  - Avoid repeating essentially identical fixtures across test modules; instead,
    centralize them in shared fixtures or factories.
  - Call out missing regression tests explicitly when reviewing bugfixes.
- Tooling & search:
  - Aim for "ruff-clean" code by default; do not introduce new lint violations, and
    remove existing ones when practical.
  - When helpful and available, use tools like `ast-grep` (via the `Bash` tool) to
    search for problematic patterns such as string-based type hints, overly broad
    `try`/`except` blocks, or repeated `getattr()` usage.
