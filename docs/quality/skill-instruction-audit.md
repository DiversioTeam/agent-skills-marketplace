# Skill Instruction Audit

Scope: all 24 repository-owned `SKILL.md` entrypoints (22 marketplace skills
and two Pi-local skills), with affected references, wrappers, workflow prompts,
and distribution metadata. External installed skills are not modified.

Source: Eric Provencher / OpenAI, September 11, 2026,
[Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra).
This is an instruction audit, not a model benchmark. The article's observations
are attributed in the repo-docs skill's portable
[model guidance](../../plugins/repo-docs/skills/repo-docs-generator/references/model-guidance.md).

## Findings And Changes

All descriptions now state a short purpose and specific trigger. Long mode
procedures move behind task routes where useful; single-purpose workflows keep
ordering that protects correctness. No new universal preflight or model switch
is added to every skill.

| Skill | Additional change or reason to retain the workflow |
|---|---|
| backend-atomic-commit | Validation reference retains hook-first execution, cache identity, type gates, bounded retries, and commit modes. |
| backend-pr-workflow | Discover inputs before asking; release and migration references load only for those changes. |
| release-manager | Retain captured-SHA attribution, exact-head validation, publication and deployment boundaries. |
| bruno-api | Default to documentation in the response; ask only for ambiguous endpoint scope or consequential output layout. |
| clickup-ticket | Route to the requested command; preserve interactive creation versus quick defaults and read-only inspection. |
| code-review-digest-writer | Derive clear reporting dates; retain evidence, partial-data labeling, and docs-only scope. |
| crafting-sandboxes | Retain live discovery, ownership, data-replacement consent, and readiness evidence. |
| dependabot-remediation | Output follows the requested mode, without fabricated execution/release sections; retain wave and closure gates. |
| frontend | Load only applicable lane references; preserve digest freshness, ephemeral fallback, and refresh-only persistence. |
| github-ticket | Route command modes separately; preserve repository routing, project fields, and partial-success reporting. |
| login-cta-attribution-skill | Retain the single-purpose registration and propagation order, platform distinctions, and type/test gates. |
| mixpanel-analytics | Retain identity, producer, tenant, privacy, post-commit delivery, and telemetry-enablement contracts. |
| monolith-review-orchestrator | Route execution detail by mode; require evidence-backed simplicity findings and the current or bundled Python clarity guide in all Python slices and handoffs. Retain worktree safety, thread history, structured memory, and worker-owned posting. |
| monty-code-review | Remove forced nits/praise quotas and simulated-tool evidence; use relevant review lenses without weakening tenant/schema rules. |
| backend-ralph-plan | Activate for an explicitly requested Ralph plan; derive discoverable inputs. Plan generation does not start execution. |
| plan-directory | Derive title, slug, and task breakdown; move templates out of the entrypoint. Preserve index/task consistency. |
| pr-description-writer | Retain full-PR evidence, optional visuals, asset consent, and draft/publication distinctions. |
| process-code-review | Honor --auto without per-finding prompts; retain interactive and dry-run modes. Avoid duplicate check passes. |
| repo-docs-generator | Add source-dated model guidance, task-routed templates, verified safe-action permissions, and explicit completion. Thin wrappers defer to the skill. |
| terraform-atomic-commit | Retain module-scoped validation, atomicity, and no infrastructure apply. |
| terraform-pr-workflow | Retain plan evidence, read-only PR checks, interface/versioning and rollout requirements. |
| visual-explainer | Stop activating HTML merely for table size; use the mixed-audience default. Preserve source verification and explicit publishing. |
| ci | Narrow remote-CI trigger; missing checks stay unknown and truncated logs are not an inspected tail. |
| dev-workflow | Route requested passes; avoid mandatory full sequences and documentation per file. Prompts/chain retain scope and publication boundaries. |

## Safety And Completion

The refresh removes generic friction, not authority checks. Required type gates
(`ty` first when configured), tenant/privacy controls, exact-target release
proof, review-thread identity, snapshot consent, and publish/deploy boundaries
remain. Explicit interactive modes and read-only reviews remain intentional.

Repo-docs may describe a safe local test permission only after verifying the
actual suite's fixture isolation, credentials, external effects, and cost.
Astra's reported thoroughness is not a substitute for required tests or proof.
Unchanged inputs may reuse valid checks; changed inputs and required wider gates
need their own evidence. Missing setup and unsafe operations remain blockers.

## Validation Scope

Use [quality gates](gates.md) for the commands. Check all skill budgets, JSON and
version synchronization, local reference links, wrapper/prompt consistency,
package contents, native Pi command discovery, and the website build. Versions
are bumped from fetched `origin/main`, not stale local marketing metadata.

Local results for this refresh:

- All 24 entrypoints pass the 500-line guardrail; total root content shrank
  from 6,160 to 4,807 lines (about 22%). Most removed entrypoint detail remains
  available on demand.
- Changed JSON, 20 plugin/marketplace/website versions, and all 22 website
  skill descriptions match; changed Markdown link paths pass outside examples.
- Package preview includes the new workflow reference in `dev-workflow` 0.0.8.
- Native Pi discovery registers 20 unique workflow commands. This checkout lacked
  `pi-cmux`; the check temporarily linked the existing installed dependency and
  removed that link afterward. No dependency or lockfile changes were needed.
- The website builds all 80 pages; diff whitespace checks pass.
- The orchestrator's bundled Python clarity guide matches the source byte for
  byte and its documented SHA-256. Its source commit and precedence are explicit.
- Fresh-eyes review verified moved sections against the fetched base and fixed
  ship ordering across the prompt, reference, and chain: commit/push before PR
  publication, then required CI for the final remote head. TypeScript parsing
  and prompt-order/safety assertions pass. The missing-guide blocker now applies
  only when neither the local guide nor the bundled fallback is available.

Static checks and native discovery do not establish model activation accuracy,
fewer unnecessary questions in real sessions, or equivalent behavior across
models. Those require representative task runs: a small docs fix, a scoped
implementation, a read-only review, and an explicitly authorized ship flow.
Do not perform live publication or deployment merely to evaluate a skill.
