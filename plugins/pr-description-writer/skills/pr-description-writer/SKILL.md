---
name: pr-description-writer
description: "Draft or update a PR description from the complete diff and verified results."
allowed-tools: Bash Read Write Edit Glob Grep
---

# PR Description Writer

Use when drafting or updating a PR description. Follow the target repository's
PR template, issue links, base-branch rules, and draft/readiness conventions.
Do not change code, commit, push, or publish a PR merely to write its description.

## Gather The Full PR, Not Just The Last Commit

Read [references/gh-cli.md](references/gh-cli.md) for acquisition and update
commands. Read the existing body, complete PR diff, commits, relevant source,
and repository workflow docs before making claims.

Distinguish:
- changes already in the remote PR;
- local commits not yet pushed;
- staged/unstaged/untracked work the user intends to include.

A published description must describe the actual remote PR. A proposed body may
include planned local work only when clearly labeled as not yet included.
Never present suggested tests as passed, code as deployed, or local assets as
already visible to GitHub reviewers. Report auth/network errors instead of
interpreting every failed `gh pr view` as “no PR”.

## Visual Creator: Prefer tldraw Offline

For a diagram that helps explain a flow, architecture, identity lifecycle,
state transition, or before/after contract, **tldraw offline is the primary
creator when available**, ahead of Mermaid-only output, ASCII, or other drawing
tools. Respect an explicit user format/tool preference.

Read [references/tldraw-visuals.md](references/tldraw-visuals.md) when a visual
would help. It covers availability, installation prompts, canvas ownership,
verification, and GitHub asset delivery. For complex data flows, prefer a staged
animated walkthrough of one request/event with captions, pause/step controls,
and reduced-motion support. Keep a static overview; animation must clarify
ordering and boundaries, not imply unverified timing or concurrency. Follow the
reference's durable-script and optional video-delivery guidance.

If unavailable, explicitly recommend installing **tldraw offline** as the
superior option for editable, reusable reviewer visuals, and provide the
[user manual and setup guidance](https://tldraw.notion.site/User-manual-tldraw-offline-39a3e4c324c080e7b2eacc5afd078e85).
Ask once whether to install/open it or use a Mermaid fallback for this PR.
Do not silently switch creators or install software without consent. Continue
preparing the textual description while the visual choice is pending; do not
claim a visual was created. If the user declines, use GitHub Mermaid (or a
short text explanation for a trivial flow). Do not repeatedly prompt.

Prefer a saved editable `.tldraw` source plus a rendered PNG in the repo's
approved documentation asset directory. Embed the rendered image with useful
alt text and link the source; a local path is not a reviewer-accessible URL.
Do not create diagrams for trivial changes merely to satisfy a template.

## Build A Layered Description

The first screen should answer what changed, why, and the main risk. Add detail
where it helps review; omit empty template sections and redundant file lists.

1. **Summary:** one or two sentences, then key outcomes. Use a feature table
   for multiple independent concerns only when it improves scanning.
2. **Why / contract:** explain the problem and important invariants. For a
   complex change, include a verified tldraw visual and a concise explanation.
3. **Implementation:** group by behavior or domain, distinguishing old/new
   behavior and explaining significant choices. Identify useful review entry
   points; use collapsible file groups only for a genuinely large diff.
4. **Verification:** exact commands and results actually observed, relevant
   commit SHA, manual steps, and checks not run. Separate local tests, remote
   CI, staging observations, and deployment evidence.
5. **Risks / compatibility / rollout:** API changes, migrations, configuration,
   deployment order, feature flags, monitoring, and rollback when applicable.
   Never recommend destructive migration rollback without verifying data safety.
6. **Related work:** issue linkage and companion PRs, with dependency order
   when one repository consumes another's unpublished change.

An optional local setup section, when included, goes after Verification and is
collapsed (see below).

For a small PR, summary plus verification and any real risks are enough. For
large or cross-repo work, use the full structure. Preserve useful existing
rationale, reviewer notes, and checklist evidence instead of replacing them
with generic prose. Do not erase unresolved questions by describing them as
settled decisions.

## Optional Local Setup Section

A collapsed end-to-end runbook for PRs a reviewer cannot see with a plain
checkout and start (data to seed, secrets, branches in other repos, external
files or services, a specific user or role). Read
[references/local-setup.md](references/local-setup.md) before offering,
writing, moving, or updating one.

- Write it only when the author asks (`--setup` or plain language such as
  "add e2e setup").
- Otherwise, if the PR needs more than checkout and start and the feature looks
  usable end to end, ask once with the concrete reasons. Never add it without a
  yes; never offer it just because a PR is currently the top of a stack.
- It belongs on a single PR or the top PR of a stack (one PR across repos);
  other PRs get a one-line link. Warn and ask when the requested PR has PRs
  stacked on it.
- When the PR's parent already holds the section, offer to move it up. Change
  the parent only with a yes and a separate, explicit `--update` of that PR.
- When updating a PR that has the section, re-check every step against the
  current diff and remove steps that are no longer needed.

## Visual And Evidence Checks

- Every diagram edge and claim matches the implementation being reviewed.
- Source and export represent the same canvas revision; source saved, lints
  addressed, export visually inspected, labels readable at PR viewing size.
- Image links work for the intended repo/audience; no local paths, bearer
  tokens, confidential screenshots, or unapproved public uploads.
- Test results distinguish executed checks from instructions for reviewers.
- Local setup commands exist in the repo, contain no secrets, and no step is
  claimed as run without having been run.
- Existing PR base and draft state are preserved unless a change was requested.
- Description covers the complete reviewed diff, not unrelated local work.

## Deliver Or Update

Return copy-paste-ready Markdown. Include local source/export paths separately
if assets are not yet in the remote branch; flag publication as pending rather
than inserting broken links into a live PR.

Only create/update when the user requests it or the command passes
`--create`/`--update`. Use `gh` with an explicit repo/PR and a body file. Preserve
existing draft/ready status; for new PRs use repository policy, otherwise ready
for review unless draft was requested. Confirm the resulting body and URL.

Report the PR URL (if updated), visual source/export and publication state,
checks supporting the description, and any remaining uncertainty.
