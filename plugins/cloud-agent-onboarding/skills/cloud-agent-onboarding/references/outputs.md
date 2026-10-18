# Outputs people can open

The VM is deleted when the session ends, and people cannot open its file
paths. Plan three output paths: artifacts (fast, private, one page), private
previews (a real running build), and draft PRs (saved work).

## Artifacts (Claude)

- Cloud sessions have an artifact publishing tool. Artifacts are private to
  the account until shared from the page's Share menu and stay under
  **Artifacts** in the claude.ai sidebar. **On a shared login everyone on it
  can open them**, so the skill must never call an artifact "private" or say
  "only you can see it"; call it a draft copy. Keep restricted or sensitive
  pages out of artifacts entirely (the generator should refuse them).
- Tell the session to publish (in the repo skill or the MCP instructions plus
  each report tool's `next_step`): "publish the HTML report unchanged as a
  private artifact and reply with the link". After that, a plain prompt with no
  mention of artifacts published one unprompted.
- Contract: one self-contained HTML page, nothing loaded from outside, at most
  16 MB. Declare `<meta charset="utf-8">` and a device-width viewport first;
  escape `</script` inside inline scripts; the publisher rejected a raw U+FFFD
  character (write it as an entity or `�`). Non-ASCII without a charset
  shows as mojibake ("âœ“") when opened as a local file.
- For reviewers, share artifacts with the people or the organization, never
  publicly, or attach images instead.

### Clickable pages instead of screenshots

Screenshots were "slow and not interactive enough". A generator that turns
one component story (or one screen with fixture data) into a single
self-contained page took about 5 seconds, against about 3 minutes for a full
Storybook build. Idea → before/after pages took about 3½ minutes; a tweak
about 1 minute.

Design of the component library's generator (a `pnpm story:page` script), reusable for any UI
project:

1. A throwaway entry **inside the repo** (an ignored cache folder), so imports
   resolve from the repo's `node_modules`, loading the story with the real
   decorators, theme and global styles.
2. Bundle with Vite and the repo's own plugins; alias root-absolute asset
   imports.
3. Inline everything: JS, CSS, only the font faces the tokens use (all 49
   faces were 18 MB), remote images found in the source; report URLs it could
   not fetch.
4. Behave like the real thing: run loaders and `play`, apply the layout,
   re-render on control and state changes.
5. Block external media and show an offline notice in its place.
6. Tests: unit tests for the helpers, and a browser test that serves the page
   as plain `text/html` with no charset and every non-local request blocked.
   Prove each test catches its bug (stash the fix, see it fail, restore).

No Storybook? A single-file Vite build of one screen with fixture data (for
example `vite-plugin-singlefile` and a preview entry). Same artifact rules.

Screenshots are for the agent's own check, not for the person.

Generate the artifact from the **real build**, not a hand-written copy: a
session asked for "an artifact preview" hand-wrote a plain imitation. The
internal website's `artifact-preview.mjs` turns one built page into one
self-contained file (the site's styles and fonts, a "draft preview" bar,
links pointing to the live site) and refuses restricted pages. The skill says
to publish exactly the file the script printed, at the same path every round,
so the artifact updates in place.

## Private previews

When the output is bigger than an artifact (a whole Storybook was 48 MB and
3,486 files) or people need a real running build, host it privately.

Our default, Cloudflare Pages behind Cloudflare Access (for Vercel, Netlify
or an identity-aware proxy, see [providers](providers.md#previews-and-access-control)):

1. Variables `CLOUDFLARE_ACCOUNT_ID` and a placeholder `CLOUDFLARE_API_TOKEN`;
   a network secret for `api.cloudflare.com` with path prefix
   `/client/v4/accounts/` (a Pages: Edit token).
2. Create a dedicated preview project with a production branch nothing
   deploys to: `npx --yes wrangler@4 pages project create <proj> --production-branch production-unused --force`.
3. **Restrict previews before any deploy** (project → Settings → Restrict
   previews). Edit the Access policy to the company domain (Google SSO if an
   identity provider exists; one-time PIN limited to the domain otherwise).
4. A service token plus a **Service Auth** policy, stored as a network secret
   for `*.<proj>.pages.dev` with headers `CF-Access-Client-Id` and
   `CF-Access-Client-Secret` (no prefix), so the session can open its own
   preview to check it.
5. Deploy: `npx --yes wrangler@4 pages deploy <dir> --project-name <proj> --branch <alias> --commit-dirty=true`.
6. Verify three ways: 200 from inside the session; 302 to the Access sign-in
   from outside with no credentials; a person signs in with a company email
   in a normal browser.

Alias rules: `exp-<few words>-<4 random chars>`, at most 28 characters,
lowercase, no people or customer names (two sessions picking the same words
overwrote each other's link). Keep the same alias for the whole experiment,
including resumed sessions. Never deploy to the production branch.

Hardening: add the bare `<proj>.pages.dev` to the Access app (the wildcard
does not cover it). Pages tokens are account-wide; keep production deploys
out of the cloud environment (GitHub Actions on merge, separate token), or
use a separate account for previews.

Traps from the internal website:

- **Create the hosting project before writing host names anywhere.**
  The wanted `<name>.pages.dev` was taken, so Cloudflare assigned
  `<name>-<3 chars>.pages.dev`, and every file, allow-list and secret had to
  use that name.
- **Cloudflare Access only fronts hostnames in a Cloudflare DNS zone.** With
  DNS elsewhere, a custom domain either forwards to `pages.dev`
  (the address bar changes after sign-in) or the site signs people in itself
  with an Access **SaaS (OIDC) app**: PKCE, state and nonce; check the ID
  token against JWKS, issuer, audience, expiry, nonce and the email domain; an
  HMAC `__Host-` session cookie; fail closed; tests.
- **Renaming the Zero Trust team domain** (a random one like
  `<words>-<n>.cloudflareaccess.com` looks like phishing in sign-in emails)
  **permanently broke the existing OIDC app's `/jwks`** (HTTP 500); a new SaaS
  app fixed it. The login page branding is separate and does not follow the
  rename. Test a fresh sign-in after any rename.
- Sign-in errors should say whose fault it is: "temporarily unavailable"
  (provider) versus "use your company email" (the person).
- Keep one source of truth for reader lists; two copies (the access
  provider and the repo) drifted on the first day.

Other shapes: a static SPA needs `/* /index.html 200` in `_redirects`; a
server-rendered app needs a host that runs code (Workers, a staging service,
a remote sandbox) behind access control, pointed at staging or mock data.

## Running copies with data (remote sandboxes)

When people need "what an HR admin sees", a static page is not enough. The
remote-sandbox project used Crafting sandboxes through a CLI: create a test copy with a
database, sync code into it, sign in with synthetic users, screenshot,
delete. Rules that carried over:

- Ask once which data to start with, recommending the newest shared dev
  snapshot; never production.
- Name created resources `cc-<two-words>-<4 random>`; reuse one per
  conversation; offer to delete what the conversation created.
- Someone else's resource: identify it first (owner, template, branches,
  mode), only look unless asked, and never delete it or replace its data.
- Data stays there: no records, names or emails in replies, artifacts,
  commits, PRs or fixtures.

## Pull requests

- Shipping directly from a session (not just a draft PR) needs a gate the
  session does not control: see [publishing](publishing.md).
- **Saving is explicit.** Iterations do not commit or push. On "save it":
  confirm in one sentence, add a focused test, run the repo's checks, commit
  without attribution, push once, open a **draft** PR into the integration
  branch, and tell the person what happens next.
- PR body: what changed and why in plain words; who asked (role, not name);
  where to look (preview link, artifacts shared with reviewers); checks run
  and results; links to matching PRs in other repos; "Needs an engineer:
  <full validation> and review."
- **Attribution footers get added by the tools.** Claude's GitHub connector
  `create_pull_request` appended "Generated by Claude Code" on its own. Right
  after creating the PR, resend the body with `update_pull_request` and read
  it back. Put this step in the skill explicitly; a rule in `AGENTS.md` alone
  did not stop it.
- Claude docs (2026-10-17) also say commits get a `Claude-Session:` trailer
  and PR bodies the session URL, and that the `attribution.sessionUrl`
  setting turns this off. If the repo forbids attribution, set that in the
  repo's `.claude/settings.json` (single-repo sessions only) and check a
  probe commit's trailers.
- `gh pr` and `gh issue` fail inside Claude cloud sessions (GraphQL is
  blocked); use the GitHub connector tools or `gh api repos/...`. Resolving
  review threads needs GraphQL, so do that from an engineer's machine.
- Branch names are assigned by the platform (`claude/<words>` on Claude,
  `codex/<words>` on Codex); do not fight them, and do not write a different
  convention into the skill.
- **The end-of-turn check.** claude.ai's own check prompts the agent to
  commit and push unsaved work after each reply; the session's safety rules
  then block it because the person has not asked. Tell the agent: "Don't
  commit before 'save it'. Answer the check in one line: 'Not saved yet:
  waiting for the person to decide.'" Tell people the agent waits for "save
  it".
- Monorepo with submodules: do not commit pointer changes in the parent;
  after pushing, put the submodule back on the parent's commit so the check
  stops reporting it, and keep the branch for further work.
- Never push to protected branches, never force-push a branch the session
  did not create, never merge.

## Handing work to an engineer's machine

Engineers continue a cloud session's work from its pushed branch or PR. Check
[platforms](platforms.md) for each vendor's hand-off commands (teleporting a
Claude session into the local CLI, applying a Codex task's diff locally).
