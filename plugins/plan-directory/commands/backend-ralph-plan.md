---
description: Create a structured plan with Ralph Wiggum Loop integration for backend Django projects.
---

Use your `backend-ralph-plan` Skill to create a plan directory with Ralph integration.

## What This Creates

1. **PLAN.md** - Task index with quality tracking tables
2. **RALPH-PROMPT.md** - The prompt to feed to `/ralph-wiggum:ralph-loop`
3. **Task files** (001-*.md, 002-*.md, ...) - Standard plan-directory format

## Two-Step Process

**Step 1:** This skill creates the plan structure

**Step 2:** Run it:
```
/plan-directory:run <slug>
```

The `run` command automatically extracts the correct completion promise from
RALPH-PROMPT.md (e.g., `ALL 4 USER-PREFERENCES TASKS COMPLETE`).

## Required Inputs

- Plan title and slug
- Task list with names and scopes
- Django app path (e.g., `optimo_surveys/`)
- Module path (e.g., `digest/`)
- Test filter (e.g., `"digest"`)

## Tooling Configuration

Specify your project's commands (defaults shown):

| Setting | Default | Example with .bin/ wrapper |
|---------|---------|---------------------------|
| Lint | `ruff check` | `.bin/ruff check` |
| Format | `ruff format` | `.bin/ruff format` |
| Types | `ty` | `.bin/ty` |
| Tests | `pytest` | `.bin/pytest` |
| Django | `django` | `.bin/django` |
| Test config | (none) | `--dc=TestLocalApp` |
| Coverage target | 90% | 90% |

## Example

> Create a backend-ralph-plan for adding user notifications.
>
> Title: User Notifications
> Slug: user-notifications
> App path: optimo_notifications/
> Module: notifications/
> Test filter: "notification"
>
> Tasks:
> 1. Notification model
> 2. Email sender service
> 3. Slack integration
> 4. Preferences API
> 5. Scheduler job
> 6. Integration tests
>
> Tooling: Use .bin/ wrappers, pytest config --dc=TestLocalApp

## After Creating the Plan

Run it:
```
/plan-directory:run <slug>
```

## Related Commands

- `/plan-directory:plan` - Base plan without Ralph integration
- `/plan-directory:run` - Execute a RALPH plan (auto-invokes ralph-loop)
- `/ralph-wiggum:cancel-ralph` - Cancel an active Ralph loop
