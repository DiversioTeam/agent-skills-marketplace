---
title: How we use AI like engineers
slug: how-we-use-ai-like-engineers
summary: How Diversio uses AI to recover context in large codebases and take repetitive work off engineers' plates without relaxing review quality or operational safety.
publishDate: 2026-05-05
author:
  name: Diversio Engineering
tags:
  - engineering
  - ai
  - developer-experience
  - workflow
sourceType: original
featured: true
draft: false
---

The AI-assisted failures we care about usually start before the model writes a line.

An engineer asks for too much in one pass. The repo does not expose enough context. The review path is too weak to catch fuzzy reasoning. A strong model inside that setup can produce a large, polished diff that still leaves the engineer doing the hard part afterward: figuring out what the change actually means.

The version that works better for us is narrower. We use AI to recover context faster, draft low-leverage work, and tighten repetitive workflows inside a system with clear owners and a review path that still catches mistakes.

## Where it actually helps

The most useful work AI does for us is practical.

A common example is cross-repo context recovery. An engineer may need to understand a change that touches instructions, code, and docs across more than one repository. The model can assemble the map of files, conventions, and likely blast radius much faster than starting from zero. That saves time at the front of the task without pretending the reasoning is complete.

It also helps with first drafts of tests or docs. It helps with rename work that has to stay consistent across many files. And when a workflow keeps failing in the same place, AI can help turn the fix into a guide, a wrapper, or a quality check instead of leaving the lesson stuck in one person's head.

## Context matters more than prompting

Weak output often comes from treating prompting as the whole system.

The bigger gains usually come from giving the model a structure it can work inside:

- stable project instructions
- clear repository conventions
- useful ignore patterns
- obvious quality gates
- enough architectural context to make the next step legible

Configuration shape matters too. Reusable rules should stay reusable. Project-specific context should stay close to the project. Technical controls like tool restrictions or ignore behavior should stay out of narrative guidance.

That advice is less exciting than a prompt trick, but it keeps paying off. A clean split between shared standards and project-specific setup is easier for humans to maintain and easier for models to use correctly.

## The workflow still has to hold up

The safeguard that matters most is keeping AI inside workflows that remain reviewable.

Big features still need to be broken into smaller releases and smaller PRs. Early feedback still beats late heroics. Bugs still deserve tests that prove the failure before the fix lands.

The same discipline applies when a change gets risky. Data changes still need production-like validation. Heavy queries still need performance attention. Authorization still needs adversarial thinking, not just happy-path optimism.

One of the easiest ways to waste time is to ask AI for too much at once. The result can look productive for a minute because a lot of text appears quickly. Then the review bill arrives. The diff is too wide, the intent is muddy, and the engineer spends longer validating the draft than they would have spent writing a smaller change directly.

The speed we care about is narrower and more practical. We want faster context recovery, tighter drafts, and quicker correction when something is off.

## What still stays human

Some work should stay obviously human.

If a change touches data integrity, authorization, or production safety, somebody has to reason directly about the failure modes. AI can assist, but it cannot be the final source of trust.

The same goes for architecture. The hard calls about coupling, isolation, and long-term maintenance belong to engineers who understand the wider system and will live with the consequences.

Final review stays human too. We still want code to be understandable, testable, and safe. The value comes from removing wasted effort from the loop, not from pretending judgment is optional.

## We evaluate AI like infrastructure

There is a second layer to this beyond coding workflow: choosing the right AI stack.

We have found it more useful to think about these systems the way we think about infrastructure. The model matters, but the surrounding system matters too.

The questions we care about are familiar ones:

- how much operational complexity does this add?
- how easy is it for engineers to build against?
- what does it change about data handling, compliance, or deployment shape?
- what will this decision cost over time, not just in a demo?

The surrounding developer experience matters as much as the model itself. So does the long-term maintenance cost.

## What changed for us

We recover context faster. We document more. We turn repeated friction into instructions, tools, or guardrails more often. We spend less time on low-leverage repetition and more time on design, review, and testing.

A lot of that progress came from engineers comparing notes, tightening instructions, and writing down what actually worked. The system improved because people kept feeding their learning back into it.

## The part that matters most

Weak engineering habits become more expensive when AI speeds them up. Strong engineering habits benefit from the same multiplier.

That is the version of AI adoption we care about: practical, reviewable, and grounded in the same standards we expect from the rest of the stack.

If another team asked where to start, I would begin with instructions, scope, review loops, and ownership before spending much time on model comparison. Those choices shape whether the rest of the system holds up.

## Related reading

- [The Monolith That Made AI Actually Useful](/blog/the-monolith-that-made-ai-actually-useful/)
- [No Code by Hand](/blog/no-code-by-hand-agentic-platform-acceleration/)
- [From Postman to Bruno - How AI Changed Our API Workflow](/blog/from-postman-to-bruno-how-ai-changed-our-api-workflow/)
