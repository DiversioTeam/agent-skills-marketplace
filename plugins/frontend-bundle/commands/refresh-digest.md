Refresh the repo-local frontend project digest for the current repository.

## Steps

1. Inspect the current repo for workspace markers, package manager, frontend
   framework, styling stack, testing stack, analytics/observability libraries,
   CI/deploy signals, and API contract sources.
2. Classify the repo as one of:
   - `frontend-app`
   - `design-system`
   - `monorepo-frontend`
   - `unknown`
3. Write or refresh these files in the target repo:
   - `docs/frontend-skill-digest/AGENTS.md`
   - `docs/frontend-skill-digest/project-digest.md`
4. If API integration work may require backend context and the repo does not
   contain that context, record that the next API task should ask the user for a
   backend working directory or spec path rather than guessing.

## Output

Summarize:
- repo classification
- detected package manager / workspace setup
- detected framework, styling, testing, analytics, and observability stacks
- any missing backend or API-spec context that later skills must request
