---
description: Execute a backend-ralph-plan with Ralph Wiggum Loop
argument-hint: "<plan-slug> [--max-iterations N]"
allowed-tools: ["Read", "Glob", "Skill"]
---

# Run a RALPH Plan

Execute an existing backend-ralph-plan using the Ralph Wiggum Loop.

## What To Do

When the user runs `/plan-directory:run <slug>`:

### Step 1: Find the Plan

Check these locations in order using Glob:
- `docs/plans/<slug>/RALPH-PROMPT.md`
- `plans/<slug>/RALPH-PROMPT.md`
- `<slug>/RALPH-PROMPT.md` (if user is already in a plans directory)

If not found, tell the user and suggest running `/plan-directory:backend-ralph-plan`.

### Step 2: Extract the Completion Promise

Use Read to get RALPH-PROMPT.md contents, then find this pattern:
```
<promise>...</promise>
```

Extract the text between the tags. This is the completion promise.

Example: If the prompt contains `<promise>ALL 4 USER-PREFERENCES TASKS COMPLETE</promise>`,
the completion promise is `ALL 4 USER-PREFERENCES TASKS COMPLETE`.

### Step 3: Parse Max Iterations

- If user provided `--max-iterations N`, use N
- Otherwise, default to 100

### Step 4: Invoke Ralph Loop

Use the **Skill tool** to invoke `ralph-wiggum:ralph-loop`:

```
skill: "ralph-wiggum:ralph-loop"
args: <prompt-content> --completion-promise "<extracted promise>" --max-iterations <N>
```

Where `<prompt-content>` is the full content of RALPH-PROMPT.md that you read in Step 2.

**Note:** The Skill tool should handle multi-line content. If it doesn't work properly,
fall back to telling the user to run manually:

```bash
cd <plan-directory>
/ralph-wiggum:ralph-loop "$(cat RALPH-PROMPT.md)" \
  --completion-promise "<promise>" \
  --max-iterations <N>
```

### Step 5: Confirm to User

After invoking, tell the user:
- Ralph loop has started
- It will iterate through the tasks
- Progress is saved via git commits
- Loop ends when the promise is output or max iterations reached
- They can use `/ralph-wiggum:cancel-ralph` to stop early

## Examples

```
/plan-directory:run user-preferences
/plan-directory:run manager-weekly-digest --max-iterations 50
/plan-directory:run notification-service
```

## Error Handling

**Plan not found:**
> Could not find plan "xyz". Looked in:
> - docs/plans/xyz/RALPH-PROMPT.md
> - plans/xyz/RALPH-PROMPT.md
>
> Run `/plan-directory:backend-ralph-plan` to create a new plan.

**No completion promise found:**
> Warning: No `<promise>...</promise>` tag found in RALPH-PROMPT.md.
> Ralph will run until max iterations (N) without a completion signal.
> Continue anyway? [Proceed / Cancel]

**Ralph plugin not installed:**
> The ralph-wiggum plugin is required but not installed.
> Install it with: `/plugin install ralph-wiggum`
