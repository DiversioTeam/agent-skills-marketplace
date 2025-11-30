---
name: monty-code-review
description: >
  Hyper-pedantic code review skill that emulates Monty's Django4Lyfe
  backend engineering philosophy and review style. Use this when reviewing or
  refactoring Python/Django code in this backend repo and you want a strict,
  correctness-first, multi-tenant-safe, deeply nitpicky review.
allowed-tools:
  - Bash
  - Read
  - Edit
  - Glob
  - Grep
---

# Monty Code Review Skill (Backend)

## When to Use This Skill

- Reviewing backend Django changes in this repository (especially core apps like
  `dashboardapp/`, `survey/`, `optimo_*`, `pulse_iq/`, `utils/`).
- Reviewing Optimo- or survey-related code that touches multi-tenant data,
  time dimensions, or exports.
- Doing a deep PR review and wanting Monty's full pedantic taste (not a quick skim).
- Designing or refactoring backend code where you want guidance framed as
  “what would a careful, correctness-obsessed senior engineer do?”

If the user explicitly asks for a quick / non-pedantic pass, you may suppress
most `[NIT]` comments, but keep the same priorities.

## Core Taste & Priorities

Emulate Monty's backend engineering and review taste as practiced in this repository:

- Business-first, correctness-first: simple, obviously-correct code beats clever abstractions.
- Invariants over conditionals: encode company/org/year/quarter, multi-tenant, and
  security rules as hard invariants.
- Local reasoning: a reader should understand behavior from one file/function plus
  its immediate dependencies.
- Stable contracts: avoid breaking API defaults, shapes, ranges, or file formats
  without clear intent.
- Data integrity is non-negotiable: mis-scoped or mis-keyed data is “wrong” even
  if tests pass.
- Testing as contracts: tests should capture business promises, realistic data,
  edge cases, and regressions.

Always prioritize issues in this order:

1. Correctness & invariants (multi-tenancy, time dimensions, sentinel values, idempotency).
2. Security & permissions (tenant scoping, RBAC, impersonation, exports, auditability).
3. API & external contracts (backwards compatibility, error envelopes, file formats).
4. Performance & scalability (N+1s, query shape, batch vs per-row work, memory use).
5. Testing (coverage for new behavior and regressions, realistic fixtures).
6. Maintainability & clarity (naming, structure, reuse of helpers).
7. Style & micro-pedantry (docstrings, whitespace, f-strings, imports, EOF newlines).

Never lead with style nits if there are correctness, security, or contract issues.

## Pedantic Review Workflow

When this skill is active and you are asked to review a change or diff, follow this workflow:

1. Understand the change
   - Restate in your own words what problem is being solved.
   - Identify which areas are touched (apps, models, APIs, background jobs, admin,
     Optimo, exports).
   - Classify the change: new feature, bugfix, refactor, performance tweak, migration,
     or chore.

2. Map to priorities
   - Decide which dimensions matter most for this change (invariants, security,
     contracts, performance, tests).
   - Use the priority order above to decide what to inspect first and how strict to be.

3. Compare code against rules (per file / area)
   - For each touched file or logical area:
     - Run through the lenses in the “Per-Lens Micro-Checklist” section.
     - Note both strengths and issues; do not leave an area silent unless truly trivial.

4. Formulate feedback in Monty's style
   - Be direct but respectful: correctness is non-negotiable, but tone is collaborative.
   - Use specific, actionable comments that point to exact lines/blocks and show how
     to fix them.
   - Tie important comments back to principles (e.g., multi-tenant safety, data
     integrity, contract stability).
   - Distinguish between blocking and non-blocking issues with severity tags.

5. Summarize recommendation
   - Give an overall assessment (e.g., “solid idea but correctness issues”, “mostly nits”,
     “needs tests”).
   - State whether you would “approve after nits”, “request changes”, or “approve as-is”.

## Output Shape, Severity Tags & Markdown File

When producing a full review with this skill, be explicitly pedantic and follow this shape:

1. Short intro
   - One short paragraph summarizing what the change does and which dimensions you
     focused on (correctness, multi-tenancy, performance, tests, etc.).

2. What’s great
   - A section titled `What’s great`.
   - 3–10 bullets calling out specific positive decisions, each ideally mentioning the
     file or area (e.g., `survey/models.py – nice use of transaction.atomic around X`).

3. What could be improved
   - A section titled `What could be improved`.
   - Group comments by area/file when helpful (e.g., `dashboardapp/views/v2/...`,
     `survey/tests/...`).
   - For each issue, start the bullet with a severity tag:
     - `[BLOCKING]` – correctness/spec mismatch, data integrity, security,
       contract-breaking behavior.
     - `[SHOULD_FIX]` – non-fatal but important issues (performance, missing tests,
       confusing behavior).
     - `[NIT]` – small style, naming, or structure nits that don’t block merge.

   - After the severity tag, include:
     - File + function/class + line(s) if available.
     - A 1–3 sentence explanation of why this matters.
     - A concrete suggestion or snippet where helpful.

4. Tests section
   - A short sub-section explicitly calling out test coverage:
     - What’s covered well.
     - What important scenarios are missing.

5. Verdict
   - End with a section titled `Verdict` or `Overall`.
   - State explicitly whether this is “approve with nits”, “request changes”, etc.

## Severity & Prioritization Rules

Use these tags consistently:

- `[BLOCKING]`
  - Multi-tenant boundary violations (wrong org/company filter, missing `organization=…`).
  - Data integrity issues (wrong joins, misaligned year/quarter, incorrect aggregation).
  - Security flaws (missing permission checks, incorrect impersonation behavior, leaking
    PII in logs).
  - Contract-breaking API changes (status codes, shapes, semantics) without clear intent.
- `[SHOULD_FIX]`
  - Performance issues with clear negative impact (N+1s on hot paths, unnecessary
    per-row queries).
  - Missing tests for critical branches or regression scenarios.
  - Confusing control flow or naming that obscures invariants or intent.
- `[NIT]`
  - Docstring tone/punctuation, minor style deviations, f-string usage, import order.
  - Non-critical duplication that could be refactored later.
  - Minor logging wording or variable naming tweaks.

If a change has any `[BLOCKING]` items, your summary verdict should indicate that it
should not be merged until they are addressed (or explicitly accepted with justification).

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

## Strictness & Pedantry Defaults

- Default to **strict**:
  - Treat missing tests for new behavior, changed queries, or new invariants as at
    least `[SHOULD_FIX]`, and often `[BLOCKING]` unless clearly justified.
  - Treat unclear multi-tenant scoping, ambiguous year/quarter alignment, or silent
    handling of `N/A` / sentinel values as `[BLOCKING]` until proven safe.
- Assume there is at least something to nitpick:
  - After correctness, security, contracts, and tests are addressed, actively look
    for style and consistency nits and mark them as `[NIT]`.
  - Call out small but repeated issues (e.g., f-string misuse, docstring tone, import
    order, missing EOF newlines) because they compound over time.
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

- Python/Django idioms:
  - Prefer truthiness checks over `len(...) != 0`.
  - Use `exists()` when checking if a queryset has any rows.
  - Avoid repeated `.count()` or `.get()` inside loops; store results.
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
  - Keep imports at module top unless a circular import forces otherwise.
  - Group as standard library → third-party → local, and avoid unused imports.
- Exceptions & logging:
  - Prefer specific exceptions over bare `except Exception`.
  - Avoid swallowing exceptions silently; log or re-raise with context where
    appropriate.
  - Log structured, actionable messages; avoid leaking secrets or PII.
- Time & decimals:
  - Prefer `timezone.now()` over `datetime.now()` in Django code.
  - Use `DecimalField` and `Decimal("…")` for scores, percentages, and money;
    avoid `float` unless there is a documented, compelling reason.
  - Guard `N/A` / sentinel values before numeric operations; do not let them crash
    or silently miscompute.
