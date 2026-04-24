# Bumang Frontend Review Taste

These rules are the review lens for this standalone plugin.

## Priorities

1. Review against the shipped contract, not the stale description.
2. Treat missing design-system or dependency readiness as a real correctness
   issue.
3. Preserve user-visible semantics, not only visual similarity.
4. Ask for regression tests at the layer where the breakage is experienced.
5. Keep naming, imports, keys, and docs aligned to the repo’s actual norms.

## Typical Findings

- UI behavior changed in a subtle but user-visible way
- app code assumes a design-system capability that is not released or supported
- docs / PR body no longer describe the final implementation
- tests only cover helpers while the integration contract remains untested
- identifiers or imports are inconsistent with repo norms
