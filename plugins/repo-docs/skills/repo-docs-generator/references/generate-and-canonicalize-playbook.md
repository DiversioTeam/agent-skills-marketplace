# Generate And Canonicalize Playbook

Use this file for command-heavy workflow details.

## Discovery Commands

Prefer targeted, fast inspection over broad dumps:

```bash
pwd
rg --files -g 'README.md' -g 'AGENTS.md' -g 'CLAUDE.md' -g 'docs/**' | sort
rg --files -g 'package.json' -g 'pyproject.toml' -g 'go.mod' -g 'Cargo.toml' -g '*.tf' | sort
rg --files -g '.pre-commit-config.*' -g '.github/workflows/**' -g 'Makefile' -g '.bin/**' -g 'scripts/**' | sort
rg -n "ty|pyright|mypy|ruff|eslint|prettier|djlint|pytest|vitest|jest|terraform|uv run|poetry run|pip install" \
  pyproject.toml package.json .pre-commit-config.yaml .pre-commit-config.yml .github/workflows Makefile scripts docs 2>/dev/null
```

Read the docs that already exist before deciding to add more.

## Generate Workflow Details

### 1. Inspect existing documentation

Read:

- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- Existing doc indexes such as `docs/README.md`, `docs/architecture/`,
  `runbooks/`, or `design/`

Preserve valuable human-authored content. Re-home it when the layer is wrong.

### 2. Inspect actual execution paths

Verify:

- Package manager and runtime commands
- Wrapper scripts (`.bin/*`, `make`, `just`, `scripts/*`)
- Test commands
- Pre-commit hooks
- CI jobs and job names
- Deployment or release commands

For Python repos, detect the active type gate in this order unless repo docs/CI
explicitly differ:

1. `ty`
2. `pyright`
3. `mypy`

If `ty` is configured via `pyproject.toml`, `ty.toml`, `.bin/ty`, CI, or
pre-commit, treat it as mandatory.

### 3. Decide the harness footprint

Use this rule of thumb:

- Tiny repo
  - Keep everything in `README.md` + short `AGENTS.md`
- Service or app repo
  - Add focused docs for architecture, quality gates, and development runbooks
- Large or fast-changing repo
  - Add docs for specs and plans as first-class artifacts

### 4. Write the right documents

Recommended content by file:

- `README.md`
  - Project purpose
  - Quickstart
  - Pointer to `AGENTS.md`
- `AGENTS.md`
  - Navigation map
  - Commands
  - Non-negotiable rules
  - Links to deeper docs
- `docs/architecture/overview.md`
  - Components, boundaries, request/data flows, ownership seams
- `docs/quality/gates.md`
  - Pre-commit, CI, type gates, wrappers, recurring gotchas
- `docs/runbooks/development.md`
  - Local setup, common workflows, debugging
- `docs/specs/`
  - Behavior-defining specs
- `docs/plans/`
  - Execution plans, staged rollouts, migrations

### 5. Validate before finishing

Check:

- All documented commands exist and are current.
- The docs hierarchy is easy to navigate.
- `AGENTS.md` is concise and mostly links outward.
- `CLAUDE.md` contains no unique rules.
- The docs mention repeated failure modes that would otherwise be rediscovered.

## Canonicalize Workflow Details

### 1. Find every doc entrypoint

```bash
rg --files -g 'AGENTS.md' -g 'CLAUDE.md' -g 'README.md' -g 'docs/**' | sort
```

In monorepos, group by directory and scope.

### 2. Identify stale patterns

Common stale patterns to remove:

- `pip install -r requirements.txt` when the repo uses `uv`
- `poetry run ...` when the repo uses `uv run ...`
- `python manage.py ...` when the repo standard is `.bin/django ...`
- `pytest` when the repo standard is `.bin/pytest`
- Outdated CI job names
- Old branch or release workflows

### 3. Split giant AGENTS.md files

When `AGENTS.md` is too long:

- Keep commands, navigation, and hard constraints in `AGENTS.md`
- Move architecture detail to `docs/architecture/...`
- Move quality rules to `docs/quality/...`
- Move long runbooks to `docs/runbooks/...`
- Move plans to `docs/plans/...`

### 4. Normalize CLAUDE.md

Use this exact pattern:

```markdown
@AGENTS.md

---

## Notes

This `CLAUDE.md` intentionally sources `AGENTS.md` so that requirements,
commands, and agent behavior have a single canonical entrypoint in this repo.
```

Do not leave extra behavioral rules in `CLAUDE.md`.

### 5. Capture missing harness upgrades

If the repo needs more than docs, report follow-ups such as:

- Add a wrapper for a fragile multi-step command
- Add clearer lint output for recurring failures
- Add CI checks for layer or boundary violations
- Add a `docs/plans/` index or `docs/specs/` directory

## Optional Diagram Guidance

Diagrams are optional. Use them only when they reduce ambiguity.

If you add diagrams:

- Use ASCII only
- Keep them compact
- Prefer boundaries and flow over decorative boxes
- Put deep diagrams in `docs/architecture/`, not `AGENTS.md`
