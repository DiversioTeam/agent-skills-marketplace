#!/usr/bin/env python3
"""Publish a generated visual explainer to Diversio Internal Share."""

from __future__ import annotations

import argparse
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import uuid
import webbrowser
from datetime import datetime, timezone
from pathlib import Path


INTERNAL_SHARE_URL = "https://internal-share.diversio.com/"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class PublishError(RuntimeError):
    """A user-facing publish error."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish a visual explainer to Diversio Internal Share.",
    )
    parser.add_argument("--html-path", required=True, help="Generated local HTML file.")
    parser.add_argument("--title", required=True, help="Human-readable explainer title.")
    parser.add_argument(
        "--slides",
        action="store_true",
        help="The page is a slide deck: check it with the slide rules.",
    )
    parser.add_argument(
        "--open-url",
        action="store_true",
        help="Open the Internal Share URL after upload.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    html_path = Path(args.html_path).expanduser().resolve()

    try:
        upload_name = build_upload_name(args.title)
        # The page is copied once, the copy is checked, and that same copy is what goes up: an edit to the source while
        # the browser sign-in is open cannot slip past the check. The check comes first, so a page below the standard
        # gets its feedback even on a machine without cloudflared.
        with tempfile.TemporaryDirectory(prefix="visual-explainer-") as temp_dir:
            staged_path = stage(html_path, Path(temp_dir) / upload_name)
            ensure_publishable(staged_path, "slides" if getattr(args, "slides", False) else "report")
            cloudflared = shutil.which("cloudflared")
            if cloudflared is None:
                raise PublishError(
                    "cloudflared is required to publish to Diversio Internal Share.\n\n"
                    "Install it with:\n\n"
                    "  brew install cloudflared"
                )
            authenticate(cloudflared)
            share_url = upload(cloudflared, staged_path, upload_name)
        if args.open_url:
            webbrowser.open(share_url)

        print("Diversio Internal Share upload complete.")
        print(f"Local HTML: {html_path}")
        print(f"Uploaded filename: {upload_name}")
        print(f"Share URL: {share_url}")
        return 0
    except PublishError as error:
        print(error)
        print(f"Local HTML: {html_path}")
        return 1


def stage(html_path: Path, staged_path: Path) -> Path:
    if not html_path.is_file():
        raise PublishError(
            "The generated HTML file was not found.\n\n"
            "Write the explainer to ~/.agent/diagrams/ first, then retry publish mode."
        )
    shutil.copy2(html_path, staged_path)
    return staged_path


def ensure_publishable(html_path: Path, kind: str = "report") -> None:
    if not html_path.is_file():
        raise PublishError("The generated HTML file was not found.")
    if html_path.stat().st_size > MAX_UPLOAD_BYTES:
        raise PublishError(
            "Diversio Internal Share accepts files up to 25 MB. "
            "Reduce the file size and retry."
        )
    problems = load_page_checker().check_page(html_path.read_text(encoding="utf-8"), kind)
    if problems:
        raise PublishError(
            "The page was not uploaded: it does not meet the readable-page standard yet. Fix these, then retry:\n"
            + "\n".join(f"- {message}" for _rule, message in problems)
        )


def load_page_checker():
    """The page checker next to this script (scripts/check_page.py), loaded by path so any working directory works."""
    path = Path(__file__).resolve().with_name("check_page.py")
    spec = importlib.util.spec_from_file_location("visual_explainer_check_page", path)
    if not path.is_file() or spec is None or spec.loader is None:
        raise PublishError(f"The page checker is missing at {path}; reinstall the visual-explainer plugin.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up while the file runs
    spec.loader.exec_module(module)
    return module


def build_upload_name(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    slug = slug[:70].strip("-") or "visual-explainer"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{slug}-{timestamp}-{uuid.uuid4().hex[:6]}.html"


def upload(cloudflared: str, staged_path: Path, upload_name: str) -> str:
    """Uploads the staged copy that was checked (its name is the upload name)."""
    completed = run_upload(cloudflared, staged_path)

    output = f"{completed.stdout}\n{completed.stderr}"
    statuses = re.findall(r"^HTTP/\S+\s+(\d{3})", output, flags=re.MULTILINE)
    locations = re.findall(r"^location:\s*(\S+)\s*$", output, flags=re.IGNORECASE | re.MULTILINE)

    if completed.returncode == 0 and "303" in statuses and locations:
        return urllib.parse.urljoin(INTERNAL_SHARE_URL, locations[-1])

    raise PublishError(
        "Could not upload the explainer to Diversio Internal Share. "
        "Check the connection and retry."
    )


def run_upload(cloudflared: str, staged_path: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [
                cloudflared,
                "access",
                "curl",
                INTERNAL_SHARE_URL,
                "--form",
                f"file=@{staged_path}",
                "--dump-header",
                "-",
                "--output",
                "/dev/null",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise PublishError(
            "The Internal Share upload timed out. Check the connection and retry."
        ) from error


def authenticate(cloudflared: str) -> None:
    print(
        "Checking Cloudflare Access. If the browser does not open, use the URL below.",
        flush=True,
    )
    try:
        completed = subprocess.run(
            [cloudflared, "access", "login", "--quiet", INTERNAL_SHARE_URL],
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise PublishError(
            "Cloudflare Access sign-in timed out. Retry when ready to sign in."
        ) from error

    if completed.returncode != 0:
        raise PublishError(
            "Cloudflare Access sign-in did not complete. Retry and finish the "
            "browser sign-in."
        )


if __name__ == "__main__":
    raise SystemExit(main())
