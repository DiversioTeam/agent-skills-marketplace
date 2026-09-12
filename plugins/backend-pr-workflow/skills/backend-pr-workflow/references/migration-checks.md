## Checklist 5 – Migrations: Cleanup and Regeneration

When the PR includes Django model changes, this Skill should be pedantic about
migrations.

### 5.1 Avoid noisy chains of migrations from one PR

If the PR has multiple intermediate migrations for the same feature
(`...x1.py`, `...x2.py`, `...x3.py`, etc.), recommend cleaning them up before
merge:

- Identify which migrations were added by this PR vs. which already exist on
  the main branches.
- Conceptual cleanup workflow:
  - Migrate back to the migration **just before** the first PR-specific
    migration.
  - Delete **only** the migrations introduced by this PR.
  - Regenerate a minimal set of migrations representing the final schema.
  - Apply the new migrations locally and ensure tests pass.

Never recommend deleting migrations that are already on production.

If the PR clearly contains many iterative migrations for one feature, emit:

- `[SHOULD_FIX]` – asking the author to collapse them into a clean final
  migration set.

### 5.2 Respect environment-specific tooling

When suggesting commands, align with the repo’s tooling:

- For Django4Lyfe / Optimo, prefer:
  - `uv run` / `.bin/django` wrappers as documented in `AGENTS.md` or linked
    repo-local docs.

This Skill should conceptually describe the migration cleanup steps, not hard
code commands that may become outdated.

## Checklist 6 – Downtime-Safe Schema Changes

This is the most critical part of the Skill for production stability.

### 6.1 Deleting a field or table

If the PR both:

- Removes a field from the database (or drops a table), **and**
- Removes or changes code that uses that field,

then:

- Highlight the deployment risk:
  - Between the time migrations run and the time all web workers are updated,
    old code can still expect the field and will throw errors if it is already
    dropped.

Enforce the safe two-step pattern:

1. **PR 1 – Code-only removal**
   - Remove all usage of the field/table from code (queries, serializers,
     forms, admin, etc.).
   - Keep the field in the DB so old and new code can still run.
   - Deploy fully.
2. **PR 2 – Schema removal**
   - Add a migration that drops the field/table.
   - Deploy once no running code expects it.

If a single PR contains both the schema drop and remaining code references, or
removes code and schema at once in a way that risks downtime, emit:

- `[BLOCKING]` – and explicitly recommend splitting into two PRs as above.

### 6.2 Adding a non-volatile default on a large table

For a new column on a large / hot table with a **static default** (e.g.
`is_active = True`):

- Explain the risk:
  - A naive `AddField` with default can cause a long-running table rewrite and
    lock, blocking writes and potentially causing errors.

Enforce a safe pattern:

1. **Migration 1 – Add nullable column, no default**
   - Add the column with `null=True` and no default.
   - This ensures the `ALTER TABLE ... ADD COLUMN` is fast.
2. **Migration 2 – Set default and backfill**
   - For Postgres 11+:
     - Use `RunSQL` to set the default for **new rows** only, avoiding a full
       table rewrite.
   - For existing rows:
     - Use a data migration, background job, or batched updates to set the
       value in manageable chunks, ideally with `atomic = False` for large
       operations.

If the PR adds a non-nullable column with a default on a table that likely has
many rows, emit:

- `[SHOULD_FIX]` or `[BLOCKING]` depending on table size and risk, and
  describe the two-step pattern above.

### 6.3 Adding a volatile default (e.g. UUID, timestamps)

For defaults that require dynamic values (e.g. generate UUIDs, timestamps):

- Warn that:
  - Setting such defaults on existing rows inside an atomic migration, for a
    large table, can be very slow and lock-heavy.

Recommend:

1. Add the column as nullable without default.
2. Backfill in batches using a non-atomic migration or out-of-band job.
3. Only then, if needed, add a default for **new** rows.

If a PR uses a volatile default in a way that will backfill a large table
inside an atomic migration, emit:

- `[BLOCKING]` – and propose the batched, non-atomic backfill approach.
