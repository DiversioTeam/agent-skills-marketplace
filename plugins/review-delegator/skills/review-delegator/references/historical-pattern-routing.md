# Historical Pattern Routing

Use this reference when selecting review lanes. Frequencies are directional,
not a substitute for inspecting the current diff. Count recurrence by
independent PR, not by repeated rounds in one thread.

## 2026 H1 baseline

| Pattern | Representative PRs | Owner |
|---|---|---|
| Consumer obligation / lifecycle parity | #3040, #3041, #3079, #3081 | `contract-propagation-check` |
| Import/export round trip | #2974, #3034, #3035 | `import-export-roundtrip-check` |
| Stale reads / transaction scope | #3017, #3035, #3197 | `contract-propagation-check` |
| Historical rows / inverse state | #3035, #3041, #3167 | `historical-data-check` |
| Existing abstraction / constant reuse | #2949, #3035, #3036, #3037, #3079 | `codebase-reuse-finder` |
| Stable shapes weakened with `Any` | #3036, #3167 | monty-v2 type-precision sweep; reuse finder locates existing `TypedDict`s |
| Speculative guards / broad exceptions | #3035, #3036, #3197 | monty-v2 simplicity sweep + contract failure-model check |
| Mock-heavy, wrapper-only, or framework tests | #3034, #3035, #3036, #3167 | `test-quality-check` |
| Merge drift / migration numbering | #1800, #3079, #3081 | `merge-drift-check` |
| CI gates | #1800 and backend PRs | `gate-runner` |

## Lane ownership

```text
review-delegator
├── monty-v2 core
│   ├── branch and input enumeration
│   ├── precise-type / added-Any sweep
│   └── necessity and evidence-based simplicity sweep
├── contract-propagation-check
│   └── callers, lifecycle, admin, concurrency, transaction scope, boundaries
├── codebase-reuse-finder
│   └── existing constants, enums, TypedDicts, clients, decorators, helpers
├── import-export-roundtrip-check
├── historical-data-check
├── test-quality-check
├── merge-drift-check
└── gate-runner
```

Do not duplicate ownership. The delegator selects lanes and compiles; focused
skills gather evidence. Monty-v2 owns cross-file judgment when no focused skill
fits.
