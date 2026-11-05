# Release Manager — Detailed Procedures

Read SKILL.md for modes, permissions, gates, staging, and hotfix sync.
[Captured release scope](release-scope.md) owns inclusion evidence and candidate
SHA capture; do not derive release notes from a merge-date cutoff.

## Version and title conventions

| Scenario | Version / tag | PR title | GitHub release title |
|----------|---------------|----------|----------------------|
| First of day | `2026.01.21` | `Release: 21st January 2026` | `January 21st 2026` |
| Second of day | `2026.01.21-2` | `Release 2: 21st January 2026` | `Release 2: January 21st 2026` |
| Third of day | `2026.01.21-3` | `Release 3: 21st January 2026` | `Release 3: January 21st 2026` |
| Hotfix | `2026.01.21` or next daily suffix | `Hotfix Release: 21st January 2026` | `Hotfix Release: January 21st 2026` |

Release candidates use `releases/YYYY.MM.DD[-N]`; hotfixes use `hotfix/<slug>`.
There are no promotion PRs or `promote/*` branches any more. Check today's date and
existing versions/releases rather than copying example dates. Edit the project
version specifically; do not broadly replace every `version` key in TOML. Run
`uv lock` after the edit and commit `pyproject.toml` and `uv.lock` together.

## PR body contract

Release PRs record the captured scope, verified URLs, and staging evidence:

```markdown
## Captured scope
- Base SHA: <full captured target SHA>
- Source SHA: <full captured source SHA>
- Candidate head SHA: <full checked PR head SHA>

## Included PRs
- https://github.com/DiversioTeam/Django4Lyfe/pull/XXXX
- https://github.com/DiversioTeam/Django4Lyfe/pull/YYYY

## Review evidence
- Direct commits: <SHAs and explanations, or none>
- Conflict adjustments: <reviewed changes, or none>
- Scope ambiguities: <unverified entries, or none after reconciliation>
- Exact-head checks: <links/results; preflight is not post-merge proof>
- Staging: <pipeline link and staged head SHA, or not staged yet>
- Deployment: not performed by PR creation/merge
```

Reconcile every ambiguous item before finalizing notes. Older history contains
promotion containers (`promote/*` into `release`); identify their underlying
features without double-counting.
After candidate edits, update the head SHA and rerun checks. After merge, append
the actual merge SHA and separate validation/deployment/publication evidence.

## Publishing a GitHub release

Publication and deployment are separate actions. The tag belongs to the selected
production PR's **merge commit**, not the current `master` tip. The deploy helper
requires the current target head and its own exact-head checks; a later master
head must not silently inherit the selected release's validation evidence.

Release PRs must use **Create a merge commit**, not squash. Check the actual
merge result, not just the PR's title. Verify repository/authentication first;
set `REPOSITORY` to the backend's verified `owner/name` and `PR_NUMBER` to the
selected PR. Use a fail-fast shell (`set -euo pipefail`) and stop on failed checks.

### Verify the selected PR and commit

```bash
PR_DETAILS=$(gh pr view "$PR_NUMBER" --repo "$REPOSITORY" \
  --json state,baseRefName,mergeCommit,body,title)
printf '%s' "$PR_DETAILS" | jq -e '.state == "MERGED" and .baseRefName == "master"' >/dev/null
RELEASE_COMMIT_SHA=$(printf '%s' "$PR_DETAILS" | jq -er '.mergeCommit.oid')
git fetch origin master
git cat-file -e "$RELEASE_COMMIT_SHA^{commit}"
git merge-base --is-ancestor "$RELEASE_COMMIT_SHA" origin/master
# Inspect the parents: a release PR must have a real merge commit.
git show --no-patch --format='%H %P' "$RELEASE_COMMIT_SHA"
```

Require the expected merge parents and reconcile the final diff with the
recorded candidate/source evidence. A commit merely being on master is not
proof that it is the selected release. If older PRs lack captured metadata,
reconstruct scope from their actual merge parents and PR diffs; mark uncertain
attribution unverified and stop rather than inventing a timestamp boundary.

Read the version from that exact commit (Python 3.11+), not the working tree:

```bash
VERSION=$(git show "$RELEASE_COMMIT_SHA:pyproject.toml" | \
  python3 -c 'import sys, tomllib; print(tomllib.load(sys.stdin.buffer)["project"]["version"])')
git check-ref-format "refs/tags/$VERSION"
```

Check the parsed value against the date-based version convention and recorded
release notes. Inspect recent release titles with `gh release list --limit 5`
for presentation only. Recheck the notes against the captured scope; do not
blindly copy an old or manually edited PR body's inclusion claims.

### Check existing tags and releases before creation or retry

```bash
TAG_FILE=$(mktemp)
git ls-remote --tags origin "refs/tags/$VERSION" "refs/tags/$VERSION^{}" > "$TAG_FILE"
if [ -s "$TAG_FILE" ]; then
  # Fetch only to FETCH_HEAD; do not overwrite any existing local tag.
  git fetch --no-tags origin "refs/tags/$VERSION"
  TAG_COMMIT_SHA=$(git rev-parse --verify 'FETCH_HEAD^{commit}')
  test "$TAG_COMMIT_SHA" = "$RELEASE_COMMIT_SHA"
fi
```

A mismatched existing tag is a blocker. Never move/delete it automatically.
Also inspect `gh release view "$VERSION" --repo "$REPOSITORY"`:

- An existing release requires verification of its actual tag commit, notes,
  and published/draft state. If already correct, report it instead of recreating.
- Only a confirmed not-found response establishes that creation is needed.
  Authentication, rate-limit, and network errors are blockers, not absence.
- An existing draft, inconsistent notes, or a release with a missing tag needs
  an explicit repair/publication decision; do not silently edit it.
- After a timeout or partial success, repeat these read-only checks before
  retrying. Do not blindly issue another create command.

### Create and verify

After confirming no release exists and any existing tag matches the expected
commit, write the reviewed notes to a file and use the exact SHA:

```bash
gh release create "$VERSION" --repo "$REPOSITORY" \
  --target "$RELEASE_COMMIT_SHA" \
  --title "$RELEASE_TITLE" --notes-file /path/to/reviewed-release-notes.md

gh release view "$VERSION" --repo "$REPOSITORY" --json url,tagName,name,isDraft,body
# targetCommitish alone is not proof; peel the actual remote tag.
git fetch --no-tags origin "refs/tags/$VERSION"
test "$(git rev-parse --verify 'FETCH_HEAD^{commit}')" = "$RELEASE_COMMIT_SHA"
```

Check the tag/version, publication state, and notes. Report the release URL and
verified tag commit separately from deployment. A normal release needs no
back-merge. After a hotfix, follow the authorized `master → dev` sync PR in
SKILL.md; a published release does not imply that sync succeeded.

## Full end-to-end example

For an illustrative feature PR #2607 and release PR #2608:

1. #2607 merges to `dev` after review. Capture `master`/`dev`, attribute
   #2607, cut `releases/YYYY.MM.DD` from the captured base with a `--no-ff`
   merge of the captured source, bump the version, `uv lock`, and record the
   candidate head. Open #2608 to `master` with the scope evidence.
2. With staging authorization, run the trigger helper from a clean checkout of
   the exact candidate head. It checks the candidate shape and local-ci, then
   deploys staging. Test there. A fix means a new `dev` PR and a re-cut `-2`.
3. After the go-ahead, #2608 merges with a merge commit. Take its
   `mergeCommit.oid` as `RELEASE_COMMIT_SHA`.
4. With production authorization, run the helper from the exact current
   `master` head. It refuses unless that merge's tree equals the staged head's
   tree and the staged head has a successful staging deploy status.
5. Run the publication checks above: read the version from that SHA, inspect
   existing tags/releases, and create/verify the tag at that SHA. A newer
   `master` tip never changes #2608's publication target.
6. No back-merge. Only a hotfix release ends with a `master → dev` sync PR.

## Error recovery

### Merge conflicts

Inspect code conflicts manually; preserve the reviewed source changes and
record any adjustments. For lock conflicts, the existing workflow is:

```bash
git checkout --theirs uv.lock
uv lock
git add uv.lock
# Stage reviewed code resolutions explicitly, then complete the merge.
git commit -m "Merge captured dev into release candidate"
```

Use `--theirs` only for the regenerable lock file, not a blanket code resolution.
Inspect the regenerated lock diff and rerun candidate checks. If safe resolution
is unclear, stop; do not drop source changes to get a green merge.

### Wrong version before publication

Correct the project version, run `uv lock`, and add a follow-up commit. Refresh
head evidence and checks. Do not force-push a published/reviewed release branch.
If the version/tag has already shipped, stop for an explicit correction plan;
never silently repoint a published tag.

### Wrong PR base

Inspect the existing PR before retrying. Correct its base only after reviewing
the resulting scope, or close it and create a replacement with the intended
base. Link the replacement and avoid leaving duplicate active release PRs.
