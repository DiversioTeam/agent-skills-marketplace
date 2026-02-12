---
description: Check what commits are pending release (on release branch but not on master).
---

Use your `release-manager` Skill in **check** mode.

Shows what is on the `release` branch but not yet on `master`:

```bash
git fetch origin master release

# PRIMARY CHECK — are there actual code differences?
git diff --stat origin/master origin/release
```

`git diff --stat` compares actual file contents between branches. It is the only
reliable way to determine whether there is something to release. If the output
is empty, there is nothing to release — stop here.

If there are differences, identify which PRs they belong to using GitHub's PR
metadata (merge timestamps):

```bash
# Get the merge date of the last release PR (the definitive cutoff)
LAST_RELEASE_DATE=$(gh pr list --base master --state merged --limit 100 \
  --json number,title,mergedAt \
  --jq '[.[] | select(.title | test("^(Release|Hotfix)"))] | sort_by(.mergedAt) | last | .mergedAt // empty' \
  2>/dev/null || echo "")

# List PRs merged to release since that date
if [ -n "${LAST_RELEASE_DATE}" ]; then
  gh pr list --base release --state merged --limit 100 --json number,title,mergedAt \
    --jq "[.[] | select(.mergedAt > \"${LAST_RELEASE_DATE}\")] | sort_by(.mergedAt) | .[] | \"#\\(.number): \\(.title)\""
else
  # No previous release — list recent merged PRs as candidates
  gh pr list --base release --state merged --limit 20 --json number,title \
    --jq '.[] | "#\(.number): \(.title)"'
fi
```

**Why the release PR's `mergedAt`?** GitHub release `publishedAt` is when a
human clicks "Publish" — which can lag behind the actual release PR merge. PRs
merged to release in that gap would be missed. The release PR's `mergedAt` is
the definitive cutoff: `git merge origin/release` captured the exact state of
release at that moment.

**Why GitHub metadata instead of `git log`?** All `git log`-based approaches
(`master..release`, `--cherry-pick`, `--first-parent` with tags) can return
stale results due to historical cherry-pick artifacts and because release tags
live on master's ancestry, not release's first-parent chain. PR merge
timestamps from GitHub are immune to git ancestry issues.

Also checks:
- Current version in `pyproject.toml`
- Recent releases for version numbering context
- Any pending release PRs

**Output:**
- Diff stat of pending changes (or empty if nothing to release)
- List of PRs pending release
- Current version
- Recommended next version (YYYY.MM.DD format)

Use this before creating a release to understand what will be included.
