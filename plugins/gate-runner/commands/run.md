---
description: "Run the exact CI gate sequence and report pass/fail with fix commands."
---

Use your `gate-runner` Skill to run the exact CI gate sequence on the current
branch, following the workflow in its SKILL.md.

**Arguments:** `$ARGUMENTS`

Focus order:
1. Run ruff_pr_diff.sh (#1 CI failure pattern).
2. Run local_imports_pr_diff.sh.
3. Run ty check on changed Python files.
4. Check migration squash (multiple migrations per app).
5. Optionally: Django system checks, targeted pytest.
