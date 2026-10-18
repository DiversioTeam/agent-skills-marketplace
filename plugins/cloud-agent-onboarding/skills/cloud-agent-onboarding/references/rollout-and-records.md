# Rollout and records

## Change record

Create it before touching anything, in the worktree:
`docs/plans/<project>-cloud-<date>.md` (skeleton in
[templates](templates.md#change-record)).

- **Pre-state**: read-only facts gathered before any change.
- **Changes**: numbered, one per state-changing action, written as you go.
  Each says what changed, how, and the read-back that proved it. Include
  mistakes: a token that leaked into output and was revoked a minute later
  gets its own numbered entry, and writing it down is the point.
- Test resources created and deleted, branches pushed and deleted, demo PRs
  opened and closed, all with read-backs.
- **Decisions**, **Risks** (with who accepted them and when), **Rollback**
  (one line per change), **Open**.
- Credentials appear only as vault item name, scope, expiry, length and
  sha256 prefix.

## Maintainer doc (in the repo)

How a session starts, the environments table (name, purpose, variables by
name, secrets by name and host), token rotation steps, how to update the
setup script and read it back, how to check a change (which probe prompt),
and rollback.

## Risks to put in front of the owner

Typical ones, each accepted in writing:

- a service account that can act on every resource of its kind, or read
  template secrets;
- endpoints protected only by the product's login;
- a shared login that shows every session, artifact and variable to all its
  users, and shares usage limits;
- environment variables holding a credential (readable by every user and by
  the agent);
- account-wide deploy tokens;
- never-expiring tokens.

Note the options for later (RBAC folders, a separate preview account,
secrets behind a vault wrapper).

## Rollback

One line per change, for example: archive the cloud environments; delete the
tokens, then the service account; delete resources with the session prefix;
archive the vault items; revert or drop the repo branch (the hook does
nothing outside cloud sessions).

## The people guide

A private artifact, written so someone with no technical background can
follow it. Engineering setup goes in a separate section at the end, or a
separate page.

How to make it:

1. **Run a fresh session as the persona**, with synthetic users and demo
   data, doing the real flow (ask, see, change, "save it", tidy up). Every
   screenshot comes from that run or an earlier test session.
2. **Capture** with the browser helpers (`cdp.mjs shot`, transcript text),
   crop and resize with a small script.
3. **Check every image** for real data, other projects' names and avatars.
   Crop out the claude.ai sidebar (it lists every session on a shared
   account). Crop attribution footers. Never publish impersonation
   screenshots. Take sign-in page screenshots in a separate headless browser,
   not the user's window.
4. **Build one self-contained HTML file** (images inlined as base64), check it
   at desktop and phone width, light and dark, with click-to-zoom.
5. **Publish privately** (an artifact, or the company's internal share host),
   link it from the maintainer doc, share only when the owner says so. Label
   staged screenshots as staged. Send other people (a second approver, a team
   channel) a short note that links to the guide rather than repeating it. Keep the source and build script so it can be republished
   to the same link.

Structure that worked:

- three cards up top (No code / A few minutes / Safe to try);
- "before you start" (which login, which environment, which repo);
- numbered steps with a screenshot each, written around what people see on
  screen (environment name, repo name, buttons), not how it is built;
- what results mean (for example FAIL / WARN / PASS / SKIP) with a real
  synthetic example;
- copyable prompts and "what to ask next";
- "a colleague's link", "seeing what a real person sees";
- "if something goes wrong" and a word list;
- that the agent waits for "save it", that saving can take a while (give the
  real number), and that every PR is authored by the account's connected
  GitHub user.

## Habits that prevent wrong reports

- Re-read live state before describing it (an old reader list was once
  repeated from memory).
- Keep one copy of any list that exists in two systems, or a check that
  compares them.
- Before loosening a control to get unstuck, find out what is really
  blocking.

## Hand-over checklist

- Owner has the guide link, the maintainer doc path and the risk list.
- Token expiry dates are in the change record and on a calendar.
- A memory note for the next agent: state, traps, where the change record
  lives, open items.
- Open the repo PR only when the owner asks; merge through normal review.
