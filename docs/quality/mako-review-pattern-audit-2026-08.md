# Mako review-pattern audit — 2026-08-24

## Scope

- Author: `MakoSlay`
- Org: `DiversioTeam`
- Inclusion rule: every accessible PR authored by this account with activity on or after `2026-05-28`, including older PRs with qualifying later review activity
- Source method: GitHub search + per-PR REST/GraphQL review collection performed during the 2026-08-24 audit session
- Durable artifact: this document is the committed summary; session-local scratch ledgers and raw corpus files were intentionally not committed

## Corpus summary

- Candidate PRs: **34**
- Repos: Django4Lyfe (29), diversio-ds (2), Diversio-Frontend (1), monolith (1), agent-skills-marketplace (1)
- PRs with post-cutoff review/comment activity: **31**
- Captured post-cutoff events:
  - issue comments: **138**
  - submitted reviews: **356**
  - inline comments: **362**
  - GraphQL review threads: **313**
- PRs with substantive external coding findings: **17**
- PRs with only approvals, automation/status chatter, or no external coding findings: **17**

## Complete PR inventory

| Repo / PR | State | Created | Updated | Post-cutoff issue comments | reviews | inline comments |
|---|---|---:|---:|---:|---:|---:|
| DiversioTeam/diversio-ds#1016 | merged | 2026-05-11 | 2026-05-29 | 1 | 0 | 0 |
| DiversioTeam/Django4Lyfe#2957 | merged | 2026-05-11 | 2026-06-01 | 0 | 0 | 0 |
| DiversioTeam/Django4Lyfe#2997 | merged | 2026-05-26 | 2026-06-01 | 0 | 0 | 0 |
| DiversioTeam/diversio-ds#1015 | merged | 2026-05-11 | 2026-06-01 | 1 | 0 | 0 |
| DiversioTeam/Diversio-Frontend#1800 | merged | 2026-05-11 | 2026-06-01 | 1 | 1 | 0 |
| DiversioTeam/Django4Lyfe#3017 | merged | 2026-06-03 | 2026-06-05 | 4 | 23 | 24 |
| DiversioTeam/Django4Lyfe#2949 | closed | 2026-05-07 | 2026-06-08 | 24 | 58 | 45 |
| DiversioTeam/Django4Lyfe#2882 | open | 2026-04-20 | 2026-06-14 | 7 | 9 | 4 |
| DiversioTeam/Django4Lyfe#2677 | open | 2026-02-17 | 2026-06-14 | 3 | 0 | 0 |
| DiversioTeam/Django4Lyfe#2670 | open | 2026-02-12 | 2026-06-14 | 3 | 0 | 0 |
| DiversioTeam/Django4Lyfe#2396 | open | 2025-09-19 | 2026-06-14 | 2 | 0 | 0 |
| DiversioTeam/Django4Lyfe#2974 | merged | 2026-05-15 | 2026-06-15 | 5 | 5 | 3 |
| DiversioTeam/Django4Lyfe#3040 | merged | 2026-06-08 | 2026-06-15 | 6 | 9 | 8 |
| DiversioTeam/Django4Lyfe#3041 | merged | 2026-06-08 | 2026-06-15 | 8 | 7 | 0 |
| DiversioTeam/Django4Lyfe#3160 | open | 2026-07-06 | 2026-07-09 | 1 | 0 | 0 |
| DiversioTeam/Django4Lyfe#2627 | open | 2026-01-30 | 2026-07-13 | 3 | 0 | 0 |
| DiversioTeam/Django4Lyfe#3077 | merged | 2026-06-15 | 2026-07-13 | 5 | 8 | 6 |
| DiversioTeam/Django4Lyfe#3079 | merged | 2026-06-16 | 2026-07-13 | 7 | 24 | 23 |
| DiversioTeam/monolith#399 | open | 2026-07-30 | 2026-07-30 | 1 | 0 | 0 |
| DiversioTeam/Django4Lyfe#3194 | merged | 2026-07-29 | 2026-07-30 | 1 | 2 | 0 |
| DiversioTeam/Django4Lyfe#3200 | merged | 2026-08-06 | 2026-08-07 | 1 | 2 | 0 |
| DiversioTeam/Django4Lyfe#3036 | open | 2026-06-08 | 2026-08-17 | 1 | 1 | 20 |
| DiversioTeam/Django4Lyfe#3037 | open | 2026-06-08 | 2026-08-17 | 1 | 1 | 18 |
| DiversioTeam/Django4Lyfe#3215 | closed | 2026-08-17 | 2026-08-18 | 1 | 0 | 0 |
| DiversioTeam/Django4Lyfe#3035 | open | 2026-06-08 | 2026-08-19 | 3 | 59 | 72 |
| DiversioTeam/Django4Lyfe#3197 | open | 2026-08-05 | 2026-08-20 | 3 | 5 | 9 |
| DiversioTeam/Django4Lyfe#3034 | open | 2026-06-08 | 2026-08-21 | 18 | 26 | 23 |
| DiversioTeam/Django4Lyfe#3167 | open | 2026-07-10 | 2026-08-21 | 4 | 43 | 45 |
| DiversioTeam/Django4Lyfe#3081 | closed | 2026-06-16 | 2026-08-21 | 4 | 25 | 21 |
| DiversioTeam/Django4Lyfe#3038 | closed | 2026-06-08 | 2026-08-21 | 15 | 43 | 38 |
| DiversioTeam/Django4Lyfe#3217 | open | 2026-08-18 | 2026-08-21 | 1 | 0 | 0 |
| DiversioTeam/agent-skills-marketplace#81 | open | 2026-05-17 | 2026-08-24 | 0 | 0 | 0 |
| DiversioTeam/Django4Lyfe#3199 | open | 2026-08-06 | 2026-08-24 | 1 | 1 | 1 |
| DiversioTeam/Django4Lyfe#3218 | merged | 2026-08-19 | 2026-08-24 | 2 | 4 | 2 |

## Recurring issue taxonomy

Counts below are **independent PR counts**, not repeated rounds in one thread.
These were synthesized from the detailed ledgers in batches A-E.

| Rank | Root problem | Independent PRs | Representative PRs | Natural owner |
|---|---|---:|---|---|
| 1 | Contract/lifecycle/parallel-path mismatch: a rule changed in one path but not in sibling consumers, rollback, cache, import/export, or UI/runtime contract | **13** | #2949, #3017, #3035, #3040, #3041, #3079, #3081, #3167, #3197 | `contract-propagation-check` |
| 2 | Low-value or mis-targeted tests: framework smoke tests, plumbing mocks, helper-only coverage, missing real-path regressions | **11** | #3034, #3035, #3036, #3037, #3077, #3167 | `test-quality-check` |
| 3 | Failure to reuse existing abstractions/constants/types/fixtures | **10** | #2949, #3035, #3036, #3037, #3038, #3079, #3167, #3197 | `codebase-reuse-finder` |
| 4 | Historical/legacy/rollback state not handled safely | **9** | #2882, #2949, #3017, #3035, #3040, #3041, #3079, #3197 | `historical-data-check` |
| 5 | Concurrency / transaction-scope / destructive-order bugs | **6** | #2882, #3017, #3035, #3038, #3197 | `contract-propagation-check` |
| 6 | Stable shapes weakened with `Any`, weak mappings, positional identity, or missing precise types | **5** | #3035, #3036, #3037, #3167, #3197 | `monty-v2-code-review` + `codebase-reuse-finder` |
| 7 | Over-defensive/speculative guards, broad catches, unused flags/wrappers | **5** | #2949, #3035, #3036, #3081, #3197 | `monty-v2-code-review` + `contract-propagation-check` |
| 8 | Merge/rebase drift or stale branch debris | **4** | #3034, #3035, #3038, #3079 | `merge-drift-check` |
| 9 | Review freshness / unresolved-thread workflow gaps | **6** | #3017, #3035, #3036, #3037, #3167, #3197 | already owned by `pr-review-fix`, `commit-and-reply`, `pr-status` |

## Skill coverage assessment

### Updated

- `plugins/contract-propagation-check/skills/contract-propagation-check/SKILL.md`
  - added transaction-scope checks, external-I/O-under-lock detection, and explicit rejection of speculative boundary handling on stable internal contracts
- `plugins/gate-runner/skills/gate-runner/SKILL.md`
  - switched to PR-base detection and made mergeability diagnosis read-only
- `plugins/moe-skills/skills/codebase-reuse-finder/SKILL.md`
  - expanded from constants-only scanning to stable types, existing clients/helpers, repeated setup/query logic, and framework-native reuse
- `plugins/moe-skills/skills/pr-review-fix/SKILL.md`
  - changed from comment-local fixes to root-cause + sibling-occurrence closure with explicit specialist routing
- `plugins/monty-v2-code-review/skills/monty-v2-code-review/SKILL.md`
  - switched to PR-base detection, full-branch stable-type/necessity/reuse sweeps, and a canonical P1-P29 blind-spot reference
- `plugins/monty-v2-code-review/skills/monty-v2-code-review/references/blind-spot-patterns.md`
  - extended the blind-spot catalog to P29 with precise stable shapes, evidence-based defensive code, and repository/framework reuse
- `plugins/review-delegator/skills/review-delegator/SKILL.md`
  - added evidence-based reuse/precise-type routing and a new historical-pattern routing reference
- `plugins/test-quality-check/skills/test-quality-check/SKILL.md`
  - broadened from branch coverage to production-path behavior, fixture/setup economy, framework/plumbing-test rejection, and rollback-vs-savepoint guidance

### Reviewed but left unchanged

- `historical-data-check`
  - still the correct owner for legacy rows, rollback/reprocess, and config reuse; no wording change needed after the new routing changes
- `merge-drift-check`
  - still the correct owner for version/lockfile/unrelated-file drift; no wording change needed beyond delegator/monty routing improvements
- `commit-and-reply`
  - already owns resolved/outdated-thread catch-up and duplicate-reply hygiene
- `pr-status`
  - already owns freshness-first PR/review/CI status reporting

## Marketplace changes made

Version bumps were applied and kept in sync between each plugin manifest and `.claude-plugin/marketplace.json`:

- `contract-propagation-check` `1.0.1 -> 1.0.2`
- `gate-runner` `1.0.0 -> 1.0.1`
- `moe-skills` `0.9.1 -> 0.9.2`
- `monty-v2-code-review` `2.6.0 -> 2.6.1`
- `review-delegator` `1.0.2 -> 1.0.3`
- `test-quality-check` `1.0.0 -> 1.0.1`

Also updated:

- `.claude-plugin/marketplace.json`
- `docs/plugins/catalog.md`
- `README.md`
- affected command wrappers for the changed skills

## Remaining gaps and confidence

### Remaining gaps

- `review-delegator` is still near the line-budget warning threshold (474 lines) and should move more transport/risk detail into references before the next expansion.
- `historical-data-check` and `merge-drift-check` were left semantically unchanged because routing/owner clarity, not check content, was the main gap found in this pass.
- `pr-status` and `commit-and-reply` were reviewed but not changed; the detected workflow problems were mainly usage/closure issues, not obvious missing instructions in those two skills.

### Confidence

- **High** that the updated skills will catch the most frequent code-review roots earlier:
  - contract/lifecycle mismatches
  - low-value test coverage
  - missed existing abstractions/types
  - broad/speculative defensive code
  - stable-shape `Any` regressions
- **Medium** for workflow/freshness issues because those depend partly on how operators invoke `pr-review-fix`, `commit-and-reply`, and `pr-status`.

## Validation run

- `bash scripts/validate-skills.sh`
- `jq -e . .claude-plugin/marketplace.json`
- `jq -e . plugins/{contract-propagation-check,gate-runner,moe-skills,monty-v2-code-review,review-delegator,test-quality-check}/.claude-plugin/plugin.json`
- version-sync check between plugin manifests and marketplace entries
- `git diff --check -- plugins .claude-plugin docs/plugins/catalog.md README.md`

Result: validation passed. `review-delegator` remains under the 500-line hard limit but above the 450-line warning threshold.
