---
description: Hyper-pedantic backend Django code review using the monty-code-review Skill.
---

Use your `monty-code-review` Skill to perform a full backend Django code review
of the current change (PR, diff, or working tree), following the workflow,
severity tags, and checklists defined in its SKILL.md.

Before reviewing, automatically resolve and load persistent review memory using
the Skill's JSON-first memory protocol and the `uv`-managed `click` helper at
`skills/monty-code-review/scripts/review_memory.py`.

Why: follow-up reviews should focus on new commits and unresolved findings
instead of re-reading every old markdown review from scratch.

Keep the repo-local `*_review.md` as the review artifact, but treat the
structured memory store as the canonical persistent history. Ask one short
clarifying question instead of assuming whenever ambiguity would change memory
identity or dedupe behavior.

If changed files include pytest tests (`test_*.py`, `*_test.py`, `tests/**/*.py`, `conftest.py`),
also run the Skill's pytest test-hardening lane and apply dangerous-pattern checks
from `skills/monty-code-review/references/pytest-dangerous-patterns.md`.

Focus order:
1. Correctness, multi-tenancy, security, and data integrity.
2. API and contract changes (including migrations / schema changes).
3. Performance in realistic hot paths.
4. Tests and regression coverage.
5. Harness gaps, maintainability, and smaller nits.

If asked to post review comments to GitHub, apply the Skill's `GitHub Posting Protocol`
(`MUST_*`, `SHOULD_*`, and `STEP_*` rules) from
`skills/monty-code-review/references/github-posting-protocol.md` before posting.
