---
description: Create a presentation-ready HTML visual explainer for a plan, diff, doc, architecture, audit, or stakeholder update.
argument-hint: "[topic] [--audience <type>] [--goal <goal>] [--technical] [--summary] [--reply-draft] [--slides]"
---

Use your `visual-explainer` Skill in the default stakeholder explainer mode.

Arguments: `$ARGUMENTS`

Workflow:

1. Resolve the topic, audience, goal, and source material from the request and
   current context.
2. If required inputs are still missing, ask one concise follow-up that covers
   only the missing items.
3. Validate the current state first and separate:
   - confirmed facts
   - inferred points
   - anything still needing external verification
4. Generate a self-contained HTML explainer using the `visual-explainer`
   references and templates.
5. Save it under `~/.agent/diagrams/` with a clear filename and try to open it
   in the browser.
6. Tell the user the HTML path and call out any important unverified points.

Optional behavior:

- `--technical`: allow more implementation detail, code references, and file
  paths.
- `--summary`: also write a Markdown summary to `~/Downloads/` when useful.
- `--reply-draft`: include a reply draft section for customer, IT, security, or
  leadership audiences.
- `--slides`: use slide mode instead of a scrollable page.

At the end, suggest the optional share-out step:
- post the HTML on Netlify Drop
- if site access controls are configured, share the link and password with the
  team
