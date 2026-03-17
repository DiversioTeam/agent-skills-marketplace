---
description: Create a presentation-ready HTML visual explainer for a plan, diff, doc, architecture, audit, or stakeholder update.
argument-hint: "[topic] [--audience <type>] [--goal <goal>] [--technical] [--summary] [--reply-draft] [--slides] [--publish] [--open-url]"
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
6. If `--publish` is present or the user explicitly wants a hosted preview,
   first verify the required `NETLIFY_VISUAL_EXPLAINER_*` variables are visible
   to the current runtime. If they were just added to shell startup files, tell
   the user to restart the current tool session before retrying.
7. If `--publish` is present or the user explicitly wants a hosted preview,
   publish the generated HTML with the Netlify helper script and return the
   deploy URL plus receipt path.
8. Tell the user the HTML path and call out any important unverified points.

Optional behavior:

- `--technical`: allow more implementation detail, code references, and file
  paths.
- `--summary`: also write a Markdown summary to `~/Downloads/` when useful.
- `--reply-draft`: include a reply draft section for customer, IT, security, or
  leadership audiences.
- `--slides`: use slide mode instead of a scrollable page.
- `--publish`: create a fresh Netlify preview site for this explainer after the
  local HTML is written.
- `--open-url`: open the Netlify deploy URL after publish.

At the end:
- if the explainer was published, return the deploy URL and receipt path
- if it was not published and sharing would help, you may suggest Netlify Drop
