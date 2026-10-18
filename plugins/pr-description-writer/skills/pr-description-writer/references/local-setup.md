# Optional Local Setup Section

A collapsed runbook in the PR description that lets a reviewer run the feature
locally from scratch. It is optional, written only with the author's consent,
and lives in exactly one PR.

## When A PR Needs It

Ask one question, for a single PR or a stack: **can a reviewer see the change
with a plain checkout and start?**

If not, the PR is a candidate. Typical reasons:

- data must be created or loaded (a seed or registration command, fixtures, a
  management command);
- new secrets or env vars, or ones loaded from a vault;
- branches must be checked out in other repos (backend, frontend, design system);
- files or services come from outside the repo (a dev bucket, a third-party
  sandbox);
- a specific user, role, or state is needed to reach the feature (for example,
  impersonating a manager and opening a direct report).

If a plain checkout and start is enough, write no section and ask nothing;
"How to test" or Verification covers it.

## Who Decides: Opt-In By The Author

The author is the person running the skill, not the reviewer. The skill cannot
reliably tell when a stack is finished or a feature is usable end to end, so:

- **Opt-in:** write the section only when the author asks for it, through the
  command's `--setup` flag or plain language such as "add e2e setup". Then
  write it without prompting, subject to the stack warning below.
- **One-time guardrail:** if the author did not ask, but the diff or context
  shows the PR needs more than checkout and start, and the feature looks
  usable end to end, ask once:
  "Seeing this change needs <reasons>. Should I add a local setup section?"
  Name the concrete reasons. Never add the section without a yes. Ask at most
  once per run; after a no, do not ask again.
- **Not for the middle of a stack:** in an unfinished stack each new PR is the
  top for a while. Being the current top is never a reason to offer the
  section. Offer it only when the needs-setup test holds **and** the feature
  looks usable end to end (for example, a PR that only adds a registration
  command, with no API or UI yet, gets no prompt).
- **Stack warning:** if the author asks for the section on a PR that has PRs
  stacked on top of it, say the section normally goes on the top PR, name the
  candidate top, and ask which PR to use.

## Placement

- **Single PR** (base is the default branch, nothing stacked on it): the
  section goes on that PR.
- **Stack:** the section goes only on the top PR. Each lower PR gets one line
  in its description, for example `End-to-end local setup: see #<top>`.
- **Across repos:** the section lives in one PR chosen by the author, usually
  the one holding most setup steps. Other repos' PRs get the one-line link.
  Do not keep copies in several PRs; they drift apart.

### Detecting A Stack

Use plain `gh` base/head detection only; do not depend on stack tools.

```bash
gh pr view <pr> --repo <owner/repo> --json baseRefName,headRefName
```

```bash
gh repo view <owner/repo> --json defaultBranchRef --jq '.defaultBranchRef.name'
```

The PR is stacked when `baseRefName` is not the default branch. To find PRs
stacked on it:

```bash
gh pr list --repo <owner/repo> --base <headRefName> --state open --json number,title
```

- **No child:** this PR is the top.
- **One child:** this PR is not the top; the child, or a PR above it, may be.
  Repeat the lookup with the child's head branch to find the top.
- **Two or more children:** the stack branches; ask the author which PR is
  the top.

Stacks across repos are not linked in git. Connect them only through a shared
issue reference or what the author says.

### When The Top Moves

If the skill is writing a PR whose parent PR holds the setup section, tell the
author and offer to move it up. Moving means the new PR gets the section and
the parent's section becomes the one-line link. Do it only with the author's
yes, and change the parent only through a separate, explicit `--update` of that
PR. Never edit other PRs as a side effect.

## Format

Place the section after Verification.

````markdown
<details>
<summary>Local setup (end to end)</summary>

Short intro: what you'll have at the end.

| Repo | Branch | PR |
|---|---|---|
| ... | ... | ... |

**1. Check out**

```bash
<one command per block>
```

**2. ...**

```bash
<command>
```

Expected: `<what success looks like>`

**N. Open it**

Where to click to see the feature.

</details>
````

- **Blank lines:** leave a blank line after `<summary>` and one before
  `</details>`. Without them GitHub does not render Markdown or code blocks
  inside.
- **Copyable commands:** one command per code block, so GitHub's copy button
  gives exactly that command. No prose or `$` prompts inside blocks.
- **Expected output:** after any step that can fail quietly, say what success
  looks like (counts, a status line, a URL).
- **Use what the repo already has:** its own tools (dev launchers, `make`,
  compose, scripts), not commands invented for the PR. Check that each command,
  script, and management command exists in the repo at the PR's head.
- **Branches, not SHAs:** name branches so the steps stay valid as the PR gets
  new commits. SHAs belong in Verification.
- **No secrets:** say where they come from ("loaded from the team vault by the
  dev tooling"), never their values. No tokens, passwords, internal hostnames,
  or personal data in commands.
- **Nothing extra:** no background the rest of the description already covers.
  It is a runbook.
- **Only verified steps:** state whether the steps were run end to end and how
  far. Mark any step that was not run as `Not run`. Never present suggested
  steps as executed.

### Generic Example

A feature that needs a seed command and a frontend branch:

````markdown
<details>
<summary>Local setup (end to end)</summary>

At the end you'll have the new reports page running locally with sample data.

| Repo | Branch | PR |
|---|---|---|
| backend | `feature/123-reports-api` | #456 |
| frontend | `feature/123-reports-page` | org/frontend#789 |

**1. Check out the backend branch**

```bash
git -C backend switch feature/123-reports-api
```

**2. Check out the frontend branch**

```bash
git -C frontend switch feature/123-reports-page
```

**3. Start the stack**

```bash
make dev
```

Secrets load from the team vault through the dev tooling.

**4. Load sample data**

```bash
python manage.py seed_reports --org demo
```

Expected: `Created 3 reports for org demo`

**5. Open it**

Sign in as a manager in the demo org and open **Reports** in the sidebar.

Steps 1–5 were run end to end on a fresh database.

</details>
````

## Keeping It Current

When updating a PR that has the section, re-check it against the current diff:
branch names, commands, expected counts, and steps. Remove steps the change no
longer needs (for example, an upload step after the upload feature is dropped)
and re-mark anything not re-run. When updating a lower stack PR, keep its
one-line link pointing at the PR that actually holds the section.
