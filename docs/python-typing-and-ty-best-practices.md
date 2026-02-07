# Python Typing + `ty` Best Practices (Skill Authoring Baseline)

Last reviewed: 2026-02-07

This document defines a project-agnostic typing policy for skills in this
marketplace that read, modify, or review Python code.

## Why This Exists

Skills were previously inconsistent about type gates (for example, allowing
"baseline acceptable" checks in one skill while another treated type failures
as blocking). This creates drift and repeated regressions.

The policy below standardizes behavior so every code-touching skill:

- Detects the repository's active type checker correctly.
- Treats that checker as a strict quality gate.
- Avoids "shortcut" suppressions (`noqa`/broad ignores) as a default workflow.
- Stays portable across projects and ecosystems.

## Non-Negotiable Rules

1. If a repository has `ty` configured, `ty` is mandatory and blocking.
2. "Baseline acceptable" is not allowed for files touched by the current change.
3. No blanket suppressions as a quick escape hatch.
4. Scoped checks are fine for iteration speed, but final merge/release gates must
   satisfy the repository's required checker(s).
5. Skills must prefer local repository policy documents when present.

## Type Gate Detection (Project-Agnostic)

Use this precedence order for Python repositories:

1. `ty` (preferred when configured)
2. `pyright`
3. `mypy`

### How To Detect

Treat `ty` as active if any of these exist:

- `pyproject.toml` with `[tool.ty]`
- `ty.toml`
- `.bin/ty`
- CI/pre-commit invokes `ty`

Treat `pyright` as active if any of these exist:

- `pyrightconfig.json`
- `[tool.pyright]` in `pyproject.toml`
- CI/pre-commit invokes `pyright`

Treat `mypy` as active if any of these exist:

- `mypy.ini`
- `.mypy.ini`
- `[tool.mypy]` in `pyproject.toml`
- CI/pre-commit invokes `mypy`

If multiple are present, follow repository docs/CI order. If that is unclear,
prefer `ty` > `pyright` > `mypy`.

## Recommended Command Resolution

Prefer repository wrappers first, then tool runners:

1. `.bin/<tool>`
2. `uv run <tool>`
3. `<tool>` directly

Examples:

```bash
# ty
.bin/ty check <paths>
uv run ty check <paths>
ty check <paths>

# pyright
.bin/pyright <paths>
uv run pyright <paths>
pyright <paths>

# mypy
.bin/mypy <paths>
uv run mypy <paths>
mypy <paths>
```

## Strictness Policy

For touched files:

- Zero type diagnostics is the target.
- Do not leave known type errors in files edited by the change.
- Do not convert concrete types to `Any` to silence errors.

For repository-level gates:

- If CI/pre-commit enforces repo-wide type checks, mirror that before merge.
- If local execution is constrained, explicitly report which gate could not run.

## Python 3.14+ Typing Guidance

These guidelines are aligned with current Python docs and typing spec:

1. Prefer modern syntax:
   - `list[str]`, `dict[str, int]`, `str | None`.
2. Use `TypedDict`, `Protocol`, dataclasses, and well-typed objects over
   `dict[str, Any]` and shape-shifting payloads.
3. Keep `Any` explicit and narrowly justified.
4. Use runtime narrowing (`isinstance`, explicit `None` guards, small helper
   functions returning `NoReturn`) before reaching for `cast`.
5. Use `cast` as a last resort, with a short comment explaining why narrowing
   cannot be expressed more directly.
6. Keep type aliases explicit and reusable for repeated structural contracts.
7. Prefer precise return types for public functions and boundary-layer helpers.
8. Avoid annotation patterns that depend on fragile runtime behavior.

## Django-Oriented Typing Guidance

1. Prefer helper functions for request/user narrowing over repeated ad-hoc casts.
2. Guard `None` results from queryset lookups explicitly before attribute access.
3. Keep dynamic framework attributes wrapped behind typed helpers/protocols.
4. Avoid broad exception swallowing that hides type and control-flow bugs.
5. Keep model/query contracts explicit at the call boundary (querysets, serializers,
   services).

## `ty`-Specific Guidance

1. Enable strict warning behavior when repository policy expects it:
   - `[tool.ty] error-on-warning = true`
2. Keep ignores narrow and code-specific.
3. Prefer fixing root type issues over adding ignore comments.
4. In code review, treat new suppressions as design debt unless justified.

## Skill Authoring Requirements

Any skill that edits or reviews Python must:

1. Include a "Type Gate Detection" section with the precedence policy above.
2. State that touched files must pass the active type gate.
3. Avoid wording like "baseline acceptable."
4. Reference local repo typing docs when present, especially:
   - `docs/python-typing-3.14-best-practices.md`
   - `TY_MIGRATION_GUIDE.md`
   - `AGENTS.md` / `CLAUDE.md`
5. Report unresolved type-gate blockers explicitly with file-level detail.

## References (Primary Sources)

- Python typing docs:
  - https://docs.python.org/3/library/typing.html
- Python "What's New in 3.14" (annotation behavior changes):
  - https://docs.python.org/3/whatsnew/3.14.html
- Typing specification:
  - https://typing.python.org/
- Typing best practices:
  - https://typing.python.org/en/latest/reference/best_practices.html
- Typing annotations HOWTO:
  - https://docs.python.org/3/howto/annotations.html
- Astral `ty` docs:
  - https://docs.astral.sh/ty/
- Agent Skills open specification:
  - https://agentskills.io/specification/
- OpenAI Codex Skills docs:
  - https://developers.openai.com/codex/skills/
- Anthropic Claude skills docs:
  - https://docs.anthropic.com/en/docs/claude-code/tutorials/use-skills
