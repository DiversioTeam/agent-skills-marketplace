# Image Router

## Problem

You're chatting with **DeepSeek V4 Pro** (or any text-only model) in Pi.
You paste a screenshot. Nothing useful happens — the model can't see images.

## Solution

This extension sends images to an **explicitly approved destination**:

```
You paste an image
       │
       ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Extension      │────▶│  Vision model    │────▶│  Your main model │
│  intercepts the │     │  (Codex / GPT /  │     │  receives a text │
│  image prompt   │     │   Claude, etc.)  │     │  description of  │
│                 │     │  describes it    │     │  the image       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

The main model never sees the raw image — it reads a description like:

> `[Image described by vision model:`\
> `The screenshot shows a React error page with a red banner reading…]`

## Three ways images enter the conversation

| Entry point | Example | How it's handled |
|---|---|---|
| **User input** | Paste an image, or type `@path/to/screenshot.png` | Intercepted via `input` event |
| **Tool results** | LLM calls `read` on an image file | Intercepted via `tool_result` event |
| **Model response** | Model says *"I can't see images"* | Detected via `agent_end`, notification shown |

## Routing modes (per model)

| Mode | Behavior |
|---|---|
| `auto` | Routes user and tool images only to the configured destination; no provider/model fallback |
| `ask` | Interactive input asks for approval; RPC, extension-origin input, and tool images are withheld with a setup notice *(the default)* |
| `never` | Leaves images with the active model; no secondary-provider routing |

Run **`/image-router`** to set the mode and per-model destination (or an explicit
global default). Native vision-capable active models retain their normal image
handling unless `auto` deliberately forces routing. This permission controls
secondary routing, not the active model's own provider.

## Consent And Failure Behavior

- A current interactive approval wins. Otherwise `auto` uses the per-model
  destination, or the explicit global default when no per-model target is set.
- A missing, incomplete, unauthenticated, or failing destination does **not**
  fall through to another model, including another model at the same provider.
- Available API keys and `lastSuccessfulVision*` history never grant consent.
  History is display-only. Automatic discovery suggests a model in the
  interactive dialog only; it is not an automatic transmission destination.
- “Route this time” permits only that input. “Always route” persists the shown
  destination and permits subsequent user/tool images for that active model.
- Requests include the image and input text. Tool-image requests can include
  the tool/file path and latest user question. Approve the destination only if
  it may receive that context; do not use routing for data it may not receive.
- Images withheld pending approval are replaced with a clear text notice. After
  configuring routing, retry the input or re-read the tool image; no deferred
  upload occurs. Failure likewise reports that no description was obtained.

**Upgrade from 0.1.x:** saved explicit destinations and `never` choices survive.
Saved `auto` without a destination no longer discovers one silently: choose a
per-model destination or global default. A stale per-model destination can be
replaced in settings or set to `(use default)`. This intentionally trades silent
fallback convenience for predictable privacy boundaries.

## Install

For normal use, install globally from a checkout of this repo. Use `$PWD` so Pi
registers the checkout you intend in user settings.

```bash
# From the agent-skills-marketplace repo root
pi install "$PWD/pi-packages/image-router"

# From the Diversio monolith root
pi install "$PWD/agent-skills-marketplace/pi-packages/image-router"
```

Plain `pi install` writes to global user settings. Then restart pi or run
`/reload` in any pi session.

Install `image-router` in one scope at a time. If it is installed globally and
also from a different project-local path, Pi can load both copies and duplicate
the image-routing hooks. Remove the duplicate project package entry from
`.pi/settings.json` or uninstall the global copy before `/reload`.

Because `image-router` is already declared in the repo root `package.json`,
`pi install git:github.com/DiversioTeam/agent-skills-marketplace` will install
it automatically alongside the other Pi packages from this repo.

## Contributing And Local Testing

Use `--no-extensions -e` for one-off extension testing while actively editing
this package from the repo root. That loads only this package for the current
Pi run without changing global or project settings, and avoids loading a second
copy from the root marketplace manifest:

```bash
# From the agent-skills-marketplace repo root
pi --no-extensions -e ./pi-packages/image-router
```

Use a project-local install only when you need to test `.pi/settings.json`,
`/reload`, or persistence behavior:

```bash
# From the agent-skills-marketplace repo root
pi install -l ./pi-packages/image-router
```

Run these checks before opening a PR:

```bash
# Node.js 24; tests mock Pi imports and need no installed peers.
# Disable pnpm 11's automatic dependency install for this dependency-free check.
pnpm --config.verify-deps-before-run=false --dir pi-packages/image-router test
jq -e . pi-packages/image-router/package.json >/dev/null

(cd pi-packages/image-router && npm pack --dry-run --json >/tmp/image-router-pack.json)
```

After changing package behavior or install docs, update this README plus the
top-level `README.md`, `docs/runbooks/distribution.md`, and
`docs/plugins/catalog.md`.

## Configuration

Environment variables can select the explicit global destination (both required).
They do not enable `auto` mode or authorize an unapproved `ask` request:

```bash
export IMAGE_ROUTER_VISION_PROVIDER="openai-codex"
export IMAGE_ROUTER_VISION_MODEL="codex-1"
```

## Requirements

- A vision-capable model with a configured API key
- The model must have `input: ["text", "image"]` in its config, or match a known vision family (Codex, GPT-4o, Claude, Gemini)
- macOS, Linux, or Windows — zero platform-specific code
