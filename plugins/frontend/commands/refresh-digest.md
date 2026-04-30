---
description: "Persist a full frontend project digest to docs/frontend-skill-digest/."
---

Invoke the `frontend` skill's `refresh-digest` lane.

This is the only command that writes digest files to the repo. Other commands
use ephemeral inline detection when the digest is missing or stale.
