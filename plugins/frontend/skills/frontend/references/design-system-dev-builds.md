# Design-system dependency stage

For Diversio DS/Frontend/Optimo work, distinguish **feature iteration** from the **consumer merge handoff**.
For other repositories, discover their publisher and branch policy rather than assuming these commands apply.

## During implementation and review

- Prefer the supported dev-package loop when a feature needs unmerged DS changes. Run `pnpm release:dev` in a clean,
  pushed DS checkout with the pinned toolchain and existing credentials; install its exact printed version in the
  matching consumer feature branch. Update manifest and lockfile together. Repeat for changed snapshots as often
  as needed; the same snapshot reuses its version. Do not wait for a stable release to implement or test the feature.
- A published dev prerelease containing the required exports is an available integration artifact. Review the
  installed version and consumer evidence; do not classify it as an unpublished dependency solely because it is a
  prerelease. Missing exports, inaccessible artifacts and source-only aliases are still real findings.
- Record DS SHA, exact package version, consumer SHA and tests/preview. Keep parallel features isolated; do not pin a
  moving dev tag, bulk-upgrade unrelated consumers or assume a submodule pointer changes installed packages.
- Verify consumption on each machine, including dev-center and Crafting. A green Storybook or correct DS checkout
  does not prove which bundle the frontend loads. Dev publishing builds/packs but does not replace required tests.
- Follow the task's publication authority. An authorized dev-publish loop does not need renewed approval for each
  iteration; a read-only/review/docs-only request is not permission to publish, push or mutate a shared sandbox.

## When preparing the consumer merge

- Coordinate a stable release containing the needed DS changes, or use a suitable stable version already available.
  The reviewed DS feature may merge through its own gates first; do not demand the stable artifact before merging
  the code that produces it.
- Replace the consumer prerelease pin, update its lockfile, remove local package overrides, clean-install and rerun
  affected checks plus required merge gates. Do not merge dev pins into shared integration/release branches.
- Report dev-build integration evidence separately from final stable-package merge readiness. Creating a feature PR
  or asking for review does not itself mean the operator requested the final merge handoff.
- Keep acceptance, compatibility, exact-SHA release validation and production authorization intact. Do not add app
  copies/fallbacks or waive checks simply to avoid the dev-build workflow.

Canonical commands: [DS publisher](https://github.com/DiversioTeam/diversio-ds/blob/dev/scripts/release/README.md).
Cross-repo mapping and sandbox guidance:
[monolith workflow](https://github.com/DiversioTeam/monolith/blob/main/docs/dev-guides/design-system-dev-builds.md).
Both apply to standalone clones; do not require the monolith just to publish/install a dev package.
