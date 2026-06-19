# Release Manager — Detailed Reference

This file contains the detailed procedural steps that complement the
orchestrating SKILL.md.  Read the SKILL.md first for when to use this
skill and the core workflow, then refer here for step-by-step detail.

## Version Numbering Convention

| Scenario | Version Format | Example |
|----------|---------------|---------|
| First release of day | `YYYY.MM.DD` | `2026.01.21` |
| Second release | `YYYY.MM.DD-2` | `2026.01.21-2` |
| Third release | `YYYY.MM.DD-3` | `2026.01.21-3` |
| Hotfix release | `YYYY.MM.DD` or `YYYY.MM.DD-N` | `2026.01.21` |

## PR Title and Body Format

**Title patterns:**
- Promotion: `Promotion: 21st January 2026`
- Regular release: `Release: 21st January 2026`
- Multiple same-day: `Release 2: 21st January 2026`
- Hotfix: `Hotfix Release: 21st January 2026`

**Promotion PR body:**
```markdown
- https://github.com/DiversioTeam/Django4Lyfe/pull/XXXX
- https://github.com/DiversioTeam/Django4Lyfe/pull/YYYY
```

**Release/Hotfix PR body:**
```markdown
- https://github.com/DiversioTeam/Django4Lyfe/pull/XXXX
- https://github.com/DiversioTeam/Django4Lyfe/pull/YYYY
```

## Resolving Merge Conflicts

If the merge has conflicts:

```bash
# 1. Edit conflicted files to keep correct changes
# 2. For uv.lock conflicts, regenerate:
git checkout --theirs uv.lock
uv lock

# 3. Stage resolved files
git add <resolved-files>

# 4. Complete merge
git commit -m "Merge origin/release into releases/YYYY.MM.DD"
```

## Publishing a GitHub Release

After the release PR is merged to master, create a GitHub release.

**IMPORTANT: Merge Strategy** — Release PRs to master MUST be merged using
**"Create a merge commit"** (not squash). Squash merging breaks commit ancestry
and causes `master..release` to grow unboundedly. If GitHub is configured to
allow multiple merge strategies, always select "Create a merge commit" for
release PRs.

### Step 1: Verify PR is merged

```bash
gh pr view <PR_NUMBER> --json state,mergeCommit,mergedAt
# Should show: "state": "MERGED"
```

### Step 2: Check recent releases for format consistency

```bash
gh release list --limit 5
```

### Step 3: Get PR details for release notes

```bash
# Get the PR body which contains the list of included PRs
gh pr view <PR_NUMBER> --json body,title
```

### Step 4: Create the GitHub release

```bash
gh release create YYYY.MM.DD[-N] \
  --title "Release Title" \
  --notes "$(cat <<'EOF'
- https://github.com/DiversioTeam/Django4Lyfe/pull/XXXX
- https://github.com/DiversioTeam/Django4Lyfe/pull/YYYY
EOF
)" \
  --target master
```

### GitHub Release Title Patterns

| Release Type | Tag | Title |
|--------------|-----|-------|
| First of day | `2026.01.21` | `January 21st 2026` |
| Second release | `2026.01.21-2` | `Release 2: January 21st 2026` |
| Third release | `2026.01.21-3` | `Release 3: January 21st 2026` |
| Hotfix | `2026.01.21` | `Hotfix Release: January 21st 2026` |

### Step 5: Verify release was created

```bash
gh release list --limit 3
# Or view specific release:
gh release view YYYY.MM.DD[-N]
```

### Complete Example

```bash
# 1. Check PR is merged
gh pr view 2608 --json state,mergeCommit,mergedAt

# 2. Create release (using heredoc for multi-line notes)
gh release create 2026.01.21 \
  --title "January 21st 2026" \
  --notes "$(cat <<'EOF'
- https://github.com/DiversioTeam/Django4Lyfe/pull/2607
EOF
)" \
  --target master

# 3. Verify
gh release list --limit 3
```

## Full End-to-End Example

Here's a complete example of promoting and releasing PR #2607:

```bash
# ============================================
# PHASE 1: Promote dev → release (staging)
# ============================================

# 1. Check what's on dev but not release
git fetch origin dev release
git diff --stat origin/release origin/dev

# 2. Create promotion branch and merge dev
git checkout -b promote/2026.01.21 origin/release
git merge origin/dev --no-edit
git push -u origin promote/2026.01.21
gh pr create --base release \
  --title "Promotion: 21st January 2026" \
  --body "- https://github.com/DiversioTeam/Django4Lyfe/pull/2607"

# 3. After promotion PR is merged, staging deploy triggers automatically.
#    Validate staging before proceeding.

# ============================================
# PHASE 2: Release release → master (production)
# ============================================

# 4. Check what needs releasing
git fetch origin master release
git diff --stat origin/master origin/release
# Output shows files changed — confirms there IS something to release

# 5. Identify which PRs are included
LAST_RELEASE_DATE=$(gh pr list --base master --state merged --limit 100 \
  --json number,title,mergedAt \
  --jq '[.[] | select(.title | test("^(Release|Hotfix)"))] | sort_by(.mergedAt) | last | .mergedAt // empty' \
  2>/dev/null || echo "")
gh pr list --base release --state merged --limit 100 --json number,title,mergedAt \
  --jq "[.[] | select(.mergedAt > \"${LAST_RELEASE_DATE}\")] | sort_by(.mergedAt) | .[] | \"#\\(.number): \\(.title)\""
# Output: #2607: #GH-4420: Include alert notifications in Slack App Home

# 6. Create branch from master and merge release
git checkout -b releases/2026.01.21 origin/master
git merge origin/release --no-edit

# 7. Bump version (^ anchors to line start — only matches project-level
#     version, not python-version or target-version under [tool.*] sections)
sed -i '' 's/^version = ".*"/version = "2026.01.21"/' pyproject.toml
uv lock
git add pyproject.toml uv.lock
git commit -m "Version bump to 2026.01.21"

# 8. Push and create release PR
git push -u origin releases/2026.01.21
gh pr create --base master \
  --title "Release: 21st January 2026" \
  --body "- https://github.com/DiversioTeam/Django4Lyfe/pull/2607"

# 9. After PR is merged, publish GitHub release
gh pr view 2608 --json state  # Verify merged
gh release create 2026.01.21 \
  --title "January 21st 2026" \
  --notes "- https://github.com/DiversioTeam/Django4Lyfe/pull/2607" \
  --target master

# 10. Merge master back into release AND dev (MANDATORY)
git fetch origin
git checkout release
git merge origin/master --no-edit
git push origin release
git checkout dev
git merge origin/release --no-edit
git push origin dev

# 11. Verify
gh release list --limit 3
git diff --stat origin/master origin/release  # Should be empty
git diff --stat origin/release origin/dev      # Should be empty
```

## Error Recovery

### Merge conflict during release branch creation
```bash
# For uv.lock conflicts:
git checkout --theirs uv.lock
uv lock
git add uv.lock

# For code conflicts: resolve manually, then:
git add <resolved-files>
git commit  # Completes the merge
```

### Wrong version bumped
```bash
# Edit pyproject.toml to correct version
uv lock
git add pyproject.toml uv.lock
git commit --amend -m "Version bump to correct-version"
git push --force-with-lease  # Only if not yet reviewed
```

### PR created against wrong base
```bash
gh pr close <NUMBER>
# Create new PR with correct base
gh pr create --base master ...
```
