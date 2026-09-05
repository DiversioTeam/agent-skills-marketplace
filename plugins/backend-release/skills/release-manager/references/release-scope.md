# Captured Release Scope

Use commit evidence, not a time window. A release candidate captures `release`
when it is merged into the candidate branch, often hours before that PR merges
to `master`. Changes added to `release` during that gap belong to the next
candidate. Neither the production PR's `mergedAt` nor the GitHub release's
`publishedAt` establishes inclusion.

## Capture before preparing the candidate

Run from the target backend checkout. Set `SKILL_DIR` to the absolute directory
containing the loaded `release-manager/SKILL.md`; do not assume the marketplace
is checked out in the backend. Scope capture requires Git, jq, and Python 3.9+.
The publication TOML command separately requires Python 3.11+; scope capture
does not use `tomllib`. If the packaged helper is missing, stop and repair the
skill installation.

```bash
# Fetch failures are blockers, not an empty release scope.
git fetch origin master release
SCOPE_FILE=$(mktemp)
python3 "$SKILL_DIR/scripts/get_release_scope.py" origin/master origin/release > "$SCOPE_FILE"
# Stop if the helper failed. Never use an empty/partial file as evidence.
BASE_SHA=$(jq -er '.base_sha' "$SCOPE_FILE")
SOURCE_SHA=$(jq -er '.source_sha' "$SCOPE_FILE")
git diff --stat "$BASE_SHA" "$SOURCE_SHA"
```

Run the commands with fail-fast shell behavior (`set -euo pipefail`) or check
each status before continuing. For a promotion, fetch `dev release` and pass
`origin/release origin/dev` instead. The helper is read-only and accepts both
refs and full SHAs. All Git subprocesses ignore inherited `GIT_*` environment
overrides so scope comes from the current checkout. It rejects shallow or
unrelated histories and invalid refs.
It does not fetch, check out branches, contact GitHub, tag, publish, or deploy.

Its JSON contains:

- `base_sha`: the captured target commit.
- `source_sha`: the captured source commit.
- `tree_changed`: whether those commits have different trees.
- `source_only_commits`: complete ancestry range `base_sha..source_sha`, with
  full SHAs in topological order. This is evidence, **not** an automatic list of
  unshipped patches or included PRs.

No tree difference means no content release; report any history-only changes
separately. A difference is not sufficient by itself: version-only drift,
production-only hotfixes, reverts, and conflict adjustments require inspection.
No source-only commits means there is no new source ancestry to promote; do not
mistake an older source tree for a new release. Check pending release PRs and
the project version at `SOURCE_SHA` before recommending a date-based version.

Persist the full `BASE_SHA`, `SOURCE_SHA`, and later `CANDIDATE_HEAD_SHA` in the
PR body alongside reviewed PR URLs and any unresolved scope evidence. Keep the
scope JSON with the review artifacts. Use these captured SHAs to create and
merge the candidate; do not re-read moving refs halfway through preparation.

## Attribute the range to PRs

Inspect the captured tree diff and complete commit list. For each candidate
commit, get associated PRs using the target repository's owner/name, not the
marketplace's remote. For example:

```bash
# COMMIT_SHA comes from source_only_commits. REPOSITORY is verified owner/name.
gh api --paginate "repos/$REPOSITORY/commits/$COMMIT_SHA/pulls" \
  --jq '.[] | select(.merged_at != null) | {number, title, html_url, merge_commit_sha, base: .base.ref}'
```

Deduplicate PR numbers, inspect their base branches and merge commits, and
check ancestry against **both** captured endpoints. A PR's merge commit in
`source_only_commits` establishes new source ancestry. Association alone does
not prove inclusion: a commit can be associated with multiple PRs. Distinguish
promotion containers from underlying feature PRs; retain their full URLs.
Account for direct commits explicitly rather than inventing a PR association.
Do not cap the search at the latest 20/100 PRs or silently discard API failures.

Legacy cherry-picks/squashes can make already-shipped changes appear in the
ancestry range. Check patch equivalence and the actual diff, then reconcile
with prior release notes and PR diffs. `git cherry "$BASE_SHA" "$SOURCE_SHA"`
is useful evidence for individual non-merge patches, not proof for an entire
PR, a squash, a revert, or a conflict-adjusted merge. Mark ambiguous entries
**unverified** and stop final notes/publication until reconciled. Never fall
back to merge timestamps to make an uncertain list look complete.

## Validate the candidate and final release

After merging the captured source and committing version/lock updates:

```bash
CANDIDATE_HEAD_SHA=$(git rev-parse --verify HEAD)
git merge-base --is-ancestor "$SOURCE_SHA" "$CANDIDATE_HEAD_SHA"
git diff --stat "$BASE_SHA" "$CANDIDATE_HEAD_SHA"
```

Review conflict resolutions and the final diff; ancestry does not prove every
source patch survived a manual resolution. Record the head SHA and check CI
for that exact head. Any new candidate commit requires refreshed review and
checks. If the target advances, reassess the new target/candidate combination
before merging; do not imply the earlier preflight validated it.

After the PR merges, take `RELEASE_COMMIT_SHA` from **that PR's** `mergeCommit.oid`.
Read its version from that commit and tag that commit, even if `master` advances
before publication. See [publication checks](detailed-procedures.md#publishing-a-github-release).
Deployment remains a separate authorized operation: the backend deploy helper
requires the current clean target head. If it differs from this release commit,
stop for an explicit deployment decision rather than deploying a newer head
under the old release's validation evidence.

## Regression checks

From the marketplace checkout:

```bash
python3 -m unittest discover -s tests -p test_release_scope.py -v
```

Temporary Git histories cover a late source commit before production merge,
a moving `master` after merge, cherry-picked/reverted equal trees, invalid
refs, unrelated histories, missing shallow history, and inherited Git overrides
pointing at another checkout. No backend changes,
network calls, tags on real repositories, publication, or deployment occur.
