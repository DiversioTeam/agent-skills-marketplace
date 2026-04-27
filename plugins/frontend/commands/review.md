---
description: "Review a frontend PR using the repo-local digest and Bumang-style priorities."
argument-hint: "[PR number]"
---

Parse `$ARGUMENTS` for an optional PR number, then invoke the `frontend`
skill with the `review` lane.

If no PR number is provided, review the current branch diff or ask for the PR
number.
