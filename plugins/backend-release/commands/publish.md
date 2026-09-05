---
description: "Publish the selected merged release PR at its verified merge commit."
---

Use the `release-manager` skill in **publish** mode with `$ARGUMENTS`.
Require the PR number, verify its scope and exact tag target, and inspect
existing tags/releases before retrying. Report deployment and both branch-sync
outcomes separately; publishing does not authorize those operations.
