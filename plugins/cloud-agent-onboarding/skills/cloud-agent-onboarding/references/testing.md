# Testing in real cloud sessions

Local tests are not enough: proxy, permission, classifier and start-up
behaviour only show up in real cloud sessions. Every test session's prompt
forbids changes unless the test is about changes, and every run is compared
against a known answer.

Prompt texts are in [templates](templates.md#test-prompts). Write each to a
file and send it with `cdp.mjs send <file> && cdp.mjs enter`, then
`cdp.mjs idle 20`, then `cdp.mjs text` and `cdp.mjs shot`.

**Fresh session after every change.** Environment, secret, setup-script and
`.claude/settings.json` changes only reach new sessions; an old session keeps
what it started with.

**Check evidence outside the chat**: commit statuses
(`gh api repos/<org>/<repo>/commits/<branch>/status`), the preview URL, CI
runs, the live page. A session's own report is not proof.

**Never send the person's decisive words for them** ("publish", "approve");
the agent's safety check blocks it, and it is the right boundary.

**Pick the branch carefully.** A session only sees the skill, hook and scripts
on the branch picked. Test on the feature branch until it is merged.

## The ladder

### 1. Environment check

"Environment check only: do not change, commit, or push anything." Print the
setup log; tool versions and paths against the repo's pins; a frozen install
with its time; the slowest build with time and size; a headless browser
screenshot and which browser binary worked.

What it found on the component library: setup had run outside the clone; Node and pnpm
were wrong; install took 8.7 s; the Storybook build about 3 minutes (108 s of
it type declarations, later skipped with `SKIP_DTS=true`); headless
screenshots worked only with the preinstalled Chromium at
`/opt/pw-browsers/chromium`.

### 2. Secret control

For each secret, the same request in the **project environment** and in the
**default environment**: 200 versus 401 proves the secret works and nothing
else grants access. Report status codes only, never headers.

### 3. Engineer probe

One prompt that asks for a table: check | pass/fail | one-line evidence.
Cover: hook status and logs; variables set or unset (length only, never
values); code checkout and a push **dry run**; each outside tool's version
and identity; create a test resource, use it, delete it and confirm; a
screenshot. End with "list anything in the skill or scripts that was wrong,
unclear or failed, with the fix you'd make (don't commit or push)".

For an MCP project, a "setup check" section after the real task: last commit;
how many MCP tools loaded; whether the token variable is set (never print it)
and the proxy flag's value; whether it had to wait for any background step;
the output of the write-guard test.

### 4. Diagnose

For anything that failed, a diagnosis prompt: exact error text; the tool's
own log for that run (secrets redacted, lines cut to 200 chars); proxy
variable **names**; certificate issuers through the proxy; WebSocket and
HTTP/2 behaviour; any proxy docs inside the VM. "Report plainly; don't change
any files." This is how the `cs exec` 403 was traced to a CLI that bypassed
`HTTPS_PROXY`; reproduce locally through a logging proxy, then fix.

### 5. Fix and retest

Fix locally, push the branch, then in the same session: `git pull`, rerun the
hook, repeat the failed checks. Then a fresh session with the same prompt.

### 6. Rehearsal

A full fake request with "do not push, open a pull request, or touch any
remote": one small change, the checks, a private artifact or preview, a local
commit only, with timings per step. It proves the toolchain, the output path
and the time cost.

### 7. Persona runs

Real requests as a non-engineer, in sequence, in one session: ask to see
something → change something → "save it" → "delete the test copy". Then a
shared link ("only look, don't change anything"). They test plain language,
the one consequential question, outputs, the save flow and the attribution
cleanup. Finish with a **plain prompt with no hints** ("QC item 12345")
that must still do everything right, including publishing the artifact.

### 8. Wrong starts

The other branch (`main` before merge), several repos attached, the other
product's environment. The fallback must still make the session follow the
rules.

### 9. Approval paths

What Auto mode's classifier blocks (acting as a real user, granting admin),
and that it runs after the person switches to **Accept edits**, then back to
Auto. The mode menu had Auto / Accept edits / Plan. Never work around the
classifier.

## Known answers

Always compare against something fixed: a committed reference fixture with
its expected FAIL/WARN/SKIP set; a measured build time; a 200/401 pair; a
file hash in a remote resource. "It looked fine" is not a result.

## What a run records

Session id, environment, branch, prompt file, result vs known answer, timings,
what it created and what was deleted (read back), and the instruction change
it led to. A run log from the MCP server project:

| Run | Finding | Fix |
| --- | --- | --- |
| 1 | Setup script failed: ran outside the clone | Script finds the clone, `|| true` |
| 2 | Tools loaded without approval; token unset; secret auth worked. But a 74k-character tool result, and a report waiting on an AI step that could never run | Compact results; remove the server-side AI |
| 3 | Correct answer; pytest missing; a product rule false positive | Product fix; dev extra optional |
| 4 | Users can't open the report path | Publish as an artifact |
| 5 | Plain prompt published the artifact unprompted | Done |

## Tune instructions from what sessions really did

Each row is a real session behaviour and the change it led to. This was most
of the work after the first build.

| What happened | Change |
| --- | --- |
| Status command exits 0 when signed out; hook skipped login | Grep its output |
| Submodule checkout failed (only attached repos reachable) | Status line and skill: "attach with add_repo, rerun the hook"; warn that `git -C` hits the parent |
| A CLI got 403 from the egress gateway | A relay through the proxy; a 403 tip next to the command |
| Multi-line remote command broke | Base64-encode remote commands |
| First sync from a stale base overwrote 74 files | Ancestor guard; "start from the commit the remote copy is on" |
| Classifier blocked minting a token for a real dev-data user | Synthetic users by default |
| A screen needed a real role | Product's read-only impersonation, only after Accept edits, then back |
| Wrong product's template | Default from the environment variable; ask before the other; user-level fallback |
| End-of-turn check pushed to commit unsaved work | One-line answer, wait for "save it" |
| Connector added a "Generated by Claude Code" footer | Resend the body with `update_pull_request`, read back |
| A check took over 20 minutes | Set expectations in the guide; consider moving checks |
| Technical words in replies | Plain-language reference, one question at a time |
| Skill told agents to use a specific browser | "Use whatever browser or screenshot tool your environment provides" |
| Screenshots slow and not interactive | Clickable artifact pages |
| Two sessions overwrote one preview alias | Random 4-character suffix |
| Session hand-wrote an artifact copy | "Publish exactly what the script printed; same path every round" |
| Session said "only you can open it" on a shared account | "It's a draft copy, not private; never call it private" |
| Commit-status posting failed from the session | "Never run checks with GitHub posting in a cloud session"; CI posts the status |
| Session refused to write an approver name from the chat | Request-only script; approvals on a signed-in page |
| Approval went stale after main moved | "The branch must contain today's main; an approval covers one exact commit" |
| Ambiguous yes | Explicit list of what counts as approval |

After each change, **re-run the exact prompt that failed**, then one persona
run, so you know nothing else regressed.
