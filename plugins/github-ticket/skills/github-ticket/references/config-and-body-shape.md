# GitHub Ticket Config And Body Shape

## Sample Config

```json
{
  "planning_repo": "DiversioTeam/monolith",
  "execution_repos": [
    "DiversioTeam/Django4Lyfe",
    "DiversioTeam/Optimo-Frontend"
  ],
  "backlog_labels": ["needs: enrichment"],
  "quick_issue_labels": [],
  "project_owner": "DiversioTeam",
  "project_number": 2,
  "project_field_defaults": {
    "Status": "Ready",
    "Priority": "Normal"
  }
}
```

For the current Diversio migration baseline, `Diversio Work` is organization
project `#2`.

Project hydration assumes the authenticated `gh` session has `project` scope.
If not, issue creation can still succeed but project add / field edits will
fail until the user refreshes auth, for example:

```bash
gh auth refresh -s project
```

When adding issues there, prefer:

- `Status: Ready` for scoped, actionable work
- `Status: Blocked` for dependency-held work
- `Status: Inbox` only for intentionally rough capture
- `Target Repo` mapped to the execution repo when the field exists
- if the project does not have a dedicated repo option, use `other`
- `Priority` from config when the user or team has a default

Mode-specific overrides should beat global defaults:

- `add-to-backlog` should normally force `Status: Inbox`
- `quick-issue` should use `Inbox` unless the captured context is already
  actionable
- `create-linked-issue` and `route` should normally use `Ready` or `Blocked`
  rather than `Inbox`

## Optional Path Repo Map

`path_repo_map` is optional. Prefer runtime repo detection from the current git
checkout before adding path-specific overrides.

Why:

- worktree roots move
- absolute local paths do not belong in public checked-in guidance
- most repo selection can be derived from `git rev-parse --show-toplevel` plus
  `git remote get-url origin`

When using `git remote get-url origin`, normalize both of these forms into
`owner/repo` before routing:

- `git@github.com:Owner/Repo.git`
- `https://github.com/Owner/Repo.git`

Use `path_repo_map` only when a real workflow enters directories where git
checkout detection is not enough.

## Project Hydration Recipe

Use the project field display names from config, but resolve the live ids at
runtime:

1. Get the project id:

```bash
gh project view 2 --owner DiversioTeam --format json
```

2. Get field ids and option ids:

```bash
gh project field-list 2 --owner DiversioTeam --format json
```

3. Add the issue to the project:

```bash
gh project item-add 2 --owner DiversioTeam --url <issue-url>
```

4. Find the project item id for that issue:

```bash
gh project item-list 2 --owner DiversioTeam --format json
```

5. Edit one field at a time:

```bash
gh project item-edit \
  --id <item-id> \
  --project-id <project-id> \
  --field-id <field-id> \
  --single-select-option-id <option-id>
```

For the current Diversio baseline, the common single-select fields are:

- `Status`
- `Target Repo`
- `Priority`

For `Target Repo`, the current project has dedicated options for:

- `monolith`
- `backend`
- `frontend`
- `optimo-frontend`
- `design-system`
- `infrastructure`
- `naboo`
- `diversio-serverless`
- `launchpad`
- `skiddie`
- `other`

So repos like `agent-skills-marketplace` and `terraform-modules` should
normally map to `other` in that project unless the board schema later grows a
dedicated option.

## Canonical Issue Body

```markdown
## Problem or request

Describe the pain, risk, or opportunity in plain language.

## Success criteria

- Concrete outcome 1
- Concrete outcome 2

## Constraints / non-goals

- Guardrail or explicit non-goal

## Supporting links

- https://github.com/DiversioTeam/monolith/issues/1234

## Legacy metadata

- Legacy ClickUp ID: GH-4321
```

## Label Defaults

Prefer:

- `triage` on newly created issues
- `type:*` when the work type is known
- `needs: enrichment` only when the issue is intentionally rough
- keep `backlog_labels` and `quick_issue_labels` focused on add-on labels rather
  than defaults that the skill already applies separately
