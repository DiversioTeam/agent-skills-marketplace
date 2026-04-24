# Plugin Catalog

This is the canonical inventory for marketplace plugins, their skill paths, and
their slash commands. Update it when a plugin is added, removed, renamed, or
when command files change.

## Review And Workflow

- `monolith-review-orchestrator`
  - Purpose: monolith-local PR review harness with structured intake,
    deterministic worktree reuse/bootstrap, persistent review context across
    passes, resolved-comment-aware reassessment, and narrow v1 posting
    boundaries.
  - Recent helper additions:
    - monolith PR support without a submodule path
    - external review/artifact and deterministic worktree roots
    - repair mode for dirty worker-owned deterministic worktrees
  - Claude install:
    `claude plugin install monolith-review-orchestrator@diversiotech`
  - Plugin README:
    `plugins/monolith-review-orchestrator/README.md`
  - Skill path:
    `plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator`
  - Worktree/intake reference:
    `plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/references/intake-and-worktree-protocol.md`
  - Review-context reference:
    `plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/references/review-context-protocol.md`
  - Helper explainer:
    `plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/references/workflow-helpers.md`
  - Helper scripts:
    `plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/`
  - GitHub thread helper:
    `plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator/scripts/fetch_review_threads.py`
  - Scope note: requires a Diversio monolith checkout and is not a generic
    repo-agnostic review plugin.
  - Slash commands: `/monolith-review-orchestrator:review-prs`,
    `/monolith-review-orchestrator:reassess-prs`,
    `/monolith-review-orchestrator:post-review`
- `monty-code-review`
  - Purpose: hyper-pedantic Django4Lyfe backend code review with persistent JSON-first review memory.
  - Claude install: `claude plugin install monty-code-review@diversiotech`
  - Skill path: `plugins/monty-code-review/skills/monty-code-review`
  - Memory helper:
    `plugins/monty-code-review/skills/monty-code-review/scripts/review_memory.py`
  - Memory protocol:
    `plugins/monty-code-review/skills/monty-code-review/references/review-memory-protocol.md`
  - Slash commands: `/monty-code-review:code-review`,
    `/monty-code-review:test-hardening`
- `backend-atomic-commit`
  - Purpose: backend pre-commit fixes and strict atomic commits aligned to repo-local commit hygiene.
  - Claude install: `claude plugin install backend-atomic-commit@diversiotech`
  - Skill path: `plugins/backend-atomic-commit/skills/backend-atomic-commit`
  - Slash commands: `/backend-atomic-commit:pre-commit`,
    `/backend-atomic-commit:atomic-commit`, `/backend-atomic-commit:commit`
- `backend-pr-workflow`
  - Purpose: backend PR workflow, GitHub issue linkage, and migration safety checks.
  - Claude install: `claude plugin install backend-pr-workflow@diversiotech`
  - Skill path: `plugins/backend-pr-workflow/skills/backend-pr-workflow`
  - Slash commands: `/backend-pr-workflow:check-pr`
- `process-code-review`
  - Purpose: process findings from `monty-code-review`.
  - Claude install: `claude plugin install process-code-review@diversiotech`
  - Skill path: `plugins/process-code-review/skills/process-code-review`
  - Slash commands: `/process-code-review:process-review`
- `backend-release`
  - Purpose: Django4Lyfe backend release management.
  - Claude install: `claude plugin install backend-release@diversiotech`
  - Skill path: `plugins/backend-release/skills/release-manager`
  - Slash commands: `/backend-release:check`, `/backend-release:create`,
    `/backend-release:publish`
- `dependabot-remediation`
  - Purpose: backend and frontend Dependabot triage, execution, and release
    closure.
  - Claude install:
    `claude plugin install dependabot-remediation@diversiotech`
  - Skill path:
    `plugins/dependabot-remediation/skills/dependabot-remediation`
  - Slash commands: `/dependabot-remediation:backend`,
    `/dependabot-remediation:frontend`
- `terraform`
  - Purpose: Terraform/Terragrunt atomic-commit and PR workflow checks.
  - Claude install: `claude plugin install terraform@diversiotech`
  - Skill paths: `plugins/terraform/skills/terraform-atomic-commit`,
    `plugins/terraform/skills/terraform-pr-workflow`
  - Slash commands: `/terraform:pre-commit`, `/terraform:atomic-commit`,
    `/terraform:check-pr`

## Documentation And Planning

- `bruno-api`
  - Purpose: generate API docs from Bruno collections by tracing Django
    implementations.
  - Claude install: `claude plugin install bruno-api@diversiotech`
  - Skill path: `plugins/bruno-api/skills/bruno-api`
  - Slash commands: `/bruno-api:docs`
- `code-review-digest-writer`
  - Purpose: generate weekly code-review digest docs from PR comments.
  - Claude install:
    `claude plugin install code-review-digest-writer@diversiotech`
  - Skill path:
    `plugins/code-review-digest-writer/skills/code-review-digest-writer`
  - Slash commands: `/code-review-digest-writer:review-digest`
- `plan-directory`
  - Purpose: create structured plan directories and backend RALPH execution
    plans.
  - Claude install: `claude plugin install plan-directory@diversiotech`
  - Skill paths: `plugins/plan-directory/skills/plan-directory`,
    `plugins/plan-directory/skills/backend-ralph-plan`
  - Slash commands: `/plan-directory:plan`,
    `/plan-directory:backend-ralph-plan`, `/plan-directory:run`
- `pr-description-writer`
  - Purpose: reviewer-friendly pull request descriptions with diagrams, tables,
    and repo-local workflow context.
  - Claude install:
    `claude plugin install pr-description-writer@diversiotech`
  - Skill path:
    `plugins/pr-description-writer/skills/pr-description-writer`
  - Slash commands: `/pr-description-writer:write-pr`
- `repo-docs`
  - Purpose: generate and canonicalize repository harness docs.
  - Claude install: `claude plugin install repo-docs@diversiotech`
  - Skill path: `plugins/repo-docs/skills/repo-docs-generator`
  - Slash commands: `/repo-docs:generate`, `/repo-docs:canonicalize`
- `visual-explainer`
  - Purpose: presentation-ready HTML explainers for plans, diffs, diagrams,
    and stakeholder updates, with optional fresh Netlify preview publishing.
  - Claude install: `claude plugin install visual-explainer@diversiotech`
  - Skill path: `plugins/visual-explainer/skills/visual-explainer`
  - Slash commands: `/visual-explainer:explain`

## Operations And Implementation

- `clickup-ticket`
  - Purpose: legacy ClickUp ticket management during the GitHub migration.
  - Claude install: `claude plugin install clickup-ticket@diversiotech`
  - Skill path: `plugins/clickup-ticket/skills/clickup-ticket`
  - Slash commands: `/clickup-ticket:get-ticket`,
    `/clickup-ticket:list-tickets`, `/clickup-ticket:my-tickets`,
    `/clickup-ticket:create-ticket`, `/clickup-ticket:quick-ticket`,
    `/clickup-ticket:create-subtask`, `/clickup-ticket:add-to-backlog`,
    `/clickup-ticket:configure`, `/clickup-ticket:switch-org`,
    `/clickup-ticket:add-org`, `/clickup-ticket:list-spaces`,
    `/clickup-ticket:refresh-cache`
- `github-ticket`
  - Purpose: GitHub-native issue management with planning-hub routing, repo-local execution issues, and project-board defaults.
  - Claude install: `claude plugin install github-ticket@diversiotech`
  - Skill path: `plugins/github-ticket/skills/github-ticket`
  - Slash commands: `/github-ticket:configure`,
    `/github-ticket:get-issue`, `/github-ticket:list-issues`,
    `/github-ticket:my-issues`, `/github-ticket:create-issue`,
    `/github-ticket:quick-issue`, `/github-ticket:add-to-backlog`,
    `/github-ticket:create-linked-issue`, `/github-ticket:route`
- `mixpanel-analytics`
  - Purpose: implement and review MixPanel tracking for the Django
    `optimo_analytics` module.
  - Claude install: `claude plugin install mixpanel-analytics@diversiotech`
  - Skill path: `plugins/mixpanel-analytics/skills/mixpanel-analytics`
  - Slash commands: `/mixpanel-analytics:implement`,
    `/mixpanel-analytics:review`
- `login-cta-attribution-skill`
  - Purpose: add CTA login attribution sources and related tests.
  - Claude install:
    `claude plugin install login-cta-attribution-skill@diversiotech`
  - Skill path:
    `plugins/login-cta-attribution-skill/skills/login-cta-attribution-skill`
  - Slash commands: `/login-cta-attribution-skill:implement`

## Frontend

- `frontend-bundle`
  - Purpose: recommended install-once frontend bundle with repo classification,
    persistent `docs/frontend-skill-digest/` memory, and routing for review,
    API, testing, analytics, observability, CI/CD, planning, and commit work.
  - Claude install:
    `claude plugin install frontend-bundle@diversiotech`
  - Skill paths:
    `plugins/frontend-bundle/skills/frontend-bundle`,
    `plugins/frontend-bundle/skills/frontend-project-digest`
  - Slash commands: `/frontend-bundle:frontend`,
    `/frontend-bundle:refresh-digest`
- `frontend-atomic-commit`
  - Purpose: digest-first frontend pre-commit and atomic-commit using detected
    repo commands, workspace scope, and commit conventions.
  - Claude install:
    `claude plugin install frontend-atomic-commit@diversiotech`
  - Skill path:
    `plugins/frontend-atomic-commit/skills/frontend-atomic-commit`
  - Slash commands: `/frontend-atomic-commit:pre-commit`,
    `/frontend-atomic-commit:atomic-commit`
- `frontend-pr-workflow`
  - Purpose: digest-first frontend PR creation and review for app,
    design-system, and monorepo repos.
  - Claude install:
    `claude plugin install frontend-pr-workflow@diversiotech`
  - Skill paths:
    `plugins/frontend-pr-workflow/skills/frontend-pr-workflow`,
    `plugins/frontend-pr-workflow/skills/frontend-pr-review`
  - Slash commands: `/frontend-pr-workflow:create-pr`,
    `/frontend-pr-workflow:pr-review`
- `frontend-testing`
  - Purpose: digest-first testing guidance that chooses the repo’s real
    unit/component/E2E stack and preview target.
  - Claude install:
    `claude plugin install frontend-testing@diversiotech`
  - Skill path: `plugins/frontend-testing/skills/frontend-testing`
  - Reference: `plugins/frontend-testing/skills/frontend-testing/references/e2e-debugging.md`
  - Slash commands: `/frontend-testing:run-e2e-local`
- `frontend-api-integrator`
  - Purpose: digest-first API integration using the repo’s real contract source:
    generated client, OpenAPI/Swagger, Bruno/Postman, local backend code, or a
    provided backend path.
  - Claude install:
    `claude plugin install frontend-api-integrator@diversiotech`
  - Skill path:
    `plugins/frontend-api-integrator/skills/frontend-api-integrator`
  - Slash commands: `/frontend-api-integrator:api-integrator`
- `frontend-mixpanel`
  - Purpose: digest-first Mixpanel workflow that first verifies Mixpanel exists
    locally and then follows the repo’s tracking layer and privacy rules.
  - Claude install:
    `claude plugin install frontend-mixpanel@diversiotech`
  - Skill path: `plugins/frontend-mixpanel/skills/frontend-mixpanel`
  - Slash commands: `/frontend-mixpanel:implement`,
    `/frontend-mixpanel:review`
- `frontend-sentry`
  - Purpose: digest-first Sentry workflow that first verifies Sentry is present
    and then adapts to local bootstrap, release, and privacy patterns.
  - Claude install:
    `claude plugin install frontend-sentry@diversiotech`
  - Skill path: `plugins/frontend-sentry/skills/frontend-sentry`
  - Slash commands: `/frontend-sentry:sentry`
- `frontend-cicd`
  - Purpose: digest-first frontend CI/CD workflow that detects the repo’s real
    CI provider, deploy target, and preview platform.
  - Claude install:
    `claude plugin install frontend-cicd@diversiotech`
  - Skill path: `plugins/frontend-cicd/skills/frontend-cicd`
  - Slash commands: `/frontend-cicd:cicd`
- `frontend-plan`
  - Purpose: digest-first frontend planning workflow using detected branch and
    docs conventions instead of fixed defaults.
  - Claude install:
    `claude plugin install frontend-plan@diversiotech`
  - Skill path: `plugins/frontend-plan/skills/frontend-plan`
  - Slash commands: `/frontend-plan:plan`, `/frontend-plan:new-branch`
