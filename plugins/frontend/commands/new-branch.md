---
description: "Create a frontend branch using the repo's detected branch model."
argument-hint: "[issue-number] [short description]"
---

Parse `$ARGUMENTS` for an optional issue number and description, then invoke
the `frontend` skill with the `new-branch` lane.

Input formats: `1234 short description`, `#1234 short description`, or
`short description`.
