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
