# Style & Micro-Guidelines

Pay particular attention to these when commenting on code.

## Multi-Tenancy, Time Dimensions & Data Integrity

- Queries and serializers must respect tenant boundaries (company/org).
- Year/quarter must be aligned across related rows; misalignment is a correctness bug.
- Handle N/A / sentinel values explicitly; never let them silently miscompute.

## APIs, Contracts & External Integrations

- Preserve existing defaults, ranges, and response shapes unless intentional change.
- Use consistent status codes and error envelopes across endpoints.
- Treat external systems (Slack, Salesforce, survey providers) as unreliable:
  guard against timeouts, malformed responses, per-row external calls in loops.

## Python/Django Idioms

- Prefer truthiness checks over `len(...) != 0`.
- Use `exists()` when checking if a queryset has rows.
- Avoid repeated `.count()` or `.get()` inside loops.
- Prefer Django reverse relations over importing models solely to traverse relationships.

## Strings & F-Strings

- Use f-strings for interpolated strings; don't use them for constants.
- Prefer `", ".join(items)` over dumping list representations in logs.
- Keep log messages human-readable and informative.

## Docstrings & Formatting

- Non-trivial public functions need imperative, punctuated docstrings.
- Newline at end of file, PEP8 spacing.
- No `print()` debugging or large commented-out blocks.
- Delete obsolete code rather than commenting it out.

## Imports

- Keep imports at module top. Do not use local imports to work around circular deps.
- Propose refactors to break circular deps (separate modules, typing modules).
- Group: stdlib → third-party → local. No unused imports.

## Dynamic Attributes

- Prefer direct attribute access over `getattr()`/`hasattr()` for normal interfaces.
- Use `getattr()`/`hasattr()` only for genuinely generic/optional attributes.

## Security & Privacy

- Least-privilege in serializers, views, exports.
- Centralize permission checks via helpers/mixins, not ad-hoc `if user.is_superuser`.
- Never log secrets or PII; use stable identifiers or redacted values.

## Exceptions & Logging

- Specific exceptions over bare `except Exception`.
- Small `try` blocks; avoid large catch-all regions.
- Don't swallow exceptions silently; log or re-raise with context.
- In `optimo_*` apps, use structured logging helpers over ad-hoc string logging.

## Time & Decimals

- `timezone.now()` over `datetime.now()` in Django code.
- `DecimalField` and `Decimal("...")` for scores, percentages, money. Avoid `float`.
- Guard N/A / sentinel values before numeric operations.

## Types & Type Hints

- Precise annotations over `Any` wherever possible.
- Avoid string-based type hints; arrange imports so real types work.
- Use `TypedDict`, dataclasses, or typed value objects over `dict[str, Any]`.
- If flexibility is needed, explain why in a comment.

## Tests

- New/changed behavior must be covered, especially multi-tenant scoping and edge cases.
- Realistic fixtures/factories over toy objects.
- Centralize repeated fixtures.
- Call out missing regression tests explicitly for bugfixes.

## Tooling

- Aim for ruff-clean code. Don't introduce new lint violations.
- Use `ast-grep` via Bash when helpful to find patterns (string type hints,
  broad try/except, repeated getattr).
