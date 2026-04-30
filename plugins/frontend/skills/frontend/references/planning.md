# Planning Lane

Plan frontend work using the current repo's actual docs, branch, and package
conventions.

Do not assume:
- branch from `dev`
- plan docs live under `docs/feature/<slug>/`
- the work targets a single app package

## Planning Workflow

### 1. Resolve scope

Ask for:
- issue/reference
- feature name / slug
- affected app or package when this is a monorepo

### 2. Resolve the planning location

Use this precedence:
1. repo-local docs conventions
2. digest workflow conventions
3. a minimal fallback planning folder

### 3. Understand the request

Read the provided docs/specs/figma/notes and summarize the intended outcome.

### 4. Ask scoping questions

Cover:
- user goals
- edge/error states
- data/API dependencies
- design-system impact
- affected packages or consumers
- success criteria
- out-of-scope items

### 5. Capture plan artifacts

Create only the artifacts that help this repo's planning flow, such as:
- scoping questions
- design notes or wireframes
- implementation plan

### 6. Branch creation

Use the repo's detected branch model and naming conventions. Ask before
creating the branch only if the correct base branch is unclear.

Input formats for branch creation: `1234 short description`,
`#1234 short description`, or `short description`.

Use repo's detected naming conventions (fallback:
`feature/{issue-number}-{feature-slug}`).

## Output

Report:
- digest status
- affected package(s) / repo class
- planning folder used
- branch model chosen
- artifacts written
