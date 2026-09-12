---
name: monty-code-review
description: "Review Django backend changes for correctness, tenant safety, contracts, and migration risk."
allowed-tools: Bash Read Edit Glob Grep
---

# Monty Code Review Skill (Backend)

## When to Use This Skill

- Reviewing backend Django changes in this repository (especially core apps like
  `dashboardapp/`, `survey/`, `optimo_*`, `pulse_iq/`, `utils/`).
- Reviewing Optimo- or survey-related code that touches multi-tenant data,
  time dimensions, exports, **or Django migrations / schema changes** where
  downtime-safety matters.
- Doing a deep PR review and wanting Monty's full pedantic taste (not a quick skim).
- An explicit request for Monty's review of a backend design or refactor;
  ordinary implementation alone does not activate this review workflow.

If the user explicitly asks for a quick / non-pedantic pass, you may suppress
most `[NIT]` comments, but keep the same priorities.

## Core Taste & Priorities

Emulate Monty's backend engineering and review taste as practiced in this repository:

- Business-first, correctness-first: simple, obviously-correct code beats clever abstractions.
- Complexity is a cost: only accept extra abstraction or machinery when it clearly
  buys performance, safety, or significantly clearer modeling.
- Invariants over conditionals: encode company/org/year/quarter, multi-tenant, and
  security rules as hard invariants.
- Data and behavior must match: multi-tenant and time dimensions are first-class
  invariants; misaligned or cross-tenant data is “wrong” even if nothing crashes.
- Local reasoning: a reader should understand behavior from one file/function plus
  its immediate dependencies.
- Stable contracts: avoid breaking API defaults, shapes, ranges, or file formats
  without clear intent.
- Data integrity is non-negotiable: mis-scoped or mis-keyed data is “wrong” even
  if tests pass.
- Testing as contracts: tests should capture business promises, realistic data,
  edge cases, and regressions.
- Agent legibility matters: when a non-obvious invariant or workflow only lives
  in tribal knowledge, weak docs and weak guardrails are part of the defect.

Always prioritize issues in this order:

1. Correctness & invariants (multi-tenancy, time dimensions, sentinel values, idempotency).
2. Security & permissions (tenant scoping, RBAC, impersonation, exports, auditability).
3. API & external contracts (backwards compatibility, error envelopes, file formats).
4. Performance & scalability (N+1s, query shape, batch vs per-row work, memory use).
5. Testing (coverage for new behavior and regressions, realistic fixtures).
6. Maintainability & clarity (naming, structure, reuse of helpers).
7. Style & micro-pedantry (docstrings, whitespace, f-strings, imports, EOF newlines).

Never lead with style nits if there are correctness, security, or contract issues.

## Pedantic Review Workflow

When this skill is active and you are asked to review a change or diff, follow this workflow:

1. Understand intent and context
   - Read the PR description, ticket, design doc, or docstrings that explain what
     the code is supposed to do.
   - Read `AGENTS.md` and any linked repo-local docs/specs/runbooks that define
     architecture, invariants, or quality gates for the changed area.
   - Scan nearby modules/functions to understand existing patterns and helpers that
     this code should align with.
   - Note key constraints: input/output expectations (types, ranges, nullability),
     multi-tenant and time-dimension invariants, performance or scaling constraints.

2. Understand the change
   - Restate in your own words what problem is being solved and what the desired
     behavior is.
   - Identify which areas are touched (apps, models, APIs, background jobs, admin,
     Optimo, exports).
   - Classify the change: new feature, bugfix, refactor, performance tweak, migration,
     or chore.

3. Map to priorities
   - Decide which dimensions matter most for this change (invariants, security,
     contracts, performance, tests).
   - Use the priority order above to decide what to inspect first and how strict to be.

4. Compare code against rules (per file / area)
   - For each touched file or logical area:
     - Use the relevant checks in [review lenses](references/review-lenses.md).
     - Report evidence-backed findings and useful strengths, not a quota per file.

5. Check tooling & static analysis
   - Run relevant tooling when permitted by the review scope and environment.
     Code inspection is not execution evidence; report checks not run.
   - Detect Python type checker in this order unless repo docs/CI differ:
     - `ty`, then `pyright`, then `mypy`.
   - If `ty` is configured in the repo, treat it as mandatory and blocking.
   - Treat any violations that indicate correctness, security, or contract issues as
     at least `[SHOULD_FIX]`, and often `[BLOCKING]`.
   - Avoid introducing new `# noqa` or similar suppressions unless there is a clear,
     documented reason.

6. Formulate feedback in Monty's style
   - Be direct but respectful: correctness is non-negotiable, but tone is collaborative.
   - Use specific, actionable comments that point to exact lines/blocks and show how
     to fix them, ideally with concrete code suggestions or minimal diffs.
   - Tie important comments back to principles (e.g., multi-tenant safety, data
     integrity, contract stability).
   - Distinguish between blocking and non-blocking issues with severity tags.

7. Summarize recommendation
   - Give an overall assessment (e.g., “solid idea but correctness issues”, “mostly nits”,
     “needs tests”).
   - State whether you would “approve after nits”, “request changes”, or “approve as-is”.

## Pytest Test-Hardening Lane

Use this lane when changed files include pytest tests (`test_*.py`, `*_test.py`,
`tests/**/*.py`, `conftest.py`) or when the user asks for pytest hardening.

Lane contract:
- First, verify `.bin/pytest-file-selector` exists in the target repo.
  If it does not, stop and tell the user the repo has not adopted the pytest
  hardening lane yet.
- Use `.bin/pytest-file-selector` to build the file set (single source of truth).
  - Default (no args): changed-files-only (branch diff + staged + unstaged + untracked).
  - `--all` flag: full-repo scan (opt-in only).
  - `--base <ref>`: override base branch (strict — exits 1 if ref is invalid, no fallback).
  - Exit 1 on unresolvable base or branch-diff failure (fail-closed).
- If the script outputs zero files, return out-of-scope and stop.
- Do NOT build your own file list — always delegate to this script.

Detection and review strategy:
- Primary detection should be structural (`ast-grep` patterns) where possible.
- Use `rg` as fallback/triage heuristics only.
- Do not emit high-noise heuristic matches as standalone findings without context
  proof (for example raw `sum(` / `len(` and raw `monkeypatch.setattr(`).

For this lane, focus especially on silent-pass patterns and include wrong/correct
snippet suggestions in findings.

Required output columns for pytest hardening findings:
- `Severity` (`[BLOCKING]`, `[SHOULD_FIX]`, `[NIT]`)
- `Pattern`
- `File:Line`
- `Detector`
- `Risk`
- `Safe Fix`

For pattern definitions and canonical wrong/correct snippets, load:
- `references/pytest-dangerous-patterns.md`

## GitHub Posting Protocol (When User Asks To Post Review Comments)

When user intent includes posting comments/reviews to GitHub PRs, load and follow:

- `references/github-posting-protocol.md`

Non-negotiables:

- Keep one authoritative top-level summary review.
- Keep one inline anchor per root-cause cluster.
- Run duplicate audits before and after posting.
- Use slurped pagination (`--paginate --slurp`) for post-audit dedupe commands.
- Treat pass condition as strict: both post-audit duplicate detector results must be empty.

## Review Memory

Persistent review memory is default-on for this skill.

- Resolve a deterministic memory target before reviewing, then load/update JSON-first
  memory via the `click`-based `scripts/review_memory.py` helper using
  `uv run --script`.
- Keep the repo-local `*_review.md` as the human/process artifact, but treat the
  structured memory store as the canonical persistent history.
- Store canonical timestamps in UTC and present times to the engineer in local time.
- Ask one short clarifying question instead of assuming whenever ambiguity would change
  memory identity or dedupe behavior.
- Do not ask for ordinary review judgment calls.

For the full protocol and on-disk schema, load:

- `references/review-memory-protocol.md`

## Output Shape, Severity Tags & Markdown File

When producing a full review with this skill, you **must** write the review into a Markdown
file in the target repository (not just respond in chat), using the structure below.
- If the user specifies a filename or path, respect that.
- If they do not, choose a clear, descriptive `.md` filename (for example based on the
  ticket or branch name) and create or update that file with the full review.

Then, within that Markdown file, be explicitly pedantic and follow this shape:

1. Short intro
   - One short paragraph summarizing what the change does and which dimensions you
     focused on (correctness, multi-tenancy, performance, tests, etc.).

2. What’s great
   - A section titled `What’s great`.
   - Include specific positive decisions when useful, with file/area evidence.
     Do not manufacture praise to fill a minimum count.

3. What could be improved
   - A section titled `What could be improved`.
   - Group comments by area/file when helpful (e.g., `dashboardapp/views/v2/...`,
     `survey/tests/...`).
   - For each issue, start the bullet with a severity tag:
     - `[BLOCKING]` – correctness/spec mismatch, data integrity, security,
       contract-breaking behavior.
     - `[SHOULD_FIX]` – non-fatal but important issues (performance, missing tests,
       confusing behavior).
     - `[NIT]` – small style, naming, or structure nits that don’t block merge.

   - After the severity tag, include:
     - File + function/class + line(s) if available.
     - A 1–3 sentence explanation of why this matters.
     - A concrete suggestion or snippet where helpful.

4. Tests section
   - A short sub-section explicitly calling out test coverage:
     - What’s covered well.
     - What important scenarios are missing.

5. Verdict
   - End with a section titled `Verdict` or `Overall`.
   - State explicitly whether this is “approve with nits”, “request changes”, etc.

## Severity & Prioritization Rules

Use these tags consistently:

- `[BLOCKING]`
  - Multi-tenant boundary violations (wrong org/company filter, missing `organization=…`).
  - Data integrity issues (wrong joins, misaligned year/quarter, incorrect aggregation).
  - Unsafe migrations or downtime-risky schema changes (destructive changes in the
    same deploy as dependent code; large-table defaults that will lock or rewrite
    the table).
  - Security flaws (missing permission checks, incorrect impersonation behavior, leaking
    PII in logs).
  - Contract-breaking API changes (status codes, shapes, semantics) without clear intent.
- `[SHOULD_FIX]`
  - Performance issues with clear negative impact (N+1s on hot paths, unnecessary
    per-row queries).
  - Missing tests for critical branches or regression scenarios.
  - Confusing control flow or naming that obscures invariants or intent.
  - Missing or stale repo-local docs for non-obvious invariants, workflows, or
    architecture boundaries that reviewers/agents need to infer correctly.
  - Repeated review issues that should become docs, wrappers, lint rules, or
    CI guardrails.
  - Type-check debt that is not currently breaking merge gates but should be
    reduced before follow-up work.
- `[NIT]`
  - Docstring tone/punctuation, minor style deviations, f-string usage, import order.
  - Non-critical duplication that could be refactored later.
  - Minor logging wording or variable naming tweaks.

If a change has any `[BLOCKING]` items, your summary verdict should indicate that it
should not be merged until they are addressed (or explicitly accepted with justification).

## Review Lenses

Read [review lenses](references/review-lenses.md) for the dimensions relevant
to the diff: tenant/time invariants, API contracts, typing, tests, imports,
logging, and schema rollout. Migration changes require the migration lens.
These are evidence checks, not a quota of nits or reasons to broaden the diff.

## SOLID Principles

When reviewing code, check for SOLID violations. If you spot concrete-client
instantiation, kitchen-sink services, repeated platform branching, mock/prod contract
drift, or overly wide interfaces, load `SOLID_principles.md` for the detailed
checklists and examples.

## Examples

Load `references/review-examples.md` for concrete prompt variants and output sketches.

## Compatibility Notes

Works with Claude Code via the plugin slash commands and with Codex via
`name: monty-code-review`. For installation, see this repo's `README.md`.
