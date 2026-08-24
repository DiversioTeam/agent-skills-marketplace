---
description: "Audit test quality: production-path depth, behavior value, test economy, and safe relaxed assertions."
---

Use your `test-quality-check` Skill to verify tests actually prove the behavior
they claim, following the workflow in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:
1. Trace every new test to its production entry point.
2. Verify bugfix tests reproduce the reported scenario.
3. Reject framework/plumbing-only tests and inspect fixture/setup reuse.
4. Check transaction changes via induced-failure rollback; only assert
   SAVEPOINT shape when it is the feature.
5. Audit relaxed assertions for multiplicity preservation.
