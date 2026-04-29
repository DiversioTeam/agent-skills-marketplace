# Plugin Catalog

This is the canonical inventory for marketplace plugins, their skill paths, and
their slash commands. Update it when a plugin is added, removed, renamed, or
when command files change.

## Review And Workflow

- `ci-status` (pi package)
  - Purpose: pi-native CI status extension with GitHub Actions and CircleCI
    status discovery, auto-watch after pushes, widget/status rendering,
    notifications, CI-provider/workflow-cycle TUI job details, failed-job reruns,
    guided fix prompts, and log access.
  - Pi install from repo checkout: `pi install -l ./pi-packages/ci-status`
  - Package path: `pi-packages/ci-status`
  - Extension path: `pi-packages/ci-status/extensions/ci-status`
  - Slash commands: `/ci`, `/ci-detail`, `/ci-logs`, `/ci-refresh`,
    `/ci-watch`, `/ci-unwatch`, `/ci-clear`
  - Shortcut: `Ctrl+Shift+.` opens `/ci-detail` by default; override with
    `PI_CI_DETAIL_SHORTCUT`.
  - LLM tools: `get_ci_status`, `ci_fetch_job_logs`
  - Environment: uses `gh` CLI for GitHub; set `CIRCLECI_TOKEN` for CircleCI
    enrichment.
- `dev-workflow` (pi package)
  - Purpose: pi-native daily developer workflow with TypeScript extension
    commands, interactive TUI help panel, CI analysis prompt, local skills, and
    optional pi-subagents review chain.
  - Pi install from repo checkout:
    `pi install -l ./pi-packages/dev-workflow`
  - Package path: `pi-packages/dev-workflow`
  - Extension path:
    `pi-packages/dev-workflow/extensions/ai-review-workflow`
  - Skill paths: `pi-packages/dev-workflow/skills/ai-review-workflow`,
    `pi-packages/dev-workflow/skills/ci`
  - Chain path: `pi-packages/dev-workflow/agents/review-pipeline.chain.md`
  - Slash commands: `/review:plan`, `/review:self`, `/review:standards`,
    `/review:ci`, `/review:docs`, `/review:ship`, `/review:context`,
    `/review:handoff`, `/review:onboard`, `/review:scout`, `/review:oracle`,
    `/review:reviewer`, `/review:parallel`, `/review:help`, `/review:flow`
  - TUI behavior: `/review:help` uses the user's configured
    `app.message.followUp` keybinding (default `Alt+Enter`, often
    `Option+Enter` on macOS) to queue the selected command or edited prompt as a
    follow-up while pi is streaming.
  - Recommended companion package: `ci-status` for `/ci`, `/ci-detail`, and
    `/ci-logs`; workflow prompts fall back to `get_ci_status` /
    `ci_fetch_job_logs` only when the current harness exposes those tools.
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
