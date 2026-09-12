---
name: process-code-review
description: "Fix or explicitly defer findings from a Monty review document, interactively or with --auto."
allowed-tools:
  - Bash
  - Read
  - Edit
  - Glob
  - Grep
  - TodoWrite
---

# Process Code Review Skill

## When to Use This Skill

- After running `/monty-code-review:code-review` to generate a review document.
- When you have a `*_review.md` file with severity-tagged issues to process.
- When you want systematic, tracked resolution of code review findings.
- When reviewing a colleague's code review document and fixing issues one-by-one.

This skill is the **second step** in the code review workflow:

```text
Step 1: /monty-code-review:code-review → Creates *_review.md
Step 2: /process-code-review:process-review *_review.md → Fix/skip issues
Step 3: /backend-atomic-commit:pre-commit → Run pre-commit checks and fix issues
```

Before applying fixes, read local typing policy docs when present (for example
`docs/python-typing-3.14-best-practices.md`, `TY_MIGRATION_GUIDE.md`,
`AGENTS.md`) and align type-check behavior with those rules.

## Example Prompts

### Basic Usage

- "Process the wellbeing_service_review.md file and help me fix the issues."
- "Use your process-code-review skill on optimo_core/docs/code_reviews/api_review.md"
- "Go through the code review findings in this file and fix or skip each one."

### With Arguments

- `/process-code-review:process-review myfile_review.md` - Interactive mode (default)
- `/process-code-review:process-review --dry-run myfile_review.md` - Preview only, no changes
- `/process-code-review:process-review --auto myfile_review.md` - Auto-fix all issues
- `/process-code-review:process-review --auto --severity=NIT myfile_review.md` - Auto-fix only NITs
- `/process-code-review:process-review --severity=BLOCKING api_review.md` - Process only BLOCKING issues

## Processing Workflow

When this skill is active and you are asked to process a review document:

### 1. Parse Review Document

Read the review file and extract all issues. Look for:

- **Severity tags**: `[BLOCKING]`, `[SHOULD_FIX]`, `[NIT]`
- **Issue titles**: Following the severity tag
- **Location**: File path and line numbers
- **Code snippets**: Current problematic code
- **Problem description**: Explanation of the issue
- **Proposed fix**: Suggested code or approach

Common patterns to look for:

```markdown
### [BLOCKING] Issue Title

**Location:** path/to/file.py:L120-L145

**Current code:**
...

**Problem:**
...

**Proposed fix:**
...
```

### 2. Create Todo List

Use TodoWrite to track all issues:

- Group by severity: BLOCKING first, then SHOULD_FIX, then NIT
- Mark each as pending initially
- Update status as you process each issue

Example todo list structure:

```text
[BLOCKING] C1. N+1 Query Pattern - pending
[BLOCKING] C2. Missing Org Scoping - pending
[SHOULD_FIX] S1. Performance Issue - pending
[NIT] N1. Docstring Missing - pending
```

### 3. Present Issues One-by-One

For each issue, starting with highest severity, display:

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[SEVERITY] Issue Title (N of M)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Location: file.py:L120-L145

Current Code:
    <code snippet from review>

Problem:
    <description of issue>

Proposed Fix:
    <suggested code or approach>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

In default interactive mode, ask **Fix this issue or skip it?** and wait.
With `--auto`, continue through the selected findings without per-issue approval;
stop for consequential ambiguity or actions outside the authorized scope.
`--dry-run` only reports proposals and never changes source or review status.

### 4. Handle User Response

#### If User Says "Fix" / "Yes" / "Proceed"

1. Read the source file to understand current state
2. Apply the proposed fix using Edit tool
3. Run the affected quality checks described below; do not run a duplicate
   formatter/linter pass solely because the next section names it again.
4. Update the review document to mark the issue as FIXED:

   ```markdown
   ### [BLOCKING] Issue Title
   **Status:** ✅ FIXED (YYYY-MM-DD)
   ```

5. Update TodoWrite to mark as completed
6. Move to the next issue

#### If User Says "Skip" / "Ignore" / "No"

1. Do NOT modify the source file
2. Ask for optional reason (or use "Deferred")
3. Update the review document to mark the issue as IGNORED:

   ```markdown
   ### [BLOCKING] Issue Title
   **Status:** ⏭️ IGNORED (YYYY-MM-DD)
   **Reason:** [User's reason or "Deferred"]
   ```

4. Update TodoWrite to mark as completed (skipped)
5. Move to the next issue

### 5. Quality Checks

After each fix, run quality checks:

- `ruff check <file> --fix` - Auto-fix linting issues
- `ruff format <file>` - Format code
- Active type gate (`ty` if configured; else `pyright`; else `mypy`) - Type check
- `python manage.py check` - Django system checks (if applicable)

For touched files, "baseline acceptable" is not allowed. Resolve all active
type-gate errors before moving on. If repo policy requires wider type checks
before merge, run them before final completion.

Fix check failures caused by the change and required touched-file gate errors.
Report unrelated failures without expanding the task. Reuse passing checks for
unchanged inputs; rerun affected checks after edits and any required wider gates
before completion.

### 6. Summary After Processing

When all issues are processed, provide a summary:

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Review Processing Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Issues: 13
  ✅ Fixed: 8
  ⏭️ Skipped: 3
  📅 Deferred: 2

Files Modified:
  - optimo_core/services/wellbeing_service.py
  - optimo_core/schemas/wellbeing.py

Next Steps:
  Run /backend-atomic-commit:pre-commit to run pre-commit checks and fix issues.
  Review document remains uncommitted (working documentation).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Status Markers

Use these markers when updating review documents:

| Status | Marker | Meaning |
|--------|--------|---------|
| Open | (no marker) | Issue not yet addressed |
| Fixed | ✅ FIXED | Issue has been resolved in code |
| Ignored | ⏭️ IGNORED | Issue intentionally skipped |
| Won't Fix | 🚫 WON'T FIX | Issue acknowledged but will not be fixed |
| Deferred | 📅 DEFERRED | Issue to be addressed in future work |

Always include the date: `**Status:** ✅ FIXED (2025-01-15)`

## Severity Priority Order

Process issues in this order:

1. **[BLOCKING]** - Must fix before merge
   - Correctness issues
   - Security flaws
   - Data integrity problems
   - Multi-tenant boundary violations

2. **[SHOULD_FIX]** - Important but not blocking
   - Performance issues
   - Missing tests
   - Confusing control flow

3. **[NIT]** - Minor style/structure issues
   - Docstring improvements
   - Variable naming
   - Code organization

## Quality Gates

Before marking a review as complete, verify:

1. All [BLOCKING] issues are either Fixed or explicitly Ignored with documented reason
2. All [SHOULD_FIX] issues are addressed or have a documented deferral reason
3. Linting passes: `.bin/ruff check --fix`
4. Formatting is correct: `.bin/ruff format`
5. Active type gate passes for touched files, and any repo-required broad type
   gate is satisfied before merge
6. Relevant tests still pass

## Handling Arguments

Parse arguments to adjust behavior:

### Available Flags

| Flag | Description |
|------|-------------|
| `--dry-run` | Show all issues and proposed fixes without modifying any files |
| `--auto` | Apply all fixes without prompting (use with caution) |
| `--severity=<LEVEL>` | Filter to only process issues of specified severity |
| (no flags) | Interactive mode - prompt for each issue (default) |

### Severity Filter Values

- `--severity=BLOCKING` - Only process BLOCKING issues
- `--severity=SHOULD_FIX` - Only process SHOULD_FIX issues
- `--severity=NIT` - Only process NIT issues

### Examples

```bash
# Preview all issues without making changes
/process-code-review:process-review --dry-run api_review.md

# Auto-fix everything (careful!)
/process-code-review:process-review --auto api_review.md

# Auto-fix only minor issues, prompt for important ones
/process-code-review:process-review --auto --severity=NIT api_review.md

# Focus on critical issues only
/process-code-review:process-review --severity=BLOCKING api_review.md

# Dry-run to see only BLOCKING issues
/process-code-review:process-review --dry-run --severity=BLOCKING api_review.md
```

### Combining Flags

Flags can be combined:

- `--dry-run --severity=BLOCKING`: Preview only BLOCKING issues
- `--auto --severity=NIT`: Auto-fix only NITs (safe for minor style fixes)

## File Modification Rules

- **Source files**: Modify to apply fixes
- **Review document**: Update with status markers only
- **This skill does NOT commit**: After processing, run `/backend-atomic-commit:pre-commit` to run pre-commit checks on staged changes

## Strictness Guidelines

- For [BLOCKING] issues: Be thorough, verify the fix addresses the root cause
- For [SHOULD_FIX] issues: Apply the suggested fix, ensure it doesn't break tests
- For [NIT] issues: Apply quickly, these are usually straightforward
- Always read the source file before editing to understand context
- If a proposed fix seems incomplete or incorrect, suggest improvements before applying

## Integration Notes

This skill integrates with:

- **monty-code-review**: Generates the review documents this skill processes
- **backend-atomic-commit**: Runs pre-commit checks and fixes issues after processing

The three-step workflow ensures:

1. Thorough review generation
2. Systematic fix application
3. Pre-commit validation before any commit

## GitHub Review Comment Posting Mode

Use this mode only when the user explicitly asks to post processed findings to GitHub PR comments.

### RULES_MUST

- `MUST_01`: use one authoritative top-level review summary.
- `MUST_02`: avoid redundant inline comments (one anchor per root-cause cluster).
- `MUST_03`: run pre/post dedupe audit against both endpoints:
  - `/pulls/{pr}/comments`
  - `/issues/{pr}/comments`
- `MUST_04`: keep diagrams/ascii blocks fenced in markdown.
- `MUST_05`: if line anchor fails with `422`, fallback to file-level inline comment.

### RULES_SHOULD

- `SHOULD_01`: default inline comment cap is 5 unless user requests more.
- `SHOULD_02`: prefer editing existing submitted review in place for formatting fixes.
- `SHOULD_03`: do not post extra PR-level chatter comments.

### STEP_CHECKLIST

1. `STEP_01`: pre-audit existing reviews and comments by current user.
2. `STEP_02`: map findings to non-overlapping anchor set.
3. `STEP_03`: post review/comments once.
4. `STEP_04`: run duplicate detector and delete redundant comments if any.
