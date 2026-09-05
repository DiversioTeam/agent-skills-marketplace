# PR Context And Publication With gh

## Establish Identity And Scope

Read repository `AGENTS.md`, relevant workflow docs, and the PR template first.
Use explicit repository/PR identity when supplied. Otherwise inspect:

```bash
git status --short
git branch --show-current
git remote get-url origin
gh pr view --json number,title,body,url,baseRefName,headRefName,headRefOid,isDraft,state
```

A failed `gh pr view` is not proof of absence. Inspect the error; repair/report
missing auth, wrong repository, or network failure before deciding to create.
Do not overwrite the user's current branch or working tree to write a body.

For an existing PR, read the complete remote diff and metadata:

```bash
gh pr view <number> --repo <owner/repo> --json title,body,commits,files,baseRefName,headRefOid,isDraft
gh pr diff <number> --repo <owner/repo>
```

The remote PR is the authority for a body being published now. Read relevant
surrounding implementation too; metadata and commit messages are not proof of
behavior. If an API output is limited, paginate or use the full fetched Git
diff rather than claiming to have reviewed omitted files.

## Choose A Base For A Proposed PR

Order: explicit user target, repository-documented workflow, then confirmed
remote default. Existing PRs retain their actual base unless a change was
requested. If candidate bases remain ambiguous, ask; never guess `main` or
`release` from a list of branch names.

```bash
gh repo view <owner/repo> --json defaultBranchRef --jq '.defaultBranchRef.name'
git symbolic-ref --short refs/remotes/origin/HEAD
```

The second command is a local cached fallback, not proof the remote default is
current. Fetch only the confirmed base/head refs needed for accurate comparison.
With `BASE_REF` set to a verified ref such as `origin/dev`:

```bash
git log "${BASE_REF}"..HEAD --oneline
git diff "${BASE_REF}"...HEAD --stat
git diff "${BASE_REF}"...HEAD
git diff --cached
git diff
git status --short
```

Three-dot diff represents branch changes since merge-base. A two-tree diff
against the current base can also include unrelated base-branch evolution;
do not call it “what reviewers see”. Inspect intended untracked files separately.
Distinguish remote PR content, unpushed commits, and uncommitted work. A proposed
body can discuss intended local changes only with their pending status explicit.

## Record Verification Honestly

Use checks and test results actually obtained for the relevant SHA. Never copy
old passing results as evidence for new changes. Label reviewer commands as a
plan when not executed. Separate deployment and staging evidence from CI.
For Python changes, follow repo gates (`ty`, then `pyright`, then `mypy`;
configured `ty` is blocking), not a hardcoded historical command.

## Publish Only When Requested

Write the proposed Markdown to a temporary body file using the file tools.
Re-read existing PR content before updating to avoid overwriting intervening
reviewer/author edits. Confirm assets referenced by the body are accessible to
repo reviewers; local visual files are not yet published.

```bash
gh pr edit <number> --repo <owner/repo> --body-file <body-file>
```

For creation, use verified head/base branches and repository policy:

```bash
gh pr create --repo <owner/repo> --head <head-branch> --base <base-branch> \
  --title '<title>' --body-file <body-file>
```

Use `--draft` only when requested or required by repository workflow. Editing a
body does not authorize changing the existing readiness state, base, title,
reviewers, labels, or branch. Committing/pushing assets requires the user's
normal authorization, not an implicit side effect of `--update`.

Verify the returned PR URL and resulting body after publication. Report any
pending visual assets or unverified checks rather than claiming full completion.
