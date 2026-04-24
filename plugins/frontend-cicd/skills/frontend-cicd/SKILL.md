---
name: frontend-cicd
description: "Digest-first frontend CI/CD workflow. Detects the repo’s real CI provider, deploy target, preview platform, and release process instead of assuming GitHub Actions, CloudFlare, or Crafting."
---

# Frontend CI/CD Skill

Debug and explain frontend delivery workflows using the repo’s actual CI/CD
stack.

## Digest-First Preflight

1. Load `docs/frontend-skill-digest/project-digest.md`.
2. Refresh it first if missing or stale.
3. Use the detected CI provider, deploy platform, preview/sandbox tooling, and
   build/test commands.

## Workflow

### 1. Identify the delivery shape

Possible combinations:
- GitHub Actions + Vercel
- GitHub Actions + Netlify
- GitHub Actions + CloudFlare
- internal preview/sandbox tooling
- other CI or deploy setups

Do not assume CloudFlare Pages or Crafting.

### 2. Route the request

Use the digest to route into:
- workflow overview
- deploy/release flow
- preview/sandbox flow
- failing CI debug

### 3. Debug with local commands

When reproducing locally, use the repo’s real build/lint/type/test commands and
the affected package scope for monorepos.

### 4. Release and preview rules

Use repo-local branch and release conventions from the digest. If preview
deployments require secrets or external tooling not present locally, say exactly
what is missing.

## Output

Report:
- digest status
- detected CI/deploy/preview stack
- affected workflow or failure
- local reproduction commands used
