# Frontend Release PR Template (Remediation Wave)

Use this for integration -> production release PRs after a dependency/security
remediation wave.

```markdown
## Summary
Release batch containing dependency/security remediation changes merged to `dev` since the previous release PR.

### What's going live
- High-level remediation highlights
- Manual remediation PRs (if any)

### Change scope (`origin/<production-branch>...origin/<integration-branch>`)
- `<N>` files changed
- `+<adds> / -<dels>`

## PRs included
- https://github.com/<org>/<repo>/pull/<id>
- ...

## Validation context
- `yarn lint`: pass
- `yarn test:<suite>`: pass
- Dependabot alerts status at release-cut time
```
