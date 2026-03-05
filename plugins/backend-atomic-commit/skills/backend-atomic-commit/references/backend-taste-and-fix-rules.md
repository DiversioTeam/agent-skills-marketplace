# Backend Taste And Fix Rules

Load this file when you are actively fixing backend code and need concrete
heuristics beyond the main workflow in `SKILL.md`.

## Imports And Local Imports

- Enforce **no local imports at any cost**:
  - Avoid `from myapp.models import MyModel` inside functions or methods just
    to dodge cyclic imports.
  - Use `./.security/local_imports_pr_diff.sh` as the first line of defense.
  - Prefer module-level imports, refactoring helpers to avoid cycles, and
    type-only imports where needed.
  - If moving imports risks a real cycle, suggest structural changes and do not
    silently reintroduce local imports.

## Logging

- Prefer structured payloads over single log strings.
- In `optimo_*` apps, treat unstructured logging as at least `[SHOULD_FIX]`.
- Never log PII such as employee emails; prefer UUIDs/IDs instead.
- Avoid `logger.exception` for expected error paths; use explicit `warning` or
  `error` messages.

## Try/Except And Error Handling

- Shrink large catch-all `try/except` blocks to the smallest raisable region.
- Replace bare `except:` / `except Exception:` with specific exceptions when
  possible.
- Never swallow exceptions silently in behaviorally important code.
- Avoid `getattr`/`hasattr` as a “just in case” crutch.

## Types And Data Structures

- Avoid `Any` when a precise type is available.
- Avoid string-based type hints; arrange imports so real types can be used.
- Add missing annotations on new/changed functions in core apps.
- Replace stable-shape dict payloads with `TypedDict` or dataclasses when
  reasonable.

## Tests, Fixtures, And ORM Patterns

- Prefer existing rich fixtures documented in `AGENTS.md` or linked test docs.
- Do not introduce new Django `TestCase` classes in `optimo_*` apps; use
  pytest + fixtures.
- Treat multi-tenant fixture mismatches as correctness bugs.
- Watch for N+1 loops and use reverse relations when they improve clarity.

## Debug Artifacts And Commented Code

- Remove `print(...)`, `pdb.set_trace()`, `ipdb.set_trace()`, and
  `breakpoint()` from non-test code.
- Remove clearly obsolete commented-out blocks.
- Flag ambiguous commented sections or ticket-less `TODO` / `FIXME` notes as
  `[SHOULD_FIX]`.

## Templates And djlint

- Treat template lint failures as first-class issues. In `atomic-commit` mode
  they are usually `[BLOCKING]`.
- Reformat before lint/check.
- Restage modified templates after reformatting.
- Look for `[tool.djlint]` or `.djlintrc`; if hooks exist without config, note
  that as `[SHOULD_FIX]`.
- Common blockers:
  - Inline styles should usually become CSS classes.
  - Named blocks should close with named endblocks.

## Security And Secrets

- Flag hardcoded tokens, passwords, or API keys as `[BLOCKING]`.
- Avoid staging obvious secret-heavy files such as `.env` or local creds JSON.

## Migrations And Schema Changes

- Do **not** change migration strategy automatically; instead detect and report:
  - destructive drops combined with live code expectations,
  - new non-nullable fields with defaults on large/hot tables,
  - volatile defaults that imply heavy atomic backfills.
- Recommend the safer nullable -> backfill -> default pattern when applicable.

## Critical Patterns From Repo Docs

- Watch for patterns explicitly banned in backend `AGENTS.md` or linked docs,
  such as Django Ninja `Query()` module constants or legacy survey models.
- Treat new usage of those patterns as `[BLOCKING]`.
