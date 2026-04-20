---
name: frontend-plan
description: "Feature planning workflow for frontend projects with GitHub issue linkage, structured 8-step process, scoping questions, wireframes, and implementation plan generation."
---

# Frontend Planning Skill

This skill MUST be followed strictly. Do not skip steps. Do not rush to implementation.

**Philosophy**: 90% of the time should be spent planning. 10% implementing. Ambiguity in planning becomes chaos in code.

## When to Use This Skill

- When starting a new feature and needing a structured plan before implementation.
- `/frontend-plan:plan` — full 8-step planning workflow with GitHub issue linkage.
- `/frontend-plan:new-branch` — create a feature branch from dev with proper naming.

## Example Prompts

- "Plan the new notification preferences feature"
- "Create a plan for implementing dark mode"
- "/plan slack-pr-notifications"
- "/new-branch 1234-fix-login-redirect"

---

## Step 0: Issue Reference & Branch Setup

**Ask the user:**

> "What GitHub issue or planning reference should this plan link to? Provide `#1234`, `owner/repo#1234`, or `none`."

Wait for the issue reference.

**Then ask:**

> "What are you implementing? Give a brief kebab-case description (e.g., `slack-pr-notifications`, `fix-login-redirect`)"

Wait for the feature name.

**Create the feature branch:**

```bash
git checkout dev
git pull origin dev
# If the work has a GitHub issue:
git checkout -b feature/{issue-number}-{feature-name}

# Otherwise:
git checkout -b feature/{feature-name}
```

**Branch naming rules:**

- Prefer `feature/{feature-name}`
- If tracked, use `feature/{issue-number}-{feature-name}`
- Branch from: `dev` (always)

**Create the docs folder:**

```bash
mkdir -p docs/feature/{feature-name}/
```

---

## Step 1: Locate Documentation

**Ask the user:**

> "Where have you placed all the relevant docs for what you want to build? This could be feedback, specs, early ideas, image inspiration, Figma links, Slack threads, etc. Please provide the folder path. Or should I use `docs/feature/{feature-name}/`?"

Wait for the user to provide or confirm the docs folder path.

---

## Step 2: Understand What's Being Presented

Read all documents the user has provided. Understand:

- What is the user trying to build?
- What problem does this solve?
- Who is it for?
- What context exists already?

Summarize your understanding back to the user in 3-5 sentences. Ask: "Is this accurate?"

---

## Step 3: Scoping Questions (Minimum 10)

Ask **at least 10 scoping questions** to clarify gaps. Cover:

- User goals and pain points
- Edge cases and error states
- Data requirements and sources
- Role-specific behavior
- Integration with existing features
- Success criteria / definition of done
- What's explicitly out of scope
- Technical constraints or dependencies
- Timeline or priority context
- Inspiration or anti-inspiration

**Ask the user:**

> "I have [N] scoping questions to clarify the direction. Would you like me to write these to `scoping-questions.md` in your docs folder?"

If yes, write `scoping-questions.md` with numbered questions and space for answers.

---

## Step 4: Review Scoping Answers

Once the user has answered, synthesize their answers:

- What we're building
- What we're NOT building
- Key decisions made
- Open questions remaining

Ask: "Does this capture the direction correctly?"

---

## Step 5: Visual Design (ASCII Art + User Stories)

**Ask the user:**

> "Would you like me to create ASCII wireframes for the key screens, along with user stories?"

If yes, create `design-wireframes.md` containing:

- ASCII art mockups of screens/components
- User stories: "As a [role], I want to [action] so that [outcome]"
- Notes on interactions, states, and edge cases

---

## Step 6: Prototype or Direct Implementation?

**Ask the user:**

> "Do you want to build this as a **prototype** or implement **directly as a feature**?"

### If Prototype:

Scaffold under a proto directory with feature-flagged routes.

### If Direct:

Proceed to implementation plan for the main codebase.

---

## Step 7: Create Implementation Plan

Write `implementation-plan.md` to the docs folder:

### 1. Overview
- What we're building (1-2 sentences)
- Why (problem/opportunity)
- Who it's for (roles affected)

### 2. Scope
- What's included
- What's excluded
- Dependencies
- Backend branch dependency (if any)

### 3. Technical Approach
- Key components to create/modify
- Data flow and state management
- API endpoints needed
- Integration points

### 4. Implementation Steps
Numbered, discrete tasks. Each should be:
- Small enough for one session
- Clear about "done"
- Independent where possible

### 5. Testing & Validation
- How to verify each step
- Edge cases to test
- Acceptance criteria

### 6. Open Questions
- Unresolved items
- Decisions deferred to implementation

---

## Step 8: Sign Off & Handoff

**Tell the user:**

> "The planning phase is complete. All documentation has been written to your docs folder:
>
> - `scoping-questions.md`
> - `design-wireframes.md`
> - `implementation-plan.md`
>
> **Next steps:**
> 1. Start a **new session** to keep context clean
> 2. Read `implementation-plan.md`
> 3. Begin implementation following the plan"

---

## If the User Gets Stuck

> "Let's stick to the plan. Want to go over the next step?"

Do not let anyone skip steps. The process exists for a reason.

---

## Quick Reference

| Step | Action                | Output                            |
| ---- | --------------------- | --------------------------------- |
| 0    | Issue ref + branch    | Branch created, docs folder ready |
| 1    | Locate docs           | Docs folder confirmed             |
| 2    | Understand scope      | Understanding confirmed           |
| 3    | Scoping questions     | `scoping-questions.md`            |
| 4    | Review answers        | Direction clarified               |
| 5    | Visual design         | `design-wireframes.md`            |
| 6    | Proto vs Direct       | Mode decided                      |
| 7    | Implementation plan   | `implementation-plan.md`          |
| 8    | Sign off              | Handoff to new session            |
