# Non-technical intake

Ask only what is needed for the next visible pass. Do not turn this into a requirements interview.

## Opening

Start with:

> What are you hoping someone can do or understand on this screen?

Then use the first applicable follow-up:

- “Is there an existing screen, Storybook example, screenshot, or sketch you want to start from?”
- “Who is looking at this—an employee, manager, HR leader, or someone else?”
- “What is the first decision or action they should notice?”

Accept ordinary descriptions. Translate them into implementation details yourself.

## Useful choices

When the user is unsure, offer concrete choices:

- **Starting point:** improve an existing screen / combine existing pieces / try a new pattern
- **First pass:** desktop / phone-sized / both
- **States:** typical / empty / loading / error / unavailable
- **Access:** private to me / invite named colleagues / organization-wide
- **Goal:** explore visually / compare two variants / prepare an engineering handoff

Default to one typical state at desktop and phone-sized widths, then add states they need to judge the idea.

## Atomic recommendation

Treat these as likely new atomic components:

- a control with its own interaction
- a reusable card, banner, notice, field, badge, selector, disclosure, or data presentation
- a visual pattern likely to appear on more than one page
- a new component whose states need to be reviewed independently

Say:

> This looks like a reusable building block rather than one-off page layout. I recommend we make the small piece first
> and then place it in the screen. You will still review it through the same live link.

Do not ask whether it should use React, styled-components, tokens, or a particular folder.

## Data safety

Before using user-provided content, check whether it includes employee/customer names, survey responses, notes, email,
company data, credentials, or unreleased confidential language. Replace it with finite synthetic data and tell the user
what was substituted. Never place sensitive language in sandbox names, Git branches, commits, URLs, fixtures, actions,
or analytics.

## Iteration

Ask one observable question per pass. Good questions compare hierarchy, clarity, wording, density, and workflow. Avoid:

- “What API should this use?”
- “What props do you want?”
- “Which breakpoint?”
- “Should this be local state or context?”
- “Can you run this command?”

Those are the agent's or engineering's decisions.
