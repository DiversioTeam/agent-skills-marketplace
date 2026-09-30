#!/usr/bin/env python3
"""Publish a generated visual explainer to Diversio Internal Share."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
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
        "--open-url",
        action="store_true",
        help="Open the Internal Share URL after upload.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    html_path = Path(args.html_path).expanduser().resolve()

    try:
        ensure_publishable(html_path)
        cloudflared = shutil.which("cloudflared")
        if cloudflared is None:
            raise PublishError(
                "cloudflared is required to publish to Diversio Internal Share.\n\n"
                "Install it with:\n\n"
                "  brew install cloudflared\n\n"
                "The local HTML is still available."
            )

        upload_name = build_upload_name(args.title)
        share_url = upload(cloudflared, html_path, upload_name)
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


def ensure_publishable(html_path: Path) -> None:
    if not html_path.is_file():
        raise PublishError(
            "The generated HTML file was not found.\n\n"
            "Write the explainer to ~/.agent/diagrams/ first, then retry publish mode."
        )
    if html_path.stat().st_size > MAX_UPLOAD_BYTES:
        raise PublishError(
            "Diversio Internal Share accepts files up to 25 MB.\n\n"
            "The local HTML is still available. Reduce its size and retry."
        )


def build_upload_name(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    slug = slug[:70].strip("-") or "visual-explainer"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{slug}-{timestamp}-{uuid.uuid4().hex[:6]}.html"


def upload(cloudflared: str, html_path: Path, upload_name: str) -> str:
    with tempfile.TemporaryDirectory(prefix="visual-explainer-") as temp_dir:
        staged_path = Path(temp_dir) / upload_name
        shutil.copy2(html_path, staged_path)

        completed = run_upload(cloudflared, staged_path)
        if authentication_required(completed):
            print(
                "Cloudflare Access authentication is required. Complete the Diversio "
                "email and one-time PIN steps in the browser."
            )
            authenticate(cloudflared)
            completed = run_upload(cloudflared, staged_path)

    output = f"{completed.stdout}\n{completed.stderr}"
    statuses = re.findall(r"^HTTP/\S+\s+(\d{3})", output, flags=re.MULTILINE)
    locations = re.findall(r"^location:\s*(\S+)\s*$", output, flags=re.IGNORECASE | re.MULTILINE)

    if completed.returncode == 0 and "303" in statuses and locations:
        return urllib.parse.urljoin(INTERNAL_SHARE_URL, locations[-1])

    if authentication_required(completed):
        raise PublishError(
            "Cloudflare Access authentication did not complete.\n\n"
            "The local HTML is still available. Retry publish mode and complete "
            "the browser sign-in."
        )

    raise PublishError(
        "Could not upload the explainer to Diversio Internal Share.\n\n"
        "The local HTML is still available. Check the connection and retry."
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
            "The Internal Share upload timed out.\n\n"
            "The local HTML is still available. Check the connection and retry."
        ) from error


def authentication_required(completed: subprocess.CompletedProcess[str]) -> bool:
    output = f"{completed.stdout}\n{completed.stderr}".lower()
    return (
        "cloudflareaccess.com" in output
        or "failed to fetch token" in output
        or "access login" in output
        or "authentication" in output
    )


def authenticate(cloudflared: str) -> None:
    try:
        completed = subprocess.run(
            [cloudflared, "access", "login", INTERNAL_SHARE_URL],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise PublishError(
            "Cloudflare Access authentication timed out.\n\n"
            "The local HTML is still available. Retry when ready to complete the "
            "browser sign-in."
        ) from error

    if completed.returncode != 0:
        raise PublishError(
            "Cloudflare Access authentication did not complete.\n\n"
            "The local HTML is still available. Retry publish mode and complete "
            "the browser sign-in."
        )


if __name__ == "__main__":
    raise SystemExit(main())
