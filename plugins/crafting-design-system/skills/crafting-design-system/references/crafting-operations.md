# Crafting operations

Use live CLI help and JSON/YAML output because Crafting templates, sandbox definitions, endpoint URLs, and CLI flags can
change. Never expose auth tokens in commands, logs, screenshots, or chat.

## Establish context

```sh
cs version
cs info
cs template list --output-format json
cs sandbox list --accessible-only --personal --output-format json
```

If `cs info` is unauthenticated, guide the user through `cs login` using their normal Crafting access. Do not accept a
token in chat. If multiple organizations are available, ask which Diversio organization to use and pass `--org` on
later commands.

## Find the template

For plausible templates, inspect live definitions:

```sh
cs template show <name> --def --output-format yaml
```

Require evidence of:

- a workspace checkout for `DiversioTeam/diversio-ds`
- an HTTP endpoint routing to Storybook port 6006
- use of the repository's `.sandbox/manifest.yaml` or equivalent checkout hooks
- a branch/version appropriate for experimentation

A historical template name is not evidence. If no template qualifies, stop and ask engineering to repair/provide one.
Do not create/update/remove an organization template.

## Create safely

First agree on a short non-sensitive name. Check for collisions before creating. Default access is private:

```sh
cs sandbox create <safe-name> --template <verified-template> --access private --wait
```

Do not add `--if-exists skip` and silently adopt an existing sandbox. If it exists, inspect it and ask whether to reuse.
Do not use `--refresh-base`, `sandbox rebuild`, `sandbox remove`, or exclusions without explicit data-loss confirmation.

Use `cs sandbox access show --sandbox <safe-name>`, then inspect `cs sandbox access invite --help` before inviting named
collaborators. Never switch to organization-wide sharing unless the user explicitly chooses it.

## Inspect and operate

```sh
cs sandbox show <safe-name> --output-format json
cs log nodejs --workspace <safe-name>/<ds-workspace> --kind daemon --lines 100
cs exec --workload <safe-name>/<ds-workspace> --dir <remote-checkout> -- <command>
```

Use the actual workspace, checkout path, daemon name, and endpoint returned by the live definition. The examples are
shapes, not names to copy blindly.

When already inside the Crafting DS workspace, normal file and shell tools are remote and may be used directly. When
outside it:

- file reads, edits, Git, installs, tests, and Storybook commands must execute via the remote workspace
- do not run equivalent commands against a local repository
- prefer non-interactive `cs exec`; use `cs ssh` or `cs ide` only when interaction is necessary

## Verify the template-managed startup

The tracked Optimo template already defines a `ds` workspace with Node 22.23.1, a `diversio-ds` checkout, port 6006,
and a `ds` endpoint. The checked-out DS `.sandbox/manifest.yaml` then runs its post-checkout installer and starts
Storybook through the `nodejs` daemon. Treat these live files as the expected shape, but still inspect the current
Crafting template because deployed template configuration can change.

During normal startup, do not install Node/pnpm/dependencies or start a second Storybook process. Inspect sandbox state
and daemon logs, then open the endpoint named `ds` from `cs sandbox show`. Confirm:

- checkout/post-checkout completed
- the Crafting package supplied the declared Node version
- the repository hook selected pinned pnpm and installed dependencies
- the existing daemon runs Storybook on port 6006
- the endpoint responds without Bad Gateway or Vite host rejection

Only after a verified failure should the agent rerun the repo installer or restart the existing daemon—and only inside
Crafting. If HMR is unavailable, wait for the daemon rebuild and refresh; do not install or start an alternate server.

## Save and share

A live private sandbox may remain uncommitted while iterating. Before Git operations, inspect remote `git status`, branch,
remote, and upstream. With explicit permission:

```sh
git switch -c experiment/<safe-name> # only if no existing experiment branch is intended
git add <intended-files>
git commit -m "feat: prototype <plain idea>"
git push -u origin experiment/<safe-name>
```

Use the repo's hooks and conventions; never force-push. Share the direct Storybook story URL and invite collaborators
through sandbox access controls. Sandbox sharing is not package publishing or production deployment.
