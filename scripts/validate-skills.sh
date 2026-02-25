#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

MAX_LINES="${SKILL_MAX_LINES:-500}"
WARN_LINES="${SKILL_WARN_LINES:-450}"
SCOPE="${1:-}"

if [[ -n "${SCOPE}" && "${SCOPE}" != "--all" ]]; then
  echo "Usage: bash scripts/validate-skills.sh [--all]"
  exit 2
fi

SKILL_FILES=()
if [[ "${SCOPE}" == "--all" ]]; then
  while IFS= read -r skill_file; do
    SKILL_FILES+=("${skill_file}")
  done < <(find plugins -type f -name 'SKILL.md' | sort)
else
  skill_path_regex='^plugins/.+/SKILL\.md$'
  changed_candidates=""
  if [[ "${CI:-}" == "true" && -n "${GITHUB_BASE_REF:-}" ]]; then
    base_ref="origin/${GITHUB_BASE_REF}"
    if ! git rev-parse --verify "${base_ref}" >/dev/null 2>&1; then
      git fetch --no-tags --depth=1 origin "${GITHUB_BASE_REF}" >/dev/null 2>&1 || true
    fi
    if ! git rev-parse --verify "${base_ref}" >/dev/null 2>&1; then
      echo "::error::Unable to resolve base ref ${base_ref} for SKILL.md validation."
      exit 1
    fi
    changed_candidates="$(git diff --name-only "${base_ref}...HEAD" | grep -E "${skill_path_regex}" || true)"
  elif [[ "${CI:-}" == "true" && -n "${GITHUB_BEFORE:-}" && "${GITHUB_BEFORE}" != "0000000000000000000000000000000000000000" ]] && git rev-parse --verify "${GITHUB_BEFORE}" >/dev/null 2>&1; then
    changed_candidates="$(git diff --name-only "${GITHUB_BEFORE}..HEAD" | grep -E "${skill_path_regex}" || true)"
  elif [[ "${CI:-}" == "true" ]] && git rev-parse --verify HEAD~1 >/dev/null 2>&1; then
    changed_candidates="$(git diff --name-only HEAD~1..HEAD | grep -E "${skill_path_regex}" || true)"
  else
    changed_candidates="$(
      {
        git diff --name-only | grep -E "${skill_path_regex}" || true
        git diff --cached --name-only | grep -E "${skill_path_regex}" || true
        git ls-files --others --exclude-standard | grep -E "${skill_path_regex}" || true
      } | sort -u
    )"
  fi

  seen=" "
  while IFS= read -r skill_file; do
    [[ -z "${skill_file}" ]] && continue
    case "${seen}" in
      *" ${skill_file} "*) continue ;;
    esac
    seen="${seen}${skill_file} "
    SKILL_FILES+=("${skill_file}")
  done < <(printf '%s\n' "${changed_candidates}" | sort -u)
fi

if [[ "${#SKILL_FILES[@]}" -eq 0 ]]; then
  if [[ "${SCOPE}" == "--all" ]]; then
    echo "No SKILL.md files found under plugins/."
  else
    echo "No changed SKILL.md files detected."
  fi
  exit 0
fi

if [[ "${SCOPE}" == "--all" ]]; then
  echo "Validating SKILL.md size budget for all skills (max=${MAX_LINES}, warn=${WARN_LINES})..."
else
  echo "Validating SKILL.md size budget for changed skills (max=${MAX_LINES}, warn=${WARN_LINES})..."
fi

has_error=0
for skill_file in "${SKILL_FILES[@]}"; do
  if [[ ! -f "${skill_file}" ]]; then
    echo "::notice file=${skill_file}::Skipping missing SKILL.md path from diff set."
    continue
  fi

  line_count="$(wc -l < "${skill_file}" | tr -d ' ')"

  if (( line_count > MAX_LINES )); then
    has_error=1
    echo "::error file=${skill_file}::SKILL.md has ${line_count} lines (max ${MAX_LINES}). Move deep guidance to references/ and scripts/, keep SKILL.md focused on activation workflow and output contract."
    continue
  fi

  if (( line_count > WARN_LINES )); then
    echo "::warning file=${skill_file}::SKILL.md has ${line_count} lines (warn threshold ${WARN_LINES}). Consider splitting now to stay within the ${MAX_LINES}-line hard limit."
  fi
done

if (( has_error )); then
  cat <<'EOF'

Skill size validation failed.
How to fix:
1. Keep SKILL.md as an orchestrator: when to use, priorities, and output shape.
2. Move long procedures/examples to references/*.md.
3. Move reusable command logic to scripts/.
4. Keep references one level deep from SKILL.md.
5. Re-run: bash scripts/validate-skills.sh
EOF
  exit 1
fi

echo "SKILL.md size validation passed."
