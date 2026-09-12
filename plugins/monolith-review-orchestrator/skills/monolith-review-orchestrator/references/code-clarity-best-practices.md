# Code Clarity Best Practices

Use this guide when you are changing code shape, naming, comments, helper
structure, or small refactors.

## Main Goal

Write code that another engineer can scan quickly without tracing half the
file.

## How to Use This Guide

Use these priority levels during review:

- **Must**: correctness, security, tenant scope, data integrity, hidden side
  effects, and real performance regressions
- **Should**: naming, helper extraction, comments, enums/constants placement,
  and test setup quality
- **Consider**: local cleanup that improves readability without widening the
  scope of the change

A smell is a prompt to inspect, not proof that the code must change.
Refactor when it improves the current change, reduces real risk, or prevents
likely near-term churn.

## Common Code Smells

Use this list as a review checklist, not as an automatic rewrite order.

- **Duplicated logic**
  - The same validation, calculation, branching, error handling, or
    near-copy-pasted code shows up in more than one place.

- **Function does too much**
  - One function fetches, validates, transforms, authorizes, saves, logs, and
    formats output in one flow.
  - It has more than one real reason to change.

- **Class or module does too much**
  - One file becomes the dumping ground for unrelated helpers, unrelated state,
    or changes from many different features.

- **Bad or misleading names**
  - You must read the implementation to know what a variable, function, or
    module actually means.
  - Vague names like `data`, `result`, `helper`, or `manager` are warning
    signs.

- **Too many parameters**
  - A function needs a long argument list, or the same few values are
    repeatedly passed together as a clump.

- **Primitive obsession**
  - Raw strings, numbers, booleans, or loose dicts carry business rules that
    should live in a clearer domain type, enum, value object, or typed payload.

- **Deep nesting and complex conditionals**
  - The normal path is hard to see because logic is buried under nested `if`
    blocks, flags, or switch-style branches.

- **Shotgun surgery**
  - One small business change forces edits across many unrelated files.

- **High coupling or feature envy**
  - Code reaches too deeply into another object or module through long chains,
    getters, or private details.

- **Hidden side effects**
  - A function sounds like a read or calculation, but it writes to the
    database, mutates input, sends notifications, logs important state, or
    changes external systems.

- **Dead, speculative, or explanatory code**
  - Code exists "just in case," old paths remain unused, or comments are doing
    the job the code structure should be doing.

## General Rules

### Naming

- Use full, searchable names.
- Do not use shorthand, acronyms, or single-letter names unless it is a
  standard loop counter like `i`.
- Name each value after what it contains at that point.
- If a value changes meaning across steps, assign a new variable.
- Name functions after the job they do, not after the layer they live in.

Examples:

```python
# Bad
handle_employee_data(...)

# Better
filter_visible_employees_by_manager(...)
validate_employee_visibility(...)
```

### Control flow and size

- Use one obvious control flow.
- Prefer guard clauses, early returns, and shallow nesting.
- If order matters, make the order explicit in variable names, helper names,
  and comments.
- Split a long flow into a few named steps only when the split makes the top
  level easier to read.
- Prefer functions and classes small enough to scan in one 4k editor screen.
- Split only when it removes real reading burden and does not change behavior.
- Do not extract helpers just because a function is long; extract only when the
  new helper has a clear single job and makes the caller easier to read.

### Comments

- Write comments only to explain a local rule, ordering constraint, or
  guardrail.
- Write comments and docstrings as the code works today.
- Do not write historical notes when a current-state explanation is enough.
- Explain things as if the reader is new to this part of the codebase but
  already understands the product goal.
- Do not use generic labels like `Phase 1/2/3`.
- Do not narrate what the code already says plainly.
- If a branch is hard to follow, explain why that branch exists.

### Make invalid states hard to represent

- Prefer shapes that make invalid states hard to represent.
- Do not pass around partially valid data longer than necessary.
- Validate at boundaries, then use typed internal shapes after validation.

## Python Rules

### Prefer precise function verbs

Common useful verbs:

- `validate_*` for checks that may raise or return an error
- `get_*` / `load_*` for fetching data or a full set
- `filter_*_by_*` for narrowing an input set or queryset
- `add_*` / `remove_*` for one modifier step
- `classify_*` for bucketing
- `build_*` for final output objects

Avoid vague verbs like:

- `handle`
- `process`
- `manage`
- `resolve`
- `apply`
- `keep`

Use them only when a more exact verb would be dishonest.

### Constants, enums, and shared vocabulary

- For closed, reused domain values, use `StrEnum` instead of repeating string
  literals or relying on `Literal` alone.
- If you already have a `StrEnum`, use the enum members directly in code.
  Do not add parallel literal aliases unless a compatibility layer truly needs
  them.
- Use `Literal` when you only need typing and do not need a shared runtime
  symbol.
- Put shared constants in a low-level constants module.
- Do not make types or constants modules depend on service modules for simple
  literals.
- If the same literal appears across apps or services, stop and look for a
  shared home before copying it again.

Example:

```python
# Bad
employee.status == "active"

# Better
employee.status == EmployeeStatus.ACTIVE
```

### Data shapes and typing

- Prefer explicit typed shapes over loose dictionaries.
- Use `TypedDict` when a dictionary is a real structured payload.
- Avoid `Any` unless there is no better honest type.
- Prefer narrowing over `cast()`.
- Treat `typing.cast()` as a smell. Use it only when a real type-checker
  limitation leaves no better option, and explain why.
- Avoid string-based type hints unless a real forward-reference or import-cycle
  case requires them.
- Be pedantic about type hints and keep the full information where possible.
- If a value can be one of a few closed states, use an enum or a literal type
  plus a named constant.

### Imports and dependencies

- Use top-level imports.
- Do not hide imports inside functions unless there is a real circular import
  that you cannot remove another way.
- Before adding a local import, check whether the dependency direction is the
  real problem.
- Prefer reverse relations in Django ORM queries when they avoid unnecessary
  model imports.

### Error handling

- Keep `try` / `except` blocks narrow.
- Catch only the errors you actually expect.
- Use precise error messages that expose hidden assumptions.
- Do not use broad exception handling as control flow.
- Do not use large `try` / `except` blocks when a smaller guarded block will do.
- Do not add speculative defensive `try` / `except` blocks for rare database,
  network, or infrastructure failures unless the caller has a clear fallback the
  product actually wants.
- `DatabaseError` and `OperationalError` are not special just because they come
  from Django or the database layer. Treat them like any other speculative
  failure unless there is real incident history, a product requirement, or a
  clearly wanted degraded mode.
- A pointless fallback path usually makes the code worse and hides the real
  failure mode.
- If you intentionally handle an exception without raising it, add a local
  comment explaining why that is safe and what behavior is being preserved.

## Django Rules

### General Django shape

- Be explicit and avoid magic. If a reader has to guess where behavior came
  from, the code is too implicit.
- Keep one concept in one place. Do not repeat the same rule across models,
  services, serializers, and tests when one source of truth will do.
- Prefer standard Django shapes before custom ones.
- Put query logic in querysets/managers, request parsing at the boundary, and
  hard invariants in database constraints when possible.
- In Django views, name the first argument `request`.
- In Django models, use lowercase field names with underscores and keep `Meta`
  after field definitions.

### ORM and performance

- Use timezone-aware datetimes. Prefer `timezone.now()` when you need the
  current time.
- Do not validate at read time. Validate at the write boundary, request
  boundary, or model/database boundary.
- Keep `transaction.atomic()` blocks narrow.
- Add deterministic ordering before slicing, pagination, or `latest`-style
  reads.
- Profile first, then optimize.
- Know when querysets evaluate and when ORM attributes are cached.
- Be intentional with `select_related()` and `prefetch_related()` to avoid N+1
  queries.
- When queryset performance matters, add query-count tests so future changes do
  not silently add extra queries.
- Avoid `only()` and `defer()` unless measurement proves they help and you are
  sure deferred fields will not cause follow-up queries.
- If you will need queryset rows later, do not issue separate `.exists()`,
  `.count()`, or similar checks first unless they really save work.
- If you only need a foreign key id, use the foreign key id directly instead of
  loading the related object.
- Prefer `object.related_id` over `object.related.id` when you only need the
  id. Type checkers may be less helpful here, but the direct `*_id` field avoids
  an unnecessary related-object load and is the better default for performance.
- Do not order results if you do not care about the order.

## Optimo-Specific Rules

### Logging

- In `optimo_` apps, use structured logging.
- Prefer named fields over string-built log messages with mixed data inside.
- Do not hide important decision inputs in prose when they can be separate
  structured fields.
- Do not hardcode strings or numbers inside logs when they should be structured
  fields or typed values.
- `logger.warning()` is log-only. It does not notify engineers in Sentry.
- If a problem needs engineer attention, use `logger.error()` or
  `logger.exception()`.
- If you use `logger.warning()` for an unusual condition, add a local comment
  explaining why log-only handling is intentional.

### Readability cleanups

- Keep readability changes behavior-preserving.
- Do not smuggle refactors into a cleanup pass.
- If you move long-form package notes out of code into a `README.md`, keep the
  module docstring short and add a note telling future editors to update the
  README when policy or package structure changes.

## Tests and Fixtures

- Do not repeat fixtures when an existing fixture already expresses the setup.
- If several tests need the same setup, prefer one clear fixture or one small
  helper over copy-pasted setup blocks.
- Repeated `Model.objects.create(...)` setup in pytest tests is a smell. Prefer
  fixtures or small factory helpers so model-shape changes do not force wide
  test edits.
- Do not create unwanted objects in tests. Keep setup minimal so each test stays
  fast.
- Aim for individual tests to stay under 500ms unless the behavior truly needs
  slower integration coverage.
- Use `@pytest.mark.django_db` as narrowly as possible. Prefer test-level or
  class-level markers over lazy module-level markers unless the whole module
  truly needs database access.
- When behavior depends on aware datetimes, freeze time in the test to reduce
  flakiness and make the fixed clock obvious to the reader.
- Prefer `@freeze_time(...)` on the test itself when that makes the frozen clock
  visible at a glance.
- Assert business behavior, not implementation trivia.

## Tooling and Checks

- Keep Ruff completely happy.
- Use `ast-grep` when it helps you check repeated patterns or broad edits.
- Treat pre-commit output as part of the change, not as an afterthought.

## Quick Smell Checks

Stop and reconsider if you see any of these:

- one variable reused for several meanings
- a function name that needs a paragraph to explain it
- repeated string literals for the same closed domain value
- a loose dictionary where a `TypedDict` would make the payload clear
- `getattr()` where direct access or a better branch would do
- `hasattr()` where the object shape should already be known
- a wide `try` / `except` block covering too much code
- repeated test setup that should be one fixture
- comments that say only `phase`, `step`, or `helper`
- helpers that are used once and do not make the caller clearer
- a types module importing from a service module

## Further Reading

- [Django design philosophies](https://docs.djangoproject.com/en/stable/misc/design-philosophies/)
- [Django database access optimization](https://docs.djangoproject.com/en/stable/topics/db/optimization/)
- [Django time zone support](https://docs.djangoproject.com/en/stable/topics/i18n/timezones/)
- [Django coding style](https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/coding-style/)
- [Refactoring Guru: Code Smells](https://refactoring.guru/refactoring/smells)
- [Samman Technical Coaching: Code Smells](https://sammancoaching.org/reference/code_smells/)
- [Martin Fowler: Data Clump](https://martinfowler.com/bliki/DataClump.html)
