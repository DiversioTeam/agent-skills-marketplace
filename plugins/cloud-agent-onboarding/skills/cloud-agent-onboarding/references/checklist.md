# Checklist

Use for a new project (top to bottom) or an `audit` (mark each item pass,
fail or not applicable, with evidence).

## Prepare

- [ ] Platform docs re-read; differences from this skill recorded.
- [ ] Decisions answered and recorded ([assess](assess.md#decide-first)); the
      owner accepted the risks in writing.
- [ ] Worktree and change record created; pre-state captured read-only.
- [ ] Laptop assumptions audited; outside systems inventoried read-only.
- [ ] The vendor's GitHub app covers the repo and every submodule's repo; a
      throwaway session or task can clone it (Codex especially).
- [ ] Branch protection: PR required, approving review, required checks.

## Access

- [ ] Non-admin service accounts with the narrowest role.
- [ ] One token per environment, scopes confirmed in the issuing UI.
- [ ] Tokens minted into the vault or created by the human; only length and
      sha256 prefix ever printed.
- [ ] CLI credentials proven with a throwaway `HOME`, then logged out.
- [ ] Network secret vs variable decided per credential; exposures recorded.

## Environment

- [ ] Agent browser on its own profile and port; the user signed in.
- [ ] Name obvious to people; Custom network with defaults; extra hosts as
      chips; nothing extra.
- [ ] Setup script: tools only, pinned, checksums, SSH→HTTPS rewrite,
      user-level fallback, logged, `exit 0`; read back by hash.
- [ ] Variables: non-secret flags and placeholders (names read back).
- [ ] Secrets: host and path prefix; Add **and** Save; 200 in the project
      environment, 401 in default.

## Repo

- [ ] `CLAUDE.md` = `@AGENTS.md`; legacy rules mapped; links checked;
      attribution rule present.
- [ ] SessionStart hook: remote-only guard, logins, submodules for attached
      repos, status written as instructions, `exit 0`, safe to rerun; wired
      in `.claude/settings.json`; helpers allow-listed.
- [ ] Repo skill in `.claude/skills/` (and `.agents/skills/` for Codex):
      audience, what it has, request table, levels, one question with a
      recommendation, explicit-yes list, rules block, reply shape, save step
      with PR-footer cleanup, real timings, traps where they bite.
- [ ] Helper scripts for anything improvised; tokens into mode-600 files.
- [ ] `.mcp.json` works from a fresh clone; compact tool results; MCP
      instructions ordered; write guard plus test.
- [ ] Outputs: artifacts built from the real output (never called private on
      a shared account); previews behind access control if needed; draft-only
      PRs; push once.
- [ ] If sessions publish: gate rules in a script; request-only commit with
      verified trailers; CI verifies and ships; approvals on a signed-in page;
      production-only secrets; first real publish sent by the person.
- [ ] Maintainer doc; docs describe only the current system.
- [ ] Pushed to the branch sessions clone; merged through normal review when
      the owner asks.

## Test

- [ ] Environment check passed.
- [ ] Secret control passed for each secret.
- [ ] Engineer probe table all pass (or each failure fixed and retested).
- [ ] Rehearsal timed.
- [ ] Persona sequence: question → result → change → "save it" → draft PR
      with no attribution → tidy up.
- [ ] Plain prompt with no hints does everything right.
- [ ] Shared link "only look" works.
- [ ] Wrong starts (other branch, several repos, other environment) still
      follow the rules.
- [ ] Approval-gated actions: blocked in Auto, run after Accept edits, back to
      Auto.
- [ ] Everything the tests created deleted and read back; session working
      tree clean.
- [ ] Each change tested in a fresh session; evidence checked outside the
      chat (statuses, previews, CI runs, live page).

## Hand over

- [ ] People guide published privately; desktop and phone; light and dark;
      no real data, no sidebar, no other projects.
- [ ] Change record complete; risks, rollback and open items listed.
- [ ] Token expiry dates recorded and on a calendar.
- [ ] Memory note for the next agent.
