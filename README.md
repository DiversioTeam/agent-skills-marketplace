# agent-skills-marketplace

Agent Skills marketplace for Diversio.

## Agent Skills Standard

This repo follows the [Agent Skills standard](https://agentskills.io/specification): an
open, tool-agnostic format for packaging capabilities and workflows for agents.
A skill is a directory with a required `SKILL.md` that contains YAML frontmatter
(`name`, `description`) and Markdown instructions, plus optional `scripts/`,
`references/`, and `assets/`.

Key points from the standard:
- `SKILL.md` is required and starts with YAML frontmatter.
- `name` must match the skill directory and use lowercase letters, numbers, and hyphens.
- `description` should explain what the skill does and when to use it.
- Optional frontmatter fields include `license`, `compatibility`, `metadata`, and experimental `allowed-tools` (space-delimited string).
- Keep `SKILL.md` focused; link to longer guidance in `references/` or helpers in `scripts/`.

Skills are designed for progressive disclosure: agents read metadata first,
load the full `SKILL.md` when invoked, and open `references/` or `scripts/`
only if needed.

### Compatibility (Codex + Claude Code)

To keep Skills portable across both OpenAI Codex and Claude Code:
- Prefer only `name` + `description` in YAML frontmatter; treat other fields as optional/ignored by many runtimes.
- Keep `description` single-line and ≤500 chars (Codex validates this at startup).
- Avoid `anthropic`/`claude` in Skill names and don’t include XML tags in `name`/`description` (Claude).
- Keep `SKILL.md` reasonably small (≈<500 lines); move deep docs into `references/`.

### SKILL.md Size Guardrail (CI-Enforced)

To keep Skills reliable and LLM-friendly, treat `SKILL.md` as an orchestrator, not a dump:
- Hard limit: each changed `SKILL.md` in a PR/push must stay at or below 500 lines (CI fails above this).
- Keep only activation workflow, core priorities, and output contract in `SKILL.md`.
- Move long procedures/examples into `references/*.md`.
- Move reusable command logic into `scripts/`.
- Keep reference depth shallow (one level deep where possible) for progressive disclosure.

Run the guard locally before opening a PR:

```bash
bash scripts/validate-skills.sh
```

This default mode validates changed and untracked `SKILL.md` files in your working tree.
Use `bash scripts/validate-skills.sh --all` for a full-repo audit.

## Working on Skills (LLM checklist)

- Start with `AGENTS.md` (source of truth); `CLAUDE.md` only includes it.
- Required structure: `plugins/<plugin>/skills/<skill-name>/SKILL.md` with YAML frontmatter (`name`, `description`).
- Ensure the skill directory name matches `name` and stays in kebab-case.
- Add or update a corresponding `plugins/<plugin>/commands/*.md` entrypoint.
- Keep `SKILL.md` focused; put deep docs in `references/` and helpers in `scripts/`.
- After substantive edits, do a fresh-eyes self-review of the changed skill,
  adjacent commands/docs, and version metadata, then fix obvious issues before
  stopping.
- If you change a plugin, bump its version in `plugins/<plugin>/.claude-plugin/plugin.json`
  and keep `.claude-plugin/marketplace.json` in sync.

## Overview

This repository hosts Diversio-maintained Agent Skills and plugin manifests so
the same skills can be distributed via the Claude Code marketplace or other
channels.

## Documentation Philosophy

The `repo-docs` plugin is now explicitly informed by OpenAI's February 11,
2026 article [Harness engineering: leveraging Codex in an agent-first
world](https://openai.com/index/harness-engineering/).

The practical takeaway for this repo is:
- Keep `AGENTS.md` as a short routing map, not a giant handbook.
- Put durable detail in focused repo-local docs.
- Treat repeated failures as harness gaps to encode in docs, wrappers, or CI.

## Repository Structure

```
agent-skills-marketplace/
├── .claude-plugin/
│   └── marketplace.json               # Marketplace definition
├── pi-packages/
│   ├── ci-status/                     # Pi-native CI status extension
│   └── dev-workflow/                  # Pi-native daily developer workflow extension + skills
├── plugins/
│   ├── monty-code-review/             # Monty backend code review plugin
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/monty-code-review/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   └── commands/
│   │       ├── code-review.md
│   │       └── test-hardening.md
│   ├── monolith-review-orchestrator/  # Monolith PR review orchestration plugin
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/monolith-review-orchestrator/
│   │   │   ├── SKILL.md
│   │   │   ├── references/
│   │   │   └── scripts/
│   │   └── commands/
│   │       ├── review-prs.md
│   │       ├── reassess-prs.md
│   │       └── post-review.md
│   ├── backend-atomic-commit/         # Backend pre-commit & atomic-commit plugin
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/backend-atomic-commit/SKILL.md
│   │   └── commands/
│   │       ├── pre-commit.md
│   │       ├── atomic-commit.md
│   │       └── commit.md
│   ├── backend-pr-workflow/           # Backend PR workflow plugin
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/backend-pr-workflow/SKILL.md
│   │   └── commands/check-pr.md
│   ├── bruno-api/                     # Bruno API docs generator
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/bruno-api/SKILL.md
│   │   └── commands/docs.md
│   ├── code-review-digest-writer/     # Code review digest generator
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/code-review-digest-writer/SKILL.md
│   │   └── commands/review-digest.md
│   ├── plan-directory/                # Structured plan directories + RALPH loop
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/
│   │   │   ├── plan-directory/
│   │   │   │   ├── SKILL.md
│   │   │   │   └── references/        # Extended guidance
│   │   │   └── backend-ralph-plan/    # RALPH loop integration
│   │   │       ├── SKILL.md
│   │   │       ├── references/
│   │   │       └── examples/
│   │   └── commands/
│   │       ├── plan.md
│   │       ├── backend-ralph-plan.md
│   │       └── run.md                 # Execute RALPH plans
│   ├── pr-description-writer/         # PR description generator
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/pr-description-writer/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   └── commands/write-pr.md
│   ├── process-code-review/           # Code review processor (fix/skip issues)
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/process-code-review/SKILL.md
│   │   └── commands/process-review.md
│   ├── mixpanel-analytics/            # MixPanel tracking implementation & review
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/mixpanel-analytics/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   └── commands/
│   │       ├── implement.md
│   │       └── review.md
│   ├── clickup-ticket/                # ClickUp ticket management
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/clickup-ticket/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   └── commands/
│   │       ├── configure.md
│   │       ├── create-ticket.md
│   │       ├── quick-ticket.md
│   │       ├── create-subtask.md
│   │       ├── add-to-backlog.md
│   │       ├── list-spaces.md
│   │       ├── switch-org.md
│   │       ├── add-org.md
│   │       └── refresh-cache.md
│   ├── github-ticket/                 # GitHub issue management
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/github-ticket/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   └── commands/
│   │       ├── configure.md
│   │       ├── get-issue.md
│   │       ├── list-issues.md
│   │       ├── my-issues.md
│   │       ├── create-issue.md
│   │       ├── quick-issue.md
│   │       ├── add-to-backlog.md
│   │       ├── create-linked-issue.md
│   │       └── route.md
│   ├── repo-docs/                     # Repository harness docs generator
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/repo-docs-generator/
│   │   │   ├── SKILL.md
│   │   │   └── references/           # Harness principles, templates, playbooks
│   │   └── commands/
│   │       ├── generate.md
│   │       └── canonicalize.md
│   ├── visual-explainer/              # HTML visual explainers for mixed audiences
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/visual-explainer/
│   │   │   ├── SKILL.md
│   │   │   ├── references/           # Stakeholder mode, layout, diagram, and slide guidance
│   │   │   ├── scripts/              # Optional publish helpers for hosted previews
│   │   │   └── templates/            # Reference HTML templates
│   │   └── commands/explain.md
│   ├── backend-release/               # Django4Lyfe release workflow
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/release-manager/SKILL.md
│   │   └── commands/
│   │       ├── check.md
│   │       ├── create.md
│   │       └── publish.md
│   ├── dependabot-remediation/        # Unified backend/frontend Dependabot remediation
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/dependabot-remediation/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   └── commands/
│   │       ├── backend.md
│   │       └── frontend.md
│   ├── terraform/                     # Terraform/Terragrunt workflows
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/
│   │   │   ├── terraform-atomic-commit/SKILL.md
│   │   │   └── terraform-pr-workflow/SKILL.md
│   │   └── commands/
│   │       ├── pre-commit.md
│   │       ├── atomic-commit.md
│   │       └── check-pr.md
│   ├── login-cta-attribution-skill/   # CTA login attribution
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/login-cta-attribution-skill/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   └── commands/implement.md
│   ├── frontend/                      # Digest-first frontend skill (all lanes)
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/frontend/
│   │   │   ├── SKILL.md
│   │   │   └── references/
│   │   └── commands/
│   │       ├── work.md
│   │       ├── refresh-digest.md
│   │       ├── review.md
│   │       ├── commit.md
│   │       └── new-branch.md
├── AGENTS.md                          # Source of truth for Claude Code behavior
├── CLAUDE.md                          # Sources AGENTS.md
├── README.md
├── CONTRIBUTING.md
└── LICENSE
```

## Available Plugins

| Plugin | Description |
|--------|-------------|
| `monolith-review-orchestrator` | Monolith-local PR review harness for deep PR understanding, thread-aware GitHub review acquisition, deterministic worker-owned review worktrees, persistent review context, and author-guiding review output |
| `monty-code-review` | Hyper-pedantic Django4Lyfe backend code review Skill with a built-in pytest test-hardening lane and persistent JSON-first review memory |
| `backend-atomic-commit` | Backend pre-commit / atomic-commit Skill with iterative convergence protocol (budgets + stuck detection), enforcing AGENTS.md, pre-commit hooks (including djlint), .security helpers, and repo-local commit hygiene without AI signatures |
| `backend-pr-workflow` | Backend PR workflow Skill that follows repo-local workflow docs, GitHub issue linkage, and migration safety checks |
| `bruno-api` | API endpoint documentation generator from Bruno (`.bru`) files that traces Django4Lyfe implementations (DRF/Django Ninja) |
| `code-review-digest-writer` | Weekly code-review digest writer Skill (repo-agnostic) |
| `plan-directory` | Structured plan directories with PLAN.md index, numbered task files, and RALPH loop integration for iterative execution |
| `pr-description-writer` | Generates comprehensive, reviewer-friendly PR descriptions with diagrams, structured sections, and repo-local workflow context |
| `process-code-review` | Process code review findings - interactively fix or skip issues from monty-code-review output with status tracking |
| `mixpanel-analytics` | MixPanel tracking implementation and review Skill for Django4Lyfe optimo_analytics module with PII protection and pattern enforcement |
| `clickup-ticket` | Legacy ClickUp ticket management during the GitHub work-management migration |
| `github-ticket` | GitHub-native issue management with smart defaults for `monolith`, backlog capture, repo-local execution routing, and project-board hydration |
| `repo-docs` | Generate and canonicalize repository harness docs: short AGENTS.md maps, README.md, CLAUDE.md stubs, and focused repo-local docs for architecture, gates, and runbooks |
| `visual-explainer` | Generate presentation-ready HTML explainers for plans, diffs, diagrams, audits, and stakeholder updates with interactive intake, explicit fact-vs-inference separation, and optional Netlify preview publishing |
| `backend-release` | Django4Lyfe backend release workflow - create release PRs, date-based version bumping (YYYY.MM.DD), and GitHub release publishing |
| `dependabot-remediation` | Unified backend/frontend Dependabot remediation workflow: `.github/dependabot.yml` review/scaffold, backend waves, frontend triage/execute/release, and post-merge closure verification |
| `terraform` | Terraform/Terragrunt workflows: atomic-commit quality gates and PR workflow checks |
| `login-cta-attribution-skill` | CTA login attribution implementation Skill for Django4Lyfe — guides adding new CTA sources, button/tab attribution, and enum registration |
| `frontend` | Digest-first frontend skill with repo classification, dynamic detection, and internal lane routing for review, API, testing, analytics, observability, CI/CD, planning, and commit workflows |

## Available Pi Packages

| Package | Description | Install |
|---------|-------------|---------|
| `ci-status` | Pi-native CI status extension with `/ci`, `/ci-detail`, `/ci-logs`, auto-watch after pushes, widget/status rendering, GitHub Actions + CircleCI support, and LLM CI tools | `pi install "$PWD/pi-packages/ci-status"` |
| `dev-workflow` | Pi-native daily developer workflow with 15 core workflow prompts, `/workflow:help`, `/workflow:run`, `/workflow:prompts`, `/workflow:flow`, XDG/project prompt config, CI analysis, PR review feedback, release PR prep, local skills, and optional pi-subagents chain | `pi install "$PWD/pi-packages/dev-workflow"` |
| `skills-bridge` | Auto-discovers all 21 Claude Code plugin skills from plugins/*/skills/ and registers them as pi skills. One install bridges the gap between the plugin ecosystem and pi | `pi install "$PWD/pi-packages/skills-bridge"` |

## Installation

### 1. Add the marketplace

From your terminal (outside Claude Code):

```bash
claude plugin marketplace add DiversioTeam/agent-skills-marketplace
```

Or from within a Claude Code session:

```
/plugin marketplace add DiversioTeam/agent-skills-marketplace
```

### 2. Install plugins

**Recommended:** Install at user scope (default) for compatibility with git worktrees.
Project-scope plugins don't persist across worktrees.

### Pi-native packages

Pi-native packages live under `pi-packages/` and install with the pi CLI instead
of the Claude Code marketplace. For normal use, install them globally from an
absolute local path:

```bash
pi install "$PWD/pi-packages/ci-status"
pi install "$PWD/pi-packages/dev-workflow"
pi install "$PWD/pi-packages/skills-bridge"
```

Plain `pi install` writes to global user settings. Use `pi -e ./pi-packages/<package>`
for one-off extension testing without changing settings. Use `pi install -l`
only when you need to test project-local install, reload, or persistence
behavior.

Install each pi package in one scope at a time. If `ci-status` is installed
globally and also from a different project-local path, Pi can load both copies
and duplicate `get_ci_status` / `ci_fetch_job_logs` tool registration. Remove
the duplicate project package entry from `.pi/settings.json` or uninstall the
global copy before reloading.

Run `/reload` in pi after installation. See `pi-packages/ci-status/README.md`
and `pi-packages/dev-workflow/README.md` for command inventory, contribution
workflow, and local testing commands.

### Monolith Review Orchestrator

`monolith-review-orchestrator` is a harness-local workflow for Diversio
monolith review work. Read `plugins/monolith-review-orchestrator/README.md`
for prerequisites, helper commands, and usage examples.

If you already use the upstream `visual-explainer` plugin, uninstall it before
installing this marketplace version:

```bash
claude plugin uninstall visual-explainer@visual-explainer-marketplace
```

<details>
<summary><strong>Install All Plugins (CLI commands)</strong></summary>

Copy-paste these commands in your terminal:

```bash
claude plugin install monolith-review-orchestrator@diversiotech
claude plugin install monty-code-review@diversiotech
claude plugin install backend-atomic-commit@diversiotech
claude plugin install backend-pr-workflow@diversiotech
claude plugin install bruno-api@diversiotech
claude plugin install code-review-digest-writer@diversiotech
claude plugin install plan-directory@diversiotech
claude plugin install pr-description-writer@diversiotech
claude plugin install process-code-review@diversiotech
claude plugin install mixpanel-analytics@diversiotech
claude plugin install clickup-ticket@diversiotech
claude plugin install github-ticket@diversiotech
claude plugin install repo-docs@diversiotech
claude plugin install visual-explainer@diversiotech
claude plugin install backend-release@diversiotech
claude plugin install dependabot-remediation@diversiotech
claude plugin install terraform@diversiotech
claude plugin install login-cta-attribution-skill@diversiotech
claude plugin install frontend@diversiotech
```

For project-scoped installation (shared with collaborators via `.claude/settings.json`):

```bash
claude plugin install monty-code-review@diversiotech --scope project
# ... repeat for each plugin
```

</details>

<details>
<summary><strong>Install Individual Plugins</strong></summary>

| Plugin | CLI Command |
|--------|-------------|
| Monolith PR review orchestrator | `claude plugin install monolith-review-orchestrator@diversiotech` |
| Monty backend code review | `claude plugin install monty-code-review@diversiotech` |
| Backend pre-commit / atomic commit | `claude plugin install backend-atomic-commit@diversiotech` |
| Backend PR workflow | `claude plugin install backend-pr-workflow@diversiotech` |
| Bruno API docs generator | `claude plugin install bruno-api@diversiotech` |
| Code review digest writer | `claude plugin install code-review-digest-writer@diversiotech` |
| Plan directory + RALPH loop | `claude plugin install plan-directory@diversiotech` |
| PR description writer | `claude plugin install pr-description-writer@diversiotech` |
| Code review processor | `claude plugin install process-code-review@diversiotech` |
| MixPanel analytics | `claude plugin install mixpanel-analytics@diversiotech` |
| ClickUp ticket management | `claude plugin install clickup-ticket@diversiotech` |
| GitHub issue management | `claude plugin install github-ticket@diversiotech` |
| Repository docs generator | `claude plugin install repo-docs@diversiotech` |
| Visual explainer | `claude plugin install visual-explainer@diversiotech` |
| Backend release workflow | `claude plugin install backend-release@diversiotech` |
| Dependabot remediation (backend/frontend) | `claude plugin install dependabot-remediation@diversiotech` |
| Terraform workflows | `claude plugin install terraform@diversiotech` |
| Login CTA attribution | `claude plugin install login-cta-attribution-skill@diversiotech` |
| Frontend (all lanes) | `claude plugin install frontend@diversiotech` |

</details>

### 3. Use slash commands

Once plugins are installed:

   ```text
   /monolith-review-orchestrator:review-prs    # Monolith-local v1 review harness for one PR or one linked cross-repo PR pair
   /monolith-review-orchestrator:reassess-prs  # Reload structured state and reassess after a PR or linked cross-repo PR pair changes
   /monolith-review-orchestrator:post-review   # Narrow v1 posting path; backend-safe path should reuse Monty machinery
   /monty-code-review:code-review            # Hyper-pedantic backend code review
   /monty-code-review:test-hardening         # Pytest-only dangerous-pattern hardening lane
   /backend-atomic-commit:pre-commit         # Fix backend files to meet AGENTS/pre-commit/.security standards
   /backend-atomic-commit:atomic-commit      # Strict atomic commit helper (all gates green, no AI signature)
   /backend-atomic-commit:commit             # Run all gates, fix, and create commit (full closure)
   /backend-pr-workflow:check-pr             # Backend PR workflow & migrations check
   /bruno-api:docs                           # Generate endpoint docs from Bruno (.bru) files
   /code-review-digest-writer:review-digest  # Generate a code review digest
   /plan-directory:plan                      # Create structured plan directory with PLAN.md
   /plan-directory:backend-ralph-plan        # Create RALPH loop-integrated plan for backend
   /plan-directory:run <slug>                # Execute a RALPH plan via ralph-wiggum loop
   /pr-description-writer:write-pr           # Generate a comprehensive PR description
   /process-code-review:process-review       # Process code review findings (fix/skip issues)
   /mixpanel-analytics:implement             # Implement new MixPanel tracking events
   /mixpanel-analytics:review                # Review MixPanel implementations for compliance
   /clickup-ticket:configure                 # Initial setup and org configuration
   /clickup-ticket:create-ticket             # Full interactive ticket creation
   /clickup-ticket:quick-ticket              # Fast ticket with minimal prompts
   /clickup-ticket:create-subtask            # Add subtask to existing ticket
   /clickup-ticket:add-to-backlog            # Quick add to configured backlog list
   /clickup-ticket:list-spaces               # Browse workspace hierarchy
   /clickup-ticket:switch-org                # Switch between organizations
   /clickup-ticket:add-org                   # Add a new organization
   /clickup-ticket:refresh-cache             # Force refresh cached data
   /github-ticket:configure                  # Configure planning repo, execution repos, project defaults, and labels
   /github-ticket:get-issue                  # Fetch one GitHub issue in detail
   /github-ticket:list-issues                # List/search issues across one repo or a small repo set
   /github-ticket:my-issues                  # Show assigned work across configured repos
   /github-ticket:create-issue               # Create a full issue with canonical sections
   /github-ticket:quick-issue                # Create a minimal issue quickly
   /github-ticket:add-to-backlog             # Capture backlog work in monolith with default labels
   /github-ticket:create-linked-issue        # Create a linked follow-up or execution issue
   /github-ticket:route                      # Route planning work into the right execution repo
   /repo-docs:generate                       # Generate harness docs (AGENTS map + README + CLAUDE + focused docs)
   /repo-docs:canonicalize                   # Audit and fix existing docs (trim AGENTS, normalize CLAUDE, add topic docs)
   /visual-explainer:explain                 # Create a presentation-ready HTML explainer with interactive intake
   /visual-explainer:explain "Auth rollout" --publish --open-url  # Publish a fresh Netlify preview and open it
   /backend-release:check                    # Check what commits are pending release
   /backend-release:create                   # Create release PR with merge method
   /backend-release:publish                  # Publish GitHub release after PR merge
   /dependabot-remediation:backend           # Backend lane: triage (includes config review/scaffold + backend scope filter) | execute-wave <N> | release
   /dependabot-remediation:frontend          # Frontend lane: triage (includes config review/scaffold) | execute | release
   /terraform:pre-commit                     # Fix Terraform/Terragrunt repos to meet fmt/validate/docs standards
   /terraform:atomic-commit                  # Strict atomic commit helper for Terraform/Terragrunt repos
   /terraform:check-pr                       # Terraform/Terragrunt PR workflow check
   /login-cta-attribution-skill:implement   # Add new CTA login attribution source
   /frontend:work                          # Main frontend entrypoint — routes to the correct lane based on arguments
   /frontend:refresh-digest                # Persist a full frontend project digest to docs/frontend-skill-digest/
   /frontend:review                        # Review a frontend PR using the repo-local digest and Bumang-style priorities
   /frontend:commit                        # Create a digest-aware atomic frontend commit with quality gates
   /frontend:new-branch                    # Create a frontend branch using the repo's detected branch model
   ```

## Monty Review Memory

`monty-code-review` now includes persistent JSON-first review memory.

Why this exists:

- PR review is iterative, so the reviewer often comes back after new commits.
- Re-reading every old markdown review wastes tokens and repeats old findings.
- Structured memory lets the skill load only the small amount of prior context
  it actually needs.

Mental model:

```text
resolve target -> load compact memory summary -> run new review
               -> write repo-local *_review.md for humans
               -> persist structured memory for the next pass
```

Important rule:

- Structured JSON/JSONL files are the canonical memory store.
- The repo-local `*_review.md` is still the human-facing artifact and the
  current compatibility input for `process-code-review`.
- The small v1 persistence model is just `state.json` plus `reviews.jsonl`
  inside one deterministic scope directory.

The helper lives at:

- `plugins/monty-code-review/skills/monty-code-review/scripts/review_memory.py`

Useful commands:

```bash
uv run --script plugins/monty-code-review/skills/monty-code-review/scripts/review_memory.py --help

uv run --script plugins/monty-code-review/skills/monty-code-review/scripts/review_memory.py \
  resolve-scope \
  --provider github \
  --host github.com \
  --owner DiversioTeam \
  --repo monolith \
  --pull-number 1842

uv run --script plugins/monty-code-review/skills/monty-code-review/scripts/review_memory.py \
  summarize-context \
  --scope-dir "<resolved-scope-dir>"

cat <<'EOF' | uv run --script plugins/monty-code-review/skills/monty-code-review/scripts/review_memory.py \
  record-review \
  --scope-dir "<resolved-scope-dir>"
{
  "head_sha": "abc123",
  "history_status": "linear",
  "repo_review_file": "docs/code_reviews/pr_1842_review.md",
  "recommendation": "request_changes",
  "findings": {
    "new": [],
    "carried_forward": [],
    "resolved": []
  }
}
EOF
```

For the full protocol, schema, and maintenance rules, read:

- `plugins/monty-code-review/skills/monty-code-review/references/review-memory-protocol.md`

### Uninstall Plugins (Claude Code)

<details>
<summary><strong>Uninstall All Diversio Plugins</strong></summary>

**Step 1: Check what's installed**

```bash
claude plugin list
```

Or inside Claude Code: `/plugin list`

Look for plugins with `@diversiotech` - note the `Scope:` field (user or project).

**Step 2: Uninstall user-scoped plugins**

Copy-paste these commands in your terminal:

```bash
claude plugin uninstall monolith-review-orchestrator@diversiotech
claude plugin uninstall monty-code-review@diversiotech
claude plugin uninstall backend-atomic-commit@diversiotech
claude plugin uninstall backend-pr-workflow@diversiotech
claude plugin uninstall bruno-api@diversiotech
claude plugin uninstall code-review-digest-writer@diversiotech
claude plugin uninstall plan-directory@diversiotech
claude plugin uninstall pr-description-writer@diversiotech
claude plugin uninstall process-code-review@diversiotech
claude plugin uninstall mixpanel-analytics@diversiotech
claude plugin uninstall clickup-ticket@diversiotech
claude plugin uninstall github-ticket@diversiotech
claude plugin uninstall repo-docs@diversiotech
claude plugin uninstall visual-explainer@diversiotech
claude plugin uninstall backend-release@diversiotech
claude plugin uninstall dependabot-remediation@diversiotech
claude plugin uninstall terraform@diversiotech
claude plugin uninstall login-cta-attribution-skill@diversiotech
claude plugin uninstall frontend@diversiotech
```

**Step 3: Uninstall project-scoped plugins (if any)**

If `claude plugin list` shows plugins at `Scope: project`:

```bash
claude plugin uninstall monolith-review-orchestrator@diversiotech --scope project
claude plugin uninstall monty-code-review@diversiotech --scope project
claude plugin uninstall backend-atomic-commit@diversiotech --scope project
claude plugin uninstall backend-pr-workflow@diversiotech --scope project
claude plugin uninstall bruno-api@diversiotech --scope project
claude plugin uninstall code-review-digest-writer@diversiotech --scope project
claude plugin uninstall plan-directory@diversiotech --scope project
claude plugin uninstall pr-description-writer@diversiotech --scope project
claude plugin uninstall process-code-review@diversiotech --scope project
claude plugin uninstall mixpanel-analytics@diversiotech --scope project
claude plugin uninstall clickup-ticket@diversiotech --scope project
claude plugin uninstall github-ticket@diversiotech --scope project
claude plugin uninstall repo-docs@diversiotech --scope project
claude plugin uninstall visual-explainer@diversiotech --scope project
claude plugin uninstall backend-release@diversiotech --scope project
claude plugin uninstall dependabot-remediation@diversiotech --scope project
claude plugin uninstall terraform@diversiotech --scope project
claude plugin uninstall login-cta-attribution-skill@diversiotech --scope project
claude plugin uninstall frontend@diversiotech --scope project
```

</details>

<details>
<summary><strong>Troubleshooting</strong></summary>

| Problem | Solution |
|---------|----------|
| Plugin shows in list but "not found" on uninstall | Try the other scope: `--scope project` or `--scope user` |
| Plugin stuck in disabled state | Enable first (`claude plugin enable ...`), then uninstall |
| Project-scoped plugins don't persist in git worktrees | Uninstall with `--scope project`, reinstall at user scope |
| Manual cleanup needed | Delete `.claude/` directory in project root, or check `~/.claude/` for user config |

</details>

After uninstalling, reinstall using the install commands above.

## Install As Codex Skills

Codex can install these Skills directly from GitHub (separate from Claude's
marketplace) using the Skill Installer.

<details>
<summary><strong>Install All Skills (Codex)</strong></summary>

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

python3 "$CODEX_HOME/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo DiversioTeam/agent-skills-marketplace \
  --ref main \
  --path \
    plugins/monty-code-review/skills/monty-code-review \
    plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator \
    plugins/backend-atomic-commit/skills/backend-atomic-commit \
    plugins/backend-pr-workflow/skills/backend-pr-workflow \
    plugins/bruno-api/skills/bruno-api \
    plugins/code-review-digest-writer/skills/code-review-digest-writer \
    plugins/plan-directory/skills/plan-directory \
    plugins/plan-directory/skills/backend-ralph-plan \
    plugins/pr-description-writer/skills/pr-description-writer \
    plugins/process-code-review/skills/process-code-review \
    plugins/mixpanel-analytics/skills/mixpanel-analytics \
    plugins/clickup-ticket/skills/clickup-ticket \
    plugins/github-ticket/skills/github-ticket \
    plugins/repo-docs/skills/repo-docs-generator \
    plugins/visual-explainer/skills/visual-explainer \
    plugins/backend-release/skills/release-manager \
    plugins/dependabot-remediation/skills/dependabot-remediation \
    plugins/terraform/skills/terraform-atomic-commit \
    plugins/terraform/skills/terraform-pr-workflow \
    plugins/login-cta-attribution-skill/skills/login-cta-attribution-skill \
    plugins/frontend/skills/frontend
```

**Codex console alternative:**

```text
$skill-installer install from github repo=DiversioTeam/agent-skills-marketplace \
  path=plugins/monty-code-review/skills/monty-code-review \
  path=plugins/monolith-review-orchestrator/skills/monolith-review-orchestrator \
  path=plugins/backend-atomic-commit/skills/backend-atomic-commit \
  path=plugins/backend-pr-workflow/skills/backend-pr-workflow \
  path=plugins/bruno-api/skills/bruno-api \
  path=plugins/code-review-digest-writer/skills/code-review-digest-writer \
  path=plugins/plan-directory/skills/plan-directory \
  path=plugins/plan-directory/skills/backend-ralph-plan \
  path=plugins/pr-description-writer/skills/pr-description-writer \
  path=plugins/process-code-review/skills/process-code-review \
  path=plugins/mixpanel-analytics/skills/mixpanel-analytics \
  path=plugins/clickup-ticket/skills/clickup-ticket \
  path=plugins/github-ticket/skills/github-ticket \
  path=plugins/repo-docs/skills/repo-docs-generator \
  path=plugins/visual-explainer/skills/visual-explainer \
  path=plugins/backend-release/skills/release-manager \
  path=plugins/dependabot-remediation/skills/dependabot-remediation \
  path=plugins/terraform/skills/terraform-atomic-commit \
  path=plugins/terraform/skills/terraform-pr-workflow \
  path=plugins/login-cta-attribution-skill/skills/login-cta-attribution-skill \
  path=plugins/frontend/skills/frontend
```

</details>

<details>
<summary><strong>Install Individual Skills (Codex)</strong></summary>

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

python3 "$CODEX_HOME/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo DiversioTeam/agent-skills-marketplace \
  --path plugins/monty-code-review/skills/monty-code-review
```

Or from the Codex console:

```text
$skill-installer install from github repo=DiversioTeam/agent-skills-marketplace path=plugins/monty-code-review/skills/monty-code-review
```

</details>

<details>
<summary><strong>Uninstall All Skills (Codex)</strong></summary>

```bash
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
rm -rf "$CODEX_HOME/skills/monty-code-review" \
       "$CODEX_HOME/skills/monolith-review-orchestrator" \
       "$CODEX_HOME/skills/backend-atomic-commit" \
       "$CODEX_HOME/skills/backend-pr-workflow" \
       "$CODEX_HOME/skills/bruno-api" \
       "$CODEX_HOME/skills/code-review-digest-writer" \
       "$CODEX_HOME/skills/plan-directory" \
       "$CODEX_HOME/skills/backend-ralph-plan" \
       "$CODEX_HOME/skills/pr-description-writer" \
       "$CODEX_HOME/skills/process-code-review" \
       "$CODEX_HOME/skills/mixpanel-analytics" \
       "$CODEX_HOME/skills/clickup-ticket" \
       "$CODEX_HOME/skills/github-ticket" \
       "$CODEX_HOME/skills/repo-docs-generator" \
       "$CODEX_HOME/skills/visual-explainer" \
       "$CODEX_HOME/skills/release-manager" \
       "$CODEX_HOME/skills/dependabot-remediation" \
       "$CODEX_HOME/skills/terraform-atomic-commit" \
       "$CODEX_HOME/skills/terraform-pr-workflow" \
       "$CODEX_HOME/skills/login-cta-attribution-skill" \
       "$CODEX_HOME/skills/frontend"
echo "Done. Restart Codex and reinstall skills."
```

</details>

**Notes:**
- Add `--ref <branch-or-tag>` to pin a version.
- The installer does not overwrite existing Skills; delete `$CODEX_HOME/skills/<skill-name>` first to update.
- If you are replacing the upstream `visual-explainer` skill, delete
  `$CODEX_HOME/skills/visual-explainer` first, then install this repo's
  version.
- Codex installs Skills into `~/.codex/skills` by default.
- Restart Codex after installing Skills.

## Documentation

- [Agent Skills Standard](https://agentskills.io/specification)
- [Agent Skills Best Practices](https://agentskills.io/best-practices)
- [Claude Agent Skills Best Practices](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices)
- [OpenAI Codex Skills](https://developers.openai.com/codex/skills)
- [OpenAI Codex Skills (Install new skills)](https://developers.openai.com/codex/skills#install-new-skills)
- [Claude Agent Skills Overview](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)
- [Claude Code Plugins](https://code.claude.com/docs/en/plugins)
- [Discover and Install Plugins](https://code.claude.com/docs/en/discover-plugins)
- [Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Agent Skills](https://code.claude.com/docs/en/skills)

## License

MIT License - see [LICENSE](LICENSE) for details.
