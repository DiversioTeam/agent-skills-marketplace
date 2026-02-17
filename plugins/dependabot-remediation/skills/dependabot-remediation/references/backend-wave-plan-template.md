# Backend Wave Plan Template

## Wave <N> - <Title>

### Scope

- Risk tier: <LOW|MEDIUM|HIGH>
- Target packages:
  - `<package-a>` `<old> -> <new>`
  - `<package-b>` `<old> -> <new>`

### Why this wave is grouped this way

- <short rationale>

### Alert closure target

- Advisory groups:
  - `<package>/<GHSA>` -> alerts `<#...>`
- Expected closures: `<N>`

### Execution Strategy

- [ ] Independent waves: can execute in parallel
- [ ] Stacked waves: sequential and cumulative

### Commands

```bash
# update pins
# lock / resolve
# export requirements if repo requires
```

### Validation

```bash
# lock consistency
# lint
# type gate (ty > pyright > mypy)
# targeted tests
```

### Rollback

```bash
git revert <wave-commit-sha>
# re-lock / re-export if required
```

### Exit Criteria

- [ ] Resolver succeeds
- [ ] Required gates pass
- [ ] Alert closure confirmed or explained
