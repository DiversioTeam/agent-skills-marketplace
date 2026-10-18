# Driving vendor web UIs

Almost every setup step happens in a web UI: claude.ai, chatgpt.com, GitHub,
Cloudflare, the outside system's dashboard. The agent cannot and should not
log in. The pattern: the agent runs its own browser, the human signs in, the
agent does small scripted steps and reads every result back.

## Pick a browser driver

Use whichever is available and already trusted on the machine:

1. **Playwright MCP** (`browser_navigate`, `browser_snapshot`,
   `browser_click`, `browser_evaluate`, …). It has its own profile; the user
   signs in once per service. Traps: refs go stale in claude.ai menus
   (re-snapshot after every click); `browser_type` fails on combobox buttons
   (click the option instead); screenshots may be restricted to an allowed
   root such as `.playwright-mcp/`; the browser can restart and lose tabs.
2. **A separate Chrome with a debug port** (when the MCP is unavailable or
   computer use is blocked). Use [`scripts/cdp.mjs`](../scripts/cdp.mjs).

Set up once per shell. `cdp.mjs` reads `CDP_PORT` and `TAB`, so export them
and launch Chrome on the same port:

```bash
SKILL_DIR=<this skill's directory, the one holding SKILL.md>
cdp() { node "$SKILL_DIR/scripts/cdp.mjs" "$@"; }   # a function: zsh does not word-split a command in a variable
export CDP_PORT=9333            # a free port; another session may own 9222
export TAB=claude.ai/code       # cdp.mjs acts on the first tab whose URL contains this
SCRATCH=${SCRATCH:-$(mktemp -d)}; mkdir -p "$SCRATCH"
# Launch our own Chrome, or stop: never reuse a browser already on the port.
cdp_browser() {
  if curl -s "http://127.0.0.1:$CDP_PORT/json/version" >/dev/null; then
    echo "port $CDP_PORT is taken by another browser; set another CDP_PORT and run cdp_browser again"
    unset CDP_PORT; return 1
  fi
  open -na "Google Chrome" --args --remote-debugging-port="$CDP_PORT" \
    --user-data-dir="$SCRATCH/chrome-cdp-profile" --no-first-run --no-default-browser-check \
    "https://claude.ai/code"
  until curl -s "http://127.0.0.1:$CDP_PORT/json/version" >/dev/null; do sleep 1; done
  # bring it forward so the user can sign in
  osascript -e "tell application \"System Events\" to set frontmost of (first process whose unix id is $(pgrep -f "remote-debugging-port=$CDP_PORT" | head -1)) to true"
}
cdp_browser
```

Every `cdp <action>` below assumes `cdp_browser` succeeded. On a taken port it
returns 1 and unsets `CDP_PORT`, and `cdp.mjs` refuses to run without
`CDP_PORT` (it has no default port), so later `cdp` calls fail before
connecting to anything instead of driving someone else's browser. Export a
new port and run `cdp_browser` again. Changing the setting of a browser you did not
launch is never acceptable.

Recent Chrome versions refuse remote debugging on the default profile, so a
separate `--user-data-dir` is required anyway. A scratch profile also leaves
the user's own cookies and passwords alone.

## Habits that kept this safe

- **One browser, its own profile.** Before launching, check whether the port
  is taken; if a Chrome there belongs to another session (check its profile
  path read-only), leave it and use another port.
- **The user signs in.** The agent opens the page and waits for "done". It
  does not type credentials or watch the login.
- **Never close a tab the user might be using**, and never `browser.close()`
  on a CDP-attached browser (it can close the user's Chrome). Exit the
  process instead. Open new tabs for sign-ins and leave them open.
- **Small steps, one action per call, read the result before the next.** A
  run that launched many browser sessions led to the rule "one browser, a few
  small steps at a time".
- **Check you are on the right dialog and the right environment before
  writing.** Compare the dialog title and the name input; stop on mismatch.
  The claude.ai edit dialog opens with the cursor in the **Name** field: a
  stray keystroke renamed one environment to "Internal websiteeed". Only click
  Save if the name is still exact.
- **Read the form before filling it**: list every `input`, `textarea` and
  `[role=checkbox]` in the `[role=dialog]` with its placeholder before typing.
  Once a secret's name was typed into the setup-script box by mistake.
- **Find by text, not position**:
  `[...document.querySelectorAll("button")].find(b => b.innerText.trim() === "Save changes")`.
- **Never screenshot a dialog that holds a pasted secret.** One check
  screenshot showed a PAT in full; it landed in the session log and the token
  had to be replaced. Read lengths instead ("the value field holds 93
  characters").
- **Don't act in a tab while the person is typing there.** Stop if the
  composer or a field changes under you. A screenshot tab once captured the
  person's keystrokes and sent a stray sign-in email. Open your own tabs and
  touch only those.
- **Set React-controlled fields with the native setter plus an `input`
  event**; a plain `.value =` is ignored:
  `Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(ta, v); ta.dispatchEvent(new Event('input',{bubbles:true}))`.
- **Read every save back**: reopen the dialog and hash the field
  (`cdp field-hash`). The stored setup script loses its final newline, so
  hash the local file without one: `printf '%s' "$(cat setup.sh)" | shasum -a 256`.
- **Press Escape on any failure** so a half-edited dialog is not saved by a
  later click.
- **Secrets go in through stdin** (`cdp fill-env-line`), never argv; the
  script prints only length and hash prefix and writes only into an empty
  line.
- Write long prompts to a file and insert them with `Input.insertText` (or
  focus the contenteditable and `document.execCommand("insertText", false,
  text)`), not per-key typing. Check the composer was empty first and that the
  text landed.
- **Hover-only menus** (the claude.ai environment menu: row → arrow →
  settings) need a real mouse move (`Input.dispatchMouseEvent` with
  `mouseMoved`), sometimes then `ArrowRight`; a synthetic `click()` does not
  open them.

## claude.ai/code landmarks (October 2026; they drift)

Re-discover with
`cdp eval '[...document.querySelectorAll("[data-testid]")].map(e=>e.dataset.testid)'`.

| What | Selector or text seen |
| --- | --- |
| Environment picker | `[data-testid=environment-bar-trigger]` (earlier `epitaxy-env-pill`); "More" submenu `[data-testid=env-picker-more]`; each environment a `[role=menuitemradio]` whose text includes `"<Name>, environment settings"`, with a gear `button` inside (appears on hover) |
| New environment | "New environment" / "Add cloud environment…" |
| Environment row (env, repo, branch) | `[data-testid=environment-bar-row]`; branch picker `[data-testid=environment-bar-repo-branch]` |
| Search boxes | `input[placeholder^="Search environments"]`, `input[placeholder^="Search repositories"]` |
| Composer | `[data-testid=code-prompt-input]` (contenteditable inside); target the editor, not the placeholder span |
| Transcript | `[data-testid=epitaxy-virtual-transcript]`, or `main` |
| Status | `[data-testid=response-status-announcer]` ("Claude is responding" / "Claude finished the response"); a Stop button while busy; "Needs your input" or a radio group when a question is waiting |
| Mode | a `button` with text `Auto`, `Accept edits` or `Plan` |
| Environment form | name `input[placeholder="My app"]`; setup script `textarea[placeholder^="#!/bin/bash"]`; variables `textarea[placeholder^="NODE_ENV"]`; textareas in order: allowed domains, setup script, variables |
| Edit environment | gear with `aria-label="Edit cloud environment"` in a session's side panel |

Form traps: clicking the "Also include default list of common package
managers" **label** did not tick it; click `span[role=checkbox]` and read
`aria-checked`. Menus close when the pointer leaves, so do open-hover-click in
one script call. The secret form's submit button is **Add**, not "Connect".
A one-time notice (for example about auto mode) can cover the page; make
every step tolerant of a missing element. The variables box drops comment
lines on some saves; do not rely on comments there.

## Watching a running session

Poll every 15–30 seconds; treat a reply as finished when the transcript
text's hash is unchanged for several polls, or stop when the session has been idle twice in a row
and no "Running…" / "Publishing…" line shows, or when it needs input. Run the
watcher in the background (or under a monitor tool that prints a digest
when the transcript hash changes), then read the transcript text and
screenshot. `TAB=<session id> cdp idle <minutes>` does the waiting (the tab is
chosen by `TAB`, not an argument).

## Other UIs met on the way

- **GitHub token pages** accept `scopes=` and `description=` query params;
  read the ticked boxes back.
- **Cloudflare**: Escape in the Access policy editor opens "Leave without
  saving?"; click Cancel, then Save policy. Wrangler's
  `pages project create` needed `--force` to avoid Workers-based Pages.
- **ChatGPT / Codex**: sign-in is the human's; repository access depends on
  the ChatGPT GitHub connector and org approval (see [platforms](platforms.md)).
