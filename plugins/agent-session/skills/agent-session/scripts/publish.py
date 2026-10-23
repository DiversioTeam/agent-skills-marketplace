"""Upload rendered transcripts to Diversio Internal Share through Cloudflare Access.

The same path visual-explainer uses: `cloudflared access curl` with the developer's own Access login, so no storage
credentials ever reach a laptop. The Worker records the developer's email as the uploader (they can delete the file
in the app) and refuses to overwrite an existing name, so every publish gets a fresh name.
"""

from __future__ import annotations

import re
import secrets
import shutil
import subprocess
import tempfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

INTERNAL_SHARE_URL = "https://internal-share.diversio.com/"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_NAME = 180


class PublishError(RuntimeError):
    """A user-facing publish error."""


def _slug(value: str, limit: int) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:limit].strip("-")


def build_names(repo: str, branch: str, parts: int, now: datetime | None = None) -> list[str]:
    """session-<repo>-<branch>-<yyyymmdd>-<random>[-part-N].html, at most 180 characters, no slashes."""
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d")
    token = secrets.token_hex(3)
    base = f"session-{_slug(repo, 40) or 'repo'}-{_slug(branch, 90) or 'branch'}-{stamp}-{token}"
    suffixes = [f"-part-{index + 1}" if parts > 1 else "" for index in range(parts)]
    return [f"{base}{suffix}.html"[:MAX_NAME] for suffix in suffixes]


def link_for(name: str) -> str:
    return urllib.parse.urljoin(INTERNAL_SHARE_URL, urllib.parse.quote(name))


def upload(path: Path, name: str) -> str:
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        raise PublishError("Internal Share accepts files up to 25 MB; render again so the page splits into parts.")
    cloudflared = shutil.which("cloudflared")
    if cloudflared is None:
        raise PublishError("cloudflared is required to publish. Install it with: brew install cloudflared")
    login = subprocess.run([cloudflared, "access", "login", "--quiet", INTERNAL_SHARE_URL], timeout=600, check=False)
    if login.returncode != 0:
        raise PublishError("Cloudflare Access sign-in did not complete. Retry and finish the browser sign-in.")
    with tempfile.TemporaryDirectory(prefix="agent-session-") as directory:
        staged = Path(directory) / name
        shutil.copy2(path, staged)
        try:
            completed = subprocess.run(
                [cloudflared, "access", "curl", INTERNAL_SHARE_URL, "--form", f"file=@{staged};type=text/html",
                 "--dump-header", "-", "--output", "/dev/null"],
                capture_output=True, text=True, timeout=180, check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise PublishError("The Internal Share upload timed out. Check the connection and retry.") from error
    output = f"{completed.stdout}\n{completed.stderr}"
    statuses = re.findall(r"^HTTP/\S+\s+(\d{3})", output, flags=re.MULTILINE)
    locations = re.findall(r"^location:\s*(\S+)\s*$", output, flags=re.IGNORECASE | re.MULTILINE)
    if completed.returncode == 0 and "303" in statuses and locations:
        return urllib.parse.urljoin(INTERNAL_SHARE_URL, locations[-1])
    if "409" in statuses:
        raise PublishError("A file with that name already exists on Internal Share; publish again for a fresh name.")
    raise PublishError("Could not upload to Internal Share. Check the connection and retry.")
