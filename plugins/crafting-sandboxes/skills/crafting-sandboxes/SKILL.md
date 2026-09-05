---
name: crafting-sandboxes
description: "Create, inspect, or update Diversio Crafting sandbox instances with the cs CLI, branch overrides, frontend/design-system builds, and database snapshots."
allowed-tools: Bash Read Glob Grep
---

# Crafting Sandboxes

Use for Crafting instances/environments, template selection, workspace branch
changes, sandbox readiness, DS consumption, or Postgres snapshot changes.
Not for production deployments, local Docker setup, or unrelated cloud hosting.

## Discover Before Acting

1. Read target repo `AGENTS.md` and relevant `.sandbox/manifest.yml` or
   `.sandbox/manifest.yaml` files. Templates define workspace shape; repository
   manifests also define hooks, environment, checkout behavior, and daemons.
2. Check `command -v cs` and `cs sandbox --help`. If unavailable, ask the user
   to install/configure the organization's Crafting CLI; do not invent an
   installer, authentication command, or substitute cloud provider.
3. Refresh `cs template list -o yaml` and inspect the chosen template with
   `cs template show <template> -o yaml`. Treat auth/network failures as
   blockers, not “no templates”. Do not print credentials or full secret-bearing
   environment output in the report.
4. For existing instances, inspect `cs sandbox show <name> -o yaml` and ownership
   before mutation. Use live CLI help for version-dependent update/copy flags.

Read [references/operations.md](references/operations.md) for concrete commands,
DS build transfer, snapshot restore, and verification. Its source is the
Diversio Crafting playbook dated 2026-04-23; observed names/paths are examples,
not a substitute for current discovery.

## Pick The Right Product And Branches

- Legacy dashboard/survey work normally uses `diversio`: its `frontend`
  workspace is **Diversio-Frontend** (`frontend/` in the monolith).
- Optimo work normally uses `optimo`: its `frontend` workspace is
  **Optimo-Frontend** (`optimo-frontend/`), despite the identical workspace name.
- Scheduler-only work may use `diversio-scheduler`; verify it still exists and
  contains the needed workloads. Other templates require live inspection.
- For the observed `diversio` template, checkout paths are backend `lyfe`,
  frontend `frontend`, and design system `ds`. Overrides use checkout paths,
  not local submodule folder names. Never assume Optimo uses the same paths.
- Ask only about consequential unknowns: product, create versus update, exact
  branches, snapshot, or affected workspace when ambiguous. Infer branch intent
  from supplied PRs/current work where unambiguous; verify the remote branch
  exists. Local unpushed changes do not appear in sandbox checkouts.
- Exclude `aviato` unless needed, where supported. Use only necessary workloads.
  Prefer a fresh sandbox when both branch overrides and database data change;
  do not silently mutate an existing shared instance instead.

## Permission Boundaries

- Inspection/status requests are read-only. A create request authorizes the
  agreed new sandbox, not shared template edits or mutations of other instances.
- Before updating an existing instance, identify its owner, exact workspace,
  current/desired branches, and requested changes. Do not overwrite dirty
  workspace code or unrelated user work. Creation/update can incur cloud cost.
- Restoring a snapshot replaces live sandbox data. Obtain explicit approval
  for the exact snapshot and `<sandbox>/postgres` target, including data loss
  and any required backup. Updating a snapshot reference does not restore data.
- Only use snapshots approved for that environment and data-access policy.
  Do not download database contents or copy production secrets for convenience.
- Never delete/recreate a sandbox, modify shared templates, push branches,
  disable auth, or widen network exposure without separate authorization.

## Execute Only The Requested Change

Use a short descriptive sandbox name and validate CLI naming constraints.
Create from the inspected template with explicit workspace overrides. Verify
both effective specs and actual checkout SHAs; `app.definition` alone still
shows template defaults.

When frontend needs DS changes, a correct `ds` branch is not sufficient:
frontend normally consumes its installed `@diversioteam/diversio-ds` package.
Check whether current manifests already link/build the workspace. Otherwise,
use the reference's build → staged transfer → replace installed `dist` → clear
Vite cache → restart flow with approved target paths and rollback protection.
Do not change package manifests or lockfiles merely to test a sandbox build.

For an approved snapshot restore, update the definition, restore the live
Postgres dependency, then run migrations using the backend's actual interpreter
and configuration. Do not assume snapshot schema matches the branch. Surface
migration failure before claiming readiness or repeatedly restoring data.

## Completion Evidence

Report:
- sandbox name, template, ownership, included/excluded workloads;
- requested branch and observed SHA per checkout;
- snapshot reference versus confirmed live restore/migration status;
- DS source SHA and proof the frontend's installed bundle contains that build;
- daemon status and discovered endpoint URLs with observed response status;
- authenticated UI verification as a separate passed/not-run/blocked result;
- temporary artifacts, recovery actions, and remaining blockers.

An unauthenticated 401/403 can indicate a reachable protected endpoint; it does
not prove the user flow works. Localhost cookies do not authenticate a sandbox
domain. Never claim “visually verified” from daemon status or HTTP checks alone.
