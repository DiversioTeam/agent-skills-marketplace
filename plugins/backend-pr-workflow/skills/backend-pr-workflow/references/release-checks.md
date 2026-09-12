## Checklist 4 – Releases, Hotfixes, and Tags

This Skill enforces a clean release flow.

### 4.1 Normal release flow (via `dev` → `release` → `master`)

For normal deployments, check that:

- Feature/bugfix PRs merge into `dev` (integration branch).
- To stage changes:
  - A **promotion PR** is opened from `dev` → `release`.
  - A local-ci run on that promotion PR head is only a preflight. In
    Django4Lyfe today it can run the full parity lanes, but exact
    `origin/release` validation still happens after merge.
  - If that preflight fails, stop and dig into the harness/code instead of
    treating it as a footnote.
  - Merging that PR does **not** deploy automatically.
  - If the validated deploy helper exists, use it from the clean
    `origin/release` checkout; it validates with local-ci and then triggers
    staging deploy.
  - Otherwise, if the repo supports local-ci, validate the exact
    `origin/release` head locally and follow the repo-local deploy path.
- Before releasing to production:
  - The version (e.g. in `pyproject.toml`) is bumped to the intended release
    version using `YYYY.MM.DD` or `YYYY.MM.DD-N`.
- When ready to release:
  - A PR is created from `release` → `master` with a title like
    `Release: 21st January 2026` or `Release 2: 21st January 2026`.
  - The release PR **lists all tickets / PRs included** in the description.
  - A local-ci run on that release PR head is still only a preflight. In
    Django4Lyfe today it can run the full parity lanes, but exact
    `origin/master` parity happens on the clean merged branch head.
  - If the validated deploy helper exists, use it from the clean
    `origin/master` checkout; it validates with local-ci and then triggers
    production deploy.
  - Otherwise, if the repo supports local-ci, validate the exact
    `origin/master` head locally and follow the repo-local deploy path.
- Post-release:
  - Create a GitHub Release targeting `master`.
  - Sync `master` back into `release` and `dev` per repo docs.

If any of these are obviously missing from the plan, emit `[SHOULD_FIX]`.

### 4.2 Hotfix flow

For hotfixes, enforce:

- The hotfix PR targets `master` (not `release` or `dev`).
- The title clearly indicates a hotfix, e.g. `Hotfix Release: 21st January 2026`.
- After merge:
  - if the validated deploy helper exists, use it from the clean
    `origin/master` checkout; it validates with local-ci and then triggers
    deploy
  - otherwise, validate the exact `origin/master` head with local-ci when
    supported and follow the repo-local deploy path
  - merge changes back into `release` and **`dev`** so the integration branch
    does not drift from production
  - create a GitHub Release with the same `YYYY.MM.DD[-N]` version

If a supposed hotfix PR is targeting `dev` or `release`, or a hotfix is not
planned to be merged back into `release` **and `dev`**, emit `[BLOCKING]`.
