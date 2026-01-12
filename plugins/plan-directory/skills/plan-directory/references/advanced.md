# Plan Directory — Advanced Guidance

This file is referenced from `SKILL.md` to keep the main Skill short and portable.

## Quality Checklist (LLM Preflight)

Before delivering a plan, verify:

- [ ] All required inputs were gathered or reasonable defaults applied.
- [ ] PLAN.md is short and contains only the index, not detailed steps.
- [ ] Task filenames match the pattern `NNN-<slug>.md` with 3-digit padding.
- [ ] Every task file has all six required sections (Goal, Dependencies,
      Scope, Checklist, Tests, Completion Criteria).
- [ ] Dependencies are explicitly stated (even if "None").
- [ ] Checklist items are concrete and verifiable, not vague.
- [ ] Tests section contains runnable commands or specific QA steps.
- [ ] Completion criteria are measurable, not narrative.
- [ ] PLAN.md Task Index matches the task files exactly.
- [ ] No task exceeds ~10 checklist items (split if needed).
- [ ] Dependency graph has no cycles (task A can't depend on B if B depends on A).
- [ ] Parallel-executable tasks are identified where applicable.

## Parallel Task Execution

Some tasks can run concurrently if they have no dependencies on each other.
Indicate this in PLAN.md using a parallel block notation:

```markdown
## Task Index

- [ ] 001 - Database setup (`001-db-setup.md`)
- [ ] 002 - Frontend scaffolding (`002-frontend-scaffold.md`) [parallel: 001]
- [ ] 003 - API design (`003-api-design.md`) [parallel: 001, 002]
- [ ] 004 - Integration (`004-integration.md`) [after: 001, 002, 003]
```

The `[parallel: NNN]` tag means "can run at the same time as task NNN".
The `[after: NNN]` tag means "must wait for NNN to complete".

When working a plan:
- Start all tasks marked parallel that have no unmet dependencies.
- Track progress on parallel tasks independently.
- Only start `[after: ...]` tasks when all listed dependencies are checked.

## Examples

### Example 1 - Creating a New Plan

**User prompt:**
> "Create a plan for adding user authentication to my app. Use JWT tokens,
> store users in PostgreSQL, and include password reset flow."

**Expected behavior:**
1. Ask for any missing inputs (e.g., preferred directory, additional tasks).
2. Create `docs/plans/user-auth/` (or user-specified location).
3. Write `PLAN.md` with the task index.
4. Write task files like:
   - `001-user-model.md` - Create User model and migrations
   - `002-jwt-setup.md` - Configure JWT authentication
   - `003-login-endpoint.md` - Implement login/logout endpoints
   - `004-password-reset.md` - Implement password reset flow
   - `005-integration-tests.md` - Write integration tests

**Output structure:**
```
docs/plans/user-auth/
  PLAN.md
  001-user-model.md
  002-jwt-setup.md
  003-login-endpoint.md
  004-password-reset.md
  005-integration-tests.md
```

### Example 2 - Updating an Existing Plan

**User prompt:**
> "Add a new task to the user-auth plan for implementing OAuth with Google."

**Expected behavior:**
1. Read the existing `PLAN.md` to understand current state.
2. Determine the next task number (e.g., 006).
3. Create `006-google-oauth.md` with the standard sections.
4. Append the new task to PLAN.md's Task Index.
5. Do not modify existing task files unless explicitly requested.

### Example 3 - Marking Progress

**User prompt:**
> "I've completed the JWT setup task in the user-auth plan."

**Expected behavior:**
1. Read `002-jwt-setup.md`.
2. Check all checklist items, tests, and completion criteria as done.
3. Update `PLAN.md` to check the `002 - JWT Setup` entry.
4. Confirm the update to the user.

### Example 4 - Complete Task File (Reference)

Here's a fully filled-out task file for reference:

```markdown
# 003 - Login Endpoint

## Goal

Implement JWT-based login and logout endpoints that authenticate users and
return tokens.

## Dependencies

- Requires: 001, 002
- Blocks: 004, 005

## Scope

**In scope:**
- POST /api/auth/login endpoint accepting email/password
- POST /api/auth/logout endpoint invalidating tokens
- Token refresh endpoint
- Rate limiting on login attempts

**Out of scope:**
- OAuth/social login (separate task 006)
- Password reset flow (task 004)
- User registration (task 001 handles this)

## Checklist

- [ ] Create LoginSerializer with email and password fields
- [ ] Implement login view returning access and refresh tokens
- [ ] Implement logout view that blacklists the refresh token
- [ ] Add rate limiting: max 5 failed attempts per 15 minutes
- [ ] Return appropriate error codes (401 for bad credentials, 429 for rate limit)
- [ ] Log authentication attempts with user ID and IP (no passwords)

## Tests

- [ ] Run `pytest apps/auth/tests/test_login.py -v` - all pass
- [ ] Run `pytest apps/auth/tests/test_logout.py -v` - all pass
- [ ] Manual QA: Verify login with valid credentials returns token
- [ ] Manual QA: Verify 5 failed attempts triggers rate limit

## Completion Criteria

- [ ] Login endpoint returns valid JWT on correct credentials
- [ ] Logout endpoint invalidates the refresh token
- [ ] Rate limiting activates after 5 failed attempts
- [ ] All automated tests pass
- [ ] No security warnings from `bandit` scan

## Notes

- Use `djangorestframework-simplejwt` for token handling
- Token expiry: access = 15 min, refresh = 7 days
- See RFC 6749 for OAuth2 token response format reference
```

## Anti-Patterns to Avoid

- **Putting task details in PLAN.md.** The master plan is an index only.
- **Using arbitrary numbering.** Always use 3-digit zero-padded numbers.
- **Vague checklist items.** "Set up database" is bad; "Create users table
  with email, password_hash, created_at columns" is good.
- **Missing tests.** Every task should have at least one test or explicit
  "N/A - no automated tests applicable" with justification.
- **Renumbering tasks mid-project.** This breaks references and history.
- **Narrative completion criteria.** "The feature works well" is bad;
  "Users can log in and receive a valid JWT token" is good.
- **Ignoring dependencies.** Always specify what tasks depend on each other
  to prevent wasted work on blocked tasks.
- **Overly large tasks.** Tasks with 15+ checklist items are hard to track;
  split them into focused subtasks.

## Plan Lifecycle

### When a Plan Completes

When all tasks are checked:

1. Verify the PLAN.md Completion section is fully checked.
2. Add a `## Completed` section at the top of PLAN.md with the date:
   ```markdown
   ## Completed

   **Date:** 2024-02-15
   **Duration:** 3 weeks
   **Notes:** All tasks completed successfully. OAuth added as follow-up plan.
   ```
3. Optionally move the plan directory to `docs/plans/archive/<slug>/` or
   add an `[ARCHIVED]` prefix to the directory name.

### Plan Retrospective (Optional)

For significant plans, add a `RETROSPECTIVE.md` in the plan directory:

```markdown
# <Plan Title> - Retrospective

## What Went Well
- <Positive outcomes and practices>

## What Could Be Improved
- <Issues encountered and lessons learned>

## Follow-up Actions
- <New tasks or plans spawned from this work>
```

## Git Integration Best Practices

- **Commit plans early.** Commit the initial PLAN.md and task files before
  starting work so the plan is version-controlled.
- **Commit progress atomically.** When checking off items, commit the file
  changes together with any code changes they represent.
- **Use meaningful commit messages.** Reference the task number:
  `Complete 003-login-endpoint: implement JWT login/logout`
- **Don't commit partial checkbox states.** Either the item is done or it
  isn't. Commit when work is complete, not in-progress.
- **Branch per task (optional).** For larger plans, consider a branch per
  task: `plan/user-auth/003-login-endpoint`.

## Spawning Sub-Plans

When a task is too complex to fit in a single task file (even after splitting),
spawn a nested sub-plan:

1. In the parent task file, add a note:
   ```markdown
   ## Notes
   - **Sub-plan:** See `../user-auth-oauth/PLAN.md` for detailed OAuth implementation
   ```

2. Create the sub-plan in a sibling directory:
   ```
   docs/plans/
     user-auth/
       PLAN.md
       003-oauth-integration.md  # References sub-plan
     user-auth-oauth/            # Sub-plan for complex OAuth work
       PLAN.md
       001-google-oauth.md
       002-github-oauth.md
   ```

3. Link the sub-plan completion to the parent task:
   - The parent task's completion criteria should include:
     `- [ ] Sub-plan user-auth-oauth is fully complete`

4. When the sub-plan completes:
   - Archive the sub-plan as normal.
   - Check off the parent task that spawned it.

This keeps individual task files focused while allowing complex work to be
properly structured.

