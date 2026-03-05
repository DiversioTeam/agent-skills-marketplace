---
description: Create or update a structured plan directory with master index and numbered task files.
---

Use your `plan-directory` Skill to create or maintain a structured project plan.

Every create/update run must end with a fresh-eyes self-review of the plan so
obvious gaps, ordering mistakes, hidden blockers, and weak tests are fixed
before delivery.

## Modes

- **Create:** Scaffold a new plan directory with `PLAN.md` and numbered task files.
- **Update:** Add tasks, mark progress, or modify an existing plan.
- **Status:** Show current progress across all tasks in a plan.

## Options

- `--location <path>` - specify the target directory (default: `docs/plans/<slug>/`).
- `--dry-run` - show what would be created without writing files.
- `--archive` - mark a completed plan as archived.

## Common Operations

**Create a new plan:**
> Create a plan for implementing user authentication with JWT tokens

**Add a task to existing plan:**
> Add a new task for Google OAuth to the user-auth plan

**Mark task complete:**
> Mark task 003 in user-auth as complete

**Check plan status:**
> What's the current status of the user-auth plan?

**Add a blocker:**
> Task 004 in user-auth is blocked waiting for the API key from platform team

**Archive completed plan:**
> Archive the user-auth plan - it's complete

## Required Inputs (New Plans)

- Plan title and slug
- Task list with names and scopes
- Any locked decisions or constraints
- Testing expectations (optional)

For updates, specify the plan slug or path and the change to make.
