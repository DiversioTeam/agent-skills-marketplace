---
name: browser-walkthrough-recording
description: "Record a real web app walkthrough with readable captions, highlights, focused close-ups, and compact MP4s; capture clean screenshots for a PR or how-to guide. Use when asked for a browser demo video or a recorded feature walkthrough."
---

# Browser walkthrough recording

Produce a real, reviewed recording, not a mockup. Default deliverables are one
silent, captioned MP4 per requested flow, clean screenshots, a text transcript,
and a reusable capture script. A guide or publishing is optional, not implicit.

## When to use

- “Record a captioned walkthrough of this local feature for the PR.”
- “Show support how this flow works, with close-ups and clean screenshots.”

For a diagram or written explanation without a live browser recording, use the
relevant documentation skill instead.

## Settle the inputs

- Ordered flow, audience, local/dev URL, demo login, and expected outcome.
- Exact environment and data ownership. Never record production or customer data.
- Destination, access restrictions, duration and upload-size limit. Default to
  local delivery; ask before uploading or changing a PR.
- Existing browser tooling: reuse the repo's Playwright and browser when possible.
  Check Node.js, Playwright, FFmpeg with libx264, and ffprobe. If absent, explain
  what must be installed; do not silently install global tools.

Use the supplied scripts relative to this skill directory. Copy the capture
script into a task-owned scratch project before adapting it; do not edit the
installed skill. Keep scripts outside directories slated for cleanup.

## 1. Prepare safe inputs

Prefer synthetic fixtures in a disposable local database. Renaming a few fields
in a customer dump does not anonymize metrics, free text, images, or audit rows.
If approved local fixture changes are needed, verify the exact database host,
name, and ownership first. Do not rely on `DEBUG`, a dev settings suffix, a host
substring, or Python `assert` as a safety boundary. Never clear whole tables,
create a superuser, or change shared data merely to make a video prettier.

Authenticate **before creating the recording context**, using a separate
unrecorded context if necessary. Transfer only the needed storage state in memory;
never commit it. Show the signed-in starting state, not passwords, tokens, login
links, or secret-bearing terminal output. One-time tokens are still secrets.
Use fictional names and reserved email domains such as `example.test`.

Inspect the app without recording first. Confirm every screen in the flow has
only safe data, including notifications, tooltips, avatars, URLs and error states.
If a leak is discovered in a capture, quarantine it locally and re-record with
safe inputs; a caption or blur is not proof that the original is safe to publish.

## 2. Plan a readable recording

Write a short storyboard: step, action, expected visible state, caption, focus
area, screenshot. Use one task per clip; aim for 30–90 seconds unless the flow
needs longer. Trim startup and idle time, not the pauses viewers need to read.

- Capture at 1440×900 with matching viewport and video size (the template default).
  Use 1920×1080 only when the interface needs it. Avoid 4K for ordinary UI demos.
- Keep text readable at the destination's normal player size. Prefer tighter
  framing or a deliberate close-up over shrinking the entire dashboard.
- Use short numbered captions, high contrast, and plain words. The template
  allows top/bottom placement; move it when it obscures the subject. Allow at
  least 2.5 seconds, longer for longer captions. Include the outcome, not just
  “click here.” Supply the same steps as accessible text outside the video.
- Highlight one relevant control at a time; remove the previous highlight. Do
  not rely on color alone: name the control in the caption. No flashing effects.
- For small controls, use a stable close-up after an establishing wide shot.
  The template's `add_zoom` changes page CSS zoom and can reflow the app: label
  it as a presentation aid, check the layout, and restore zoom afterwards. If
  reflow changes behavior, use an FFmpeg crop/scale of the **recorded** detail
  instead. Never present a cropped screenshot as a successful interaction.
- Prefer calm cuts over animated pans. Keep enough surrounding UI for orientation.

## 3. Capture

Start with [scripts/capture-template.cjs](scripts/capture-template.cjs). It exports
caption, highlight, zoom, and screenshot helpers, plus one context per flow.
The example entry point visits `APP_URL` but intentionally contains no login or
product selectors: replace its example steps with the real flow before delivery.

For a standalone scratch project, after agreeing to dependency installation:

```bash
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/browser-walkthrough.XXXXXX")"
cd "$SCRATCH"
npm init -y
npm install --save-exact playwright
npx playwright install chromium
# Copy capture-template.cjs here as capture.cjs, then adapt its flow.
APP_URL='http://localhost:8000' node capture.cjs "$SCRATCH/run-01"
```

Keep the resulting lockfile with the reusable script. Reuse an existing browser
installation rather than downloading another version when compatible. The
example accepts loopback/`.localhost` HTTP URLs only, disables service workers,
and guards HTTP requests before loading responses. It refuses **all redirects**,
including local ones: use the verified final URL directly, and adapt flows that
need redirects only after checking their destinations. Remote fonts/assets are
also blocked. A blocked request fails the run rather than silently delivering an
incomplete recording. Preserve this guard on every recorded context.

For an approved private dev host, explicitly adapt the allowlist after verifying
environment and data ownership. This HTTP guard is not a network sandbox (for
example, WebSocket traffic needs separate controls). A local URL alone is not
proof of safe data. Check redirects, linked origins, and data connections in the
unrecorded dry run as well.

Wait for real states (`locator.waitFor`, `waitForURL`, chart-ready indicators),
not `networkidle` on polling dashboards. Use fixed waits only for presentation
pacing after readiness. Close the context before reading the video path.
Use a new output directory for every run so old deliverables are not overwritten.

Playwright records each tab separately. Prefer recording the real tab transition
and explaining it; if you intentionally change `target="_blank"` to `_self`,
disclose that recording-only change. Do not alter product behavior silently.
Dismiss optional tours before capture. Do not “fix” product bugs inside this skill;
report clipping, broken states, or inaccessible controls separately.

## 4. Encode, then review

```bash
bash /path/to/skill/scripts/to-mp4.sh run-01/raw/recording.webm run-01/flow.mp4
```

The converter uses H.264, CRF 23, slow preset, yuv420p, faststart, no audio, and
preserves source resolution. It refuses an existing output, checks full decode,
and **keeps the source**. For a silent UI demo, higher CRF (try `CRF=26`) saves
space only if small text and highlight edges remain readable. Use a new output
name when comparing encodes. Do not upscale or repeatedly transcode an MP4.
If narration is requested, adapt the no-audio command and provide synchronized
subtitles plus a transcript; this default is explicitly silent.

Review the **whole final clip**, not just one frame. Check every transition,
caption timing/placement, zoom reset, highlight, sensitive-data exposure, and
successful end state. Inspect screenshots individually. Check sample frames at
start, middle, end, and every close-up at intended display size. Play the MP4
in the actual destination browser and test seek/start/end. Codec support varies
by browser build; use installed Chrome if bundled Chromium cannot decode H.264.
A successful ffprobe is not a visual-quality or browser-playback check.

Measure duration, dimensions, and bytes. Report bytes per minute and the actual
upload limit; aim below 10 MB/minute for mostly static UI, but do not sacrifice
legibility to hit a universal quota. If too large, shorten idle time first, then
compare CRF 23/26 and a smaller viewport. Re-capture if necessary.

## 5. Deliver and clean up

Deliver the MP4s, selected screenshots, transcript, capture script/lockfile, and a
short note on environment, fictional data, presentation changes, checks and gaps.
For a guide, use a simple local HTML page with relative media files, alt text,
`<video controls preload="metadata">`, and the transcript. The `visual-explainer`
skill can help author a guide when installed; it is not required for capture.

Prefer separate compressed media files to a base64 single-file HTML (base64 adds
about one third). Build an embedded copy only if specifically needed and test it
offline, checking every image, video, poster and external resource request.

Publishing requires an explicitly approved destination and visibility. Do not
push binaries to a feature or orphan asset branch by default: both grow Git
history permanently. Use the team's approved asset store or GitHub attachments
when authorized; test access as the intended viewer. A private repo link does
not make an externally hosted file private. Never publish unreviewed artifacts.

After final quality approval and verified delivery, remove only this task's raw
WebMs, rejected runs, frame checks, and scratch dependencies. Keep one final copy
and the reusable script/lockfile until handoff is confirmed. Do not delete shared
browser caches, other worktrees, test databases, or `.local-ci` directories.
For a task-owned Dev Center worktree, inspect `dev-center delete --worktree PATH`
and remove it only after merge/handoff and checking for unrelated or unpushed work.
Report deleted paths and measured space reclaimed; do not claim Git history was
reclaimed by deleting a local file.

## Completion / stop conditions

- Finished: requested flows demonstrated, full videos and screenshots reviewed,
  text steps provided, file sizes recorded, authorized delivery verified.
- Stop with a concrete blocker for missing tools/login, unsafe data, unknown
  environment, failed playback, unreadable text, or unapproved upload destination.
- Report any unperformed manual playback or visual checks as unverified; passing
  helper tests does not prove that a particular product recording is safe or good.
