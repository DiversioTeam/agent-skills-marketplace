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
    """A user-facing publish error; an upload may have reached the server."""


class UploadRejected(PublishError):
    """This attempt did not create an upload; never delete the attempted name."""


def _slug(value: str, limit: int) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:limit].strip("-")


def build_names(repo: str, branch: str, parts: int, head: str, now: datetime | None = None) -> list[str]:
    """session-<repo>-<branch>-<yyyymmdd>-h<head12>-<random>[-part-N].html, at most 180 characters, no slashes.

    The `h<head12>` part names the commit the transcript covers: local-ci's agent-session check compares it with HEAD,
    so a transcript published before later commits reads as stale without fetching anything.
    """
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d")
    token = secrets.token_hex(3)
    covered = f"h{head[:12]}" if re.fullmatch(r"[0-9a-f]{12,40}", head) else "h000000000000"
    base = f"session-{_slug(repo, 40) or 'repo'}-{_slug(branch, 80) or 'branch'}-{stamp}-{covered}-{token}"
    suffixes = [f"-part-{index + 1}" if parts > 1 else "" for index in range(parts)]
    return [f"{base}{suffix}.html"[:MAX_NAME] for suffix in suffixes]


def link_for(name: str) -> str:
    return urllib.parse.urljoin(INTERNAL_SHARE_URL, urllib.parse.quote(name))


def _cloudflared() -> str:
    cloudflared = shutil.which("cloudflared")
    if cloudflared is None:
        raise PublishError("cloudflared is required to publish. Install it with: brew install cloudflared")
    try:
        login = subprocess.run([cloudflared, "access", "login", "--quiet", INTERNAL_SHARE_URL], timeout=600, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PublishError("Cloudflare Access sign-in did not complete. Retry and finish the browser sign-in.") from error
    if login.returncode != 0:
        raise PublishError("Cloudflare Access sign-in did not complete. Retry and finish the browser sign-in.")
    return cloudflared


def delete(name: str) -> bool:
    """Delete a page this developer uploaded (the Worker lets only the uploader delete). True when it is gone."""
    cloudflared = _cloudflared()
    try:
        completed = subprocess.run(
            [cloudflared, "access", "curl", urllib.parse.urljoin(INTERNAL_SHARE_URL, f"delete/{urllib.parse.quote(name)}"),
             "-X", "POST", "--dump-header", "-", "--output", "/dev/null"],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    statuses = re.findall(r"^HTTP/\S+\s+(\d{3})", f"{completed.stdout}\n{completed.stderr}", flags=re.MULTILINE)
    return completed.returncode == 0 and bool(statuses) and statuses[-1] in ("303", "404")


def upload(path: Path, name: str) -> str:
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        raise UploadRejected("Internal Share accepts files up to 25 MB; render again so the page splits into parts.")
    try:
        cloudflared = _cloudflared()
    except PublishError as error:
        raise UploadRejected(str(error)) from error
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
    statuses = re.findall(r"^HTTP/\S+[ \t]+(\d{3})(?=[ \t\r\n]|$)", output, flags=re.MULTILINE)
    status = statuses[-1] if statuses else None
    locations = re.findall(r"^location:\s*(\S+)\s*$", output, flags=re.IGNORECASE | re.MULTILINE)
    if completed.returncode == 0 and status == "303" and locations:
        return urllib.parse.urljoin(INTERNAL_SHARE_URL, locations[-1])
    if status == "409":
        raise UploadRejected("A file with that name already exists on Internal Share; run share (or render) again for a fresh name.")
    raise PublishError("Could not upload to Internal Share. Check the connection and retry.")
