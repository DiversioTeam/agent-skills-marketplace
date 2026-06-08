# Editorial Workflow

Use this guide when you need to decide **what kind of website change** to make before you start editing files.

For page ownership rules, read `docs/content-governance.md`.
For direct file targets, read `docs/editing-recipes.md`.

## Start with the kind of idea you have

### 1. Is it a durable engineering habit or standard?
Put it in:
- `/how-we-work`

Good fits:
- review habits
- quality expectations
- decision rules
- delivery standards

If it needs examples or nuance, add a supporting blog post instead of overloading the page.

### 2. Is it architecture, stack, or workflow structure?
Put it in:
- `/systems`

Good fits:
- stack choices
- CI/CD shape
- infrastructure approach
- workflow architecture
- tooling ecosystems

If it becomes very detailed, support it with a blog post rather than turning `/systems` into a reference manual.

### 3. Is it about a specific open tool, package, skill, or install flow?
Put it in:
- `/agentic-tools`
- `/registry`
- `/docs/*`
- `/skills/*`
- `/pi/*`

Good fits:
- package docs
- runtime-specific install guidance
- skill behavior
- Pi extension surface details

### 4. Is it a story, explanation, case study, or argument?
Put it in:
- `/blog/*`

Good fits:
- deep dives
- examples
- tradeoffs
- retrospective-style writing
- supporting material for `/how-we-work` or `/systems`

### 5. Is it about following, engaging, contributing, or contacting?
Put it in:
- `/community`

Good fits:
- how to engage with the work
- where to find open repos
- how contribution tends to go
- security/contact paths

## When to update a page vs write a post

Update a top-level page when:
- the idea is stable
- it is part of the site’s permanent map
- the point can be made concisely

Write a blog post when:
- the idea needs examples
- the idea needs tradeoffs
- the reasoning would make the top-level page too long
- the same concept benefits from a stronger narrative voice

Rule of thumb:
- top-level pages explain the model
- blog posts show the model in action

## When to use shared data instead of page-local copy

Use shared data when:
- the same route summary or CTA appears in multiple places
- a stack entry is used as a maintained engineering layer
- a systems highlight is part of a shared catalog
- a principle is a stable part of `/how-we-work`
- a `/how-we-work` practice has become a maintained recurring part of the site

Keep copy page-local when:
- it only makes sense in one page’s local context
- it depends on nearby layout or neighboring content
- reusing it elsewhere would make the copy weaker

## Before adding a new section

Ask:
1. does this page already say this in another form?
2. is this really a new section, or should it replace an older weaker one?
3. would this be better as a support post instead?
4. does this belong to a different page family?

## Before adding another stack item

Ask:
1. is this part of the core stack, delivery path, design system, analytics layer, or truly important daily tooling?
2. should it be a primary technology or only a supporting tool?
3. does adding it make the layer clearer, or just longer?
4. do we have a usable official logo/icon for it?

## Editorial sanity check

If a change makes you edit the same idea in:
- homepage
- `/how-we-work`
- `/systems`
- `/community`

pause and ask whether that idea should live in shared data instead.
