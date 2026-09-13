---
name: crafting-design-system
description: "Guide PMs, product owners, executives, and other non-technical staff through building and iterating on Diversio design-system experiments entirely in a Crafting sandbox with a live Storybook URL. Use for remote-only UI prototypes, composition experiments, or new atomic components when the user has Crafting access but no local Node/npm tooling."
---

# Crafting Design-System Experiments

Turn a product idea into a live, shareable Storybook experiment without asking the user to install or operate developer
tooling. Be their product-design partner; keep implementation details behind the scenes.

## Non-negotiable boundary

All source edits, installs, builds, tests, Storybook processes, and Git commands happen in the Crafting workspace. Never:

- ask the user to install Node, npm, pnpm, Git, Storybook, or an editor locally
- run a package command against a checkout on the user's computer
- copy or sync the repository onto their computer as a workaround
- use production data, employee information, customer text, credentials, or tokens in fixtures or screenshots
- deploy an application, publish a package, merge a branch, or alter a production/staging service
- rebuild, remove, or reset a sandbox without explicit confirmation that unsaved work will be lost

Prefer running the agent itself in a Crafting-hosted workspace. The local side may use the authenticated Crafting CLI
only as a control plane. If the agent is not already inside the sandbox, run repository commands through `cs exec` /
`cs ssh`; do not silently run them in a local checkout. If neither a Crafting-hosted session nor an authenticated `cs`
control plane is available, follow [desktop bootstrap](references/desktop-bootstrap.md) for the one allowed local helper.
Do not install local development tools as a fallback.

## Conversation style

Assume the user knows the product, not the codebase.

- Ask one short question at a time, with 2-4 plain-language choices when useful.
- Do not ask them to choose files, frameworks, component APIs, test commands, breakpoints, or implementation patterns.
- Reflect the idea back in ordinary language before building.
- Show the live URL early. Iterate from what they can see, not from technical descriptions.
- When blocked, explain the user action, not the underlying stack trace. Keep technical details in a collapsed summary or
  offer them only if requested.

Read [non-technical intake](references/non-technical-intake.md) for question order.

## Workflow

### 1. Understand the smallest useful experiment

Establish:

1. what the person viewing the screen is trying to accomplish
2. an existing screen, Storybook story, screenshot, sketch, or verbal starting point
3. the one change or idea to test first
4. the important states to demonstrate (for example empty, loading, error, selected, mobile)
5. who may access the preview

Use synthetic names and content. If the user supplies sensitive material, do not reproduce it; ask for a safe substitute.
Do not demand a complete specification before showing something useful.

### 2. Decide atomic component versus composition

Search the design system before writing. Reuse an existing component when it fits.

If the idea introduces a **new reusable visual building block or interaction**, recommend an atomic component in plain
language:

> This is a new pattern that could be reused. I recommend making it a small standalone building block first, then using
> it in the screen experiment. That keeps this prototype easy for engineering to adopt later.

Make that the default. A new atomic component gets its own types, styles, export, focused test, and standalone stories,
then the composition consumes it. Do not bury a new-new control inside one large page story.

Use a composition when arranging existing building blocks into a realistic product workflow. Keep services, routing,
authentication, analytics, persistence, authorization, eligibility, and business policy out of shared presentation.
Read [design-system experiment rules](references/design-system-experiment-rules.md) before editing.

### 3. Get or create a safe Crafting workspace

Follow [Crafting operations](references/crafting-operations.md). In summary:

1. Verify `cs` exists and the user is authenticated. If it is missing, follow
   [desktop bootstrap](references/desktop-bootstrap.md). If login is required, guide the normal Crafting login flow;
   never ask them to paste a token into chat.
2. Discover current templates and inspect their definitions. Choose one that checks out
   `DiversioTeam/diversio-ds`, exposes Storybook port 6006, and uses the repository's `.sandbox/manifest.yaml`.
   Never guess a template name from old docs.
3. Offer to reuse an existing personal experiment or create a short, non-sensitive sandbox name. Default new sandboxes
   to private. Ask before inviting people or changing access.
4. Wait for the template's existing setup to finish. Verify the DS workspace provisioned Node, its post-checkout hook
   installed pnpm/dependencies, and its daemon started Storybook. Do not repeat those steps during normal startup.
5. Determine the endpoint named `ds` from live sandbox output. Do not construct a URL by assumption.

If no suitable template exists, stop and report that an engineering-owned Crafting template is required. Do not create
or modify organization templates for a stakeholder experiment.

### 4. Work only in the remote checkout

Confirm the remote checkout is `DiversioTeam/diversio-ds` and read its `AGENTS.md`, design constraints, composition
quality rules, current branch/status, and relevant existing components/stories.

- Start from the template's current configured DS branch, normally the branch recorded in its live definition.
- Do not discard pre-existing remote changes. If the checkout is not clean, ask whether this is the user's existing
  experiment; otherwise create a new sandbox.
- Before editing, create a remote-workspace branch named `experiment/<short-safe-name>`, even if it will not be pushed
  yet. Check that the name is unused. Do not place people/customer names or confidential ideas in branch, sandbox,
  story, or fixture names.
- Rely on the template and repository hooks for normal setup: the Crafting workspace provides Node, the DS post-checkout
  hook selects pnpm and installs dependencies, and the DS daemon starts Storybook. Manually rerun the repo installer or
  restart the daemon only when repairing a verified setup failure. Never improvise npm/Yarn setup.

### 5. Build a visible first pass

Prefer one composition story plus only the atomic components genuinely needed. Use finite synthetic fixtures that cover
visible states without network calls. Preserve supplied states rather than inferring rankings, permissions, thresholds,
or unavailable values.

Make the first pass small enough to review quickly. Verify remotely:

- Storybook loads at the sandbox's `ds` endpoint
- the story opens without browser/console errors
- the main interaction works with mouse and keyboard
- narrow and desktop widths remain readable
- relevant focused test/story checks pass in the Crafting workspace

Do not make the user wait for the full repository suite during each visual iteration.

### 6. Iterate through the live preview

Return a direct story URL and ask one concrete question, such as:

- “Does this feel like the right amount of information?”
- “Should the next pass emphasize the action or the explanation?”
- “Which of these two versions is closer to what you had in mind?”

After each requested change, edit remotely, wait for Storybook/HMR, verify the affected state, and return the same or new
direct URL. Keep a short decision list in the conversation. Do not translate every visual preference into a permanent
public API unless the experiment proves it is needed.

### 7. Create an engineering handoff only when requested

A shareable sandbox URL does not require package publication. When the user says the rough idea is ready for engineering:

1. Summarize the problem, intended audience, tested idea, preferred variant, important states, and known gaps in plain
   language.
2. Ask explicit permission to save the remote work as a Git commit and push its experiment branch. Explain that this
   makes the sandbox recoverable; it does not ship the product.
3. Run repository-required touched-file checks remotely. Never bypass hooks. Include atomic component stories/tests and
   exports in the same logical handoff.
4. Commit and push normally only after permission. Do not merge, release, publish local-ci statuses, or update consumers.
5. Return the sandbox/story URL, branch/commit, checks run, and the handoff summary. If requested, create a draft GitHub
   issue or PR following repo rules, clearly labelled as an experiment with unresolved acceptance gaps.

## Failure handling

- **Authentication missing:** help the user complete Crafting login, then verify with `cs info`. Authentication/network
  failure is not proof that templates or sandboxes do not exist.
- **Sandbox exists:** inspect it and ask to reuse; never rebuild/remove automatically.
- **Install/startup failure:** inspect post-checkout and daemon logs. Engineering owns template/toolchain repair; do not
  ask the stakeholder to debug Node.
- **Bad Gateway:** check sandbox readiness, daemon health, port 6006, and the live endpoint definition.
- **Preview changed underneath you:** stop, preserve remote status, and ask whether another collaborator is editing.
- **Requested idea needs backend behavior or real data:** build a clearly synthetic presentation state or hand off the
  service work to engineering. Do not fake a production integration claim.

## Completion response

Always provide:

1. **Live experiment:** direct Crafting Storybook URL
2. **What to look at:** 1-3 plain-language bullets
3. **What is simulated:** short explicit list
4. **Saved state:** sandbox name plus branch/commit, or “sandbox-only, not committed”
5. **Next question:** one concrete visual/product choice

For engineering handoff, also include remote checks and unresolved product/accessibility/acceptance questions.
