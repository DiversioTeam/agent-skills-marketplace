# Monolith Review Orchestrator

Monolith-local PR review workflow for deep understanding, thread-aware GitHub
review history, persistent review context, deterministic worktree reuse, and
reviewer-friendly final output.

Use this plugin when the goal is not just to skim a diff, but to:

- deeply understand the PR and the back-and-forth review history
- treat resolved comments as important context, not noise
- reassess incrementally after new commits
- post clearer, more instructive GitHub reviews and inline comments

## What It Figures Out For You

The normal path should not require the user to think about worktree names,
cursor pagination, or local repo layout.

```text
you provide:
  - PR URL(s)
  - review intent
  - whether posting is allowed

the plugin figures out:
  - review batch identity
  - linked-pair metadata when two PRs must be reviewed together
  - live PR head SHAs before local checkout
  - worktree reuse or preparation
  - thread-aware GitHub review history
  - durable local review context
  - what changed since the last pass
```

That is why the example prompts below focus on the review ask, not the setup
mechanics.

## Best Inputs

The workflow is strongest when your prompt includes:

- the PR URL
- linked PR URLs when the change spans repos
- whether this is `status`, `review`, `reassess`, or `post`
- for linked PRs: why they are linked and which PR is authoritative if the
  verdicts diverge
- whether GitHub posting is allowed in this run

Only mention a local worktree or submodule path when you explicitly want the
plugin to reuse a specific local setup instead of resolving or preparing one
itself.

## Example Prompts

### 1. Deep PR Understanding

```text
Please deeply understand https://github.com/DiversioTeam/Django4Lyfe/pull/2779.

Read the PR thoroughly, including all review comments and replies. Treat resolved comments as context too. Tell me the real current status: what is fixed, what is still legitimate, and what earlier feedback is now moot.
```

### 2. Linked Cross-Repo Review

```text
Please deeply understand these linked PRs and review them together:

https://github.com/DiversioTeam/Django4Lyfe/pull/2779
https://github.com/DiversioTeam/Optimo-Frontend/pull/389

Read all comments and resolved threads, verify the author's claims against the current code, and review the end-to-end behavior with no compromises.
```

### 3. Thorough Review Pass

```text
Use monolith-review-orchestrator in review mode for https://github.com/DiversioTeam/Django4Lyfe/pull/2779.

Do a very thorough review. Reuse prior review context if it exists. I want business-logic issues, contract issues, tests, reuse opportunities, and any real edge cases, not just style feedback.
```

### 4. Reassessment After New Commits

```text
The author pushed updates to https://github.com/DiversioTeam/Django4Lyfe/pull/2779.

Please reassess it using the existing review context. Focus on deltas, re-check prior findings, and tell me exactly what is newly resolved, still open, newly introduced, or now moot.
```

### 5. Post Final Review

```text
Now post the final GitHub review for https://github.com/DiversioTeam/Django4Lyfe/pull/2779.

Keep one authoritative top-level review and use inline comments where they help. Teach the author: explain the problem, why it matters, and the next step. Approve only if there are no legitimate blocking issues left.
```

### 6. Status-Only Read

```text
Use monolith-review-orchestrator in status mode for https://github.com/DiversioTeam/Optimo-Frontend/pull/389.

I do not want a fresh full review yet. I want the final status based on the current code plus the entire review history, including resolved threads.
```

## Slash Commands

If you prefer slash commands:

```text
/monolith-review-orchestrator:review-prs
/monolith-review-orchestrator:reassess-prs
/monolith-review-orchestrator:post-review
```

Then provide the same concrete PR URLs and review intent in the prompt that
follows.

## Notes

- The plugin uses a thread-aware GitHub acquisition helper when GitHub auth is
  available, and that deterministic path currently uses `gh`.
- The cache is strongest when you reuse the same deterministic review worktree
  and batch state across passes.
- Worktree prep should fail closed unless each review submodule is detached at
  the exact PR head SHA being reviewed.
- `post` should only run after current-head validation plus a prior substantive
  pass on the same heads, and it should consume the live-state validation token
  from that check while it is still fresh. That validation now re-reads GitHub
  from the thread-helper artifact instead of trusting caller-typed state.
- This plugin is still intentionally narrow on generic non-backend posting and
  broad multi-PR automation.

## Why These Pieces Exist

```text
fetch_review_threads.py
  reads the real review discussion, including resolved/outdated threads

review_state.py
  keeps the reusable memory of what we learned

SKILL.md + references/
  explain when to use the workflow and how to interpret its output
```

Without the fetch helper, the review cache would be downstream of an incomplete
read path. Without the review-state helper, every reassessment would have to
reconstruct prior context from scratch.

## Related Files

- Skill: `skills/monolith-review-orchestrator/SKILL.md`
- Review context protocol:
  `skills/monolith-review-orchestrator/references/review-context-protocol.md`
- Workflow helpers:
  `skills/monolith-review-orchestrator/references/workflow-helpers.md`
