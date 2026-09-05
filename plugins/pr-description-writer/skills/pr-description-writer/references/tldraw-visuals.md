# tldraw Offline PR Visuals

Preferred creator: [tldraw offline](https://tldraw.notion.site/User-manual-tldraw-offline-39a3e4c324c080e7b2eacc5afd078e85).
Use its installed `tldraw-offline` operator skill and live `/readme` for current
API details; do not copy a machine-specific operator installation into this
marketplace. The desktop app is distinct from the hosted tldraw website.

## Check Availability Without Changing Anything

1. Look for the installed `tldraw-offline` skill and load it.
2. Use its local connection discovery/helper to check that the app is running.
   Its default local server is `http://localhost:7236`; use current launch
   metadata when the operator skill specifies another port. A stale metadata
   file or unreachable port means “not running”, not necessarily “not installed”.
3. Read `/readme` for the running app's supported document, export, and save
   operations. Keep per-launch bearer tokens private; never put them in a PR,
   command transcript, asset, or committed config. Re-read credentials per shell
   call or use the app's helper rather than assuming exported variables persist.
4. If installed but stopped, ask the user to open it. If absent, recommend
   installation using the manual above and its agent integration instructions.
   Do not invent a package-manager command or download executable software
   without approval. If the app runs but its operator skill is absent, use
   the live documented API only if available; otherwise request setup.

Suggested prompt:

> tldraw offline is the preferred, superior option here because reviewers get
> both a readable diagram and an editable source for future changes. Would you
> like to install/open it using this manual, or use Mermaid for this PR?

Ask once. If headless or awaiting a response, finish the text and mark the
visual pending. If declined, use Mermaid without further installation prompts.
An explicit user request for another format takes precedence.

## Create And Verify

- Read the repo's asset conventions, including `docs/assets/AGENTS.md` when
  present. Pick descriptive names for the diagram, editable source, and export.
- Create a new named `.tldraw` document through the app, or confirm the exact
  existing target by name/path and ownership before editing. Never repurpose
  the only open document or clear an unrelated/shared board.
- Prefer the app's Mermaid-to-bound-shapes recipe for structured diagrams;
  this still produces an editable tldraw canvas, not just a Mermaid code block.
  For hand-authored connections, use bound-arrow helpers, not decorative lines.
- Load only relevant operator recipes. Keep labels concise and architecture
  facts explicit; avoid unreadable all-in-one diagrams.
- Run canvas lints and address actionable results. Inspect a rendered image for
  clipping, overlaps, direction, and readable contrast. Verify meaning against
  the PR source—not merely a successful API response.
- Save a locally owned document through the app before reporting completion.
  Do not edit an open archive or internal database directly. Remote/shared
  document persistence belongs to its host; do not claim a local archive exists
  unless an authorized export actually produced one.
- Export a PNG using the running app's documented export operation. Save the
  editable `.tldraw` source beside it when locally owned and allowed by repo
  conventions. If export is unavailable, report that limitation; do not rename
  a JPEG screenshot to `.png` or invent an export endpoint.

## Animate Complex Data Flows

Prefer a staged animated walkthrough when a static diagram makes ordering,
branching, fan-out, queues, retries, or transaction boundaries hard to follow.
Keep simple flows static. Motion must explain a verified behavior, not decorate
arrows or imply timing guarantees the code does not provide.

### Make One Journey Easy To Follow

- Begin with a readable, stable overview. Keep node positions, labels, and the
  camera steady; animate highlights or small labeled tokens along bound edges.
- Follow one representative request, event, or record from source to outcome.
  Number the stages and show a short caption for the active step: what moved,
  what changed, and why the next component receives it. Use synthetic data only.
- Highlight the active node/edge and gently de-emphasize unrelated paths. Use
  labels and shape changes as well as color; do not rely on color alone.
- Show the happy path first. Put failure/retry and alternative branches in
  separate selectable walkthroughs, rather than moving everything at once.
- Show fan-out and joins only where real concurrency exists. Distinguish enqueue
  from worker execution, request from response, and commit from post-commit
  delivery. Clearly label illustrative timing; animation speed is not latency.
- Provide labeled play/pause, next-step, and restart controls. Default to a
  paused overview, avoid endless autoplay, and let viewers inspect every step.
  Use keyboard-accessible controls and respect reduced-motion preferences;
  reduced-motion mode uses discrete highlights/captions without moving tokens.
- Keep a complete static view and numbered text explanation available. No
  essential fact should require catching a brief moving frame.

### Use The App's Durable Script Support

Load the installed operator skill and the relevant live recipes before coding:
`animation-simulation-loop`, `add-durable-behavior-with-a-board-script`, and
`clickable-card-or-button-ui`. For a shared board, also read
`scripts-on-a-shared-board`. Do not invent APIs or install an animation library.

For a locally owned document, use `/script-workspace` for durable behavior;
read and extend existing scripts rather than replacing them. Use stable IDs
and preserve editable diagram shapes. Keep playback state per client, not in
shared shape props. Use `helpers.renderEphemeral` for visual frames so playback
does not dirty the document, persist every frame, or flood collaboration and
undo history. `history: 'ignore'` alone does not prevent persistence.

Tie listeners, timers, and animation loops to the provided abort signal. Any
persistent document writes on a shared board must be host-gated; purely local
view/playback behavior can run independently for each viewer. Do not use a
continuous loop to delete and recreate the underlying diagram.

Check `script-status` for successful application, run canvas lints, and verify
play, pause, single-step, restart, and reduced-motion/static behavior. Save the
local source and reopen it once to prove the walkthrough survives reopening
without duplicate shapes, listeners, or automatic playback. If the installed
app cannot support these requirements, report the limitation and deliver a
numbered static sequence rather than pretending the animation works.

### Preserve Animation Outside The Canvas

A PNG is static, and GitHub does not execute tldraw board scripts. Deliver the
editable source plus the overview PNG; when useful and authorized, also capture
a short video walkthrough with readable captions. Verify the actual recording
before claiming an animated PR artifact exists. If recording is unavailable,
provide the static sequence and local playback instructions instead.

For authorized GitHub publication, check `gh pr create/edit --help` for
`--attach` support and use it for the rendered image/video. References to those
local files in the body are rewritten to uploaded asset URLs. Keep editable
sources in the repo's approved asset workflow; do not assume `--attach` accepts
`.tldraw` archives. A nonzero exit can follow partial upload success: inspect
the returned PR and body before retrying to avoid duplicate PRs or attachments.
See the [GitHub CLI media announcement](https://github.blog/changelog/2026-09-01-github-cli-media-in-issues-pull-requests-and-comments/).
Uploads still require approval, and sensitive content must not be published.

## Deliver To GitHub

- Prefer repo-owned assets with Markdown embedding the rendered PNG and linking
  the editable source. Use repo-relative links in committed docs and verified
  GitHub links in the PR body, ideally pinned to the relevant commit.
- Local `file://` paths and authenticated localhost URLs cannot serve reviewers.
  Until assets are committed/pushed under the user's workflow, report their
  local paths separately and keep the live PR free of broken asset links.
- A private repo asset link is fine for authorized repo reviewers; do not move
  private content to public hosting to make the image render. External uploads
  or public board sharing require separate explicit authorization.
- Include useful alt text and a textual summary so the PR remains readable
  without the image. State source/export verification and publication status.
