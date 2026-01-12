---
description: Generate a comprehensive PR description using the pr-description-writer Skill.
argument-hint: "[pr-number] [--update|--create]"
---

Use your `pr-description-writer` Skill to create or update a PR description.

## Arguments

- `<pr-number>` (optional): Specific PR to update. If omitted, use the current
  branch's PR if it exists; otherwise prepare a description for a new PR.
- `--update`: If set, apply the generated description to the PR using `gh pr edit`.
- `--create`: If set, create a new PR using `gh pr create`.

## Workflow (Thin Wrapper)

1. Gather PR + branch context (base branch, commits, diffs, staged/unstaged, existing PR body/files).
   - Exact commands live in: `plugins/pr-description-writer/skills/pr-description-writer/references/gh-cli.md`.
2. Generate the PR description using the structure and rules in the `pr-description-writer` Skill.
3. Output the full markdown body (copy/paste ready for GitHub).
4. If requested (or `--update`/`--create` is passed), update/create the PR using `gh` (see the reference file above).

## Requirements

- Cover **all** changes (base..HEAD plus any uncommitted work the user intends to include).
- Include a clear test plan (automated + manual) and call out risks/breaking changes/deploy steps.
