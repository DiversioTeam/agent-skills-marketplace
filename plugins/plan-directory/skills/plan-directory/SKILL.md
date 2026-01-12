---
name: plan-directory
description: "Create or update a structured plan directory with a PLAN.md index and numbered task files (001-*.md) containing checklists, tests, and completion criteria."
allowed-tools: Read Write Edit Glob Bash
---

# Plan Directory Skill

## When to Use This Skill

- Scaffolding a new project, feature, or migration that benefits from a
  structured, step-by-step plan.
- Creating a repeatable plan that an LLM or engineer can execute with
  explicit, verifiable checkboxes.
- Maintaining an existing plan directory: adding tasks, updating progress,
  or archiving completed plans.
- When the user says "create a plan", "scaffold a plan", "plan this feature",
  or similar intent implying structured task breakdown.

Do **not** use this skill for ad-hoc todo lists, single-file notes, or when
the user explicitly wants a different format.

## LLM Intake (Required Inputs)

Before writing any files, gather these inputs. If any are missing, **ask**
the user for them explicitly.

| Input | Required | Description |
|-------|----------|-------------|
| Plan title | Yes | Human-readable name (e.g., "User Authentication Overhaul") |
| Plan slug | Yes | Hyphenated directory/file slug (e.g., `user-auth-overhaul`) |
| Target location | No | Directory path; defaults to `docs/plans/<slug>/` or `plans/<slug>/` |
| Task list | Yes | List of tasks with short names and scopes |
| Locked decisions | No | Key constraints or choices that must not change |
| Testing expectations | No | Commands, subsets, or manual QA requirements |

When updating an existing plan, read the current `PLAN.md` first to understand
context before modifying.

## Invariants (Do Not Violate)

1. **PLAN.md is the index, not the content.** It contains only the purpose,
   usage instructions, locked decisions, and a task index with checkboxes.
   Detailed steps live in individual task files.

2. **Task files use 3-digit numbering.** Format: `NNN-<slug>.md` where `NNN`
   is zero-padded (001, 002, ..., 999) and `<slug>` is hyphenated lowercase.

3. **Every task file has six sections.** Goal, Scope, Checklist, Tests,
   Completion Criteria, and Dependencies. All are required (use "None" for
   Dependencies if truly independent, "N/A" for Tests only with justification).

4. **Checkboxes are the only status markers.** Do not add "Status: Done"
   fields, emoji indicators, or separate progress sections. Check `- [x]`
   when complete, leave `- [ ]` when pending.

5. **Mirror completion in PLAN.md.** When all checklist items in a task file
   are checked, check the corresponding task in PLAN.md.

6. **Do not renumber existing tasks.** Once a task number is assigned and
   work has started, it is permanent. Append new tasks at the end.

7. **Keep task files self-contained.** A reader should understand the task
   from the file alone without reading other task files.

8. **Track blockers explicitly.** When a task is blocked, add a `## Blockers`
   section describing what's blocking and link to the blocking task or issue.

## Workflow

### 1. Determine Mode: Create or Update

- **Create:** No plan directory exists. Scaffold everything from scratch.
- **Update:** `PLAN.md` already exists. Read it, understand the current
  state, and make targeted modifications.

### 2. Validate Inputs

- Confirm all required inputs are present.
- If the user provides a vague task list, ask for clarification before
  proceeding.
- For updates, verify the plan slug and location match the existing plan.

### 3. Create or Update the Plan Directory

**For new plans:**
1. Create the directory at the target location.
2. Write `PLAN.md` with the master index.
3. Write each task file (`001-*.md`, `002-*.md`, etc.).

**For updates:**
1. Read the existing `PLAN.md` and relevant task files.
2. Apply changes: add new tasks, update checklists, check completed items.
3. Ensure PLAN.md index stays in sync with task files.

### 4. Fill PLAN.md (Master Index)

Keep it minimal. Include only:
- **Purpose:** 1-3 bullets on why the plan exists.
- **How to use:** Brief instructions for working the plan.
- **Decisions (locked):** Key constraints that should not change.
- **Task Index:** Checkbox list linking to task files.
- **Completion:** Definition of when the entire plan is done.

### 5. Fill Task Files

Each task file must include:
- **Goal:** Single sentence describing the outcome.
- **Dependencies:** List of task numbers that must complete first, or "None".
- **Scope:** Bulleted list of what's in scope (and optionally out of scope).
- **Checklist:** 3-8 concrete, actionable steps with checkboxes.
- **Tests:** Specific test commands, files, or manual QA steps.
- **Completion Criteria:** Measurable definitions of done.
- **Notes (optional):** Constraints, references, warnings.
- **Blockers (optional):** Added when work is blocked; removed when unblocked.

### 6. Maintain Progress

As work completes:
1. Check items in the task file's Checklist and Tests sections.
2. When all items are checked, check the Completion Criteria items.
3. Check the corresponding task in PLAN.md's Task Index.

## Task Sizing Rules

- **Target 3-8 checklist items per task.** This keeps tasks focused and
  completable in a reasonable session.
- **Split if exceeding 10 items.** If a task grows beyond ~10 checklist
  items, break it into subtasks.
- **Tests must be explicit.** Include runnable commands or specific file
  paths. Avoid vague "test that it works" items.
- **Completion criteria must be measurable.** Use "X is true" or "Y passes"
  rather than narrative descriptions.

## Update Rules (Existing Plans)

| Scenario | Rule |
|----------|------|
| Adding tasks | Append at the end with the next number |
| Removing tasks | Mark as "[REMOVED]" in PLAN.md; delete file only if user requests |
| Renaming tasks | Update both the task file and PLAN.md index entry |
| Reordering tasks | Do not renumber; use dependencies or notes to indicate order changes |
| Splitting tasks | Create new task files; mark original as "[SPLIT]" pointing to new tasks |

## Templates

### PLAN.md

```markdown
# <Plan Title> - Master Plan

## Purpose

- <Why this plan exists>
- <What it delivers when complete>

## How to Use

1. Work tasks in order unless dependencies indicate otherwise.
2. Check items in task files as they are completed.
3. This file is the index only; details live in task files.

## Decisions (Locked)

- <Key constraint or choice that should not change>
- <Another locked decision>

## Task Index

- [ ] 001 - <Task Name> (`001-<slug>.md`)
- [ ] 002 - <Task Name> (`002-<slug>.md`)
- [ ] 003 - <Task Name> (`003-<slug>.md`)

## Completion

- [ ] All tasks in the index are checked.
- [ ] All tests listed in task files pass.
- [ ] <Any additional project-specific completion criteria>
```

### Task File (NNN-<slug>.md)

```markdown
# NNN - <Task Name>

## Goal

<Single sentence describing the outcome of this task.>

## Dependencies

- Requires: 001, 002 (or "None" if independent)
- Blocks: 004, 005 (tasks waiting on this one)

## Scope

**In scope:**
- <What this task covers>
- <Another in-scope item>

**Out of scope:**
- <What this task explicitly does not cover>

## Checklist

- [ ] <Concrete implementation step with verifiable outcome>
- [ ] <Another concrete step>
- [ ] <Another concrete step>

## Tests

- [ ] Run `<test command>` and verify all pass
- [ ] Manual QA: <specific verification step>

## Completion Criteria

- [ ] <Measurable definition of done>
- [ ] <Another measurable definition>

## Notes

- <Optional: constraints, references, links, or warnings>
```

### Blocked Task (when work cannot proceed)

When a task is blocked, add a `## Blockers` section immediately after Dependencies:

```markdown
## Blockers

- **Blocked by:** External API not yet available (ETA: 2024-02-15)
- **Blocked by:** Waiting on 003 to complete first
- **Action needed:** Contact platform team for API access
```

Remove the Blockers section when the task is unblocked.

## References

- Advanced guidance and examples: [references/advanced.md](references/advanced.md)

## Compatibility Notes

This Skill is designed to work with both Claude Code and OpenAI Codex.

- Claude Code: install the corresponding plugin and use its slash commands (see `plugins/plan-directory/commands/`).
- Codex: install the Skill directory and invoke `name: plan-directory`.

For installation, see this repo's `README.md`.
