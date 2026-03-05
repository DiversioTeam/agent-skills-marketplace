# Usage Examples

Representative user prompts for this skill:

- “Run `/backend-atomic-commit:pre-commit` on this repo and actively fix all
  files in `git status` so they obey backend `AGENTS.md`,
  `.pre-commit-config.yaml`, `.security/*` helpers, and Monty’s taste.”
- “Use `/backend-atomic-commit:atomic-commit` to prepare an atomic commit for
  the staged changes in `backend/`. Enforce all hooks and checks, then propose
  a ticket-prefixed commit message with no AI signature.”
- “Treat my current backend changes as one logical bugfix and run
  `/backend-atomic-commit:pre-commit` in a strict mode: eliminate local
  imports, fix type hints, clean up debug statements, and ensure the active
  gates are happy.”
- “Before I commit these `optimo_*` changes, run
  `/backend-atomic-commit:atomic-commit --auto` to enforce structured logging,
  ensure no PII in logs, verify tests and `.security/*` scripts, and tell me
  whether the commit is ready.”
- “Use `/backend-atomic-commit:commit` to run all gates on my staged changes,
  then create the commit once everything is green. If something fails, keep
  fixing and re-running until it commits or you have a clear `[BLOCKING]`
  reason it can’t.”
