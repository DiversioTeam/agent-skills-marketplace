# Review-Delegator Multi-Lane Transport

## Goal

Make `review-delegator` run delegated review checks in parallel helper lanes.

The transport should autodetect the best available mechanism and fall back
cleanly when a mechanism is missing.

## What The User Wants

- Keep **all model behavior changes in `review-delegator` only**.
- The delegator runs helper work through `subagent` transport when available, then
  can use `pi-intercom` for lane stop/decision handoff.
- If `pi-subagents` is missing, degrade to cmux fallback; if cmux is also unavailable,
  degrade to inline sequential review.
- Lanes are optional, driven by PR size/risk and feature flag:
  - `--lanes=auto` (default): enable lanes for medium/high-risk reviews,
    disable for low-risk small reviews.
  - `--lanes=on`: always attempt lane transport.
  - `--lanes=off`: force inline-only.
- Split layout should stay readable: right first, then down on the right, max ~4 visible panes.
- Default reviewer lane roles should be concise and machine-comprehensible.

## Architecture Decision: Transport Abstraction

The delegator does **not** think "subagents OR cmux." It thinks:

> "I need parallel review lanes. Use the best available transport."

Internal abstraction: `spawnReviewLane(role, prompt) -> LaneHandle`

| Capability detected | Transport used | Parent sees |
|---|---|---|
| `subagent` tool present | `subagent({ agent: "reviewer", task, context: "fresh" })` | Native subagent result + status tracking |
| `subagent` unavailable, inside cmux + `pi-intercom` available | Seeded cmux split + intercom coordination | `intercom` message stream, including `ask/ reply` prompts and stop signals |
| `subagent` unavailable, inside cmux, no `pi-intercom` | Seeded cmux split + shared markdown artifact | Parent reads artifact after child writes |
| `subagent` unavailable, no cmux | Inline sequential review passes | Same-session multi-pass review |

## Transport Detail: Seeded cmux Split (Fallback)

When a cmux split opens as a review lane:

1. Open split (right, then down if already split right).
2. Child session starts Pi in the same cwd.
3. Child receives a seeded handoff message:
   - same working directory
   - current git branch
   - short `git status --snapshot`
   - the review prompt + scope
   - parent session model (when available)
4. Child names itself (`/name reviewer-<n>`) for intercom targeting.
5. Child runs the review prompt, reports findings.
6. Child session closes itself when done (`exit` after writing artifact).

## Result Coordination (Fallback)

### When `pi-intercom` is available

- Parent sends review prompt via `intercom send`.
- Child returns findings via `intercom send`.
- If child needs a decision, it uses `intercom ask`.
- Parent synthesizes all findings.

### When `pi-intercom` is NOT available

- Parent writes review prompt into a stable artifact path.
- Child reads that prompt, runs review, writes findings to artifact.
- Parent polls/reads that artifact after the child session finishes.

Artifact layout:

```
.pi/delegator-runs/<run-id>/
├── reviewer-1-prompt.md     # parent writes this before spawning
├── reviewer-1-findings.md   # child writes this
├── reviewer-2-prompt.md
├── reviewer-2-findings.md
├── reviewer-3-prompt.md
├── reviewer-3-findings.md
└── synthesis.md             # parent writes final synthesis
```

## Split Layout Strategy

| Helper lanes | Layout | Rationale |
|---|---|---|
| 1 lane | Split right | Clean single side column |
| 2 lanes | Split right, then split down on right | Two stacked review panes on right |
| 3 lanes | Split right, split down on right (top), split down on right (middle) | Three stacked panes |
| 4 lanes | Split right, split down right → two columns of two | Grid; still readable |
| 5+ lanes | **DO NOT split.** Use workspace tabs or reduce parallelism. | Too cluttered |

Default: max **3** parallel review lanes in cmux fallback mode.

## Default Review Lanes (v1)

| Lane | Role | Prompt Angle |
|---|---|---|
| `reviewer-1` | correctness / regressions | Inspect diff for bugs, edge cases, contract violations |
| `reviewer-2` | tests / validation | Inspect test quality, coverage gaps, assertion strength |
| `reviewer-3` | simplicity / maintainability | Inspect for unnecessary complexity, duplication, readability |

## Fallback Chain (Single Lane)

```text
1. subagent tool present?
   → YES: launch async fresh-context reviewer subagent
   → NO:  go to 2

2. Inside cmux?
   → YES: spawn seeded cmux split
         → pi-intercom available?
           → YES: coordinate via intercom
           → NO:  coordinate via shared markdown artifacts
   → NO:  go to 3

3. Run inline sequential review passes in current session
```

### Duplicate detection policy (best-effort deterministic)
- Normalize each finding into a dedupe key:
  `severity | file | issue_class | anchor_line | short_issue_hash`
- If two findings produce same key, keep one instance (prefer richer evidence).
- If same issue_class appears across >=2 lanes or across monty + lanes, emit
  as `[SYSTEMIC]` and mark severity as at least `[SHOULD_FIX]`.
- Do not let a higher-priority source suppress a finding with stronger evidence.


## Constraints

- Model is owned exclusively by `review-delegator` (no changes in review-orchestrator).
- The parent session is the **sole synthesizer** and the **sole writer**.
- Helper lanes are **read-only** — they inspect and report, never edit files.
- If a child encounters an unapproved product/scope decision, it escalates
  via `intercom ask` (if available) or `ESCALATE` artifact flag; never guess.
- No helper lane runs its own subagent orchestration.
- Children do not post to GitHub, create commits, or mutate the repo.

- Full-check policy:
  - `--quick` = mandatory monty core + guard checks for PRs with obvious risk markers.
  - `auto` = PR classification drives lanes: small/low-risk stays monty-only,
    medium/high-risk runs lane set.
  - `--deep` = all Tier-1 + Tier-2 lanes + explicit bias pass.
  - `--self-review` = enforce bias-first and full evidence-before-accept requirement.

## Non-Goals for v1

- Workspace-tab fallback (splits only for cmux mode).
- 5+ helper lanes.
- Resume / restart of completed cmux sessions.
- Async status tracking for cmux lanes (subagent mode already has it).
- Custom agent creation or chain files.
- Frontend-specific review lanes.

## Dependencies

| Dependency | Role | Required? |
|---|---|---|
| `pi-subagents` | Subagent transport | Best path; not required |
| `oh-my-pi` / `@diversio/pi-cmux` | cmux split primitives | Required for cmux fallback |
| `pi-intercom` | cmux session coordination | Optional; improves cmux fallback |
| `review-delegator` | Orchestrator logic | Base plugin being extended |

## Related Skills (Do Not Duplicate)

| Existing skill | What it already does | Overlap? |
|---|---|---|
| `pi-subagents` | Generic subagent orchestration | Reuse; do not rebuild |
| `dev-workflow` | Workflow prompts + cmux split for subagent-style commands | Refer to its cmux lane pattern |
| `oh-my-pi` | Explicit user-facing cmux split/workspace commands | `@diversio/pi-cmux` shared dep |
| `monolith-review-orchestrator` | Monolith PR review with optional parallel sidecars | Different scope; not duplicated |
| `pi-intercom` | Session-to-session messaging | Use as coordination layer in cmux fallback |
