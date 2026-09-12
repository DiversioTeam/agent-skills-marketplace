---
name: github-ticket
description: "Create, inspect, or route GitHub issues and set Diversio project-board fields with gh."
allowed-tools: Bash Read Edit Write Glob Grep
---

# GitHub Ticket Skill

## When to Use This Skill

Use this Skill when you want to:

- create GitHub issues without opening the browser
- capture backlog work quickly with smart defaults
- fetch or list issues across `monolith` and a small repo set
- view your assigned work
- route planning work into repo-local execution issues
- add created issues to `Diversio Work` with the right board fields
- keep GitHub issue creation skill-driven instead of form-driven

This Skill is the GitHub-native replacement for the old `clickup-ticket`
workflow. Issue forms in `monolith` are a human fallback and a schema
reference, not the primary creation path.

## Prerequisites

Before calling GitHub for the requested action:

1. Run `gh auth status`.
2. Confirm `gh` is authenticated for the right GitHub account.
3. Confirm the token has the scopes needed for the requested action:
   - `repo` for issue read/write
   - `read:org` for org visibility
   - `project` when project add or field hydration is expected
4. Fail fast if `gh` is missing or unauthenticated.

Preferred auth model:

- normal `gh` login
- no plugin-specific token in the common case
- if project hydration is part of the workflow and `project` scope is missing,
  prefer `gh auth refresh -s project`

## Default Operating Model

Treat these defaults as the steady-state baseline unless the user overrides
them:

- planning repo: `DiversioTeam/monolith`
- execution repos:
  - `DiversioTeam/Django4Lyfe`
  - `DiversioTeam/Diversio-Frontend`
  - `DiversioTeam/Optimo-Frontend`
  - `DiversioTeam/diversio-ds`
  - `DiversioTeam/infrastructure`
  - `DiversioTeam/naboo`
  - `DiversioTeam/diversio-serverless`
  - `DiversioTeam/launchpad`
  - `DiversioTeam/skiddie`
  - `DiversioTeam/terraform-modules`
  - `DiversioTeam/agent-skills-marketplace`
- canonical IDs: native GitHub issue numbers
- legacy ClickUp `GH-xxxx` IDs: metadata only when applicable

Routing rules:

- If you are in the monolith root and no repo is specified, prefer
  `DiversioTeam/monolith`.
- If you are inside a repo checkout and no repo is specified, prefer that repo
  as the execution repo after normalizing the git remote into `owner/repo`.
- If the work clearly spans repos or still needs planning, create the issue in
  `DiversioTeam/monolith`.
- If the user asks for implementation work in a specific repo, create the
  issue in that repo when issues are enabled there.
- If repo detection yields a GitHub repo outside the default execution list,
  it is still valid to use that repo; do not reject it only because it is not
  prelisted in config.

## Local Config

Default config path:

```bash
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/github-ticket"
CONFIG_FILE="${CONFIG_DIR}/config.json"
```

Use a small JSON file with fields like:

- `planning_repo`
- `execution_repos`
- `backlog_labels`
- `quick_issue_labels`
- `project_owner`
- `project_number`
- `project_field_defaults`
- optional `path_repo_map`

See `references/config-and-body-shape.md` for a sample config and issue body.

For the current Diversio baseline, prefer organization project `#2`
(`Diversio Work`) unless the user overrides project placement.
Treat `project_field_defaults` as a display-name keyed map for stable defaults
like `Status` and `Priority`, not as a place to hard-code field or option IDs.
Prefer runtime repo detection from the current git checkout before falling back
to `path_repo_map`. In worktree-heavy setups, avoid hard-coded absolute path
maps unless there is a real non-git edge case.

## Repo Alias Map

Allow these shorthand values when the user names a repo informally:

- `monolith` -> `DiversioTeam/monolith`
- `backend` -> `DiversioTeam/Django4Lyfe`
- `frontend` -> `DiversioTeam/Diversio-Frontend`
- `optimo-frontend` -> `DiversioTeam/Optimo-Frontend`
- `design-system` -> `DiversioTeam/diversio-ds`
- `infrastructure` -> `DiversioTeam/infrastructure`
- `naboo` -> `DiversioTeam/naboo`
- `diversio-serverless` -> `DiversioTeam/diversio-serverless`
- `launchpad` -> `DiversioTeam/launchpad`
- `skiddie` -> `DiversioTeam/skiddie`
- `terraform-modules` -> `DiversioTeam/terraform-modules`
- `agent-skills-marketplace` -> `DiversioTeam/agent-skills-marketplace`
- `skills-marketplace` -> `DiversioTeam/agent-skills-marketplace`

If a repo alias is ambiguous, ask one short clarifying question.

## Choose A Command

Read the requested mode in [command modes](references/command-modes.md):

- `get-issue`, `list-issues`, `my-issues`: read-only issue inspection.
- `configure`: local defaults and authentication requirements.
- `create-issue`, `quick-issue`, `add-to-backlog`: creation with the mode's
  defaults and required project fields.
- `create-linked-issue`, `route`: source/target linkage; do not close the
  planning issue unless requested.

For creation, also use that reference's project hygiene, project commands, and
canonical issue body sections. Inspect live field IDs; report partial success
without duplicating an issue whose creation already succeeded.

## Implementation Backend

Prefer this command set:

- `gh issue create`
- `gh issue view`
- `gh issue list`
- `gh search issues`
- `gh issue comment`
- `gh project view`
- `gh project field-list`
- `gh project item-add`
- `gh project item-list`
- `gh project item-edit`
- `gh api`

Use `gh api` only when a simpler `gh issue ...` subcommand does not cover the
action cleanly.

## Output Expectations

When this Skill completes a write action, always return:

- repo
- issue number
- title
- URL
- labels applied
- whether project add succeeded or was skipped
- which project fields were applied, skipped, or failed

When it completes a read or list action, keep the response scan-friendly and
show enough context that the user does not need to open GitHub immediately.

## Adjacent Skill Fallout

This Skill unblocks the GitHub issue workflow, but it does not by itself clean
up every older ClickUp assumption elsewhere.

Known follow-up areas:

- `backend-pr-workflow`
- `backend-atomic-commit`
- repo-local harness docs or commands that still require `clickup_*` branches

If those older instructions conflict with repo-local GitHub workflow docs, the
repo-local GitHub workflow docs should win.
