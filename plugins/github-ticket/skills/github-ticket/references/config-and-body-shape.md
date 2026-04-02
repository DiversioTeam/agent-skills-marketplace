# GitHub Ticket Config And Body Shape

## Sample Config

```json
{
  "planning_repo": "DiversioTeam/monolith",
  "execution_repos": [
    "DiversioTeam/Django4Lyfe",
    "DiversioTeam/Optimo-Frontend"
  ],
  "backlog_labels": ["triage", "needs: enrichment"],
  "quick_issue_labels": ["triage"],
  "project_owner": "DiversioTeam",
  "project_number": 2,
  "path_repo_map": {
    "/Users/monty/work/diversio/monolith-clickup-to-gh/backend": "DiversioTeam/Django4Lyfe",
    "/Users/monty/work/diversio/monolith-clickup-to-gh/optimo-frontend": "DiversioTeam/Optimo-Frontend"
  }
}
```

For the current Diversio migration baseline, `Diversio Work` is organization
project `#2`.

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
