# Commit and Reply — Merge Conflict Resolution Reference

Use this reference when Step 3 of `commit-and-reply` hits merge conflicts after
pulling the PR base branch.

## Inspect conflicted files

```bash
git diff --name-only --diff-filter=U
```

## Resolve by conflict type

### Migration conflicts (most common)

Two branches added migrations with overlapping numbers for the same app.

1. Accept the **base branch** version of the conflicting migration (it is
   already deployed or ahead in the pipeline):
   ```bash
   git checkout --theirs <app>/migrations/<conflicting_file>.py
   ```
2. Delete the **branch's** conflicting migration file.
3. Regenerate the branch migration with the next available number:
   ```bash
   .bin/django makemigrations <app>
   ```
4. Run `.bin/ruff format` on the new migration file.
5. Verify there are no pending model changes:
   ```bash
   .bin/django migrate --check
   ```
6. Stage the resolved files:
   ```bash
   git add <app>/migrations/
   ```

### Lock files and generated files

Regenerate instead of manually merging:

```bash
# uv.lock
uv lock
git add uv.lock

# requirements.txt (if present)
git checkout --theirs requirements.txt
git add requirements.txt
```

### Code conflicts — non-overlapping hunks

If Git marked a conflict but both changes are in different parts of the file,
accept both changes. Read both sides, verify they do not interact, then edit
the file to include both.

### Code conflicts — same function, additive changes

If both sides added different logic to the same function, read the full
function, understand both intents, and merge both changes manually.

## Stop-and-ask categories

Do **not** auto-resolve these without user confirmation:

- model field definition conflicts
- security-related code (auth, permissions, tenant scoping, PII gates)
- business-logic rewrites with incompatible approaches
- test fixture conflicts where the correct fixture shape is ambiguous

Prompt template:

> Conflict in `<file>` involves <security/schema/business logic>. This needs
> your judgment. Here's what each side did:
>
> - **Base branch**: <summary>
> - **Branch**: <summary>
>
> How should I resolve this?

## After conflicts are resolved

Complete the merge:

```bash
git commit --no-edit
```

Then re-run the full post-merge gate sequence from `commit-and-reply` before
pushing.
