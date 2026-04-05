#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "click>=8.1,<9",
# ]
# ///
"""JSON-first review memory helper for ``monty-code-review``.

This is intentionally a small v1 helper.

What it does:
- resolve one deterministic review-memory scope
- summarize the compact state a new review needs
- persist one completed review pass

What it intentionally does not do:
- multi-target bundles
- separate changelog files
- comment-thread persistence
- reset/archive workflows

The goal is to keep the durable state simple enough that future reviewers can
understand it quickly and future agents can load it cheaply.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import NamedTemporaryFile
from typing import Literal, NotRequired, TypedDict

import click


SCHEMA_VERSION = 1
LOCK_TIMEOUT_SECONDS = 10.0
LOCK_POLL_INTERVAL_SECONDS = 0.1
LOCK_STALE_SECONDS = 300
HISTORY_STATUS_VALUES = {"linear", "rewritten", "uncertain"}

JsonObject = dict[str, object]


class BranchContext(TypedDict):
    """Branch details used when a review target does not have a stable PR yet."""

    branch_name: str
    base_branch: str | None
    merge_base_sha: str | None


class ReviewFinding(TypedDict):
    """One finding from a single review pass."""

    finding_id: str
    severity: str | None
    summary: str | None


class OpenFinding(TypedDict):
    """A finding that is still considered unresolved."""

    finding_id: str
    first_seen_review: int
    last_seen_review: int
    status: str
    severity: str | None
    summary: str | None


class CommitRecord(TypedDict):
    """Minimal commit metadata that helps explain a review pass."""

    sha: str
    subject: str


class ReviewGroups(TypedDict):
    """Finding groups for one review pass."""

    new: list[ReviewFinding]
    carried_forward: list[ReviewFinding]
    resolved: list[ReviewFinding]


class ReviewRecord(TypedDict):
    """Append-only record for one completed review pass."""

    schema_version: int
    review_number: int
    scope_id: str
    created_at_utc: str
    head_sha: str
    merge_base_sha: str | None
    history_status: str
    repo_review_file: str
    recommendation: str
    review_basis: str | None
    summary_points: list[str]
    commits: list[CommitRecord]
    touched_paths: list[str]
    findings: ReviewGroups


class StateRecord(TypedDict):
    """Current compact state for one deterministic review target."""

    schema_version: int
    scope_kind: Literal["target"]
    scope_id: str
    scope_slug: str
    created_at_utc: str
    updated_at_utc: str
    branch_context: NotRequired[BranchContext]
    last_synced_at_utc: str | None
    last_reviewed_head_sha: str | None
    last_reviewed_merge_base_sha: str | None
    history_status: str
    next_review_number: int
    open_findings: list[OpenFinding]


class CompactFinding(TypedDict, total=False):
    """Small projection used in summarize-context output."""

    finding_id: str
    severity: str | None
    summary: str | None
    status: str
    first_seen_review: int
    last_seen_review: int


def utc_now() -> str:
    """Return a canonical UTC timestamp for persistence."""

    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_utc(timestamp: str) -> datetime:
    """Parse the helper's persisted UTC timestamp shape."""

    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def format_local(timestamp: str) -> str:
    """Render a persisted UTC timestamp for the engineer's local timezone."""

    return parse_utc(timestamp).astimezone().strftime("%Y-%m-%d %H:%M %Z")


def local_timezone_name() -> str:
    """Return the engineer-visible local timezone name for display."""

    timezone_name = datetime.now().astimezone().tzname()
    if timezone_name is not None:
        return timezone_name
    return "local"


def local_utc_offset() -> str:
    """Return the engineer-visible local UTC offset for display."""

    return datetime.now().astimezone().strftime("%z")


def slugify(value: str) -> str:
    """Create a filesystem-safe slug from a human-readable identifier."""

    slug_chars: list[str] = []
    last_dash = False
    for char in value.lower():
        if char.isalnum():
            slug_chars.append(char)
            last_dash = False
            continue
        if not last_dash:
            slug_chars.append("-")
            last_dash = True
    slug = "".join(slug_chars).strip("-")
    if slug:
        return slug
    return "review-memory"


def short_hash(value: str) -> str:
    """Create a short stable hash for deterministic directory names."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def storage_root() -> Path:
    """Resolve the XDG-aware root used for persistent review memory."""

    custom = os.environ.get("MONTY_REVIEW_MEMORY_HOME")
    if custom:
        return Path(custom).expanduser()
    xdg_state = os.environ.get("XDG_STATE_HOME")
    if xdg_state:
        return Path(xdg_state).expanduser() / "monty-code-review"
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache).expanduser() / "monty-code-review"
    return Path.home() / ".cache" / "monty-code-review"


def ensure_dir(path: Path) -> None:
    """Create a directory if needed and keep permissions restrictive when possible."""

    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def atomic_write_json(path: Path, payload: object) -> None:
    """Write JSON via a temp file so readers never see a half-written object."""

    ensure_dir(path.parent)
    with NamedTemporaryFile(
        "w",
        delete=False,
        dir=path.parent,
        encoding="utf-8",
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    os.replace(temp_path, path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def append_jsonl(path: Path, rows: Sequence[object]) -> None:
    """Append newline-delimited JSON records without rewriting prior history."""

    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        path.chmod(0o600)
    except OSError:
        pass


def read_json_object(path: Path, *, default: JsonObject | None = None) -> JsonObject:
    """Read one JSON object from disk and reject non-object payloads."""

    if not path.exists():
        if default is None:
            return {}
        return default
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"expected JSON object at {path}")
    return dict(loaded)


def read_jsonl_tail(path: Path, limit: int) -> list[JsonObject]:
    """Read only the newest JSONL rows needed for a compact context summary."""

    if not path.exists() or limit <= 0:
        return []
    chunk_size = 8192
    buffer = b""
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        while position > 0 and buffer.count(b"\n") <= limit:
            read_size = min(chunk_size, position)
            position -= read_size
            handle.seek(position)
            buffer = handle.read(read_size) + buffer

    rows: list[JsonObject] = []
    for line in buffer.splitlines()[-limit:]:
        if not line.strip():
            continue
        loaded = json.loads(line.decode("utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"expected JSON object lines in {path}")
        rows.append(dict(loaded))
    return rows


def require_string(payload: Mapping[str, object], key: str) -> str:
    """Read one required string field from a JSON object."""

    value = payload.get(key)
    if isinstance(value, str):
        return value
    raise ValueError(f"expected string field '{key}'")


def optional_string(payload: Mapping[str, object], key: str) -> str | None:
    """Read one optional string field from a JSON object."""

    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise ValueError(f"expected optional string field '{key}'")


def optional_int(payload: Mapping[str, object], key: str) -> int | None:
    """Read one optional integer field from a JSON object."""

    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"expected optional integer field '{key}'")
    if isinstance(value, int):
        return value
    raise ValueError(f"expected optional integer field '{key}'")


def require_schema_version(payload: Mapping[str, object], path: Path) -> int:
    """Require a valid schema version for persisted state metadata."""

    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise ValueError(
            f"state metadata at {path} is missing a valid integer schema_version; "
            "an explicit migration or regeneration step is required",
        )
    if schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"state metadata at {path} has schema_version={schema_version}, "
            f"expected {SCHEMA_VERSION}; an explicit migration step is required",
        )
    return schema_version


def object_dict(value: object, label: str) -> JsonObject:
    """Require one JSON object from an unknown value."""

    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object for '{label}'")
    return dict(value)


def object_dict_list(value: object, label: str) -> list[JsonObject]:
    """Require a list of JSON objects from an unknown value."""

    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"expected JSON object list for '{label}'")
    items: list[JsonObject] = []
    for item in value:
        items.append(object_dict(item, label))
    return items


def string_list(value: object, label: str) -> list[str]:
    """Require a list of strings from an unknown value."""

    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"expected list for '{label}'")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"expected string items for '{label}'")
        items.append(item)
    return items


def validate_repo_review_file(value: str) -> str:
    """Require a repo-local relative review path, not a machine-specific path."""

    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if posix_path.is_absolute() or windows_path.is_absolute():
        raise ValueError("repo_review_file must be a relative in-repo path")
    if any(part == ".." for part in posix_path.parts) or any(
        part == ".." for part in windows_path.parts
    ):
        raise ValueError("repo_review_file must not contain parent-directory segments")
    if value.strip() == "":
        raise ValueError("repo_review_file must not be empty")
    return value


def normalize_branch_context(value: object) -> BranchContext | None:
    """Normalize optional branch context from raw JSON."""

    if value is None:
        return None
    payload = object_dict(value, "branch_context")
    return {
        "branch_name": require_string(payload, "branch_name"),
        "base_branch": optional_string(payload, "base_branch"),
        "merge_base_sha": optional_string(payload, "merge_base_sha"),
    }


def normalize_review_finding(raw: Mapping[str, object]) -> ReviewFinding:
    """Normalize one review finding from raw JSON."""

    return {
        "finding_id": require_string(raw, "finding_id"),
        "severity": optional_string(raw, "severity"),
        "summary": optional_string(raw, "summary"),
    }


def normalize_review_finding_list(value: object, label: str) -> list[ReviewFinding]:
    """Normalize a list of review findings from raw JSON."""

    return [normalize_review_finding(item) for item in object_dict_list(value, label)]


def normalize_open_finding(raw: Mapping[str, object]) -> OpenFinding:
    """Normalize one persisted open finding from raw JSON."""

    first_seen_review = optional_int(raw, "first_seen_review")
    last_seen_review = optional_int(raw, "last_seen_review")
    if first_seen_review is None or last_seen_review is None:
        raise ValueError("open finding requires first_seen_review and last_seen_review")
    return {
        "finding_id": require_string(raw, "finding_id"),
        "first_seen_review": first_seen_review,
        "last_seen_review": last_seen_review,
        "status": require_string(raw, "status"),
        "severity": optional_string(raw, "severity"),
        "summary": optional_string(raw, "summary"),
    }


def normalize_open_finding_list(value: object, label: str) -> list[OpenFinding]:
    """Normalize a list of persisted open findings from raw JSON."""

    return [normalize_open_finding(item) for item in object_dict_list(value, label)]


def normalize_commit(raw: Mapping[str, object]) -> CommitRecord:
    """Normalize one commit summary from raw JSON."""

    return {
        "sha": require_string(raw, "sha"),
        "subject": require_string(raw, "subject"),
    }


def normalize_commit_list(value: object, label: str) -> list[CommitRecord]:
    """Normalize a list of commit summaries from raw JSON."""

    return [normalize_commit(item) for item in object_dict_list(value, label)]


def normalize_review_groups(value: object) -> ReviewGroups:
    """Normalize the grouped findings for one review pass."""

    if value is None:
        return {"new": [], "carried_forward": [], "resolved": []}
    payload = object_dict(value, "findings")
    return {
        "new": normalize_review_finding_list(payload.get("new"), "findings.new"),
        "carried_forward": normalize_review_finding_list(
            payload.get("carried_forward"),
            "findings.carried_forward",
        ),
        "resolved": normalize_review_finding_list(
            payload.get("resolved"),
            "findings.resolved",
        ),
    }


def normalize_state(
    raw: Mapping[str, object], scope_id: str, scope_slug: str
) -> StateRecord:
    """Coerce raw JSON into the compact state shape the helper relies on."""

    created_at_utc = optional_string(raw, "created_at_utc")
    updated_at_utc = optional_string(raw, "updated_at_utc")
    history_status = optional_string(raw, "history_status")
    next_review_number = optional_int(raw, "next_review_number")

    state: StateRecord = {
        "schema_version": SCHEMA_VERSION,
        "scope_kind": "target",
        "scope_id": scope_id,
        "scope_slug": scope_slug,
        "created_at_utc": created_at_utc if created_at_utc is not None else utc_now(),
        "updated_at_utc": updated_at_utc if updated_at_utc is not None else utc_now(),
        "last_synced_at_utc": optional_string(raw, "last_synced_at_utc"),
        "last_reviewed_head_sha": optional_string(raw, "last_reviewed_head_sha"),
        "last_reviewed_merge_base_sha": optional_string(
            raw,
            "last_reviewed_merge_base_sha",
        ),
        "history_status": history_status if history_status is not None else "uncertain",
        "next_review_number": next_review_number
        if next_review_number is not None
        else 1,
        "open_findings": normalize_open_finding_list(
            raw.get("open_findings"), "open_findings"
        ),
    }
    branch_context = normalize_branch_context(raw.get("branch_context"))
    if branch_context is not None:
        state["branch_context"] = branch_context
    return state


def normalize_history_status(value: str) -> str:
    """Validate and normalize one persisted history status value."""

    normalized = value.strip().lower()
    if normalized not in HISTORY_STATUS_VALUES:
        valid_values = ", ".join(sorted(HISTORY_STATUS_VALUES))
        raise ValueError(
            f"invalid history_status '{value}'; expected one of: {valid_values}",
        )
    return normalized


def default_state(
    scope_id: str, scope_slug: str, branch_context: BranchContext | None
) -> StateRecord:
    """Build the default state for a brand-new scope."""

    now = utc_now()
    state: StateRecord = {
        "schema_version": SCHEMA_VERSION,
        "scope_kind": "target",
        "scope_id": scope_id,
        "scope_slug": scope_slug,
        "created_at_utc": now,
        "updated_at_utc": now,
        "last_synced_at_utc": None,
        "last_reviewed_head_sha": None,
        "last_reviewed_merge_base_sha": None,
        "history_status": "uncertain",
        "next_review_number": 1,
        "open_findings": [],
    }
    if branch_context is not None:
        state["branch_context"] = branch_context
    return state


@contextmanager
def scope_lock(scope_dir: Path) -> Iterator[None]:
    """Serialize writes per scope so concurrent worktrees do not clobber state."""

    lock_path = scope_dir / ".lock"
    ensure_dir(scope_dir)
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            os.write(
                descriptor,
                json.dumps(
                    {"pid": os.getpid(), "created_at_utc": utc_now()},
                    sort_keys=True,
                ).encode("utf-8"),
            )
            os.close(descriptor)
            break
        except FileExistsError:
            if stale_lock_recovered(lock_path):
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for lock: {lock_path}")
            time.sleep(LOCK_POLL_INTERVAL_SECONDS)
    try:
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def canonical_scope_id(
    *,
    provider: Literal["github", "git"],
    host: str,
    owner: str | None,
    repo: str | None,
    pull_number: int | None,
    repo_key: str | None,
    branch_name: str | None,
    base_branch: str | None,
    merge_base_sha: str | None,
) -> tuple[str, str, BranchContext | None]:
    """Build the stable identity used to store and re-find review memory."""

    if provider == "github":
        if owner is None or repo is None or pull_number is None:
            raise ValueError("github scopes require --owner, --repo, and --pull-number")
        normalized_host = host.lower()
        normalized_owner = owner.lower()
        normalized_repo = repo.lower()
        scope_id = (
            f"{normalized_host}/{normalized_owner}/{normalized_repo}/pull/{pull_number}"
        )
        scope_slug = slugify(f"{normalized_repo}-pr-{pull_number}")
        return scope_id, scope_slug, None

    if repo_key is None or branch_name is None:
        raise ValueError("git scopes require --repo-key and --branch-name")
    if (base_branch is None) == (merge_base_sha is None):
        raise ValueError(
            "git scopes require exactly one of --base-branch or --merge-base-sha"
        )
    base_value = base_branch if base_branch is not None else merge_base_sha
    scope_id = f"git/{repo_key}/branch/{branch_name}@{base_value}"
    scope_slug = slugify(f"{Path(repo_key).name}-branch-{branch_name}")
    return (
        scope_id,
        scope_slug,
        {
            "branch_name": branch_name,
            "base_branch": base_branch,
            "merge_base_sha": merge_base_sha,
        },
    )


def state_path(scope_dir: Path) -> Path:
    """Return the path for the compact current-state file."""

    return scope_dir / "state.json"


def reviews_path(scope_dir: Path) -> Path:
    """Return the append-only reviews log path."""

    return scope_dir / "reviews.jsonl"


def require_state(scope_dir: Path) -> StateRecord:
    """Load one resolved scope and fail closed if it does not exist yet."""

    path = state_path(scope_dir)
    if not path.exists():
        raise FileNotFoundError(
            f"state metadata not found at {path}; run resolve-scope first",
        )
    raw = read_json_object(path)
    require_schema_version(raw, path)
    scope_id = require_string(raw, "scope_id")
    scope_slug = require_string(raw, "scope_slug")
    return normalize_state(raw, scope_id, scope_slug)


def ensure_reviews_file(scope_dir: Path) -> None:
    """Create the append-only reviews log if it does not exist yet."""

    path = reviews_path(scope_dir)
    if not path.exists():
        ensure_dir(path.parent)
        path.touch(mode=0o600)


def process_is_alive(pid: int) -> bool:
    """Return whether a recorded PID still appears to be alive."""

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def stale_lock_recovered(lock_path: Path) -> bool:
    """Remove a stale lock when the owner is gone or the lock is too old."""

    try:
        age_seconds = time.time() - lock_path.stat().st_mtime
    except FileNotFoundError:
        return True

    pid: int | None = None
    try:
        raw = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = None

    if isinstance(raw, dict):
        raw_pid = raw.get("pid")
        if isinstance(raw_pid, bool):
            pid = None
        elif isinstance(raw_pid, int):
            pid = raw_pid

    if pid is not None:
        if process_is_alive(pid):
            return False
        stale = True
    else:
        stale = age_seconds > LOCK_STALE_SECONDS

    if not stale:
        return False

    try:
        lock_path.unlink()
    except FileNotFoundError:
        return True
    return True


def add_local_display_fields(
    record: Mapping[str, object],
    keys: Sequence[str],
) -> JsonObject:
    """Augment persisted UTC records with local-time display fields for humans."""

    enriched: JsonObject = dict(record)
    for key in keys:
        timestamp = record.get(key)
        if isinstance(timestamp, str):
            local_key = key.removesuffix("_utc") + "_local"
            enriched[local_key] = format_local(timestamp)
    return enriched


def compact_open_findings(
    items: Sequence[OpenFinding], limit: int
) -> list[CompactFinding]:
    """Trim open findings to the smallest summary the model usually needs."""

    trimmed: list[CompactFinding] = []
    for item in items[:limit]:
        trimmed.append(
            {
                "finding_id": item["finding_id"],
                "severity": item["severity"],
                "summary": item["summary"],
                "status": item["status"],
                "first_seen_review": item["first_seen_review"],
                "last_seen_review": item["last_seen_review"],
            }
        )
    return trimmed


def normalize_open_findings(
    incoming: Sequence[ReviewFinding],
    existing_open: Mapping[str, OpenFinding],
    review_number: int,
    status: str,
) -> dict[str, OpenFinding]:
    """Normalize findings while preserving when an issue was first seen."""

    normalized: dict[str, OpenFinding] = {}
    for item in incoming:
        previous = existing_open.get(item["finding_id"])
        first_seen_review = review_number
        if previous is not None:
            first_seen_review = previous["first_seen_review"]
        normalized[item["finding_id"]] = {
            "finding_id": item["finding_id"],
            "first_seen_review": first_seen_review,
            "last_seen_review": review_number,
            "status": status,
            "severity": item["severity"],
            "summary": item["summary"],
        }
    return normalized


def print_json(payload: object) -> None:
    """Print one pretty JSON object to stdout."""

    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def read_stdin_json() -> object:
    """Read one JSON payload from stdin."""

    raw = sys.stdin.read().strip()
    if not raw:
        raise ValueError("expected JSON on stdin")
    return json.loads(raw)


def command_resolve_scope(
    *,
    provider: Literal["github", "git"],
    host: str,
    owner: str | None,
    repo: str | None,
    pull_number: int | None,
    repo_key: str | None,
    branch_name: str | None,
    base_branch: str | None,
    merge_base_sha: str | None,
) -> int:
    """Create or update the deterministic directory that owns one memory scope."""

    root = storage_root()
    ensure_dir(root)
    targets_root = root / "targets"
    ensure_dir(targets_root)

    scope_id, scope_slug, branch_context = canonical_scope_id(
        provider=provider,
        host=host,
        owner=owner,
        repo=repo,
        pull_number=pull_number,
        repo_key=repo_key,
        branch_name=branch_name,
        base_branch=base_branch,
        merge_base_sha=merge_base_sha,
    )
    scope_hash = short_hash(scope_id)
    scope_dir = targets_root / f"{scope_slug}--{scope_hash}"

    with scope_lock(scope_dir):
        current_state_path = state_path(scope_dir)
        if current_state_path.exists():
            state = require_state(scope_dir)
        else:
            state = default_state(scope_id, scope_slug, branch_context)
        state["updated_at_utc"] = utc_now()
        if branch_context is not None:
            state["branch_context"] = branch_context
        atomic_write_json(current_state_path, state)
        ensure_reviews_file(scope_dir)

    response: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "scope_dir": str(scope_dir),
        "scope_id": scope_id,
        "scope_kind": "target",
        "scope_slug": scope_slug,
        "scope_hash": scope_hash,
        "display_timezone": local_timezone_name(),
        "display_utc_offset": local_utc_offset(),
    }
    print_json(response)
    return 0


def command_summarize_context(*, scope_dir: Path, finding_limit: int) -> int:
    """Return a compact summary so the skill can avoid loading raw history files."""

    resolved_scope_dir = scope_dir.expanduser().resolve()
    with scope_lock(resolved_scope_dir):
        state = require_state(resolved_scope_dir)
        latest_review = None
        recent_resolved_findings: list[ReviewFinding] = []
        review_rows = read_jsonl_tail(reviews_path(resolved_scope_dir), 1)
        if review_rows:
            latest_review = add_local_display_fields(
                review_rows[-1],
                ["created_at_utc"],
            )
            latest_findings = normalize_review_groups(review_rows[-1].get("findings"))
            recent_resolved_findings = latest_findings["resolved"][:finding_limit]

    last_synced_at_utc = state["last_synced_at_utc"]
    response: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "scope_dir": str(resolved_scope_dir),
        "scope_id": state["scope_id"],
        "scope_kind": state["scope_kind"],
        "display_timezone": local_timezone_name(),
        "display_utc_offset": local_utc_offset(),
        "history_status": state["history_status"],
        "last_synced_at_utc": last_synced_at_utc,
        "last_synced_at_local": format_local(last_synced_at_utc)
        if last_synced_at_utc is not None
        else None,
        "last_reviewed_head_sha": state["last_reviewed_head_sha"],
        "last_reviewed_merge_base_sha": state["last_reviewed_merge_base_sha"],
        "next_review_number": state["next_review_number"],
        "open_findings_count": len(state["open_findings"]),
        "open_findings": compact_open_findings(
            state["open_findings"],
            finding_limit,
        ),
        "recent_resolved_findings": recent_resolved_findings,
        "latest_review": latest_review,
    }
    print_json(response)
    return 0


def command_record_review(*, scope_dir: Path) -> int:
    """Record one completed review pass into structured memory.

    Important behavior:
    - Explicitly resolved findings leave open state.
    - Newly omitted findings stay open until a later review resolves them.
    - The repo-local markdown review remains a referenced artifact, not the
      canonical source of truth.
    """

    resolved_scope_dir = scope_dir.expanduser().resolve()
    raw_payload = object_dict(read_stdin_json(), "record-review payload")
    findings = normalize_review_groups(raw_payload.get("findings"))
    head_sha = require_string(raw_payload, "head_sha")
    history_status = normalize_history_status(
        require_string(raw_payload, "history_status")
    )
    repo_review_file = validate_repo_review_file(
        require_string(raw_payload, "repo_review_file")
    )
    recommendation = require_string(raw_payload, "recommendation")
    merge_base_sha = optional_string(raw_payload, "merge_base_sha")
    review_basis = optional_string(raw_payload, "review_basis")
    summary_points = string_list(raw_payload.get("summary_points"), "summary_points")
    commits = normalize_commit_list(raw_payload.get("commits"), "commits")
    touched_paths = string_list(raw_payload.get("touched_paths"), "touched_paths")

    with scope_lock(resolved_scope_dir):
        state = require_state(resolved_scope_dir)
        review_number = state["next_review_number"]
        recorded_at = utc_now()
        existing_open = {item["finding_id"]: item for item in state["open_findings"]}
        new_findings = normalize_open_findings(
            findings["new"],
            existing_open,
            review_number,
            "new",
        )
        carried_findings = normalize_open_findings(
            findings["carried_forward"],
            existing_open,
            review_number,
            "carried_forward",
        )
        current_open = dict(existing_open)
        current_open.update(new_findings)
        current_open.update(carried_findings)
        for item in findings["resolved"]:
            current_open.pop(item["finding_id"], None)

        review_record: ReviewRecord = {
            "schema_version": SCHEMA_VERSION,
            "review_number": review_number,
            "scope_id": state["scope_id"],
            "created_at_utc": recorded_at,
            "head_sha": head_sha,
            "merge_base_sha": merge_base_sha,
            "history_status": history_status,
            "repo_review_file": repo_review_file,
            "recommendation": recommendation,
            "review_basis": review_basis,
            "summary_points": summary_points,
            "commits": commits,
            "touched_paths": touched_paths,
            "findings": findings,
        }
        reviews_file = reviews_path(resolved_scope_dir)
        previous_size = reviews_file.stat().st_size if reviews_file.exists() else 0
        state["updated_at_utc"] = recorded_at
        state["last_synced_at_utc"] = recorded_at
        state["last_reviewed_head_sha"] = head_sha
        state["last_reviewed_merge_base_sha"] = merge_base_sha
        state["history_status"] = history_status
        state["next_review_number"] = review_number + 1
        state["open_findings"] = sorted(
            current_open.values(),
            key=lambda item: item["finding_id"],
        )
        append_jsonl(reviews_file, [review_record])
        try:
            atomic_write_json(state_path(resolved_scope_dir), state)
        except OSError:
            with reviews_file.open("r+", encoding="utf-8") as handle:
                handle.truncate(previous_size)
                handle.flush()
                os.fsync(handle.fileno())
            raise

    response: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "scope_dir": str(resolved_scope_dir),
        "scope_id": state["scope_id"],
        "review_number": review_number,
        "created_at_utc": recorded_at,
        "created_at_local": format_local(recorded_at),
        "reviews_file": str(reviews_path(resolved_scope_dir)),
        "repo_review_file": repo_review_file,
        "open_findings_count": len(current_open),
        "resolved_findings_count": len(findings["resolved"]),
    }
    print_json(response)
    return 0


def run_click_command(command: Callable[[], int]) -> None:
    """Convert expected operational failures into concise CLI errors."""

    try:
        command()
    except (
        FileNotFoundError,
        ValueError,
        TimeoutError,
        json.JSONDecodeError,
        OSError,
    ) as error:
        raise click.ClickException(str(error)) from error


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help=(
        "Manage monty-code-review's persistent JSON-first review memory.\n\n"
        "This v1 helper intentionally stays small: one deterministic target, one "
        "compact state file, and one append-only reviews log."
    ),
)
def cli() -> None:
    """JSON-first review memory helper for monty-code-review."""


@cli.command(
    "resolve-scope",
    help="Create or refresh the deterministic memory directory for one PR or branch.",
)
@click.option(
    "--provider",
    type=click.Choice(["github", "git"]),
    default="github",
    show_default=True,
    help="Identity source used to build the canonical scope ID.",
)
@click.option(
    "--host",
    default="github.com",
    show_default=True,
    help="GitHub host for PR-backed scopes.",
)
@click.option("--owner", help="Repository owner for PR-backed scopes.")
@click.option("--repo", help="Repository name for PR-backed scopes.")
@click.option(
    "--pull-number", type=int, help="Pull request number for PR-backed scopes."
)
@click.option("--repo-key", help="Canonical repository key for branch-backed scopes.")
@click.option("--branch-name", help="Branch name for branch-backed scopes.")
@click.option("--base-branch", help="Base branch name for branch-backed scopes.")
@click.option(
    "--merge-base-sha",
    help="Merge-base SHA when branch history is rewritten or base names are unclear.",
)
def resolve_scope_cli(
    provider: str,
    host: str,
    owner: str | None,
    repo: str | None,
    pull_number: int | None,
    repo_key: str | None,
    branch_name: str | None,
    base_branch: str | None,
    merge_base_sha: str | None,
) -> None:
    run_click_command(
        lambda: command_resolve_scope(
            provider=provider,
            host=host,
            owner=owner,
            repo=repo,
            pull_number=pull_number,
            repo_key=repo_key,
            branch_name=branch_name,
            base_branch=base_branch,
            merge_base_sha=merge_base_sha,
        )
    )


@cli.command(
    "summarize-context",
    help="Return the compact context the model should read before a new review.",
)
@click.option(
    "--scope-dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Resolved memory directory returned by resolve-scope.",
)
@click.option(
    "--finding-limit",
    type=click.IntRange(min=1),
    default=10,
    show_default=True,
    help="Maximum number of open or recently resolved findings to include.",
)
def summarize_context_cli(scope_dir: Path, finding_limit: int) -> None:
    run_click_command(
        lambda: command_summarize_context(
            scope_dir=scope_dir,
            finding_limit=finding_limit,
        )
    )


@cli.command(
    "record-review",
    help=(
        "Read one completed review result from stdin and persist it into the "
        "canonical JSON-first memory store."
    ),
)
@click.option(
    "--scope-dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Resolved memory directory returned by resolve-scope.",
)
def record_review_cli(scope_dir: Path) -> None:
    run_click_command(lambda: command_record_review(scope_dir=scope_dir))


if __name__ == "__main__":
    cli()
