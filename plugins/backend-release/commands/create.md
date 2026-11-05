---
description: "Cut a releases/* candidate from master and a captured dev commit, open its PR, and stage it when authorized."
---

Use the `release-manager` skill in **create** mode with `$ARGUMENTS`, including
`--hotfix` or `--dry-run` when supplied. Follow its scope, version, candidate
shape, merge-method, and exact-head gate rules. PR creation does not authorize
a staging or production deploy.
