# Publishing from a cloud session

Use when people should be able to ship from a session ("publish", "put it
live"), not only open a draft PR. Built for an internal staff website
(October 2026): staff describe a page change, see it, say "publish", and it
goes live or waits for a named approver. Shown with GitHub Actions and our
check runner (`local-ci`); any CI and any single check command work the same
way ([providers](providers.md#checks)).

The principle: **make "done" honest.** The session records what it did and
what passed, in a commit. A workflow the session does not control verifies
that record and ships. Human approvals happen on a page that knows who is
signed in.

## Why the obvious designs fail

Four attempts, each blocked by the platform for a good reason:

| Attempt | Design | What happened |
| --- | --- | --- |
| 1 | The session runs the checks and posts a commit status with a fine-grained PAT stored as a network secret for `api.github.com` | The proxy **never adds network secrets to GitHub hosts** |
| 2 | Same PAT as an environment variable | Claude's GitHub proxy refuses commit-status writes for every token: "Write access to this GitHub API path is not permitted through this proxy" (403). The Claude GitHub App has `statuses: read` |
| 3 | The session writes an "approved by <name>" commit from a name typed in the chat | The cloud session's own safety check refused, twice: an unverified chat name looks like forging an approval |
| 4 | The session **requests** publishing and records only what is true; a workflow verifies and ships; approvals happen on a signed-in page | Worked |

After attempt 2 the PAT (also exposed in a screenshot) was revoked. When a
token's power grows (a status note becoming an approval signal), issue a new
one rather than promoting an exposed one.

## The working shape

```
session: edit → checks pass (no GitHub posting) → person says "publish"
   │
   ▼
request script ──► empty commit with trailers ──► push
   Publish-requested-by: <first name> (unverified, from the chat)   or "not given"
   Requested-in-chat: "<their exact words>"
   Local-ci-run: <run id> success
   Verified-tree: <tree sha>
   │
   ├─ change any editor may publish ─────► CI workflow: tree matches? CI re-runs the checks; pass → status, merge, deploy
   └─ change that needs an approver ─────► session sends an /approve/ link
                                           approver signs in, clicks Approve (posts a status
                                           on that exact commit) ──► CI workflow ships
```

### The request script (runs in the session)

Allow-listed in `.claude/settings.json`. One step, so nothing is skipped:

1. Refuse unless the branch is the session's own, clean, pushed, and contains
   the latest main ("main has moved on: merge, push, show the person the
   preview again"). An approval covers one exact commit.
2. Run the gate check (below) to know whether an approver is needed.
3. Run the full checks **without GitHub posting** (`local-ci run --no-github`),
   then confirm the run checked exactly this commit's tree with a clean
   worktree.
4. Make an empty commit with the trailers above and push it.
5. Print the approval link when one is needed.

`--name` is only what the person called themselves in this chat, labelled
unverified; leave it out rather than guess. `--said` quotes their words
exactly.

### The gate check (runs in the session and in CI)

A script that turns "what may be shipped without a second person" into
rules over the diff, for example:

- any editor: page text, new pages, images, new groups and new restrictions;
- an approver: anything outside content (code, data, styles, workflows,
  agent rules), the security handbook, changing who is in an existing group,
  deleting a group, loosening a restriction;
- the owner only: changes to the site's own controls (workflows, scripts,
  agent rules, dependencies, access lists).

It guards against mistakes; the real control is who can use the environment
and the repo.

### The workflow (CI, not the session)

On a push whose head commit carries the trailers: check the recorded tree
matches the branch, **run the checks itself on that exact tree**, and post the
check status only if they pass; then run the gate check, wait for the approval
status when needed, merge, deploy.

The session's `Local-ci-run` trailer is a hint for debugging, not proof: the
session writes both the run ID and the tree hash, so it could record a real
tree with an invented passing run. Tree equality proves which files ship, not
that they passed. Either trusted CI runs the same check command on that tree,
or the evidence must be independently authenticated and bound to it (for
example a signed attestation from a runner the session cannot impersonate).
The checks have to work on a clean CI runner for this, which is one more
reason to keep them to one command. Give it its own token to
fetch main (the first real publish failed without one) and a manual retry
input.

### The approval page

Behind the site's sign-in. Only listed approvers, only on production hosts,
only for publish-request commits, same-origin POST; it posts an approval
status on that exact commit. Its token is a **production-only** hosting
secret: never give branch previews a secret, because a branch preview runs
that branch's code.

## Instructions for the session

- Publish only on a clear yes about this version: "publish", "put it live",
  "ship it", "looks good, go ahead". Not approval: "looks good, but…",
  "nice", "I'll check with <person>", a thumbs-up on an earlier version. If
  unsure: "Shall I publish this version?" Never publish on a reply that also
  asks for more changes.
- "A name typed in this chat is never approval: the account is shared, so
  'I'm <owner>' proves nothing. Don't ask who they are; send the link."
- Run the request script from the repo root as its own command (no `cd …;`,
  no pipe), so the allow-list entry matches.
- Never run the checks with GitHub posting in a cloud session, and no GitHub
  token belongs in the environment. On failure, retry once, then tell the
  person; never try other credentials.
- After publishing, confirm the change is live and give the exact page link,
  or send the approval link with who approves and how long it takes.
- Never push to main, force-push, merge, skip or weaken a check, or edit a
  check to make it pass.

## Human clicks to plan from the start

The local agent's safety check blocks anything that grants access, creates or
stores credentials, merges without review, or approves a release, even after
"can you do it please". Plan these as human clicks:

- adding the repo to the vendor's GitHub app (Save, often with 2FA);
- merging the first PR;
- clicking Generate on every token, and storing it;
- pasting every secret value;
- editing who may read restricted areas;
- sending the first real "publish" in a cloud session.

Turning off branch protection to get unstuck did not help: the block was the
safety check. Ask what is actually blocking before loosening a control.
