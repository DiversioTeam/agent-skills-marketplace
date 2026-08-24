---
description: "Verify import/export round-trip safety across CSV, config, dict, admin, and command I/O paths."
---

Use your `import-export-roundtrip-check` Skill to verify that every changed data
shape can be safely round-tripped through the import/export paths it touches,
following the workflow in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:
1. Identify changed data structures from the branch diff.
2. Enumerate all import and export paths that touch those structures.
3. Audit field-level parity for each import/export pair.
4. Check cross-path type coherence and duplicate-row handling.
5. Report findings with evidence and completion-gate verification.
