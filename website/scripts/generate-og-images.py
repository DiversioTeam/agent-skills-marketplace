#!/usr/bin/env python3
"""Generate branded Open Graph images for website pages.

Why this script exists
----------------------
The site now has many route types: hub pages, docs pages, skill pages, Pi pages,
and blog pages. A single default social image makes all of those links look the
same when shared in Slack, X, LinkedIn, or Discord.

This script keeps previews specific and repeatable:
- read marketplace metadata from the same JSON the site already uses
- read skill and blog frontmatter from repo-local source files
- generate static PNG assets into `website/public/og/`
- let page code reference those assets by stable file name

The site does not render OG images dynamically at request time.
That keeps previews deterministic and easy to cache.

Route naming convention
----------------------
A route usually maps to one predictable image name:

    /                      -> public/og/home.png
    /agentic-tools         -> public/og/agentic-tools.png
    /docs/dev-workflow     -> public/og/docs-dev-workflow.png
    /skills/dev-workflow   -> public/og/skill-dev-workflow.png
    /pi/dev-workflow       -> public/og/pi-dev-workflow.png
    /blog/my-post          -> public/og/blog-my-post.png

Typical workflow
----------------
1. Update marketplace metadata, skill docs, or blog frontmatter.
2. Re-run this script.
3. Rebuild the Astro site.
4. Check the generated page metadata and the PNG itself.

Commands:

    python3 website/scripts/generate-og-images.py
    cd website && npm run build
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_JSON = ROOT / "src" / "data" / "marketplace.json"
BLOG_DIR = ROOT / "src" / "content" / "blog"
OUTPUT_DIR = ROOT / "public" / "og"


def is_agent_skills_repo_root(candidate: Path) -> bool:
    return (candidate / "plugins").exists() and (candidate / "pi-packages").exists()


def resolve_source_repo_root() -> Path:
    configured = Path(os.environ["AGENT_SKILLS_REPO_DIR"]).expanduser().resolve() if os.environ.get("AGENT_SKILLS_REPO_DIR", "").strip() else None
    candidates = [
        configured,
        ROOT.parent,
        (ROOT.parent / "agent-skills-marketplace").resolve(),
        (ROOT.parent / "vendor" / "agent-skills-marketplace").resolve(),
        (ROOT / "vendor" / "agent-skills-marketplace").resolve(),
    ]
    for candidate in candidates:
        if candidate and is_agent_skills_repo_root(candidate):
            return candidate
    raise RuntimeError(
        "Could not locate the agent-skills-marketplace source repo. Set AGENT_SKILLS_REPO_DIR to a checkout containing plugins/ and pi-packages/."
    )


SOURCE_REPO_ROOT = resolve_source_repo_root()
PLUGINS_DIR = SOURCE_REPO_ROOT / "plugins"
PI_PACKAGES_DIR = SOURCE_REPO_ROOT / "pi-packages"

WIDTH = 1200
HEIGHT = 630
PURPLE = "#5B34E9"
PURPLE_LIGHT = "#EFE9FF"
GRID = "#E9E3FB"
TEXT = "#1F2230"
MUTED = "#54586B"
PANEL_BG = "#FFFFFF"
PANEL_SUBTLE = "#FCFBFF"
BORDER = "#D8D1EF"


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
        )

    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


FONT_LABEL = load_font(26, bold=True)
FONT_TITLE = load_font(68, bold=True)
FONT_BODY = load_font(28, bold=False)
FONT_META = load_font(24, bold=False)
FONT_SMALL = load_font(20, bold=False)
FONT_PANEL_TITLE = load_font(24, bold=True)
FONT_PANEL_VALUE = load_font(30, bold=True)
FONT_PANEL_TEXT = load_font(22, bold=False)


def normalize_display_text(value: str) -> str:
    return (
        value.replace("\u2014", ": ")
        .replace("\u2013", "-")
        .replace("  ", " ")
        .strip()
    )


def draw_grid(draw: ImageDraw.ImageDraw) -> None:
    step = 48
    for x in range(0, WIDTH, step):
        draw.line((x, 0, x, HEIGHT), fill=GRID, width=1)
    for y in range(0, HEIGHT, step):
        draw.line((0, y, WIDTH, y), fill=GRID, width=1)


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    font: ImageFont.ImageFont,
    fill: str,
    width_px: int,
    line_spacing: int = 10,
    max_lines: int | None = None,
) -> int:
    words = text.split()
    lines: list[str] = []
    current = ""

    for word in words:
        trial = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), trial, font=font)[2] <= width_px:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .,;") + "…"

    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x, y), line, font=font)
        y = bbox[3] + line_spacing
    return y


def identifier_to_title(identifier: str) -> str:
    return " ".join(part.upper() if len(part) <= 2 else part.capitalize() for part in identifier.split("-") if part)


def parse_frontmatter(raw: str) -> dict[str, object]:
    match = re.match(r"^---\n([\s\S]*?)\n---\n?", raw)
    if not match:
        return {}

    result: dict[str, object] = {}
    lines = match.group(1).splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        scalar = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not scalar:
            index += 1
            continue

        key, raw_value = scalar.group(1), scalar.group(2).strip()
        if raw_value in {">",">-","|"}:
            block: list[str] = []
            index += 1
            while index < len(lines) and (lines[index].startswith(" ") or lines[index].startswith("\t")):
                block.append(lines[index].strip())
                index += 1
            result[key] = " ".join(part for part in block if part).strip()
            continue

        if raw_value == "":
            nested: dict[str, str] = {}
            index += 1
            while index < len(lines):
                nested_match = re.match(r"^\s+([A-Za-z0-9_-]+):\s*(.*)$", lines[index])
                if not nested_match:
                    break
                nested_key, nested_value = nested_match.group(1), nested_match.group(2).strip()
                nested[nested_key] = nested_value.strip().strip('"').strip("'")
                index += 1
            result[key] = nested
            continue

        cleaned = raw_value.strip().strip('"').strip("'")
        result[key] = cleaned
        index += 1

    return result


def markdown_title(raw: str, fallback: str) -> str:
    frontmatter = re.match(r"^---\n[\s\S]*?\n---\n?", raw)
    content = raw[frontmatter.end():] if frontmatter else raw
    match = re.search(r"^#\s+(.+)$", content, re.M)
    return match.group(1).strip() if match else fallback


def asset_slug(value: str) -> str:
    return value.replace("/", "-")


def create_card(
    *,
    title: str,
    description: str,
    badge: str,
    right_title: str,
    right_lines: Iterable[str],
    footer_path: str,
    output: Path,
) -> None:
    """Render one OG card.

    First principles:
    - left side explains what the page is about
    - right side gives a compact summary panel
    - footer reminds the viewer which exact route is being shared
    """
    image = Image.new("RGB", (WIDTH, HEIGHT), "#FBFAFF")
    draw = ImageDraw.Draw(image)

    draw_grid(draw)
    draw.rectangle((0, 0, WIDTH, 8), fill=PURPLE)

    card = (70, 70, WIDTH - 70, HEIGHT - 70)
    draw.rounded_rectangle(card, radius=28, fill=PANEL_BG, outline=BORDER, width=2)

    left_x = 120
    y = 120
    draw.text((left_x, y), "DIVERSIO", font=FONT_LABEL, fill=PURPLE)
    y += 56

    badge_bbox = draw.textbbox((0, 0), badge, font=FONT_SMALL)
    badge_w = badge_bbox[2] - badge_bbox[0] + 30
    badge_h = badge_bbox[3] - badge_bbox[1] + 18
    draw.rounded_rectangle((left_x, y, left_x + badge_w, y + badge_h), radius=12, fill=PURPLE_LIGHT, outline=BORDER, width=1)
    draw.text((left_x + 15, y + 8), badge, font=FONT_SMALL, fill=PURPLE)
    y += badge_h + 34

    y = draw_wrapped_text(draw, normalize_display_text(title), (left_x, y), FONT_TITLE, TEXT, width_px=580, line_spacing=8, max_lines=2)
    y += 18
    y = draw_wrapped_text(
        draw,
        normalize_display_text(description),
        (left_x, y),
        FONT_BODY,
        MUTED,
        width_px=600,
        line_spacing=10,
        max_lines=4,
    )

    draw.text((left_x, HEIGHT - 135), normalize_display_text(footer_path), font=FONT_META, fill=MUTED)

    panel = (830, 120, 1080, 510)
    draw.rounded_rectangle(panel, radius=24, fill=PANEL_SUBTLE, outline=BORDER, width=2)
    draw.rectangle((panel[0], panel[1], panel[2], panel[1] + 64), fill=PURPLE_LIGHT)
    draw_wrapped_text(draw, normalize_display_text(right_title), (panel[0] + 22, panel[1] + 18), FONT_PANEL_TITLE, PURPLE, width_px=panel[2] - panel[0] - 44, line_spacing=4, max_lines=2)

    line_y = panel[1] + 110
    for idx, line in enumerate(right_lines):
        text_font = FONT_PANEL_VALUE if idx == 0 else FONT_PANEL_TEXT
        text_fill = PURPLE if idx == 0 else TEXT
        line_y = draw_wrapped_text(
            draw,
            normalize_display_text(line),
            (panel[0] + 22, line_y),
            text_font,
            text_fill,
            width_px=panel[2] - panel[0] - 44,
            line_spacing=8,
            max_lines=2,
        )
        line_y += 18

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG")


def load_marketplace() -> dict:
    return json.loads(MARKETPLACE_JSON.read_text())


def collect_skill_docs() -> list[dict[str, str]]:
    marketplace = load_marketplace()
    plugin_lookup = {plugin["name"]: plugin for plugin in marketplace.get("plugins", [])}
    pi_lookup = {pkg["name"]: pkg for pkg in marketplace.get("piPackages", [])}
    skills: list[dict[str, str]] = []

    for path in PLUGINS_DIR.glob("*/skills/*/SKILL.md"):
        raw = path.read_text()
        frontmatter = parse_frontmatter(raw)
        skill_name = path.parent.name
        plugin_name = path.parents[2].name
        plugin = plugin_lookup.get(plugin_name, {})
        skills.append(
            {
                "name": skill_name,
                "title": markdown_title(raw, identifier_to_title(skill_name)).replace(" Skill", ""),
                "description": frontmatter.get("description", plugin.get("description", "Reusable skill from Diversio Engineering.")),
                "badge": "PLUGIN SKILL",
                "panel_title": "PLUGIN SKILL",
                "line1": "Claude Code · Codex",
                "line2": plugin.get("title", identifier_to_title(plugin_name)),
                "line3": plugin_name,
                "footer": f"engineering.diversio.com/skills/{skill_name}",
                "output": str(OUTPUT_DIR / f"skill-{skill_name}.png"),
            }
        )

    for path in PI_PACKAGES_DIR.glob("*/skills/*/SKILL.md"):
        raw = path.read_text()
        frontmatter = parse_frontmatter(raw)
        skill_name = path.parent.name
        package_name = path.parents[2].name
        pkg = pi_lookup.get(package_name, {})
        skills.append(
            {
                "name": skill_name,
                "title": markdown_title(raw, identifier_to_title(skill_name)).replace(" Skill", ""),
                "description": frontmatter.get("description", pkg.get("description", "Pi-local skill from Diversio Engineering.")),
                "badge": "PI SKILL",
                "panel_title": "PI SKILL",
                "line1": "Pi Local",
                "line2": pkg.get("title", identifier_to_title(package_name)),
                "line3": package_name,
                "footer": f"engineering.diversio.com/skills/{skill_name}",
                "output": str(OUTPUT_DIR / f"skill-{skill_name}.png"),
            }
        )

    return skills


def collect_blog_posts() -> list[dict[str, str]]:
    posts: list[dict[str, str]] = []
    for path in BLOG_DIR.glob("*.md"):
        raw = path.read_text()
        frontmatter = parse_frontmatter(raw)
        if frontmatter.get("draft", "false").lower() == "true":
            continue
        slug = str(frontmatter.get("slug") or path.stem)
        posts.append(
            {
                "slug": slug,
                "title": str(frontmatter.get("title", identifier_to_title(slug))),
                "description": str(frontmatter.get("summary", "Engineering writing from Diversio Engineering.")),
                "sourceType": str(frontmatter.get("sourceType", "original")),
                "badge": "ENGINEERING BLOG",
                "panel_title": "BLOG",
                "line1": str(frontmatter.get("publishDate", "")),
                "line2": str((frontmatter.get("author") or {}).get("name", "Diversio Engineering")) if isinstance(frontmatter.get("author"), dict) else str(frontmatter.get("author", "Diversio Engineering")),
                "line3": "Diversio Engineering",
                "footer": f"engineering.diversio.com/blog/{slug}",
                "output": str(OUTPUT_DIR / f"blog-{asset_slug(slug)}.png"),
            }
        )
    return posts


def main() -> None:
    marketplace = load_marketplace()
    plugins = marketplace.get("plugins", [])
    pi_packages = marketplace.get("piPackages", [])
    plugin_skill_count = sum(len(plugin.get("skills", [])) for plugin in plugins)
    skill_docs = collect_skill_docs()
    blog_posts = collect_blog_posts()
    original_blog_posts = [post for post in blog_posts if post.get("sourceType") == "original"]
    repost_blog_posts = [post for post in blog_posts if post.get("sourceType") == "repost"]

    blog_index_line2 = (
        "Original + reposts"
        if original_blog_posts and repost_blog_posts
        else "Original posts"
        if original_blog_posts
        else "Curated reposts"
        if repost_blog_posts
        else "Writing in progress"
    )

    # Section-level pages.
    section_cards = [
        {
            "title": "Diversio Engineering",
            "description": "Engineering systems, open tools, deep docs, and writing from Diversio.",
            "badge": "ENGINEERING HUB",
            "panel_title": "OVERVIEW",
            "line1": f"{len(plugins)} plugins",
            "line2": f"{len(pi_packages)} Pi packages",
            "line3": "Systems · Tools · Writing",
            "footer": "engineering.diversio.com/",
            "output": OUTPUT_DIR / "home.png",
        },
        {
            "title": "How We Work",
            "description": "The standards, habits, and tooling choices behind Diversio Engineering.",
            "badge": "HOW WE WORK",
            "panel_title": "MODEL",
            "line1": "Real systems",
            "line2": "Guardrailed AI",
            "line3": "Docs as harness",
            "footer": "engineering.diversio.com/how-we-work",
            "output": OUTPUT_DIR / "how-we-work.png",
        },
        {
            "title": "Systems",
            "description": "Workflows, guardrails, and design choices behind Diversio Engineering.",
            "badge": "SYSTEMS",
            "panel_title": "PATTERNS",
            "line1": "Workflow",
            "line2": "Security",
            "line3": "Documentation",
            "footer": "engineering.diversio.com/systems",
            "output": OUTPUT_DIR / "systems.png",
        },
        {
            "title": "Agentic Tools",
            "description": "Open source tools, reusable skills, and Pi extensions from Diversio Engineering.",
            "badge": "AGENTIC TOOLS",
            "panel_title": "TOOLS",
            "line1": f"{len(plugins)} plugins",
            "line2": f"{plugin_skill_count} skills",
            "line3": f"{len(pi_packages)} Pi packages",
            "footer": "engineering.diversio.com/agentic-tools",
            "output": OUTPUT_DIR / "agentic-tools.png",
        },
        {
            "title": "Agentic Tools Docs",
            "description": "Maintainer docs for authoring, packaging, distribution, and validation.",
            "badge": "DOCUMENTATION",
            "panel_title": "DOCS",
            "line1": f"{plugin_skill_count} skills",
            "line2": f"{len(pi_packages)} Pi packages",
            "line3": "Authoring · Validation",
            "footer": "engineering.diversio.com/docs",
            "output": OUTPUT_DIR / "docs-index.png",
        },
        {
            "title": "Registry",
            "description": "Browse plugins, skill docs, and Pi package docs from Diversio Engineering.",
            "badge": "REGISTRY",
            "panel_title": "INVENTORY",
            "line1": f"{len(plugins)} plugins",
            "line2": f"{plugin_skill_count} skills",
            "line3": f"{len(pi_packages)} Pi packages",
            "footer": "engineering.diversio.com/registry",
            "output": OUTPUT_DIR / "registry.png",
        },
        {
            "title": "Skill Docs",
            "description": "Deep documentation for individual plugin skills and Pi-local skills.",
            "badge": "SKILLS",
            "panel_title": "SKILL DOCS",
            "line1": f"{len(skill_docs)} pages",
            "line2": "Plugin skills",
            "line3": "Pi-local skills",
            "footer": "engineering.diversio.com/skills",
            "output": OUTPUT_DIR / "skills-index.png",
        },
        {
            "title": "Pi Extensions",
            "description": "Pi package and extension docs for commands, tools, packaged skills, and install flows.",
            "badge": "PI PACKAGE",
            "panel_title": "PI DOCS",
            "line1": f"{len(pi_packages)} packages",
            "line2": "Extension docs",
            "line3": "Install flows",
            "footer": "engineering.diversio.com/pi",
            "output": OUTPUT_DIR / "pi-index.png",
        },
        {
            "title": "Contribute",
            "description": "How to contribute to the open Agentic Tools repository across issues, pull requests, docs, and validation workflows.",
            "badge": "CONTRIBUTE",
            "panel_title": "OPEN SOURCE",
            "line1": f"{len(plugins)} plugins",
            "line2": "Contribution docs",
            "line3": "Review workflows",
            "footer": "engineering.diversio.com/community",
            "output": OUTPUT_DIR / "community.png",
        },
        {
            "title": "Security",
            "description": "Security guidance for markdown skills, Pi package extensions, and published docs.",
            "badge": "SECURITY",
            "panel_title": "POLICY",
            "line1": "Review source",
            "line2": "Check extensions",
            "line3": "Report privately",
            "footer": "engineering.diversio.com/security",
            "output": OUTPUT_DIR / "security.png",
        },
        {
            "title": "Terms of Use",
            "description": "Terms for Diversio Engineering and its open-source tools and docs.",
            "badge": "LEGAL",
            "panel_title": "TERMS",
            "line1": "Open source",
            "line2": "Docs and skills",
            "line3": "Use at your own risk",
            "footer": "engineering.diversio.com/terms",
            "output": OUTPUT_DIR / "terms.png",
        },
        {
            "title": "Page Not Found",
            "description": "The page you asked for is missing or has moved inside Diversio Engineering.",
            "badge": "404",
            "panel_title": "NOT FOUND",
            "line1": "Browse tools",
            "line2": "Read docs",
            "line3": "Return home",
            "footer": "engineering.diversio.com/404",
            "output": OUTPUT_DIR / "404.png",
        },
        {
            "title": "Engineering Writing",
            "description": "Curated reposts, original posts over time, and technical writing from Diversio Engineering.",
            "badge": "BLOG",
            "panel_title": "WRITING",
            "line1": f"{len(blog_posts)} posts" if blog_posts else "Writing in progress",
            "line2": blog_index_line2,
            "line3": "Diversio Engineering",
            "footer": "engineering.diversio.com/blog",
            "output": OUTPUT_DIR / "blog-index.png",
        },
        {
            "title": "Skill Docs",
            "description": "Deep documentation for individual skills across Agentic Tools and Pi packages.",
            "badge": "SKILL",
            "panel_title": "SKILL",
            "line1": "Deep docs",
            "line2": "Install paths",
            "line3": "Runtime guidance",
            "footer": "engineering.diversio.com/skills",
            "output": OUTPUT_DIR / "skill-default.png",
        },
        {
            "title": "Package Docs",
            "description": "Bundle-level docs for plugins and Pi packages in Diversio Engineering.",
            "badge": "DOCS",
            "panel_title": "SUMMARY",
            "line1": "Bundle docs",
            "line2": "Install guidance",
            "line3": "Parent surfaces",
            "footer": "engineering.diversio.com/docs",
            "output": OUTPUT_DIR / "docs-default.png",
        },
        {
            "title": "Engineering Writing",
            "description": "Original posts and article pages from Diversio Engineering.",
            "badge": "BLOG",
            "panel_title": "BLOG",
            "line1": "Article page",
            "line2": "Shareable",
            "line3": "Readable everywhere",
            "footer": "engineering.diversio.com/blog",
            "output": OUTPUT_DIR / "blog-default.png",
        },
        {
            "title": "Pi Packages",
            "description": "Pi-native extensions, commands, tools, and packaged skills from Diversio Engineering.",
            "badge": "PI PACKAGE",
            "panel_title": "OVERVIEW",
            "line1": f"{len(pi_packages)} packages",
            "line2": "Pi-native docs",
            "line3": "Extensions and skills",
            "footer": "engineering.diversio.com/pi",
            "output": OUTPUT_DIR / "pi-package-default.png",
        },
    ]

    for card in section_cards:
        create_card(
            title=card["title"],
            description=card["description"],
            badge=card["badge"],
            right_title=card["panel_title"],
            right_lines=[card["line1"], card["line2"], card["line3"]],
            footer_path=card["footer"],
            output=card["output"],
        )

    # Bundle docs pages.
    for plugin in plugins:
        create_card(
            title=plugin["title"],
            description=plugin["description"],
            badge="PLUGIN DOCS",
            right_title=plugin["name"].upper().replace("-", " "),
            right_lines=[plugin.get("version", ""), plugin.get("category", "Plugin"), "Bundle docs"],
            footer_path=f"engineering.diversio.com/docs/{plugin['name']}",
            output=OUTPUT_DIR / f"docs-{plugin['name']}.png",
        )

    for pkg in pi_packages:
        create_card(
            title=pkg["title"],
            description=pkg["description"],
            badge="PACKAGE DOCS",
            right_title=pkg["name"].upper().replace("-", " "),
            right_lines=[pkg.get("version", ""), "Pi package", "Bundle docs"],
            footer_path=f"engineering.diversio.com/docs/{pkg['name']}",
            output=OUTPUT_DIR / f"docs-{pkg['name']}.png",
        )

        create_card(
            title=pkg["title"],
            description=pkg["description"],
            badge="PI PACKAGE",
            right_title="PI PACKAGE",
            right_lines=[pkg.get("version", ""), "Diversio Engineering", "Pi extension docs"],
            footer_path=f"engineering.diversio.com/pi/{pkg['name']}",
            output=OUTPUT_DIR / f"pi-{pkg['name']}.png",
        )

    # Skill pages.
    for skill in skill_docs:
        create_card(
            title=skill["title"],
            description=skill["description"],
            badge=skill["badge"],
            right_title=skill["panel_title"],
            right_lines=[skill["line1"], skill["line2"], skill["line3"]],
            footer_path=skill["footer"],
            output=Path(skill["output"]),
        )

    # Blog posts.
    for post in blog_posts:
        create_card(
            title=post["title"],
            description=post["description"],
            badge=post["badge"],
            right_title=post["panel_title"],
            right_lines=[post["line1"], post["line2"], post["line3"]],
            footer_path=post["footer"],
            output=Path(post["output"]),
        )


if __name__ == "__main__":
    main()
