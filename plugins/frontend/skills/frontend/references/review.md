# PR Review Lane

Review frontend PRs against the current repo's actual workflow, stack, and
quality gates.

## Step 1: Load PR Context

If the user provides a PR number, inspect it with GitHub metadata and diff.
Otherwise review the current branch diff or ask for the PR number.

Collect:
- title and body
- head and base branches
- changed files
- commits
- repo class from the digest
- affected package(s) when this is a monorepo

### Thread-Aware Review Acquisition

Collect existing review state via `gh api`:
- inline review threads (pending, resolved, outdated)
- resolved comments and their resolution status
- author replies to previous review comments

Use this context to avoid re-raising resolved issues and to track whether
prior feedback was addressed.

## Step 2: Determine The Right Review Shape

Use the digest to decide which standards apply.

### `frontend-app`

Focus on:
- user-visible behavior
- API/use-case contracts
- app-level testing and release readiness

### `design-system`

Focus on:
- consumer-facing contract changes
- unpublished dependency expectations
- release/versioning implications
- visual semantics and accessibility

### `monorepo-frontend`

Focus on:
- affected packages and boundaries
- workspace-aware commands
- app <-> design-system compatibility

If the digest says the repo is only partially applicable for this task, say so
explicitly instead of forcing a generic app checklist.

## Step 3: Template & Workflow Compliance

Check PR process using this precedence:

1. repo-local PR template or workflow docs
2. workflow conventions recorded in the digest
3. current branch/PR metadata

Review:
- base/head branch pairing
- issue linkage when the repo expects it
- required PR body sections or release-body shape
- preview/sandbox/backend-branch fields only when this repo uses them
- placeholder text or stale plan text

If the repo's PR process differs from the old `feature -> dev` / `dev -> main`
model, the repo wins.

## Step 4: Review The Code Using Bumang-Style Lenses

Prioritize in this order:

1. shipped contract vs stated intent
2. dependency readiness and publish/consume compatibility
3. user-visible semantics and accessibility
4. regression test quality at the consumer layer
5. local consistency for naming, imports, identifiers, and docs

Concrete things to check:
- hidden UI or design-token contract regressions
- app code depending on a design-system capability that is not actually shipped
- docs or PR text that contradict the final implementation
- missing consumer-level regression tests for bugs observed in the UI contract
- unstable or duplicate query/mutation keys
- naming and import patterns that fight the repo norm

See `review-taste.md` for the full review heuristic set.

## Step 5: Commit Hygiene

Check commit quality relative to repo standards:
- conventional-commit format when the repo uses it
- no WIP/fixup noise in a final PR
- no AI co-author signatures
- commits are reasonably atomic

Do not treat a non-conventional message as a failure unless the repo uses that
rule.

## Step 6: Run The Right Quality Gates

Use the digest's commands. Examples:
- lint
- type-check
- unit/component tests
- package-scoped checks in a monorepo

Never hardcode `yarn lint` or `yarn type-check` unless the digest says that is
correct for this repo.

## Step 7: Output The Review

Produce a structured report:

```markdown
# PR Review: #<number-or-branch>

## Repo Context
- Repo class:
- Digest status: reused | refreshed | ephemeral
- Affected package(s):

## Workflow Compliance
- Pass/fail items tied to repo-local expectations

## Review Findings
1. **[Critical/Warning/Nit]** issue summary -- file:line

## Quality Gates
- Lint:
- Type-check:
- Tests:

## Verdict
- APPROVED
- REQUEST CHANGES
- COMMENT
```

Keep findings grounded in the repo's actual stack and review taste.
