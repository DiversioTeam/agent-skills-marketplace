---
description: "Write a reviewer-friendly PR description with preferred tldraw offline visuals."
argument-hint: "[pr-number] [--update|--create] [--setup]"
---

Use the `pr-description-writer` skill for $ARGUMENTS.
Gather the full PR and repo-local workflow context. Prefer tldraw offline for
useful visuals; if unavailable, offer its installation/open flow or a Mermaid
fallback as described by the skill. Return copy-paste-ready Markdown and visual
asset status. Distinguish remote PR content from pending local work.
Only publish the body when requested or `--update`/`--create` is passed;
preserve the existing PR's base and draft/readiness state.
`--setup` (or plain language such as "add e2e setup") asks for the skill's
optional local setup section.
