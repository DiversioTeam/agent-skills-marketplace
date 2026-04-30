# CI/CD Lane

Debug and explain frontend delivery workflows using the repo's actual CI/CD
stack.

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

When reproducing locally, use the repo's real build/lint/type/test commands
and the affected package scope for monorepos.

### 4. Release and preview rules

Use repo-local branch and release conventions from the digest. If preview
deployments require secrets or external tooling not present locally, say
exactly what is missing.

## Output

Report:
- digest status
- detected CI/deploy/preview stack
- affected workflow or failure
- local reproduction commands used
