# Image Router

## Problem

You're chatting with **DeepSeek V4 Pro** (or any text-only model) in Pi.
You paste a screenshot. Nothing useful happens — the model can't see images.

## Solution

This extension acts as a **transparent middleman**:

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
| `auto` | Routes silently — you never see a prompt |
| `ask` | Shows a TUI dialog asking what to do *(the default)* |
| `never` | Sends images to the model as-is |

Run **`/image-router`** to open the settings panel and change modes.

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
jq -e . pi-packages/image-router/package.json >/dev/null

(cd pi-packages/image-router && npm pack --dry-run --json >/tmp/image-router-pack.json)
```

After changing package behavior or install docs, update this README plus the
top-level `README.md`, `docs/runbooks/distribution.md`, and
`docs/plugins/catalog.md`.

## Configuration

Environment variables (optional — auto-detection is the default):

```bash
export IMAGE_ROUTER_VISION_PROVIDER="openai-codex"
export IMAGE_ROUTER_VISION_MODEL="codex-1"
```

## Requirements

- A vision-capable model with a configured API key
- The model must have `input: ["text", "image"]` in its config, or match a known vision family (Codex, GPT-4o, Claude, Gemini)
- macOS, Linux, or Windows — zero platform-specific code
