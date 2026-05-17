---
description: "Audit test quality: depth, bug variants, transaction shape, and CI-tolerant assertion safety."
---

Use your `test-quality-check` Skill to verify tests actually prove the behavior
they claim, following the workflow in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:
1. Trace every new test to its production entry point.
2. Verify bugfix tests reproduce the reported scenario.
3. Check transactional tests for connection.queries/SAVEPOINT assertions.
4. Audit relaxed assertions for multiplicity preservation.
