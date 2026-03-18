#!/usr/bin/env python3
"""Publish a generated visual explainer HTML file to a fresh Netlify site."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_BASE = "https://api.netlify.com/api/v1"
CONFIG_DIR = Path.home() / ".config" / "visual-explainer"
GLOBAL_CONFIG_PATH = CONFIG_DIR / "global.json"
PUBLISH_HISTORY_DIR = CONFIG_DIR / "publish-history"
DEFAULT_CONFIG: dict[str, Any] = {
    "version": "1.0",
    "publisher": "netlify",
    "publish_mode": "create_new_site",
    "netlify": {
        "token_env_var": "NETLIFY_VISUAL_EXPLAINER_TOKEN",
        "account_slug_env_var": "NETLIFY_VISUAL_EXPLAINER_ACCOUNT_SLUG",
        "site_prefix_env_var": "NETLIFY_VISUAL_EXPLAINER_SITE_PREFIX",
        "open_browser_env_var": "NETLIFY_VISUAL_EXPLAINER_OPEN_BROWSER",
    },
    "preferences": {
        "open_after_publish": False,
    },
}


class PublishError(RuntimeError):
    """Base class for user-facing publish errors."""


class NetlifyApiError(PublishError):
    """Raised when Netlify returns an API error."""

    def __init__(self, message: str, status_code: int, details: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


@dataclass
class RuntimeSettings:
    token: str
    account_slug: str
    site_prefix: str
    open_after_publish: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish a visual explainer HTML file to a fresh Netlify preview site.",
    )
    parser.add_argument(
        "--html-path",
        required=True,
        help="Path to the generated local HTML file.",
    )
    parser.add_argument(
        "--title",
        required=True,
        help="Human-readable title for the Netlify deploy.",
    )
    parser.add_argument(
        "--open-url",
        action="store_true",
        help="Open the deployed Netlify URL after publish succeeds.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the final publish receipt as JSON.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="Maximum time to wait for the deploy to become ready.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=3.0,
        help="Delay between deploy status polls.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    html_path = Path(args.html_path).expanduser().resolve()
    created_at = utc_now()
    receipt_stamp = datetime_for_receipt(created_at)
    receipt: dict[str, Any] = {
        "created_at": created_at,
        "title": args.title,
        "local_html_path": str(html_path),
        "state": "error",
    }

    try:
        ensure_local_html_exists(html_path)
        config = load_or_bootstrap_config()
        settings = resolve_runtime_settings(config, force_open=args.open_url)
        site_name = build_site_name(settings.site_prefix)
        receipt["site_name"] = site_name

        site = create_site(
            token=settings.token,
            account_slug=settings.account_slug,
            site_name=site_name,
        )
        receipt["site_id"] = require_string(site, "id", "site creation")
        receipt["admin_url"] = site.get("admin_url")

        deploy = create_deploy(
            token=settings.token,
            site_id=receipt["site_id"],
            title=args.title,
            html_path=html_path,
        )
        receipt["deploy_id"] = require_string(deploy, "id", "deploy creation")

        final_deploy = poll_deploy(
            token=settings.token,
            deploy_id=receipt["deploy_id"],
            timeout_seconds=args.timeout_seconds,
            poll_interval_seconds=args.poll_interval_seconds,
        )
        deploy_url = select_deploy_url(site_name=site_name, site=site, deploy=final_deploy)
        verify_deploy_content_type(deploy_url)
        state = final_deploy.get("state", "ready")
        if state != "ready":
            raise PublishError(
                "Netlify reported a failed deploy.\n\n"
                "The local HTML still exists. Check the deploy details in Netlify "
                "and retry after fixing the issue.",
            )

        receipt["deploy_url"] = deploy_url
        receipt["state"] = state

        receipt_path = write_receipt(receipt, receipt_stamp)
        receipt["receipt_path"] = str(receipt_path)

        if settings.open_after_publish and deploy_url:
            open_in_browser(deploy_url)

        emit_success(receipt, json_output=args.json)
        return 0
    except PublishError as error:
        receipt["state"] = "error"
        receipt["error_message"] = str(error)
        receipt_path = write_receipt(receipt, receipt_stamp)
        receipt["receipt_path"] = str(receipt_path)
        emit_failure(receipt, error, json_output=args.json)
        return 1


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def datetime_for_receipt(timestamp: str) -> str:
    return timestamp.replace(":", "-")


def ensure_local_html_exists(html_path: Path) -> None:
    if not html_path.is_file():
        raise PublishError(
            "The generated HTML file was not found.\n\n"
            "Write the explainer to ~/.agent/diagrams/ first, then retry publish mode.",
        )


def load_or_bootstrap_config() -> dict[str, Any]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PUBLISH_HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    if not GLOBAL_CONFIG_PATH.exists():
        write_json(GLOBAL_CONFIG_PATH, DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))

    try:
        loaded = json.loads(GLOBAL_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise PublishError(
            "The visual-explainer publish config is not valid JSON.\n\n"
            f"Fix or remove {GLOBAL_CONFIG_PATH} and retry publish mode.",
        ) from error
    merged = merge_defaults(loaded, DEFAULT_CONFIG)
    validate_config_shape(merged)
    if merged != loaded:
        write_json(GLOBAL_CONFIG_PATH, merged)
    return merged


def merge_defaults(loaded: Any, defaults: Any) -> Any:
    if isinstance(loaded, dict) and isinstance(defaults, dict):
        merged: dict[str, Any] = {}
        for key, default_value in defaults.items():
            if key in loaded:
                merged[key] = merge_defaults(loaded[key], default_value)
            else:
                merged[key] = json.loads(json.dumps(default_value))
        for key, value in loaded.items():
            if key not in merged:
                merged[key] = value
        return merged
    return loaded


def validate_config_shape(config: Any) -> None:
    if not isinstance(config, dict):
        raise PublishError(
            "The visual-explainer publish config is invalid.\n\n"
            f"{GLOBAL_CONFIG_PATH} must contain a top-level JSON object.",
        )

    for section_name in ("netlify", "preferences"):
        section = config.get(section_name, {})
        if not isinstance(section, dict):
            raise PublishError(
                "The visual-explainer publish config is invalid.\n\n"
                f"`{section_name}` must be a JSON object in {GLOBAL_CONFIG_PATH}.",
            )


def resolve_runtime_settings(config: dict[str, Any], force_open: bool) -> RuntimeSettings:
    netlify = config.get("netlify", {})
    preferences = config.get("preferences", {})

    token_env_var = str(netlify.get("token_env_var", "NETLIFY_VISUAL_EXPLAINER_TOKEN"))
    account_slug_env_var = str(
        netlify.get("account_slug_env_var", "NETLIFY_VISUAL_EXPLAINER_ACCOUNT_SLUG"),
    )
    site_prefix_env_var = str(
        netlify.get("site_prefix_env_var", "NETLIFY_VISUAL_EXPLAINER_SITE_PREFIX"),
    )
    open_browser_env_var = str(
        netlify.get("open_browser_env_var", "NETLIFY_VISUAL_EXPLAINER_OPEN_BROWSER"),
    )

    token = os.environ.get(token_env_var, "").strip()
    if not token:
        raise PublishError(
            f"{token_env_var} not found.\n\n"
            "Add it to your shell profile:\n\n"
            f'  export {token_env_var}="..."',
        )

    account_slug = os.environ.get(account_slug_env_var, "").strip()
    if not account_slug:
        raise PublishError(
            f"{account_slug_env_var} not found.\n\n"
            "Add it to your shell profile:\n\n"
            f'  export {account_slug_env_var}="your-team-slug"',
        )

    site_prefix = os.environ.get(site_prefix_env_var, "visual-explainer").strip()
    if not site_prefix:
        site_prefix = "visual-explainer"

    open_after_publish = bool(preferences.get("open_after_publish", False))
    if open_browser_env_var in os.environ:
        open_after_publish = parse_bool(os.environ[open_browser_env_var])
    if force_open:
        open_after_publish = True

    return RuntimeSettings(
        token=token,
        account_slug=account_slug,
        site_prefix=site_prefix,
        open_after_publish=open_after_publish,
    )


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_site_name(site_prefix: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", site_prefix.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug) or "visual-explainer"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    prefix_budget = 63 - len(timestamp) - len(suffix) - 2
    slug = slug[:prefix_budget].strip("-") or "visual-explainer"
    return f"{slug}-{timestamp}-{suffix}"


def create_site(token: str, account_slug: str, site_name: str) -> dict[str, Any]:
    payload = json.dumps({"name": site_name}).encode("utf-8")
    try:
        return request_json(
            url=f"{API_BASE}/{urllib.parse.quote(account_slug)}/sites",
            token=token,
            method="POST",
            headers={"Content-Type": "application/json"},
            data=payload,
        )
    except NetlifyApiError as error:
        if error.status_code in {401, 403}:
            raise PublishError(
                "Netlify API authentication failed.\n\n"
                "Check whether NETLIFY_VISUAL_EXPLAINER_TOKEN is valid and still active.",
            ) from error
        raise PublishError(
            "Could not create a new Netlify preview site.\n\n"
            "Check NETLIFY_VISUAL_EXPLAINER_ACCOUNT_SLUG, token permissions, and "
            "network access.",
        ) from error


def create_deploy(token: str, site_id: str, title: str, html_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="visual-explainer-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        index_path = temp_dir / "index.html"
        headers_path = temp_dir / "_headers"
        shutil.copy2(html_path, index_path)
        headers_path.write_text(
            "/\n"
            "  Content-Type: text/html; charset=UTF-8\n"
            "/index.html\n"
            "  Content-Type: text/html; charset=UTF-8\n",
            encoding="utf-8",
        )
        archive_path = temp_dir / "site.zip"

        with zipfile.ZipFile(
            archive_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            archive.write(index_path, arcname="index.html")
            archive.write(headers_path, arcname="_headers")

        try:
            return request_json(
                url=(
                    f"{API_BASE}/sites/{urllib.parse.quote(site_id)}/deploys?"
                    f"{urllib.parse.urlencode({'title': title})}"
                ),
                token=token,
                method="POST",
                headers={"Content-Type": "application/zip"},
                data=archive_path.read_bytes(),
            )
        except NetlifyApiError as error:
            if error.status_code in {401, 403}:
                raise PublishError(
                    "Netlify API authentication failed.\n\n"
                    "Check whether NETLIFY_VISUAL_EXPLAINER_TOKEN is valid and still active.",
                ) from error
            raise PublishError(
                "Could not upload the explainer to Netlify.\n\n"
                "The local HTML still exists. Check token permissions and try again.",
            ) from error


def poll_deploy(
    token: str,
    deploy_id: str,
    timeout_seconds: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        deploy = request_json(
            url=f"{API_BASE}/deploys/{urllib.parse.quote(deploy_id)}",
            token=token,
        )
        state = str(deploy.get("state", "")).lower()
        if state == "ready":
            return deploy
        if state == "error":
            raise PublishError(
                "Netlify reported a failed deploy.\n\n"
                "The local HTML still exists. Check the deploy details in Netlify "
                "and retry after fixing the issue.",
            )
        time.sleep(max(poll_interval_seconds, 0.5))

    raise PublishError(
        "Netlify deploy did not reach ready state before the timeout.\n\n"
        "The local HTML still exists. Check Netlify deploy status and retry "
        "publish if needed.",
    )


def request_json(
    url: str,
    token: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
) -> dict[str, Any]:
    request_headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "visual-explainer-netlify-publisher",
        "Accept": "application/json",
    }
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(
        url=url,
        data=data,
        headers=request_headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise NetlifyApiError(
            message=f"Netlify API request failed with status {error.code}.",
            status_code=error.code,
            details=details,
        ) from error
    except urllib.error.URLError as error:
        raise PublishError(
            "Could not reach the Netlify API.\n\n"
            "Check your network connection and try again.",
        ) from error

    if not body:
        return {}
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise PublishError(
            "Netlify returned a response that could not be parsed as JSON.\n\n"
            "Retry the publish. If the problem persists, inspect the API response.",
        ) from error


def select_deploy_url(site_name: str, site: dict[str, Any], deploy: dict[str, Any]) -> str:
    def is_dns_safe_netlify_url(candidate: Any) -> bool:
        if not isinstance(candidate, str) or not candidate.strip():
            return False
        parsed = urllib.parse.urlparse(candidate.strip())
        hostname = parsed.hostname
        if not hostname:
            return False
        return all(len(label) <= 63 for label in hostname.split("."))

    candidates = [
        site.get("ssl_url"),
        site.get("url"),
        deploy.get("ssl_url"),
        deploy.get("url"),
        deploy.get("deploy_ssl_url"),
        deploy.get("deploy_url"),
    ]
    for candidate in candidates:
        if is_dns_safe_netlify_url(candidate):
            return candidate.strip()
    return f"https://{site_name}.netlify.app"


def write_receipt(receipt: dict[str, Any], receipt_stamp: str) -> Path:
    PUBLISH_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    receipt_path = PUBLISH_HISTORY_DIR / f"{receipt_stamp}.json"
    receipt["receipt_path"] = str(receipt_path)
    write_json(receipt_path, receipt)
    return receipt_path


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def require_string(payload: dict[str, Any], key: str, operation: str) -> str:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise PublishError(
        f"Netlify returned an incomplete response during {operation}.\n\n"
        f"Expected a non-empty `{key}` field in the API response.",
    )


def open_in_browser(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        return


def verify_deploy_content_type(url: str) -> None:
    content_type = fetch_content_type(url, method="HEAD")
    if content_type is None:
        content_type = fetch_content_type(url, method="GET")
    if content_type is None or not content_type.lower().startswith("text/html"):
        raise PublishError(
            "Netlify published the site, but the deployed page is not being served "
            "as text/html.\n\n"
            "Check the uploaded artifact and Netlify header rules, then retry publish.",
        )


def fetch_content_type(url: str, method: str) -> str | None:
    request = urllib.request.Request(
        url=url,
        headers={
            "User-Agent": "visual-explainer-netlify-publisher",
            "Accept": "text/html,*/*;q=0.8",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.headers.get("Content-Type")
    except urllib.error.HTTPError as error:
        if method == "HEAD" and error.code in {403, 405}:
            return None
        raise PublishError(
            "Could not verify the deployed page content type.\n\n"
            "Check the published URL in Netlify and retry publish if needed.",
        ) from error
    except urllib.error.URLError as error:
        raise PublishError(
            "Could not verify the deployed page content type.\n\n"
            "Check your network connection and the published URL, then retry.",
        ) from error


def emit_success(receipt: dict[str, Any], json_output: bool) -> None:
    if json_output:
        print(json.dumps(receipt, indent=2))
        return

    print("Netlify preview published.")
    print(f"Local HTML: {receipt['local_html_path']}")
    print(f"Deploy URL: {receipt['deploy_url']}")
    if "receipt_path" in receipt:
        print(f"Receipt: {receipt['receipt_path']}")


def emit_failure(receipt: dict[str, Any], error: PublishError, json_output: bool) -> None:
    if json_output:
        print(json.dumps(receipt, indent=2))
        return

    print(str(error))
    print(f"Local HTML: {receipt['local_html_path']}")
    if "receipt_path" in receipt:
        print(f"Receipt: {receipt['receipt_path']}")


if __name__ == "__main__":
    raise SystemExit(main())
