---
description: Generate API endpoint docs from Bruno (.bru) files by tracing Django4Lyfe implementations (DRF/Django Ninja).
---

Use your `bruno-api` Skill to generate (or plan) comprehensive API documentation
from Bruno `.bru` files by locating the corresponding Django4Lyfe endpoint code.

Support these modes (ask for any missing inputs):
- `--dry-run` – show an analysis plan only (no deep codebase search).
- `--output <path>` – write the generated markdown doc to a file.
- `--scan <dir>` – analyze all `.bru` files under a directory.

