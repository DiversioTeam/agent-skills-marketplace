#!/usr/bin/env python3
"""Generate branded Open Graph images for website pages.

Why this script exists
----------------------
The default social image is fine for generic pages, but detail pages look much
more polished when the preview image actually matches the thing being shared.

This script keeps that process simple and repeatable:
- read package metadata from the same marketplace JSON the site already uses
- render one default Pi package card plus one card per Pi package
- write static PNG files into `website/public/og/`

The site does not generate these images at request time. They are build assets.
That makes previews deterministic for Slack, X, LinkedIn, and other crawlers.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_JSON = ROOT / "src" / "data" / "marketplace.json"
OUTPUT_DIR = ROOT / "public" / "og"

WIDTH = 1200
HEIGHT = 630
PURPLE = "#5B34E9"
PURPLE_LIGHT = "#EFE9FF"
GRID = "#E9E3FB"
TEXT = "#1F2230"
MUTED = "#54586B"
PANEL_BG = "#FFFFFF"
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
FONT_PANEL_TITLE = load_font(28, bold=True)
FONT_PANEL_VALUE = load_font(36, bold=True)


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


def create_card(title: str, description: str, badge: str, right_title: str, right_lines: Iterable[str], output: Path) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#FBFAFF")
    draw = ImageDraw.Draw(image)

    draw_grid(draw)
    draw.rectangle((0, 0, WIDTH, 8), fill=PURPLE)

    # Main card shell
    card = (70, 70, WIDTH - 70, HEIGHT - 70)
    draw.rounded_rectangle(card, radius=28, fill=PANEL_BG, outline=BORDER, width=2)

    # Left content
    left_x = 120
    y = 120
    draw.text((left_x, y), "DIVERSIO ENGINEERING", font=FONT_LABEL, fill=PURPLE)
    y += 56

    badge_bbox = draw.textbbox((0, 0), badge, font=FONT_SMALL)
    badge_w = badge_bbox[2] - badge_bbox[0] + 30
    badge_h = badge_bbox[3] - badge_bbox[1] + 18
    draw.rounded_rectangle((left_x, y, left_x + badge_w, y + badge_h), radius=12, fill=PURPLE_LIGHT, outline=BORDER, width=1)
    draw.text((left_x + 15, y + 8), badge, font=FONT_SMALL, fill=PURPLE)
    y += badge_h + 34

    y = draw_wrapped_text(draw, title, (left_x, y), FONT_TITLE, TEXT, width_px=580, line_spacing=8)
    y += 18
    y = draw_wrapped_text(
        draw,
        description,
        (left_x, y),
        FONT_BODY,
        MUTED,
        width_px=600,
        line_spacing=10,
        max_lines=4,
    )

    footer = output.stem.replace("pi-", "")
    footer_text = f"engineering.diversio.com/pi/{footer}"
    draw.text((left_x, HEIGHT - 135), footer_text, font=FONT_META, fill=MUTED)

    # Right panel
    panel = (830, 120, 1080, 510)
    draw.rounded_rectangle(panel, radius=24, fill="#FCFBFF", outline=BORDER, width=2)
    draw.rectangle((panel[0], panel[1], panel[2], panel[1] + 64), fill=PURPLE_LIGHT)
    draw.text((panel[0] + 22, panel[1] + 18), right_title, font=FONT_PANEL_TITLE, fill=PURPLE)

    line_y = panel[1] + 110
    for idx, line in enumerate(right_lines):
        draw.text((panel[0] + 22, line_y), line, font=FONT_PANEL_VALUE if idx == 0 else FONT_META, fill=TEXT if idx else PURPLE)
        line_y += 62

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG")


def main() -> None:
    data = json.loads(MARKETPLACE_JSON.read_text())
    pi_packages = data.get("piPackages", [])

    create_card(
        title="Pi Packages",
        description="Pi-native extensions, commands, tools, and packaged skills from Diversio Engineering.",
        badge="PI PACKAGE",
        right_title="OVERVIEW",
        right_lines=[str(len(pi_packages)), "packages", "Pi-native docs"],
        output=OUTPUT_DIR / "pi-package-default.png",
    )

    for pkg in pi_packages:
        create_card(
            title=pkg["title"],
            description=pkg["description"],
            badge="PI PACKAGE",
            right_title=pkg["name"].upper().replace("-", " "),
            right_lines=[pkg.get("version", ""), "Diversio Engineering", "Pi extension docs"],
            output=OUTPUT_DIR / f"pi-{pkg['name']}.png",
        )


if __name__ == "__main__":
    main()
