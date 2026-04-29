---
description: "Main frontend entrypoint — routes to the correct lane based on arguments."
argument-hint: "<lane> [args] — e.g. review 123, api feedback, testing, commit"
---

Parse `$ARGUMENTS` to determine the lane and pass-through arguments, then
invoke the `frontend` skill with that lane.

Valid lanes: `review`, `api`, `testing`, `analytics`, `observability`, `cicd`,
`plan`, `commit`, `pre-commit`, `create-pr`, `new-branch`.

If no lane is provided or the lane is ambiguous, ask the user which lane they
need.

Example usage:

- `/frontend:work review 123` — review PR #123
- `/frontend:work api feedback` — API integration for "feedback" feature
- `/frontend:work testing` — run or write tests
- `/frontend:work commit "fix button alignment"` — atomic commit
