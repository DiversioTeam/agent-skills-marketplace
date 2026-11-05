## Checklist 4 – Releases, Hotfixes, and Tags

This Skill enforces a clean release flow.

### 4.1 Normal release flow (`dev` → `releases/*` → `master`)

For normal deployments, check that:

- Feature/bugfix PRs merge into `dev` (integration branch). Merging deploys
  nothing.
- The release candidate is a `releases/YYYY.MM.DD[-N]` branch cut from the
  current `master`, with a `--no-ff` merge of a chosen `dev` commit and a
  version bump (`YYYY.MM.DD` or `YYYY.MM.DD-N` in `pyproject.toml` + `uv.lock`)
  and nothing else. The PR targets `master`, is titled like
  `Release: 21st January 2026`, and **lists every included PR**.
- Staging deploys the exact candidate head:
  - If the validated deploy helper exists, run it from a clean checkout of
    that head; it checks the candidate shape, runs local-ci once for that
    tree (reused on re-staging), then triggers the staging deploy.
  - Otherwise, validate the exact head with local-ci once and follow the
    repo-local deploy path.
  - No extra local-ci runs on the release PR or `master`: the PR head is the
    staged commit and production reuses the result by tree. If the run fails,
    stop and dig into the harness/code instead of treating it as a footnote.
  - A fix found on staging goes to `dev` through a reviewed PR; the candidate
    is then re-cut (`-N+1`) and re-staged. Commits pushed straight onto a
    `releases/*` branch are `[BLOCKING]`.
- After the release PR merges (merge commit, never squash):
  - Run the deploy helper from the clean exact `origin/master` head. It runs
    no local-ci and refuses unless the merge commit's tree equals the staged
    head's tree and that head has a successful staging deploy and local-ci
    status for the same tree.
  - Create the GitHub Release at the release PR's merge commit.
  - No back-merge is needed for a normal release.

If any of these are obviously missing from the plan, emit `[SHOULD_FIX]`.

### 4.2 Hotfix flow

Only when `dev` holds work that cannot ship. Enforce:

- The hotfix PR is `hotfix/<slug>` from `master` and targets `master`.
- It gets normal review and local-ci; the title is like
  `Hotfix Release: 21st January 2026`, with the `YYYY.MM.DD[-N]` version bump.
- After merge:
  - run the deploy helper with `--hotfix` from the clean exact `origin/master`
    head (it skips the staged-tree check; the report must say staging was
    skipped), or follow the repo-local deploy path
  - create a GitHub Release with the same version
  - open a `master` → `dev` sync PR so the integration branch does not drift
    from production

If a supposed hotfix PR targets `dev`, or no `master` → `dev` sync is planned,
emit `[BLOCKING]`.
