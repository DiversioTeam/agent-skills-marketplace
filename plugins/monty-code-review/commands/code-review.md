---
description: Hyper-pedantic backend Django code review using the monty-code-review Skill.
---

Use your `monty-code-review` Skill to perform a full backend Django code review
of the current change (PR, diff, or working tree), following the workflow,
severity tags, and checklists defined in its SKILL.md.

Focus order:
1. Correctness, multi-tenancy, security, and data integrity.
2. API and contract changes (including migrations / schema changes).
3. Performance in realistic hot paths.
4. Tests and regression coverage.
5. Maintainability and smaller nits.

