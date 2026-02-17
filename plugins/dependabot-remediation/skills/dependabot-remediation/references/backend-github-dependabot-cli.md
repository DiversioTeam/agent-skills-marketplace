# Backend Dependabot GitHub CLI Reference

## Check `dependabot.yml` is present

```bash
REPO="${REPO:-$(gh repo view --json nameWithOwner --jq '.nameWithOwner')}"
gh api "repos/$REPO/contents/.github/dependabot.yml" >/dev/null 2>&1 \
  && echo "dependabot.yml present" \
  || echo "dependabot.yml missing"
```

## Fetch open Dependabot alerts (all pages)

```bash
gh api -H "Accept: application/vnd.github+json" \
  "/repos/<owner>/<repo>/dependabot/alerts?state=open&per_page=100" \
  --paginate --jq '.[]' > /tmp/dependabot_open.jsonl
```

## Filter to backend scope (required before planning)

```bash
BACKEND_ECOSYSTEM_REGEX="${BACKEND_ECOSYSTEM_REGEX:-^(pip|uv|poetry|pipenv)$}"
BACKEND_MANIFEST_REGEX="${BACKEND_MANIFEST_REGEX:-(^|/)(pyproject\\.toml|uv\\.lock|poetry\\.lock|Pipfile(\\.lock)?|requirements(\\.txt)?|requirements/)}"

jq -c \
  --arg eco "$BACKEND_ECOSYSTEM_REGEX" \
  --arg path "$BACKEND_MANIFEST_REGEX" \
  'select(
    (.dependency.package.ecosystem // "" | test($eco)) or
    (.dependency.manifest_path // "" | test($path))
  )' /tmp/dependabot_open.jsonl > /tmp/dependabot_backend_open.jsonl
```

## Count backend-scoped alerts

```bash
jq -s 'length' /tmp/dependabot_backend_open.jsonl
```

## Flat backend inventory view

```bash
jq -s -r '.[] | [
  .number,
  .dependency.package.ecosystem,
  .dependency.package.name,
  .dependency.manifest_path,
  .security_advisory.ghsa_id,
  .security_advisory.cve_id,
  .security_advisory.severity,
  (.security_vulnerability.vulnerable_version_range // "n/a"),
  (.security_vulnerability.first_patched_version.identifier // "n/a")
] | @tsv' /tmp/dependabot_backend_open.jsonl
```

## Deduplicate by package + advisory + patched version

```bash
jq -s -r '.[] | [
  .dependency.package.name,
  .security_advisory.ghsa_id,
  .security_advisory.severity,
  (.security_vulnerability.first_patched_version.identifier // "n/a"),
  .dependency.manifest_path,
  .number
] | @tsv' /tmp/dependabot_backend_open.jsonl \
| sort \
| awk -F'\t' '
{
  key=$1"\t"$2"\t"$3"\t"$4;
  count[key]++;
  manifests[key]=(manifests[key]?manifests[key]",":"")$5;
  alerts[key]=(alerts[key]?alerts[key]",":"")$6;
}
END {
  for (k in count) print count[k]"\t"k"\t"manifests[k]"\t"alerts[k]
}'
```

## Post-merge backend closure check

```bash
BACKEND_ECOSYSTEM_REGEX="${BACKEND_ECOSYSTEM_REGEX:-^(pip|uv|poetry|pipenv)$}"
BACKEND_MANIFEST_REGEX="${BACKEND_MANIFEST_REGEX:-(^|/)(pyproject\\.toml|uv\\.lock|poetry\\.lock|Pipfile(\\.lock)?|requirements(\\.txt)?|requirements/)}"

gh api -H "Accept: application/vnd.github+json" \
  "/repos/<owner>/<repo>/dependabot/alerts?state=open&per_page=100" \
  --paginate --jq '.[]' \
| jq -c \
    --arg eco "$BACKEND_ECOSYSTEM_REGEX" \
    --arg path "$BACKEND_MANIFEST_REGEX" \
    'select(
      (.dependency.package.ecosystem // "" | test($eco)) or
      (.dependency.manifest_path // "" | test($path))
    )' \
| jq -s 'length'
```
