# Crafting Operations Reference

Adapted from `crafting-sandboxes-diversio-playbook-2026-04-23.md`, supplied by
the team. Historical sandbox names, branch names, snapshots, and absolute local
paths are intentionally not defaults. Inspect live templates, CLI help, and
repository manifests before using these examples. Commands with `<...>` are
placeholders, not executable values.

## Inspect And Create

```bash
cs template list -o yaml
cs template show diversio -o yaml
cs sandbox create --help
cs sandbox show <sandbox> -o yaml
```

The observed `diversio` workspaces were `backend`, `frontend`, `ds`, and
`aviato`; checkout paths were `lyfe`, `frontend`, and `ds` respectively for the
first three. Both `diversio` and `optimo` have a workspace named `frontend`,
but they point to different repositories. Inspect `optimo` separately.

For an approved legacy-product sandbox with verified remote branches:

```bash
cs sandbox create <short-name> -t diversio \
  --exclude aviato \
  -A backend -A frontend -A ds \
  -D 'backend/checkout[lyfe].version=<backend-branch>' \
  -D 'frontend/checkout[frontend].version=<frontend-branch>' \
  -D 'ds/checkout[ds].version=<design-system-branch>'
```

`-A` selects AUTO mode for those workspaces. Use only the workspaces needed.
For existing sandbox overrides, read `cs sandbox update --help`, inspect current
state/dirty checkouts, and change only approved paths. Do not alter the shared
template. If a create request times out, inspect whether the named instance
exists before retrying to avoid duplicate environments or unexpected cost.

## Verify Effective State And Workspace Reality

`cs sandbox show` contains both:
- `app.definition`: template defaults;
- `composer.from_app.overrides` and `spec.workloads`: effective overrides/specs.

Then verify actual Git branch and SHA in each requested workspace. For the
observed legacy backend path:

```bash
cs exec -W <sandbox>/backend --disable-tty -- bash -lc \
  'cd /home/owner/lyfe && git -c safe.directory=/home/owner/lyfe status --short && git -c safe.directory=/home/owner/lyfe branch --show-current && git -c safe.directory=/home/owner/lyfe rev-parse HEAD'
cs ps -W <sandbox>/backend -o yaml
cs ps -W <sandbox>/frontend -o yaml
cs ps -W <sandbox>/ds -o yaml
```

Use `--` before the remote command so `cs` does not consume `bash -lc` flags.
Use exact-path `git -c safe.directory=...` only for the verified workspace,
not a global wildcard. Ad hoc shells may have `HOME=/home/root`, system Python,
and a different PATH from owner-run daemons. Inspect manifests/processes and
use verified absolute checkout/interpreter paths, not `$HOME` assumptions.
Do not paste full process environments into chat because they may hold secrets.

## Make Frontend Consume DS Changes

Only do this when the frontend actually needs the DS change and existing hooks
have not already linked it. A separate DS checkout/Storybook process is not
proof of frontend consumption.

1. Inspect the frontend package manager, installed DS package location, build
   layout, workspace paths, and daemon name. Confirm both workspace SHAs and
   verify no relevant uncommitted changes will be overwritten.
2. Build inside DS using its pinned tooling. The observed legacy command was:

   ```bash
   cs exec -W <sandbox>/ds --disable-tty -- bash -lc \
     'cd /home/owner/ds && yarn build'
   ```

3. Transfer the build to a unique temporary directory. Prefer a working native
   copy command after reading `cs scp --help` / `cs rsync --help`. The playbook's
   fallback was a tar stream:

   ```bash
   cs exec -W <sandbox>/ds --disable-tty -- bash -lc \
     'cd /home/owner/ds && tar czf - dist' > <temporary-directory>/ds-dist.tgz
   ```

   Check the command exit status and archive listing before touching frontend.
   Reject absolute/traversal paths or unexpected links; require only expected
   build contents under `dist/`. Keep build archives private to the task.
4. Upload/extract into a new staging directory inside the verified installed
   DS package, leaving the existing `dist` untouched. Verify extraction and
   expected entrypoints before swapping. The observed legacy package root was
   `/home/owner/frontend/node_modules/@diversioteam/diversio-ds`.
5. Preserve the existing `dist` as a task-specific backup, then move the staged
   `dist` into place. Do not start with the playbook's destructive `rm -rf dist`:
   a failed transfer would leave frontend without its package. Validate paths
   and ownership before any replacement or cleanup; never delete an unrelated
   workspace or follow an unverified package symlink.
6. Clear only the verified frontend `node_modules/.vite` optimized cache and
   restart the actual frontend daemon. The observed daemon was `nodejs`:

   ```bash
   cs restart -W <sandbox>/frontend nodejs
   ```

7. Compare a checksum or change-specific marker in the built and installed
   bundle; then check frontend readiness and, when authorized, the affected UI.
   If verification fails, restore the backup and restart. Remove only artifacts
   this operation created once recovery is no longer needed.

This is an ephemeral installed-package override: future installs or checkout
hooks may replace it. Record that limitation. Automating permanent DS linking
belongs in a separate requested manifest change, not this operational task.

## Postgres Snapshot Changes

Read current definition and `cs snapshot --help`. Confirm the exact target,
owner, data-access policy, replacement/data-loss approval, and backup requirement
before either update or restore. Confirm the snapshot exists:

```bash
cs snapshot show <snapshot> -o yaml
cs sandbox update <sandbox> -D 'postgres/snapshot=<snapshot>'
cs snapshot restore <snapshot> -W <sandbox>/postgres
```

The definition update selects future desired state; only the restore command
changes the live dependency. A failed restore is a blocker, not a reason to
report the reference update as success. Do not repeat destructive operations
blindly after timeouts—inspect the target first.

After a successful authorized restore, migrate using the verified backend
manifest configuration. The observed legacy invocation was:

```bash
cs exec -W <sandbox>/backend --disable-tty -- bash -lc \
  'cd /home/owner/lyfe && .venv/bin/python manage.py migrate --configuration=CraftingDevApp'
cs exec -W <sandbox>/backend --disable-tty -- bash -lc \
  'cd /home/owner/lyfe && .venv/bin/python manage.py showmigrations --configuration=CraftingDevApp'
```

Do not assume `uv` exists in a non-interactive shell or the same configuration
applies to Optimo. Verify relevant migration state and daemon health; report
errors and recovery options rather than improvising a destructive rollback.

## Endpoint Versus Authenticated Readiness

Discover actual endpoint URLs from sandbox output; do not manufacture URLs
from remembered names. Use a read-only request to the appropriate health or
login-protected route. Record actual statuses and expected auth requirements.

- A frontend 200 proves an HTTP response, not the target feature.
- Backend 401 or DS 403 may be normal protection; inspect daemon status before
  diagnosing a failed workspace.
- Use the sandbox's legitimate login flow for authenticated browser proof.
  Do not transplant localhost cookies, expose tokens, or disable authentication.
- Report branch/spec verification, daemon readiness, endpoint reachability,
  installed DS proof, and authenticated UI proof separately.
