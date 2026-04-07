---
name: github-ticket
description: "Create, route, and inspect GitHub issues from Claude Code or Codex with gh CLI-backed defaults for DiversioTeam/monolith, repo-local execution repos, and project-board hydration."
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

Before doing anything else:

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

## Command Modes

### `configure`

Goal:

- validate `gh` auth
- create or update local defaults
- keep prompts minimal

Workflow:

1. Run `gh auth status`.
2. Detect the current checkout path and repo if possible:
   - prefer `git rev-parse --show-toplevel`
   - then `git remote get-url origin`
   - normalize SSH or HTTPS GitHub remotes into `owner/repo`
3. Create `${XDG_CONFIG_HOME:-$HOME/.config}/github-ticket/config.json` if missing.
4. Gather only the missing defaults:
   - planning repo
   - preferred execution repos
   - backlog labels
   - quick-issue labels
   - project owner/number
   - optional project field defaults such as `Status` and `Priority`
   - only add `path_repo_map` when repo detection via git is insufficient

Use `jq` to write or update the config rather than inventing a custom format.
If project config is present but `gh auth status` shows no `project` scope,
surface that clearly instead of pretending project hydration will work.

### `get-issue`

Accepted input formats:

- `1234`
- `#1234`
- `owner/repo#1234`
- a GitHub issue URL

Behavior:

1. Resolve the issue reference to a repo plus number.
2. Use `gh issue view`.
3. Return title, state, assignees, labels, body summary, and key links.
4. If the issue is in another repo, show that clearly.

### `list-issues`

Prefer the smallest backend that matches the ask:

- one repo: `gh issue list`
- cross-repo or richer filtering: `gh search issues`

Support these filters:

- repo
- assignee
- label
- open / closed state
- `imported: clickup`
- updated recently

Keep the filter model smaller than the old ClickUp plugin.

### `my-issues`

This is the convenience view for assigned work.

Default behavior:

- search across the planning repo plus configured execution repos
- show open issues assigned to `@me`
- prefer recently updated or explicitly blocked work near the top

Use `gh search issues --assignee @me --state open` when a cross-repo query is
needed.

### `create-issue`

This is the full interactive creation path.

Gather:

- title
- work type
- target repo
- problem or request
- success criteria
- optional constraints or non-goals
- optional supporting links
- optional legacy ClickUp metadata

Then:

1. Choose the repo using the routing rules.
2. Build the canonical issue body.
3. Apply labels:
   - always include `triage` unless the user says otherwise
   - map work type to `type:*` labels when available
4. Create the issue with `gh issue create`.
5. If project config exists, or the current Diversio baseline applies, add the
   issue to the project with `gh project item-add`.
6. If the project add succeeds, hydrate the common project fields immediately:
   - `Status`
   - `Target Repo`
   - optional `Priority`
7. For `Status`, prefer:
   - `Ready` for scoped, actionable work
   - `Blocked` when the issue depends on incomplete upstream work
   - `Inbox` only for intentionally rough capture
8. For `Target Repo`, map the destination repository to the matching project
   option when that field exists. If there is no exact option for that repo,
   use `other` instead of leaving the field blank.
9. Never block issue creation on project assignment or field hydration, but do
   report the failure clearly so the user is not left with invisible board
   items.
10. If project hydration fails because of missing `project` scope, say that
    explicitly and point at `gh auth refresh -s project`.

### `quick-issue`

This should stay under three prompts.

Required input:

- title

Preferred flow:

1. Infer repo from current directory or config.
2. Use default quick-issue labels.
3. Create a minimal but useful body.
4. If the result is still intentionally rough, prefer `Status: Inbox` when
   adding it to a project. Only upgrade to `Ready` when the issue is already
   actionable from the captured context.
5. Return the created issue URL.

### `add-to-backlog`

This is the fastest capture path.

Default behavior:

- repo: `DiversioTeam/monolith`
- labels: `triage` plus configured backlog labels
- minimal body with problem/request plus optional links
- when added to `Diversio Work`, prefer `Status: Inbox`

Do not over-prompt. If the user only gives a title, create the issue.

### `create-linked-issue`

Use this when turning planning work into explicit follow-up or execution work.

Safe default:

1. Read the source issue.
2. Create the new issue in the target repo.
3. Mention the source issue in the new body.
4. Add reciprocal comments with `gh issue comment` on both issues.
5. If the new issue is added to a project, prefer `Ready` unless its own
   dependency chain means it should start in `Blocked`.

Do not rely on child-issue-only GitHub features for MVP behavior.

### `route`

Use this when a planning issue in `monolith` should become repo-local
execution work.

Behavior:

1. Read the planning issue.
2. Decide the target repo or confirm it with one short question.
3. Call the same creation logic as `create-linked-issue`.
4. Leave the planning issue open unless the user explicitly wants it closed.

## Project Hygiene

When the issue lands in `Diversio Work`, treat project visibility as part of
the ticket workflow instead of optional cleanup.

- If a work item should show up in active board views, do not leave `Status`
  blank.
- `Inbox` is appropriate for rough backlog capture; it is not appropriate for
  already-scoped execution work.
- `quick-issue` and `add-to-backlog` may legitimately choose `Inbox` even when
  a global config default says `Ready`, because the capture mode is part of the
  semantics.
- `Ready` is the default for issue-sized, actionable work that can be picked
  up now.
- `Blocked` is the default when dependency text like `requires`, `depends on`,
  or `blocked by` means the issue should exist on the board but not enter the
  active queue yet.
- When the project has a `Target Repo` field, set it to the repo that will own
  execution so grouped board views stay useful. If the project does not have a
  dedicated option for that repo, use `other`.
- After creation, verify the issue is attached to the expected project and is
  not hidden by a blank `Status`.

## Project Commands

Use the GitHub CLI's project commands directly instead of inventing ad hoc
GraphQL:

1. Resolve the project metadata:
   - `gh project view <number> --owner <owner> --format json`
2. Resolve field ids and single-select option ids:
   - `gh project field-list <number> --owner <owner> --format json`
3. Add the issue to the project:
   - `gh project item-add <number> --owner <owner> --url <issue-url>`
4. Resolve the project item id by matching the created issue:
   - `gh project item-list <number> --owner <owner> --format json`
5. Update one field per call with `gh project item-edit`:
   - `--single-select-option-id` for fields like `Status`, `Target Repo`, and
     `Priority`
   - `--project-id` is required for non-draft issue field edits

Do not assume field ids or option ids are stable across projects. Read them
from the active project each time unless a higher-level cache is explicitly in
scope.

## Canonical Issue Body

Generated issues should use these sections in this order:

1. `## Problem or request`
2. `## Success criteria`
3. `## Constraints / non-goals`
4. `## Supporting links`
5. `## Legacy metadata`

Only include `Legacy metadata` when there is actual ClickUp carryover.

Keep the body aligned with the `monolith` issue forms so manual and
skill-created issues look comparable.

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
