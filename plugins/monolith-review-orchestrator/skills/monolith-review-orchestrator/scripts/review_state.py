#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "click>=8.1,<9",
# ]
# ///
"""Structured local state helper for monolith review orchestrator.

Why this helper exists:
- markdown review notes are useful for humans but weak as reassessment identity
- follow-up review passes need stable fields like repo, PR number, base branch,
  head SHA, and merge base
- world-class reassessment also needs compact cached context about prior
  findings, comment legitimacy, and author guidance, not just paths and SHAs
- the model should not hand-edit JSON blobs in chat and hope they stay coherent

Mental model:
    markdown review artifact = human-facing review output
    JSON state = machine-facing reassessment identity + compact review context
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal, TypedDict
from urllib.parse import urlparse
from uuid import uuid4

import click

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from review_targets import KNOWN_V1_REPOS  # noqa: E402


SCHEMA_VERSION = 3
SUPPORTED_SCHEMA_VERSIONS: set[int] = {1, 2, SCHEMA_VERSION}
PUBLIC_MODES: set[str] = {"status", "review", "reassess", "post"}
COMPATIBILITY_MODE = "compatibility_recovery"
ALLOWED_PERSISTED_MODES: set[str] = {*PUBLIC_MODES, COMPATIBILITY_MODE}
ALLOWED_RECOMMENDATIONS: set[str] = {"approve", "comment", "request_changes"}
ALLOWED_POSTING_STATUSES: set[str] = {
    "not_posted",
    "posted_comment",
    "posted_request_changes",
    "posted_approved",
}
LIVE_VALIDATION_TTL = timedelta(minutes=10)
CONTEXT_LIST_FIELDS: tuple[str, ...] = (
    "still_legit",
    "moot_or_no_longer_applicable",
    "resolved_for_context",
    "follow_up",
)
LEGACY_CONTEXT_LIST_FIELDS: tuple[str, ...] = ("moot_or_resolved",)
CURRENT_STATUS_CONTEXT_FIELDS: tuple[str, ...] = (
    "still_legit",
    "moot_or_no_longer_applicable",
    "follow_up",
)
DURABLE_CONTEXT_LIST_FIELDS: tuple[str, ...] = ("resolved_for_context",)

FINDING_BUCKETS: tuple[str, ...] = ("new", "carried_forward", "resolved", "moot")
ReviewThreadStatus = Literal["open", "resolved", "moot"]
# GitHub review anchors only support two sides in the current worker contract.
# Keeping the alias explicit makes the validation logic below easier to read.
ReviewCommentSide = Literal["RIGHT", "LEFT"]


class ReviewBatchIdentity(TypedDict):
    repo: str
    pr_number: int


class LinkedBatchMetadata(TypedDict, total=False):
    link_type: str
    is_explicitly_linked: bool
    linked_pair_reason: str
    cross_repo_dependency_summary: str
    authoritative_pr: ReviewBatchIdentity


class ReviewPassEntry(TypedDict):
    repo: str
    pr_number: int
    base_branch: str
    head_sha: str
    merge_base: str
    pr_state: str
    is_draft: bool


class LiveValidationRecord(TypedDict):
    token: str
    validated_at_utc: str
    validated_against_pass_number: int
    entries: list[ReviewPassEntry]
    source_artifact_path: str


class ReviewFinding(TypedDict, total=False):
    repo: str
    pr_number: int
    id: str
    severity: str
    summary: str
    path: str
    symbol: str
    risk: str
    suggested_fix: str


class ReviewFindings(TypedDict, total=False):
    new: list[ReviewFinding]
    carried_forward: list[ReviewFinding]
    resolved: list[ReviewFinding]
    moot: list[ReviewFinding]


class AuthorClaimCheck(TypedDict, total=False):
    repo: str
    pr_number: int
    claim: str
    status: str
    evidence: str


class ReviewThreadContext(TypedDict, total=False):
    repo: str
    pr_number: int
    thread_id: str
    comment_ids: list[int]
    path: str
    line: int
    is_resolved: bool
    is_outdated: bool
    linked_finding_id: str
    status: ReviewThreadStatus
    last_seen_head_sha: str
    summary: str


class CommentContext(TypedDict, total=False):
    thread_source: str
    summary: str
    threads: list[ReviewThreadContext]
    still_legit: list[str]
    moot_or_no_longer_applicable: list[str]
    resolved_for_context: list[str]
    follow_up: list[str]


class InlineCommentTarget(TypedDict, total=False):
    """One persisted inline-comment plan tied to an active finding.

    First principle:
    this state file does not store arbitrary prose about "maybe comment here".
    It stores the smallest anchor shape that later review passes and workers can
    reason about safely.

    Visual model:

        finding_id
          -> why this comment exists

        path + line + side
          -> where the worker should expect to anchor it

        start_line + start_side
          -> optional range start for the rare multiline case

        expected_line_text
          -> optional safety check so stale anchors fail closed

    `summary` stays optional for backwards compatibility and human context, but
    the current Phase 2a contract is the explicit anchor fields above.
    """

    repo: str
    pr_number: int
    finding_id: str
    path: str
    line: int
    summary: str
    side: ReviewCommentSide
    start_line: int
    start_side: ReviewCommentSide
    expected_line_text: str


class BackendHandoff(TypedDict, total=False):
    repo: str
    pr_number: int
    worktree_path: str
    pr_url: str
    head_sha: str
    prior_open_finding_ids: list[str]
    thread_context_summary: str
    allowed_posting_action: str


class ReviewPassRecord(TypedDict, total=False):
    review_pass_number: int
    recorded_at_utc: str
    artifact_path: str
    posting_status: str
    entries: list[ReviewPassEntry]
    mode: str
    recommendation: str
    scope_summary: str
    business_logic_summary: str
    cross_repo_summary: str
    no_author_claims: bool
    no_findings_after_full_review: bool
    author_claims_checked: list[AuthorClaimCheck]
    backend_handoff: BackendHandoff
    comment_context: CommentContext
    findings: ReviewFindings
    teaching_points: list[str]
    inline_comment_targets: list[InlineCommentTarget]


class ReviewStateRecord(TypedDict, total=False):
    schema_version: int
    batch_key: str
    created_at_utc: str
    updated_at_utc: str
    worktree_path: str
    artifact_path: str
    review_pass_number: int
    posting_status: str
    prs: list[ReviewBatchIdentity]
    linked_batch: LinkedBatchMetadata
    pending_live_validation: LiveValidationRecord
    passes: list[ReviewPassRecord]


class ReviewPayloadInput(TypedDict, total=False):
    mode: str
    artifact_path: str
    posting_status: str
    recommendation: str
    validation_token: str
    scope_summary: str
    business_logic_summary: str
    cross_repo_summary: str
    no_author_claims: bool
    no_findings_after_full_review: bool
    author_claims_checked: list[AuthorClaimCheck]
    backend_handoff: BackendHandoff
    comment_context: CommentContext
    findings: ReviewFindings
    teaching_points: list[str]
    inline_comment_targets: list[InlineCommentTarget]
    entries: list[ReviewPassEntry]


class PassHistoryEntry(TypedDict, total=False):
    review_pass_number: int
    recorded_at_utc: str
    mode: str
    recommendation: str
    artifact_path: str


class ReviewContextSummary(TypedDict, total=False):
    batch_key: str
    worktree_path: str
    artifact_path: str
    review_pass_number: int
    posting_status: str
    prs: list[ReviewBatchIdentity]
    linked_batch: LinkedBatchMetadata
    pass_history: list[PassHistoryEntry]
    latest_context: ReviewPassRecord
    open_finding_count: int
    open_findings: list[ReviewFinding]
    latest_resolved_findings: list[ReviewFinding]
    latest_moot_findings: list[ReviewFinding]


class LivePullRequestMetadata(TypedDict):
    repo: str
    pr_number: int
    pr_url: str
    base_branch: str
    head_sha: str
    pr_state: str
    is_draft: bool


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_utc_timestamp(value: str, field_name: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise click.ClickException(
            f"Review payload field `{field_name}` must be a valid ISO-8601 timestamp."
        ) from exc
    if parsed.tzinfo is None:
        raise click.ClickException(
            f"Review payload field `{field_name}` must include timezone information."
        )
    return parsed.astimezone(timezone.utc)


def validate_backend_handoff_pr_url(pr_url: str, repo: str, pr_number: int) -> None:
    parsed = urlparse(pr_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "github.com":
        raise click.ClickException(
            "Review payload field `backend_handoff.pr_url` must be a GitHub pull request URL."
        )
    parts = [part for part in parsed.path.split("/") if part]
    expected_parts = ["DiversioTeam", repo, "pull", str(pr_number)]
    if parts[:4] != expected_parts:
        raise click.ClickException(
            "Review payload field `backend_handoff.pr_url` must match the backend "
            f"batch entry `{repo}#{pr_number}`."
        )


def parse_live_pr_context_payload(
    payload: object,
    known_prs: set[tuple[str, int]],
    source_label: str,
) -> dict[tuple[str, int], LivePullRequestMetadata]:
    if not isinstance(payload, dict):
        raise click.ClickException(
            f"Live PR context artifact `{source_label}` must contain a JSON object."
        )
    source = require_non_empty_string(payload.get("source"), "source")
    if source != "gh_graphql_review_threads":
        raise click.ClickException(
            f"Live PR context artifact `{source_label}` must come from "
            "`fetch_review_threads.py`."
        )
    raw_pull_requests = payload.get("pull_requests")
    if not isinstance(raw_pull_requests, list):
        raise click.ClickException(
            f"Live PR context artifact `{source_label}` is missing a valid `pull_requests` list."
        )

    parsed: dict[tuple[str, int], LivePullRequestMetadata] = {}
    for index, item in enumerate(raw_pull_requests):
        if not isinstance(item, dict):
            raise click.ClickException(
                f"Live PR context artifact `{source_label}` has a non-object `pull_requests[{index}]` entry."
            )
        pull_request = item.get("pull_request")
        if not isinstance(pull_request, dict):
            raise click.ClickException(
                f"Live PR context artifact `{source_label}` is missing `pull_requests[{index}].pull_request`."
            )
        repo = require_non_empty_string(
            pull_request.get("repo"), f"pull_requests[{index}].pull_request.repo"
        )
        pr_number = require_non_boolean_int(
            pull_request.get("pr_number"),
            f"pull_requests[{index}].pull_request.pr_number",
        )
        identity = (repo, pr_number)
        if identity not in known_prs:
            raise click.ClickException(
                f"Live PR context artifact `{source_label}` includes `{repo}:{pr_number}`, "
                "which is not part of this review batch."
            )
        if identity in parsed:
            raise click.ClickException(
                f"Live PR context artifact `{source_label}` contains duplicate PR metadata for `{repo}:{pr_number}`."
            )
        parsed[identity] = {
            "repo": repo,
            "pr_number": pr_number,
            "pr_url": require_non_empty_string(
                pull_request.get("url"),
                f"pull_requests[{index}].pull_request.url",
            ),
            "base_branch": require_non_empty_string(
                pull_request.get("base_ref_name"),
                f"pull_requests[{index}].pull_request.base_ref_name",
            ),
            "head_sha": require_non_empty_string(
                pull_request.get("head_ref_oid"),
                f"pull_requests[{index}].pull_request.head_ref_oid",
            ),
            "pr_state": require_non_empty_string(
                pull_request.get("state"),
                f"pull_requests[{index}].pull_request.state",
            ),
            "is_draft": optional_bool(
                pull_request.get("is_draft"),
                f"pull_requests[{index}].pull_request.is_draft",
            )
            if pull_request.get("is_draft") is not None
            else False,
        }

    ensure_full_batch_coverage(set(parsed), known_prs, "Live PR context artifact")
    return parsed


def parse_live_pr_context_artifact(
    artifact_path: Path, known_prs: set[tuple[str, int]]
) -> dict[tuple[str, int], LivePullRequestMetadata]:
    with artifact_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return parse_live_pr_context_payload(payload, known_prs, str(artifact_path))


def fetch_live_pr_context_from_github(
    pr_urls: list[str],
    known_prs: set[tuple[str, int]],
) -> dict[tuple[str, int], LivePullRequestMetadata]:
    script_path = Path(__file__).with_name("fetch_review_threads.py")
    command = ["uv", "run", "--script", str(script_path)]
    for pr_url in pr_urls:
        command.extend(["--pr-url", pr_url])
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise click.ClickException(
            result.stderr.strip()
            or "Failed to fetch live PR context via `fetch_review_threads.py`."
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise click.ClickException(
            "`fetch_review_threads.py` returned invalid JSON during live validation."
        ) from exc
    return parse_live_pr_context_payload(payload, known_prs, "<live-fetch>")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def atomic_write_json(path: Path, payload: ReviewStateRecord) -> None:
    ensure_dir(path.parent)
    with NamedTemporaryFile(
        "w", delete=False, dir=path.parent, encoding="utf-8"
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def read_json(path: Path) -> ReviewStateRecord:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise click.ClickException(f"{path} does not contain a JSON object.")
    raw_schema_version = data.get("schema_version")
    if raw_schema_version is None:
        raise click.ClickException(
            "State file is missing required `schema_version`. "
            f"Remove or regenerate {path} and rerun the command."
        )
    if not isinstance(raw_schema_version, int) or isinstance(raw_schema_version, bool):
        raise click.ClickException(
            "State file has invalid `schema_version`; expected an integer. "
            f"Update, migrate, or remove {path} and rerun the command."
        )
    if raw_schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        supported_versions = ", ".join(
            str(version) for version in sorted(SUPPORTED_SCHEMA_VERSIONS)
        )
        raise click.ClickException(
            "State file schema version mismatch: "
            f"found {raw_schema_version}, supported versions are {supported_versions}. "
            f"Upgrade/migrate the state file or remove {path} and rerun the command."
        )
    normalized = normalize_state_record(
        data, source_schema_version=raw_schema_version
    )
    parse_prs_from_state(normalized)
    return normalized


def normalize_state_record(
    payload: object, *, source_schema_version: int | None = None
) -> ReviewStateRecord:
    """Normalize older on-disk state into the current in-memory shape.

    First principle:
    the orchestrator's long-term value is reassessment continuity. Old state
    should not be accepted blindly, but it also should not be thrown away when
    the newer schema can still make sense of it. This function validates the
    durable identity fields we rely on now and upgrades older payloads into the
    current schema shape before later code touches them.
    """

    if not isinstance(payload, dict):
        raise click.ClickException("State file does not contain a JSON object.")

    normalized: ReviewStateRecord = {}
    normalized["schema_version"] = SCHEMA_VERSION

    for key in (
        "batch_key",
        "created_at_utc",
        "updated_at_utc",
        "worktree_path",
        "artifact_path",
        "posting_status",
    ):
        raw_value = payload.get(key)
        if raw_value is None:
            continue
        normalized[key] = require_non_empty_string(raw_value, key)
    if "posting_status" in normalized:
        normalized["posting_status"] = require_allowed_value(
            normalized["posting_status"],
            ALLOWED_POSTING_STATUSES,
            "posting_status",
        )

    raw_review_pass_number = payload.get("review_pass_number")
    if raw_review_pass_number is not None:
        normalized["review_pass_number"] = require_non_boolean_int(
            raw_review_pass_number, "review_pass_number"
        )

    prs = normalize_review_batch_identities(payload.get("prs"))
    normalized["prs"] = prs
    known_prs = {(entry["repo"], entry["pr_number"]) for entry in prs}
    linked_batch = normalize_linked_batch_metadata(payload.get("linked_batch"), prs)
    if linked_batch is not None:
        normalized["linked_batch"] = linked_batch

    raw_passes = payload.get("passes")
    if raw_passes is not None:
        if not isinstance(raw_passes, list):
            raise click.ClickException("State file has non-list `passes` field.")
        normalized_passes: list[ReviewPassRecord] = []
        for index, item in enumerate(raw_passes):
            normalized_passes.append(
                normalize_persisted_review_pass(
                    item,
                    index,
                    known_prs,
                    normalized_passes,
                    normalized.get("worktree_path"),
                    allow_legacy_missing_finding_summary=bool(
                        source_schema_version is not None
                        and source_schema_version < SCHEMA_VERSION
                    ),
                    allow_legacy_public_mode_contract_gaps=bool(
                        source_schema_version is not None
                        and source_schema_version < SCHEMA_VERSION
                    ),
                )
            )
        normalized["passes"] = normalized_passes

    pending_live_validation = normalize_live_validation_record(
        payload.get("pending_live_validation"),
        known_prs,
        "pending_live_validation",
    )
    if pending_live_validation is not None:
        normalized["pending_live_validation"] = pending_live_validation

    return normalized


def require_non_boolean_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise click.ClickException(
            f"Review payload field `{field_name}` must be a non-boolean integer."
        )
    return value


def scoped_identity_key(repo: str, pr_number: int, item_id: str) -> str:
    return f"{repo}:{pr_number}:{item_id}"


def resolve_repo_pr_scope(
    repo_value: object,
    pr_number_value: object,
    known_prs: set[tuple[str, int]],
    field_name: str,
) -> tuple[str, int]:
    if repo_value is None and pr_number_value is None and len(known_prs) == 1:
        return next(iter(known_prs))

    repo = require_non_empty_string(repo_value, f"{field_name}.repo")
    pr_number = require_non_boolean_int(pr_number_value, f"{field_name}.pr_number")
    identity = (repo, pr_number)
    if identity not in known_prs:
        raise click.ClickException(
            f"{repo}:{pr_number} is not part of this review batch for `{field_name}`."
        )
    return identity


def normalize_review_batch_identities(value: object) -> list[ReviewBatchIdentity]:
    if not isinstance(value, list):
        raise click.ClickException("State file is missing a valid `prs` list.")

    normalized: list[ReviewBatchIdentity] = []
    seen: set[tuple[str, int]] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise click.ClickException("State file has a non-object PR entry.")
        repo = require_non_empty_string(item.get("repo"), f"prs[{index}].repo")
        pr_number = require_non_boolean_int(
            item.get("pr_number"), f"prs[{index}].pr_number"
        )
        identity = (repo, pr_number)
        if identity in seen:
            raise click.ClickException(
                f"Duplicate PR identity in state file: {repo}:{pr_number}"
            )
        seen.add(identity)
        normalized.append({"repo": repo, "pr_number": pr_number})
    validate_v1_batch_scope(normalized, "State file `prs`")
    return normalized


def validate_v1_batch_scope(
    identities: list[ReviewBatchIdentity], context_label: str
) -> None:
    if not identities:
        raise click.ClickException(f"{context_label} must contain at least one PR.")
    if len(identities) > 2:
        raise click.ClickException(
            f"{context_label} exceeds v1 scope. Only one PR or one linked cross-repo pair is supported."
        )
    unknown_repos = sorted(
        identity["repo"]
        for identity in identities
        if identity["repo"] not in KNOWN_V1_REPOS
    )
    if unknown_repos:
        allowed = ", ".join(sorted(KNOWN_V1_REPOS))
        raise click.ClickException(
            f"{context_label} contains unknown repo(s): {', '.join(unknown_repos)}. "
            f"Known repos: {allowed}."
        )
    if len(identities) == 2 and identities[0]["repo"] == identities[1]["repo"]:
        raise click.ClickException(
            f"{context_label} must be cross-repo when it contains two PRs."
        )


def normalize_live_validation_record(
    value: object,
    known_prs: set[tuple[str, int]],
    field_name: str,
) -> LiveValidationRecord | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise click.ClickException(f"State file field `{field_name}` must be an object.")

    return {
        "token": require_non_empty_string(value.get("token"), f"{field_name}.token"),
        "validated_at_utc": require_non_empty_string(
            value.get("validated_at_utc"), f"{field_name}.validated_at_utc"
        ),
        "validated_against_pass_number": require_non_boolean_int(
            value.get("validated_against_pass_number"),
            f"{field_name}.validated_against_pass_number",
        ),
        "entries": normalize_persisted_review_entries(
            value.get("entries"), known_prs, f"{field_name}.entries"
        ),
        "source_artifact_path": require_non_empty_string(
            value.get("source_artifact_path"), f"{field_name}.source_artifact_path"
        ),
    }


def normalize_linked_batch_metadata(
    value: object, prs: list[ReviewBatchIdentity]
) -> LinkedBatchMetadata | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise click.ClickException("State file field `linked_batch` must be an object.")

    normalized: LinkedBatchMetadata = {}
    link_type = optional_non_empty_string(value.get("link_type"), "linked_batch.link_type")
    if link_type is not None:
        if link_type not in {"single_pr", "explicit_cross_repo_pair"}:
            raise click.ClickException(
                "State file field `linked_batch.link_type` must be one of: "
                "single_pr, explicit_cross_repo_pair."
            )
        normalized["link_type"] = link_type

    raw_is_explicitly_linked = value.get("is_explicitly_linked")
    if raw_is_explicitly_linked is not None:
        if not isinstance(raw_is_explicitly_linked, bool):
            raise click.ClickException(
                "State file field `linked_batch.is_explicitly_linked` must be a boolean."
            )
        normalized["is_explicitly_linked"] = raw_is_explicitly_linked

    linked_pair_reason = optional_non_empty_string(
        value.get("linked_pair_reason"), "linked_batch.linked_pair_reason"
    )
    if linked_pair_reason is not None:
        normalized["linked_pair_reason"] = linked_pair_reason

    dependency_summary = optional_non_empty_string(
        value.get("cross_repo_dependency_summary"),
        "linked_batch.cross_repo_dependency_summary",
    )
    if dependency_summary is not None:
        normalized["cross_repo_dependency_summary"] = dependency_summary

    raw_authoritative_pr = value.get("authoritative_pr")
    if raw_authoritative_pr is not None:
        if not isinstance(raw_authoritative_pr, dict):
            raise click.ClickException(
                "State file field `linked_batch.authoritative_pr` must be an object."
            )
        known_prs = {(entry["repo"], entry["pr_number"]) for entry in prs}
        repo, pr_number = resolve_repo_pr_scope(
            raw_authoritative_pr.get("repo"),
            raw_authoritative_pr.get("pr_number"),
            known_prs,
            "linked_batch.authoritative_pr",
        )
        normalized["authoritative_pr"] = {"repo": repo, "pr_number": pr_number}

    if len(prs) == 2:
        if normalized.get("link_type") != "explicit_cross_repo_pair":
            raise click.ClickException(
                "State file field `linked_batch.link_type` must be "
                "`explicit_cross_repo_pair` for linked review batches."
            )
        if not normalized.get("is_explicitly_linked"):
            raise click.ClickException(
                "State file field `linked_batch.is_explicitly_linked` must be true "
                "for linked review batches."
            )
        if "linked_pair_reason" not in normalized:
            raise click.ClickException(
                "State file field `linked_batch.linked_pair_reason` is required "
                "for linked review batches."
            )
        if "authoritative_pr" not in normalized:
            raise click.ClickException(
                "State file field `linked_batch.authoritative_pr` is required "
                "for linked review batches."
            )
    elif normalized:
        if normalized.get("link_type") not in {None, "single_pr"}:
            raise click.ClickException(
                "Single-PR state cannot carry linked-pair metadata."
            )
        disallowed_single_pr_fields = {
            key
            for key in (
                "linked_pair_reason",
                "cross_repo_dependency_summary",
                "authoritative_pr",
            )
            if key in normalized
        }
        if normalized.get("is_explicitly_linked") or disallowed_single_pr_fields:
            raise click.ClickException(
                "Single-PR state cannot carry linked-pair metadata."
            )

    return normalized or None


def next_review_pass_number(payload: ReviewStateRecord, path: Path) -> int:
    """Return the next batch-scoped review pass number.

    This validates the persisted field before incrementing it so corrupted or
    hand-edited state fails with a clear message instead of a raw traceback.
    """

    raw_review_pass_number = payload.get("review_pass_number", 0)
    if not isinstance(raw_review_pass_number, int) or isinstance(
        raw_review_pass_number, bool
    ):
        raise click.ClickException(
            "Existing state has invalid `review_pass_number`; expected an integer. "
            f"Update or remove the field in {path} and rerun the command."
        )
    return raw_review_pass_number + 1


def parse_prs_from_state(payload: ReviewStateRecord) -> set[tuple[str, int]]:
    """Extract the batch PR identities from persisted state.

    We validate the shape here so later commands fail with a clear message
    instead of silently recording a pass onto the wrong batch.
    """

    raw_prs = payload.get("prs")
    if not isinstance(raw_prs, list):
        raise click.ClickException("State file is missing a valid `prs` list.")

    parsed: set[tuple[str, int]] = set()
    for item in raw_prs:
        if not isinstance(item, dict):
            raise click.ClickException("State file has a non-object PR entry.")
        repo = item.get("repo")
        pr_number = item.get("pr_number")
        if not isinstance(repo, str) or not (
            isinstance(pr_number, int) and not isinstance(pr_number, bool)
        ):
            raise click.ClickException("State file has an invalid PR identity entry.")
        parsed.add((repo, pr_number))
    return parsed


def format_pr_identities(identities: set[tuple[str, int]]) -> str:
    return ", ".join(f"{repo}:{pr_number}" for repo, pr_number in sorted(identities))


def ensure_full_batch_coverage(
    seen_targets: set[tuple[str, int]],
    known_prs: set[tuple[str, int]],
    context_label: str,
) -> None:
    missing_prs = known_prs - seen_targets
    if not missing_prs:
        return
    raise click.ClickException(
        f"{context_label} is missing batch PRs: {format_pr_identities(missing_prs)}. "
        "Record one batch-scoped pass that includes every PR in the batch."
    )


def require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise click.ClickException(
            f"Review payload is missing non-empty string `{field_name}`."
        )
    return value.strip()


def optional_non_empty_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise click.ClickException(
            f"Review payload field `{field_name}` must be a non-empty string when set."
        )
    return value.strip()


def optional_bool(value: object, field_name: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise click.ClickException(
            f"Review payload field `{field_name}` must be a boolean when set."
        )
    return value


def require_allowed_value(value: str, allowed: set[str], field_name: str) -> str:
    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise click.ClickException(
            f"Review payload field `{field_name}` must be one of: {allowed_values}."
        )
    return value

def require_review_comment_side(value: object, field_name: str) -> ReviewCommentSide:
    """Validate one GitHub review-comment side field.

    We keep this as a tiny helper instead of repeating string checks inline so
    later readers can see that `RIGHT` / `LEFT` is an intentional contract,
    not an arbitrary string convention.
    """

    side = require_non_empty_string(value, field_name)
    if side == "RIGHT":
        return "RIGHT"
    if side == "LEFT":
        return "LEFT"
    raise click.ClickException(
        f"Review payload field `{field_name}` must be `RIGHT` or `LEFT`."
    )


def normalize_string_list(value: object, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise click.ClickException(
            f"Review payload field `{field_name}` must be a list."
        )

    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise click.ClickException(
                f"Review payload field `{field_name}[{index}]` must be a non-empty string."
            )
        normalized.append(item.strip())
    return normalized


def normalize_int_list(value: object, field_name: str) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise click.ClickException(
            f"Review payload field `{field_name}` must be a list."
        )

    normalized: list[int] = []
    for index, item in enumerate(value):
        normalized.append(require_non_boolean_int(item, f"{field_name}[{index}]"))
    return normalized


def parse_review_target(raw: str) -> ReviewPassEntry:
    """Parse one batch-scoped review target entry.

    Shape:
        repo:pr_number:base_branch:head_sha:merge_base
    """

    parts = raw.split(":", 4)
    if len(parts) != 5:
        raise click.ClickException(
            f"Invalid --review-target value `{raw}`. "
            "Use repo:pr_number:base_branch:head_sha:merge_base."
        )
    repo, pr_number_text, base_branch, head_sha, merge_base = parts
    try:
        pr_number = int(pr_number_text)
    except ValueError as exc:
        raise click.ClickException(
            f"Invalid --review-target value `{raw}`. PR number must be an integer."
        ) from exc
    if isinstance(pr_number, bool):
        raise click.ClickException(
            f"Invalid --review-target value `{raw}`. PR number must be a non-boolean integer."
        )
    return {
        "repo": repo,
        "pr_number": pr_number,
        "base_branch": base_branch,
        "head_sha": head_sha,
        "merge_base": merge_base,
    }


def parse_review_entry_payload(item: object, field_name: str) -> ReviewPassEntry:
    if not isinstance(item, dict):
        raise click.ClickException(
            f"Review payload field `{field_name}` must contain JSON objects."
        )

    repo = require_non_empty_string(item.get("repo"), f"{field_name}.repo")
    raw_pr_number = item.get("pr_number")
    if not isinstance(raw_pr_number, int) or isinstance(raw_pr_number, bool):
        raise click.ClickException(
            f"Review payload field `{field_name}.pr_number` must be a non-boolean integer."
        )

    normalized: ReviewPassEntry = {
        "repo": repo,
        "pr_number": raw_pr_number,
        "base_branch": require_non_empty_string(
            item.get("base_branch"), f"{field_name}.base_branch"
        ),
        "head_sha": require_non_empty_string(
            item.get("head_sha"), f"{field_name}.head_sha"
        ),
        "merge_base": require_non_empty_string(
            item.get("merge_base"), f"{field_name}.merge_base"
        ),
    }
    pr_state = optional_non_empty_string(item.get("pr_state"), f"{field_name}.pr_state")
    if pr_state is not None:
        normalized["pr_state"] = pr_state
    is_draft = optional_bool(item.get("is_draft"), f"{field_name}.is_draft")
    if is_draft is not None:
        normalized["is_draft"] = is_draft
    return normalized


def normalize_review_entries(
    value: object, known_prs: set[tuple[str, int]]
) -> list[ReviewPassEntry]:
    if not isinstance(value, list) or not value:
        raise click.ClickException(
            "Review payload field `entries` must be a non-empty list."
        )

    entries: list[ReviewPassEntry] = []
    seen_targets: set[tuple[str, int]] = set()
    for index, item in enumerate(value):
        entry = parse_review_entry_payload(item, f"entries[{index}]")
        identity = (entry["repo"], entry["pr_number"])
        if identity not in known_prs:
            raise click.ClickException(
                f"{entry['repo']}:{entry['pr_number']} is not part of this review batch."
            )
        if identity in seen_targets:
            raise click.ClickException(
                f"Duplicate review entry in payload: {entry['repo']}:{entry['pr_number']}"
            )
        seen_targets.add(identity)
        entries.append(entry)
    ensure_full_batch_coverage(seen_targets, known_prs, "Review payload `entries`")
    return entries


def normalize_author_claims(
    value: object, known_prs: set[tuple[str, int]]
) -> list[AuthorClaimCheck]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise click.ClickException(
            "Review payload field `author_claims_checked` must be a list."
        )

    normalized: list[AuthorClaimCheck] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise click.ClickException(
                f"Review payload field `author_claims_checked[{index}]` must be an object."
            )
        repo, pr_number = resolve_repo_pr_scope(
            item.get("repo"),
            item.get("pr_number"),
            known_prs,
            f"author_claims_checked[{index}]",
        )
        claim = require_non_empty_string(
            item.get("claim"), f"author_claims_checked[{index}].claim"
        )
        status = require_non_empty_string(
            item.get("status"), f"author_claims_checked[{index}].status"
        )
        entry: AuthorClaimCheck = {
            "repo": repo,
            "pr_number": pr_number,
            "claim": claim,
            "status": status,
        }
        evidence = optional_non_empty_string(
            item.get("evidence"), f"author_claims_checked[{index}].evidence"
        )
        if evidence is not None:
            entry["evidence"] = evidence
        normalized.append(entry)
    return normalized


def normalize_review_threads(
    value: object,
    known_prs: set[tuple[str, int]],
    field_name: str,
    allowed_linked_finding_ids: set[str] | None = None,
) -> list[ReviewThreadContext]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise click.ClickException(
            f"Review payload field `{field_name}` must be a list."
        )

    normalized: list[ReviewThreadContext] = []
    seen_threads: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise click.ClickException(
                f"Review payload field `{field_name}[{index}]` must be an object."
            )
        repo, pr_number = resolve_repo_pr_scope(
            item.get("repo"),
            item.get("pr_number"),
            known_prs,
            f"{field_name}[{index}]",
        )
        thread_id = require_non_empty_string(
            item.get("thread_id"), f"{field_name}[{index}].thread_id"
        )
        thread_key = scoped_identity_key(repo, pr_number, thread_id)
        if thread_key in seen_threads:
            raise click.ClickException(
                f"Duplicate review thread in payload: `{thread_key}`."
            )
        seen_threads.add(thread_key)

        status = require_non_empty_string(
            item.get("status"), f"{field_name}[{index}].status"
        )
        if status not in {"open", "resolved", "moot"}:
            raise click.ClickException(
                f"Review payload field `{field_name}[{index}].status` must be one of: open, resolved, moot."
            )

        thread: ReviewThreadContext = {
            "repo": repo,
            "pr_number": pr_number,
            "thread_id": thread_id,
            "status": status,
            "last_seen_head_sha": require_non_empty_string(
                item.get("last_seen_head_sha"),
                f"{field_name}[{index}].last_seen_head_sha",
            ),
        }
        thread["comment_ids"] = normalize_int_list(
            item.get("comment_ids"), f"{field_name}[{index}].comment_ids"
        )

        path = optional_non_empty_string(
            item.get("path"), f"{field_name}[{index}].path"
        )
        if path is not None:
            thread["path"] = path

        raw_line = item.get("line")
        if raw_line is not None:
            line = require_non_boolean_int(raw_line, f"{field_name}[{index}].line")
            if line < 1:
                raise click.ClickException(
                    f"Review payload field `{field_name}[{index}].line` must be a positive integer."
                )
            thread["line"] = line

        raw_is_resolved = item.get("is_resolved")
        if raw_is_resolved is not None:
            if not isinstance(raw_is_resolved, bool):
                raise click.ClickException(
                    f"Review payload field `{field_name}[{index}].is_resolved` must be a boolean."
                )
            if raw_is_resolved and status == "open":
                raise click.ClickException(
                    f"Review payload field `{field_name}[{index}]` cannot mark a thread "
                    "as both `status=open` and `is_resolved=true`."
                )
            if not raw_is_resolved and status == "resolved":
                raise click.ClickException(
                    f"Review payload field `{field_name}[{index}]` cannot mark a thread "
                    "as both `status=resolved` and `is_resolved=false`."
                )
            thread["is_resolved"] = raw_is_resolved

        raw_is_outdated = item.get("is_outdated")
        if raw_is_outdated is not None:
            if not isinstance(raw_is_outdated, bool):
                raise click.ClickException(
                    f"Review payload field `{field_name}[{index}].is_outdated` must be a boolean."
                )
            thread["is_outdated"] = raw_is_outdated

        linked_finding_id = optional_non_empty_string(
            item.get("linked_finding_id"), f"{field_name}[{index}].linked_finding_id"
        )
        if linked_finding_id is not None:
            linked_finding_scope_key = scoped_identity_key(
                repo, pr_number, linked_finding_id
            )
            if (
                allowed_linked_finding_ids is not None
                and linked_finding_scope_key not in allowed_linked_finding_ids
            ):
                raise click.ClickException(
                    f"Review payload field `{field_name}[{index}].linked_finding_id` "
                    f"references unknown finding `{linked_finding_scope_key}`."
                )
            thread["linked_finding_id"] = linked_finding_id

        summary = optional_non_empty_string(
            item.get("summary"), f"{field_name}[{index}].summary"
        )
        if summary is not None:
            thread["summary"] = summary

        normalized.append(thread)
    return normalized


def normalize_comment_context(
    value: object,
    known_prs: set[tuple[str, int]],
    allowed_linked_finding_ids: set[str] | None = None,
) -> CommentContext | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise click.ClickException(
            "Review payload field `comment_context` must be an object."
        )

    normalized: CommentContext = {}
    thread_source = optional_non_empty_string(
        value.get("thread_source"), "comment_context.thread_source"
    )
    if thread_source is not None:
        normalized["thread_source"] = thread_source

    summary = optional_non_empty_string(value.get("summary"), "comment_context.summary")
    if summary is not None:
        normalized["summary"] = summary

    threads = normalize_review_threads(
        value.get("threads"),
        known_prs,
        "comment_context.threads",
        allowed_linked_finding_ids,
    )
    if threads:
        normalized["threads"] = threads

    for key in CONTEXT_LIST_FIELDS:
        entries = normalize_string_list(value.get(key), f"comment_context.{key}")
        if entries:
            normalized[key] = entries

    legacy_moot_entries = normalize_string_list(
        value.get("moot_or_resolved"), "comment_context.moot_or_resolved"
    )
    if legacy_moot_entries:
        normalized["moot_or_no_longer_applicable"] = merge_unique_strings(
            normalized.get("moot_or_no_longer_applicable", []),
            legacy_moot_entries,
        )

    return normalized or None


def synthesize_legacy_finding_summary(finding: ReviewFinding) -> str:
    location_parts = [
        part
        for part in (finding.get("path"), finding.get("symbol"))
        if isinstance(part, str) and part
    ]
    if location_parts:
        return f"Legacy finding `{finding['id']}` ({', '.join(location_parts)})"
    severity = finding.get("severity")
    if isinstance(severity, str) and severity:
        return f"Legacy {severity} finding `{finding['id']}`"
    return f"Legacy finding `{finding['id']}`"


def normalize_findings(
    value: object,
    known_prs: set[tuple[str, int]],
    *,
    allow_legacy_missing_summary: bool = False,
) -> ReviewFindings:
    if value is None:
        return {bucket: [] for bucket in FINDING_BUCKETS}
    if not isinstance(value, dict):
        raise click.ClickException("Review payload field `findings` must be an object.")

    normalized: ReviewFindings = {bucket: [] for bucket in FINDING_BUCKETS}
    seen_ids: set[str] = set()
    for bucket in FINDING_BUCKETS:
        raw_bucket = value.get(bucket, [])
        if raw_bucket is None:
            raw_bucket = []
        if not isinstance(raw_bucket, list):
            raise click.ClickException(
                f"Review payload field `findings.{bucket}` must be a list."
            )

        bucket_entries: list[ReviewFinding] = []
        for index, item in enumerate(raw_bucket):
            if not isinstance(item, dict):
                raise click.ClickException(
                    f"Review payload field `findings.{bucket}[{index}]` must be an object."
                )
            finding_id = require_non_empty_string(
                item.get("id"), f"findings.{bucket}[{index}].id"
            )
            repo, pr_number = resolve_repo_pr_scope(
                item.get("repo"),
                item.get("pr_number"),
                known_prs,
                f"findings.{bucket}[{index}]",
            )
            finding_scope_key = scoped_identity_key(repo, pr_number, finding_id)
            if finding_scope_key in seen_ids:
                raise click.ClickException(
                    f"Duplicate finding id in review payload: `{finding_scope_key}`."
                )
            seen_ids.add(finding_scope_key)

            finding: ReviewFinding = {
                "repo": repo,
                "pr_number": pr_number,
                "id": finding_id,
            }
            for key in (
                "severity",
                "path",
                "symbol",
                "risk",
                "suggested_fix",
            ):
                normalized_value = optional_non_empty_string(
                    item.get(key), f"findings.{bucket}[{index}].{key}"
                )
                if normalized_value is not None:
                    finding[key] = normalized_value
            summary = optional_non_empty_string(
                item.get("summary"), f"findings.{bucket}[{index}].summary"
            )
            if summary is None:
                if allow_legacy_missing_summary:
                    summary = synthesize_legacy_finding_summary(finding)
                else:
                    raise click.ClickException(
                        "Review payload is missing non-empty string "
                        f"`findings.{bucket}[{index}].summary`."
                    )
            finding["summary"] = summary
            bucket_entries.append(finding)
        normalized[bucket] = bucket_entries
    return normalized


def normalize_inline_comment_targets(
    value: object,
    known_prs: set[tuple[str, int]],
    allowed_finding_ids: set[str],
) -> list[InlineCommentTarget]:
    """Normalize persisted inline-comment plans for the current worker contract.

    First principle:
    inline comments are riskier than top-level review prose.

    A top-level review can still be useful after lines move. An inline comment
    becomes misleading if its diff anchor drifts. That is why this helper keeps
    the anchor shape explicit and validates it early when review state is
    written or re-read.

    Visual model:

        persisted state
          -> finding_id
          -> path
          -> optional anchor fields

        normalization
          -> reject unknown findings
          -> reject malformed anchors
          -> preserve only fields later passes can trust

    Backwards compatibility note:
    older state may still carry a human-facing `summary`. We preserve it when
    present, but new automation should rely on explicit anchor fields instead.
    """

    if value is None:
        return []
    if not isinstance(value, list):
        raise click.ClickException(
            "Review payload field `inline_comment_targets` must be a list."
        )

    normalized: list[InlineCommentTarget] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise click.ClickException(
                f"Review payload field `inline_comment_targets[{index}]` must be an object."
            )
        repo, pr_number = resolve_repo_pr_scope(
            item.get("repo"),
            item.get("pr_number"),
            known_prs,
            f"inline_comment_targets[{index}]",
        )
        target: InlineCommentTarget = {
            "repo": repo,
            "pr_number": pr_number,
            "path": require_non_empty_string(
                item.get("path"), f"inline_comment_targets[{index}].path"
            ),
        }
        # `summary` is optional legacy/human context. The current worker-owned
        # inline contract is the explicit anchor payload below.
        summary = optional_non_empty_string(
            item.get("summary"), f"inline_comment_targets[{index}].summary"
        )
        if summary is not None:
            target["summary"] = summary
        finding_id = require_non_empty_string(
            item.get("finding_id"), f"inline_comment_targets[{index}].finding_id"
        )
        target_scope_key = scoped_identity_key(
            target["repo"], target["pr_number"], finding_id
        )
        if target_scope_key not in allowed_finding_ids:
            raise click.ClickException(
                "Review payload field "
                f"`inline_comment_targets[{index}].finding_id` references "
                f"unknown active finding `{target_scope_key}`."
            )
        target["finding_id"] = finding_id
        raw_line = item.get("line")
        if raw_line is not None:
            if (
                not isinstance(raw_line, int)
                or isinstance(raw_line, bool)
                or raw_line < 1
            ):
                raise click.ClickException(
                    f"Review payload field `inline_comment_targets[{index}].line` must be a positive integer."
                )
            target["line"] = raw_line
        raw_side = item.get("side")
        if raw_side is not None:
            side = require_review_comment_side(
                raw_side, f"inline_comment_targets[{index}].side"
            )
            if raw_line is None:
                raise click.ClickException(
                    f"Review payload field `inline_comment_targets[{index}].side` requires `line`."
                )
            target["side"] = side
        if raw_line is not None and raw_side is None:
            raise click.ClickException(
                "Review payload field "
                f"`inline_comment_targets[{index}].line` requires `side`."
            )
        # Multiline anchors are supported, but only when both start fields are
        # present together so later readers do not have to guess the intended
        # range shape.
        raw_start_line = item.get("start_line")
        if raw_start_line is not None:
            if (
                not isinstance(raw_start_line, int)
                or isinstance(raw_start_line, bool)
                or raw_start_line < 1
            ):
                raise click.ClickException(
                    f"Review payload field `inline_comment_targets[{index}].start_line` must be a positive integer."
                )
            target["start_line"] = raw_start_line
        raw_start_side = item.get("start_side")
        if raw_start_side is not None:
            target["start_side"] = require_review_comment_side(
                raw_start_side, f"inline_comment_targets[{index}].start_side"
            )
        if (raw_start_line is None) != (raw_start_side is None):
            raise click.ClickException(
                "Review payload field "
                f"`inline_comment_targets[{index}]` must provide `start_line` "
                "and `start_side` together."
            )
        expected_line_text = optional_non_empty_string(
            item.get("expected_line_text"),
            f"inline_comment_targets[{index}].expected_line_text",
        )
        if expected_line_text is not None:
            target["expected_line_text"] = expected_line_text
        # Advanced anchor fields only make sense when the main anchor exists.
        # That keeps the persisted shape first-principles-driven instead of
        # allowing half-specified plans like "maybe this line, maybe that one".
        if (
            raw_start_line is not None or expected_line_text is not None
        ) and (raw_line is None or raw_side is None):
            raise click.ClickException(
                "Review payload field "
                f"`inline_comment_targets[{index}]` must provide both `line` "
                "and `side` when using advanced anchor fields."
            )
        normalized.append(target)
    return normalized


def normalize_backend_handoff(
    value: object,
    known_prs: set[tuple[str, int]],
    allowed_open_finding_ids: set[str],
    entry_map: dict[tuple[str, int], ReviewPassEntry],
    recommendation: str,
    state_worktree_path: str | None,
) -> BackendHandoff | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise click.ClickException("Review payload field `backend_handoff` must be an object.")

    repo, pr_number = resolve_repo_pr_scope(
        value.get("repo"),
        value.get("pr_number"),
        known_prs,
        "backend_handoff",
    )
    if repo != "Django4Lyfe":
        raise click.ClickException(
            "Review payload field `backend_handoff` is only valid for "
            "`Django4Lyfe` review entries."
        )

    handoff: BackendHandoff = {
        "repo": repo,
        "pr_number": pr_number,
        "worktree_path": str(
            Path(
                require_non_empty_string(
                    value.get("worktree_path"), "backend_handoff.worktree_path"
                )
            ).expanduser().resolve()
        ),
        "pr_url": require_non_empty_string(value.get("pr_url"), "backend_handoff.pr_url"),
        "head_sha": require_non_empty_string(
            value.get("head_sha"), "backend_handoff.head_sha"
        ),
        "thread_context_summary": require_non_empty_string(
            value.get("thread_context_summary"),
            "backend_handoff.thread_context_summary",
        ),
    }
    validate_backend_handoff_pr_url(handoff["pr_url"], repo, pr_number)

    backend_entry = entry_map[(repo, pr_number)]
    if handoff["head_sha"] != backend_entry["head_sha"]:
        raise click.ClickException(
            "Review payload field `backend_handoff.head_sha` must match the "
            "backend batch entry head SHA."
        )
    if state_worktree_path is not None and handoff["worktree_path"] != str(
        Path(state_worktree_path).expanduser().resolve()
    ):
        raise click.ClickException(
            "Review payload field `backend_handoff.worktree_path` must match the "
            "recorded review state worktree path."
        )

    allowed_posting_action = optional_non_empty_string(
        value.get("allowed_posting_action"), "backend_handoff.allowed_posting_action"
    )
    if allowed_posting_action is not None:
        handoff["allowed_posting_action"] = require_allowed_value(
            allowed_posting_action,
            ALLOWED_RECOMMENDATIONS,
            "backend_handoff.allowed_posting_action",
        )
        if handoff["allowed_posting_action"] != recommendation:
            raise click.ClickException(
                "Review payload field `backend_handoff.allowed_posting_action` must "
                "match the current review recommendation."
            )

    prior_open_finding_ids = normalize_string_list(
        value.get("prior_open_finding_ids"), "backend_handoff.prior_open_finding_ids"
    )
    scoped_prior_open_finding_ids: list[str] = []
    for finding_id in prior_open_finding_ids:
        scoped_id = scoped_identity_key(repo, pr_number, finding_id)
        if scoped_id not in allowed_open_finding_ids:
            raise click.ClickException(
                "Review payload field `backend_handoff.prior_open_finding_ids` "
                f"references unknown active finding `{scoped_id}`."
            )
        scoped_prior_open_finding_ids.append(finding_id)
    handoff["prior_open_finding_ids"] = scoped_prior_open_finding_ids
    return handoff


def total_finding_count(findings: ReviewFindings, buckets: tuple[str, ...] = FINDING_BUCKETS) -> int:
    return sum(len(findings.get(bucket, [])) for bucket in buckets)


def has_comment_context_evidence(comment_context: CommentContext | None) -> bool:
    if comment_context is None:
        return False
    if comment_context.get("summary"):
        return True
    if comment_context.get("threads"):
        return True
    return any(comment_context.get(key) for key in CONTEXT_LIST_FIELDS)


def has_status_assessment(comment_context: CommentContext | None) -> bool:
    if comment_context is None:
        return False
    assessment_keys = (
        "still_legit",
        "moot_or_no_longer_applicable",
        "resolved_for_context",
        "follow_up",
    )
    return any(comment_context.get(key) for key in assessment_keys)


def batch_has_backend(known_prs: set[tuple[str, int]]) -> bool:
    return any(repo == "Django4Lyfe" for repo, _ in known_prs)


def normalize_persisted_review_entries(
    value: object,
    known_prs: set[tuple[str, int]],
    field_name: str,
) -> list[ReviewPassEntry]:
    """Normalize already-persisted pass entries.

    Some historical worker-owned state stores a batch-level `prs` list but has
    older pass rows whose `entries` only name the PR reviewed in that pass. For
    reads, keep the useful context when every listed entry is valid. The write
    paths (`record-pass` and `record-review`) still enforce complete
    batch-scoped entries for every new pass.
    """

    if not isinstance(value, list) or not value:
        raise click.ClickException(
            f"State file field `{field_name}` must be a non-empty list."
        )

    normalized: list[ReviewPassEntry] = []
    seen_targets: set[tuple[str, int]] = set()
    for index, item in enumerate(value):
        entry = parse_review_entry_payload(item, f"{field_name}[{index}]")
        identity = (entry["repo"], entry["pr_number"])
        if identity not in known_prs:
            raise click.ClickException(
                f"{entry['repo']}:{entry['pr_number']} is not part of this review batch."
            )
        if identity in seen_targets:
            raise click.ClickException(
                f"Duplicate persisted review entry: {entry['repo']}:{entry['pr_number']}"
            )
        seen_targets.add(identity)
        normalized.append(entry)
    return normalized


def normalize_persisted_review_pass(
    value: object,
    index: int,
    known_prs: set[tuple[str, int]],
    existing_passes: list[ReviewPassRecord],
    state_worktree_path: str | None,
    *,
    allow_legacy_missing_finding_summary: bool = False,
    allow_legacy_public_mode_contract_gaps: bool = False,
) -> ReviewPassRecord:
    if not isinstance(value, dict):
        raise click.ClickException(
            f"State file field `passes[{index}]` must be an object."
        )

    artifact_path = require_non_empty_string(
        value.get("artifact_path"), f"passes[{index}].artifact_path"
    )
    posting_status = require_non_empty_string(
        value.get("posting_status"), f"passes[{index}].posting_status"
    )
    posting_status = require_allowed_value(
        posting_status, ALLOWED_POSTING_STATUSES, f"passes[{index}].posting_status"
    )
    recorded_at_utc = require_non_empty_string(
        value.get("recorded_at_utc"), f"passes[{index}].recorded_at_utc"
    )
    review_pass_number = require_non_boolean_int(
        value.get("review_pass_number"), f"passes[{index}].review_pass_number"
    )
    entries = normalize_persisted_review_entries(
        value.get("entries"), known_prs, f"passes[{index}].entries"
    )
    entry_map = entry_identity_map(entries)

    normalized: ReviewPassRecord = {
        "artifact_path": artifact_path,
        "posting_status": posting_status,
        "recorded_at_utc": recorded_at_utc,
        "review_pass_number": review_pass_number,
        "entries": entries,
    }

    mode = optional_non_empty_string(value.get("mode"), f"passes[{index}].mode")
    if mode is None:
        normalized["mode"] = COMPATIBILITY_MODE
    else:
        normalized["mode"] = require_allowed_value(
            mode, ALLOWED_PERSISTED_MODES, f"passes[{index}].mode"
        )

    recommendation = optional_non_empty_string(
        value.get("recommendation"), f"passes[{index}].recommendation"
    )
    if recommendation is not None:
        normalized["recommendation"] = require_allowed_value(
            recommendation,
            ALLOWED_RECOMMENDATIONS,
            f"passes[{index}].recommendation",
        )

    scope_summary = optional_non_empty_string(
        value.get("scope_summary"), f"passes[{index}].scope_summary"
    )
    if scope_summary is not None:
        normalized["scope_summary"] = scope_summary

    business_logic_summary = optional_non_empty_string(
        value.get("business_logic_summary"), f"passes[{index}].business_logic_summary"
    )
    if business_logic_summary is not None:
        normalized["business_logic_summary"] = business_logic_summary

    cross_repo_summary = optional_non_empty_string(
        value.get("cross_repo_summary"), f"passes[{index}].cross_repo_summary"
    )
    if cross_repo_summary is not None:
        normalized["cross_repo_summary"] = cross_repo_summary

    findings = normalize_findings(
        value.get("findings"),
        known_prs,
        allow_legacy_missing_summary=allow_legacy_missing_finding_summary,
    )
    normalized["findings"] = findings

    all_finding_ids = {
        scoped_identity_key(finding["repo"], finding["pr_number"], finding["id"])
        for bucket in FINDING_BUCKETS
        for finding in findings.get(bucket, [])
        if "id" in finding and "repo" in finding and "pr_number" in finding
    }
    open_finding_ids = {
        scoped_identity_key(finding["repo"], finding["pr_number"], finding["id"])
        for bucket in ("new", "carried_forward")
        for finding in findings.get(bucket, [])
        if "id" in finding and "repo" in finding and "pr_number" in finding
    }

    no_author_claims = optional_bool(
        value.get("no_author_claims"), f"passes[{index}].no_author_claims"
    )
    if no_author_claims is not None:
        normalized["no_author_claims"] = no_author_claims

    no_findings_after_full_review = optional_bool(
        value.get("no_findings_after_full_review"),
        f"passes[{index}].no_findings_after_full_review",
    )
    if no_findings_after_full_review is not None:
        normalized["no_findings_after_full_review"] = no_findings_after_full_review

    author_claims_checked = normalize_author_claims(
        value.get("author_claims_checked"), known_prs
    )
    if author_claims_checked:
        normalized["author_claims_checked"] = author_claims_checked

    backend_handoff = normalize_backend_handoff(
        value.get("backend_handoff"),
        known_prs,
        open_finding_ids,
        entry_map,
        normalized.get("recommendation", ""),
        state_worktree_path,
    )
    if backend_handoff is not None:
        normalized["backend_handoff"] = backend_handoff

    comment_context = normalize_comment_context(
        value.get("comment_context"), known_prs, all_finding_ids
    )
    if comment_context is not None:
        normalized["comment_context"] = comment_context

    teaching_points = normalize_string_list(
        value.get("teaching_points"), f"passes[{index}].teaching_points"
    )
    if teaching_points:
        normalized["teaching_points"] = teaching_points

    inline_comment_targets = normalize_inline_comment_targets(
        value.get("inline_comment_targets"), known_prs, open_finding_ids
    )
    if inline_comment_targets:
        normalized["inline_comment_targets"] = inline_comment_targets

    persisted_mode = normalized.get("mode")
    legacy_read_compat = bool(
        allow_legacy_public_mode_contract_gaps
        and persisted_mode in {"status", "review", "reassess"}
    )
    if legacy_read_compat and persisted_mode in {"review", "reassess"}:
        if (
            "no_findings_after_full_review" not in normalized
            and total_finding_count(findings) == 0
        ):
            normalized["no_findings_after_full_review"] = True
        if "no_author_claims" not in normalized and not author_claims_checked:
            normalized["no_author_claims"] = True
    if persisted_mode in PUBLIC_MODES:
        validate_review_requirements(
            mode=persisted_mode,
            posting_status=normalized["posting_status"],
            recommendation=normalized.get("recommendation", ""),
            artifact_path=Path(artifact_path),
            entries=entries,
            findings=findings,
            no_findings_after_full_review=bool(
                normalized.get("no_findings_after_full_review", False)
            ),
            author_claims_checked=author_claims_checked,
            no_author_claims=bool(normalized.get("no_author_claims", False)),
            comment_context=comment_context,
            backend_handoff=backend_handoff,
            known_prs=known_prs,
            existing_passes=existing_passes,
            enforce_artifact_existence=False,
            require_post_validation_proof=False,
            require_pr_lifecycle=False,
            require_comment_context_evidence=not legacy_read_compat,
            require_status_assessment=not legacy_read_compat,
        )

    return normalized


def load_review_payload_from_stdin() -> ReviewPayloadInput:
    raw_input = sys.stdin.read()
    if not raw_input.strip():
        raise click.ClickException(
            "Expected review JSON on stdin, but stdin was empty."
        )
    try:
        payload = json.loads(raw_input)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"stdin does not contain valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise click.ClickException("stdin JSON must be an object.")
    return payload


def finding_scope_key_from_record(finding: ReviewFinding) -> str | None:
    repo = finding.get("repo")
    pr_number = finding.get("pr_number")
    finding_id = finding.get("id")
    if (
        not isinstance(repo, str)
        or not isinstance(pr_number, int)
        or isinstance(pr_number, bool)
    ):
        return None
    if not isinstance(finding_id, str) or not finding_id.strip():
        return None
    return scoped_identity_key(repo, pr_number, finding_id)


def thread_scope_key_from_record(thread: ReviewThreadContext) -> str | None:
    repo = thread.get("repo")
    pr_number = thread.get("pr_number")
    thread_id = thread.get("thread_id")
    if (
        not isinstance(repo, str)
        or not isinstance(pr_number, int)
        or isinstance(pr_number, bool)
    ):
        return None
    if not isinstance(thread_id, str) or not thread_id.strip():
        return None
    return scoped_identity_key(repo, pr_number, thread_id)


def merge_unique_strings(existing: list[str], new_items: list[str]) -> list[str]:
    merged = list(existing)
    seen = set(existing)
    for item in new_items:
        if item in seen:
            continue
        merged.append(item)
        seen.add(item)
    return merged


def merge_author_claim_history(
    passes: list[ReviewPassRecord],
    max_items: int | None = None,
) -> list[AuthorClaimCheck]:
    merged: dict[str, AuthorClaimCheck] = {}
    order: list[str] = []
    for pass_record in passes:
        claims = pass_record.get("author_claims_checked", [])
        if not isinstance(claims, list):
            continue
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            claim_text = claim.get("claim")
            repo = claim.get("repo")
            pr_number = claim.get("pr_number")
            if not isinstance(claim_text, str) or not claim_text.strip():
                continue
            if (
                not isinstance(repo, str)
                or not isinstance(pr_number, int)
                or isinstance(pr_number, bool)
            ):
                continue
            claim_key = scoped_identity_key(repo, pr_number, claim_text)
            if claim_key not in merged:
                order.append(claim_key)
            merged[claim_key] = claim
    if max_items is None:
        return [merged[key] for key in order]
    return [merged[key] for key in order[-max_items:]]


def merge_comment_context_history(
    passes: list[ReviewPassRecord],
    max_threads: int | None = None,
    max_items_per_bucket: int | None = None,
) -> CommentContext | None:
    """Merge durable discussion context across recent passes.

    We intentionally merge here instead of taking only the latest pass because
    reviewers often learn something important in an earlier pass that the author
    did not restate later. At the same time, `summarize-context` must stay
    compact, so the caller can cap thread and prose history to the most recent
    useful slice.
    """

    merged: CommentContext = {}
    merged_threads: dict[str, ReviewThreadContext] = {}
    thread_order: list[str] = []
    latest_context: CommentContext | None = None

    for pass_record in passes:
        context = pass_record.get("comment_context")
        if not isinstance(context, dict):
            continue
        latest_context = context

        thread_source = context.get("thread_source")
        if isinstance(thread_source, str) and thread_source.strip():
            merged["thread_source"] = thread_source

        summary = context.get("summary")
        if isinstance(summary, str) and summary.strip():
            merged["summary"] = summary

        raw_threads = context.get("threads", [])
        if isinstance(raw_threads, list):
            for thread in raw_threads:
                if not isinstance(thread, dict):
                    continue
                thread_key = thread_scope_key_from_record(thread)
                if thread_key is None:
                    continue
                if thread_key not in merged_threads:
                    thread_order.append(thread_key)
                merged_threads[thread_key] = thread

        for key in DURABLE_CONTEXT_LIST_FIELDS:
            raw_items = context.get(key, [])
            if not isinstance(raw_items, list):
                continue
            valid_items = [
                item for item in raw_items if isinstance(item, str) and item.strip()
            ]
            if not valid_items:
                continue
            merged[key] = merge_unique_strings(merged.get(key, []), valid_items)

    if isinstance(latest_context, dict):
        for key in CURRENT_STATUS_CONTEXT_FIELDS:
            raw_items = latest_context.get(key, [])
            if not isinstance(raw_items, list):
                continue
            valid_items = [
                item for item in raw_items if isinstance(item, str) and item.strip()
            ]
            if valid_items:
                merged[key] = valid_items

    if thread_order:
        selected_thread_keys = (
            thread_order if max_threads is None else thread_order[-max_threads:]
        )
        merged["threads"] = [merged_threads[key] for key in selected_thread_keys]

    if max_items_per_bucket is not None:
        for key in CONTEXT_LIST_FIELDS:
            values = merged.get(key)
            if not values:
                continue
            merged[key] = values[-max_items_per_bucket:]

    return merged or None


def merge_teaching_points_history(
    passes: list[ReviewPassRecord], max_items: int | None = None
) -> list[str]:
    merged: list[str] = []
    for pass_record in passes:
        raw_items = pass_record.get("teaching_points", [])
        if not isinstance(raw_items, list):
            continue
        valid_items = [
            item for item in raw_items if isinstance(item, str) and item.strip()
        ]
        merged = merge_unique_strings(merged, valid_items)
    if max_items is None:
        return merged
    return merged[-max_items:]


def merge_inline_targets_history(
    passes: list[ReviewPassRecord],
    max_items: int | None = None,
) -> list[InlineCommentTarget]:
    merged: dict[str, InlineCommentTarget] = {}
    order: list[str] = []
    for pass_record in passes:
        raw_targets = pass_record.get("inline_comment_targets", [])
        if not isinstance(raw_targets, list):
            continue
        for target in raw_targets:
            if not isinstance(target, dict):
                continue
            repo = target.get("repo")
            pr_number = target.get("pr_number")
            finding_id = target.get("finding_id")
            if (
                not isinstance(repo, str)
                or not isinstance(pr_number, int)
                or isinstance(pr_number, bool)
            ):
                continue
            if not isinstance(finding_id, str) or not finding_id.strip():
                continue
            target_key = scoped_identity_key(repo, pr_number, finding_id)
            if target_key not in merged:
                order.append(target_key)
            merged[target_key] = target
    if max_items is None:
        return [merged[key] for key in order]
    return [merged[key] for key in order[-max_items:]]


def latest_substantive_pass(
    passes: list[ReviewPassRecord],
) -> ReviewPassRecord | None:
    for pass_record in reversed(passes):
        if pass_record.get("mode") in {"status", "review", "reassess"}:
            return pass_record
    return None


def entry_identity_map(entries: list[ReviewPassEntry]) -> dict[tuple[str, int], ReviewPassEntry]:
    return {(entry["repo"], entry["pr_number"]): entry for entry in entries}


def entries_match_exactly(
    left_entries: list[ReviewPassEntry], right_entries: list[ReviewPassEntry]
) -> bool:
    left_map = entry_identity_map(left_entries)
    right_map = entry_identity_map(right_entries)
    if left_map.keys() != right_map.keys():
        return False
    for identity, left_entry in left_map.items():
        right_entry = right_map[identity]
        for key in ("base_branch", "head_sha", "merge_base", "pr_state", "is_draft"):
            if left_entry.get(key) != right_entry.get(key):
                return False
    return True


def entries_match_live_validated_fields(
    left_entries: list[ReviewPassEntry], right_entries: list[ReviewPassEntry]
) -> bool:
    left_map = entry_identity_map(left_entries)
    right_map = entry_identity_map(right_entries)
    if left_map.keys() != right_map.keys():
        return False
    for identity, left_entry in left_map.items():
        right_entry = right_map[identity]
        for key in ("base_branch", "head_sha", "pr_state", "is_draft"):
            if left_entry.get(key) != right_entry.get(key):
                return False
    return True


def ensure_entries_have_pr_lifecycle(
    entries: list[ReviewPassEntry], context_label: str
) -> None:
    for entry in entries:
        repo = entry["repo"]
        pr_number = entry["pr_number"]
        if "pr_state" not in entry:
            raise click.ClickException(
                f"{context_label} is missing `pr_state` for `{repo}:{pr_number}`."
            )
        if "is_draft" not in entry:
            raise click.ClickException(
                f"{context_label} is missing `is_draft` for `{repo}:{pr_number}`."
            )


def latest_matching_substantive_pass(
    passes: list[ReviewPassRecord], entries: list[ReviewPassEntry]
) -> ReviewPassRecord | None:
    for pass_record in reversed(passes):
        mode = pass_record.get("mode")
        if mode not in {"status", "review", "reassess"}:
            continue
        raw_entries = pass_record.get("entries")
        if not isinstance(raw_entries, list) or not raw_entries:
            continue
        persisted_entries = [
            entry for entry in raw_entries if isinstance(entry, dict)
        ]
        if len(persisted_entries) != len(entries):
            continue
        if entries_match_exactly(persisted_entries, entries):
            return pass_record
    return None


def ensure_artifact_exists(artifact_path: Path) -> None:
    if not artifact_path.exists() or not artifact_path.is_file():
        raise click.ClickException(
            f"Review artifact `{artifact_path}` must exist before recording a pass."
        )


def active_findings_signature(
    findings: ReviewFindings,
) -> dict[str, tuple[str, str, str | None, str | None, str | None, str | None, str | None]]:
    signature: dict[
        str, tuple[str, str, str | None, str | None, str | None, str | None, str | None]
    ] = {}
    for bucket in ("new", "carried_forward"):
        for finding in findings.get(bucket, []):
            key = scoped_identity_key(finding["repo"], finding["pr_number"], finding["id"])
            signature[key] = (
                bucket,
                finding.get("summary", ""),
                finding.get("severity"),
                finding.get("path"),
                finding.get("symbol"),
                finding.get("risk"),
                finding.get("suggested_fix"),
            )
    return signature


def validate_review_requirements(
    *,
    mode: str,
    posting_status: str,
    recommendation: str,
    artifact_path: Path,
    entries: list[ReviewPassEntry],
    findings: ReviewFindings,
    no_findings_after_full_review: bool,
    author_claims_checked: list[AuthorClaimCheck],
    no_author_claims: bool,
    comment_context: CommentContext | None,
    backend_handoff: BackendHandoff | None,
    known_prs: set[tuple[str, int]],
    existing_passes: list[ReviewPassRecord],
    pending_live_validation: LiveValidationRecord | None = None,
    validation_token: str | None = None,
    enforce_artifact_existence: bool = True,
    require_post_validation_proof: bool = True,
    require_pr_lifecycle: bool = True,
    require_comment_context_evidence: bool = True,
    require_status_assessment: bool = True,
) -> None:
    if enforce_artifact_existence:
        ensure_artifact_exists(artifact_path)
    if require_pr_lifecycle and mode in PUBLIC_MODES:
        ensure_entries_have_pr_lifecycle(entries, "Review payload `entries`")

    active_finding_count = total_finding_count(findings, ("new", "carried_forward"))
    total_findings = total_finding_count(findings)

    if recommendation == "approve" and active_finding_count > 0:
        raise click.ClickException(
            "Review payload cannot recommend `approve` while active findings remain."
        )
    if posting_status == "posted_approved" and active_finding_count > 0:
        raise click.ClickException(
            "Review payload cannot record `posted_approved` while active findings remain."
        )

    if no_author_claims and author_claims_checked:
        raise click.ClickException(
            "Review payload cannot set `no_author_claims=true` while also "
            "recording `author_claims_checked`."
        )
    if no_findings_after_full_review and total_findings > 0:
        raise click.ClickException(
            "Review payload cannot set `no_findings_after_full_review=true` while "
            "also recording findings."
        )

    if mode == "status":
        if require_comment_context_evidence and not has_comment_context_evidence(
            comment_context
        ):
            raise click.ClickException(
                "`status` review payloads must include non-empty `comment_context` evidence."
            )
        if require_status_assessment and not has_status_assessment(comment_context):
            raise click.ClickException(
                "`status` review payloads must classify current state via "
                "`still_legit`, `moot_or_no_longer_applicable`, "
                "`resolved_for_context`, or `follow_up`."
            )

    if mode in {"review", "reassess"}:
        if require_comment_context_evidence and not has_comment_context_evidence(
            comment_context
        ):
            raise click.ClickException(
                f"`{mode}` review payloads must include non-empty `comment_context` evidence."
            )
        if not author_claims_checked and not no_author_claims:
            raise click.ClickException(
                f"`{mode}` review payloads must record `author_claims_checked` "
                "or set `no_author_claims=true`."
            )
        if total_findings == 0 and not no_findings_after_full_review:
            raise click.ClickException(
                f"`{mode}` review payloads with zero findings must set "
                "`no_findings_after_full_review=true`."
            )

    if mode == "post":
        prior_validated_pass = latest_matching_substantive_pass(existing_passes, entries)
        if prior_validated_pass is None:
            raise click.ClickException(
                "`post` review payloads require a prior `status`, `review`, or "
                "`reassess` pass recorded on the exact same batch heads."
            )
        if posting_status == "not_posted":
            raise click.ClickException(
                "`post` review payloads must record a concrete posted status."
            )
        expected_posting_status = {
            "approve": "posted_approved",
            "comment": "posted_comment",
            "request_changes": "posted_request_changes",
        }[recommendation]
        if posting_status != expected_posting_status:
            raise click.ClickException(
                "`post` review payloads must align `posting_status` with "
                f"`recommendation={recommendation}`."
            )
        prior_recommendation = prior_validated_pass.get("recommendation")
        if prior_recommendation != recommendation:
            raise click.ClickException(
                "`post` review payloads must reuse the latest validated substantive "
                f"recommendation. Expected `{prior_recommendation}`, got `{recommendation}`."
            )
        prior_findings = prior_validated_pass.get("findings")
        if not isinstance(prior_findings, dict):
            raise click.ClickException(
                "The latest validated substantive pass is missing findings; record "
                "a new substantive pass before posting."
            )
        if active_findings_signature(prior_findings) != active_findings_signature(findings):
            raise click.ClickException(
                "`post` review payloads must reuse the latest validated active "
                "finding set. Record a new substantive pass before changing the verdict."
            )
        if require_post_validation_proof:
            if validation_token is None:
                raise click.ClickException(
                    "`post` review payloads must include `validation_token` from "
                    "the latest successful `validate-live-state` run."
                )
            if pending_live_validation is None:
                raise click.ClickException(
                    "`post` review payloads require a pending live-state validation "
                    "proof in the state file."
                )
            if pending_live_validation["token"] != validation_token:
                raise click.ClickException(
                    "`post` review payloads supplied an invalid `validation_token`."
                )
            if pending_live_validation["validated_against_pass_number"] != prior_validated_pass.get(
                "review_pass_number"
            ):
                raise click.ClickException(
                    "`post` review payloads must use a live-state validation proof "
                    "generated against the current latest substantive pass."
                )
            if not entries_match_live_validated_fields(
                pending_live_validation["entries"], entries
            ):
                raise click.ClickException(
                    "`post` review payloads must use a live-state validation proof "
                    "for the exact live-validated batch fields being posted."
                )
            validated_at = parse_utc_timestamp(
                pending_live_validation["validated_at_utc"],
                "pending_live_validation.validated_at_utc",
            )
            now = datetime.now(timezone.utc)
            if validated_at > now + timedelta(minutes=1):
                raise click.ClickException(
                    "The stored live-state validation proof has an invalid future "
                    "timestamp."
                )
            if now - validated_at > LIVE_VALIDATION_TTL:
                raise click.ClickException(
                    "The stored live-state validation proof is stale. Re-run "
                    "`validate-live-state` immediately before posting."
                )
            prior_recorded_at = optional_non_empty_string(
                prior_validated_pass.get("recorded_at_utc"),
                "prior_validated_pass.recorded_at_utc",
            )
            if prior_recorded_at is not None:
                prior_recorded_at_dt = parse_utc_timestamp(
                    prior_recorded_at, "prior_validated_pass.recorded_at_utc"
                )
                if validated_at < prior_recorded_at_dt:
                    raise click.ClickException(
                        "The stored live-state validation proof predates the "
                        "latest substantive pass. Re-run `validate-live-state`."
                    )
            for entry in entries:
                pr_state = str(entry["pr_state"]).upper()
                if pr_state != "OPEN":
                    raise click.ClickException(
                        "`post` review payloads require the live PR state to be "
                        f"`OPEN`; got `{pr_state}` for `{entry['repo']}:{entry['pr_number']}`."
                    )
                if entry["is_draft"]:
                    raise click.ClickException(
                        "`post` review payloads require non-draft PRs. Re-run after "
                        f"`{entry['repo']}:{entry['pr_number']}` is ready for review."
                    )

    if batch_has_backend(known_prs) and mode in {"review", "reassess", "post"}:
        if backend_handoff is None:
            raise click.ClickException(
                f"`{mode}` review payloads that include `Django4Lyfe` must persist "
                "`backend_handoff` before recording the pass."
            )


@click.group()
def cli() -> None:
    """Manage structured local review state."""


@cli.command("init")
@click.option("--state-path", type=click.Path(path_type=Path), required=True)
@click.option("--batch-key", required=True)
@click.option("--worktree-path", type=click.Path(path_type=Path), required=True)
@click.option("--artifact-path", type=click.Path(path_type=Path), required=True)
@click.option("--force/--no-force", default=False, show_default=True)
@click.option(
    "--pr", "prs", multiple=True, required=True, help="Repeat as repo:number."
)
@click.option(
    "--link-type",
    type=click.Choice(["single_pr", "explicit_cross_repo_pair"], case_sensitive=False),
    default=None,
    help="Optional linked-batch metadata for the initialized state.",
)
@click.option("--linked-pair-reason", default=None)
@click.option("--cross-repo-dependency-summary", default=None)
@click.option(
    "--authoritative-pr",
    default=None,
    help="Use repo:number for the PR whose verdict wins if linked PRs diverge.",
)
def init_state(
    state_path: Path,
    batch_key: str,
    worktree_path: Path,
    artifact_path: Path,
    force: bool,
    prs: tuple[str, ...],
    link_type: str | None,
    linked_pair_reason: str | None,
    cross_repo_dependency_summary: str | None,
    authoritative_pr: str | None,
) -> None:
    """Initialize one structured review-state file.

    This should happen once per batch before the first review artifact is
    written. Later reassessment passes should update the same state file rather
    than inventing a new identity.
    """

    entries: list[ReviewBatchIdentity] = []
    seen: set[tuple[str, int]] = set()
    for raw in prs:
        if ":" not in raw:
            raise click.ClickException(f"Invalid --pr value `{raw}`. Use repo:number.")
        repo, number_text = raw.split(":", 1)
        try:
            pr_number = int(number_text)
        except ValueError as exc:
            raise click.ClickException(
                f"Invalid --pr value `{raw}`. PR number must be an integer."
            ) from exc
        identity = (repo, pr_number)
        if identity in seen:
            raise click.ClickException(f"Duplicate --pr entry: {repo}:{number_text}")
        seen.add(identity)
        entries.append({"repo": repo, "pr_number": pr_number})
    validate_v1_batch_scope(entries, "`init --pr`")

    linked_batch: LinkedBatchMetadata | None = None
    if len(entries) == 2:
        resolved_link_type = (link_type or "explicit_cross_repo_pair").lower()
        if resolved_link_type != "explicit_cross_repo_pair":
            raise click.ClickException(
                "Linked review batches must use `--link-type explicit_cross_repo_pair`."
            )
        if linked_pair_reason is None or not linked_pair_reason.strip():
            raise click.ClickException(
                "Linked review batches require `--linked-pair-reason`."
            )
        if authoritative_pr is None or not authoritative_pr.strip():
            raise click.ClickException(
                "Linked review batches require `--authoritative-pr`."
            )
        if ":" not in authoritative_pr:
            raise click.ClickException(
                "Invalid `--authoritative-pr` value. Use repo:number."
            )
        authoritative_repo, authoritative_pr_number_text = authoritative_pr.split(":", 1)
        try:
            authoritative_pr_number = int(authoritative_pr_number_text)
        except ValueError as exc:
            raise click.ClickException(
                "Invalid `--authoritative-pr` value. PR number must be an integer."
            ) from exc
        authoritative_identity = (authoritative_repo, authoritative_pr_number)
        if authoritative_identity not in seen:
            raise click.ClickException(
                "`--authoritative-pr` must point at one of the batch PRs."
            )
        linked_batch = {
            "link_type": resolved_link_type,
            "is_explicitly_linked": True,
            "linked_pair_reason": linked_pair_reason.strip(),
            "cross_repo_dependency_summary": (
                cross_repo_dependency_summary.strip()
                if isinstance(cross_repo_dependency_summary, str)
                and cross_repo_dependency_summary.strip()
                else linked_pair_reason.strip()
            ),
            "authoritative_pr": {
                "repo": authoritative_identity[0],
                "pr_number": authoritative_identity[1],
            },
        }
    elif any(
        value
        for value in (
            link_type,
            linked_pair_reason,
            cross_repo_dependency_summary,
            authoritative_pr,
        )
    ):
        raise click.ClickException(
            "Linked-batch metadata is only valid when initializing a two-PR linked batch."
        )

    resolved_state_path = Path(state_path).expanduser().resolve()
    if resolved_state_path.exists() and not force:
        raise click.ClickException(
            f"{resolved_state_path} already exists. Re-run with --force only if "
            "you intentionally want to overwrite the existing reassessment state."
        )

    now = utc_now()
    payload: ReviewStateRecord = {
        "schema_version": SCHEMA_VERSION,
        "batch_key": batch_key,
        "created_at_utc": now,
        "updated_at_utc": now,
        "worktree_path": str(Path(worktree_path).expanduser().resolve()),
        "artifact_path": str(Path(artifact_path).expanduser().resolve()),
        "review_pass_number": 0,
        "posting_status": "not_posted",
        "prs": entries,
    }
    if linked_batch is not None:
        payload["linked_batch"] = linked_batch
    atomic_write_json(resolved_state_path, payload)
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


@cli.command("show")
@click.option(
    "--state-path", type=click.Path(path_type=Path, exists=True), required=True
)
def show_state(state_path: Path) -> None:
    """Show the full state JSON."""

    click.echo(
        json.dumps(
            read_json(state_path.expanduser().resolve()), indent=2, sort_keys=True
        )
    )


@cli.command("summarize-context")
@click.option(
    "--state-path", type=click.Path(path_type=Path, exists=True), required=True
)
@click.option("--max-open-findings", default=12, show_default=True)
@click.option("--max-pass-history", default=3, show_default=True)
def summarize_context(
    state_path: Path, max_open_findings: int, max_pass_history: int
) -> None:
    """Return compact context for reassessment or posting.

    This is the default read path before a follow-up pass. It keeps the model
    from re-reading the full raw history when it only needs the durable review
    identity, latest verdict, open findings, and prior discussion summary.
    """

    payload = read_json(state_path.expanduser().resolve())
    raw_passes = payload.get("passes", [])
    if not isinstance(raw_passes, list):
        raise click.ClickException("Existing state has non-list `passes` field.")

    passes: list[ReviewPassRecord] = [
        item for item in raw_passes if isinstance(item, dict)
    ]
    # `<= 0` means "do not trim" rather than "return nothing". That keeps the
    # command useful for intentional deep dives while still defaulting to a
    # small recent slice for normal reassessment/posting runs.
    recent_passes = passes if max_pass_history <= 0 else passes[-max_pass_history:]
    open_findings_limit: int | None = (
        None if max_open_findings <= 0 else max_open_findings
    )
    # We keep a dict for the current active finding set and a separate recency
    # list so the compact output can prefer the most recently re-confirmed open
    # issues instead of whichever issue happened to appear first in history.
    open_findings: dict[str, ReviewFinding] = {}
    open_finding_order: list[str] = []
    for pass_record in passes:
        raw_findings = pass_record.get("findings")
        if not isinstance(raw_findings, dict):
            continue
        for bucket in ("new", "carried_forward"):
            bucket_entries = raw_findings.get(bucket, [])
            if not isinstance(bucket_entries, list):
                continue
            for item in bucket_entries:
                if isinstance(item, dict):
                    finding_key = finding_scope_key_from_record(item)
                    if finding_key is not None:
                        if finding_key in open_findings:
                            open_finding_order = [
                                key for key in open_finding_order if key != finding_key
                            ]
                        open_findings[finding_key] = item
                        open_finding_order.append(finding_key)
        for closed_bucket in ("resolved", "moot"):
            resolved_entries = raw_findings.get(closed_bucket, [])
            if not isinstance(resolved_entries, list):
                continue
            for item in resolved_entries:
                if isinstance(item, dict):
                    finding_key = finding_scope_key_from_record(item)
                    if finding_key is not None:
                        open_findings.pop(finding_key, None)
                        open_finding_order = [
                            key for key in open_finding_order if key != finding_key
                        ]

    latest = latest_substantive_pass(passes) or (passes[-1] if passes else {})
    latest_resolved = []
    latest_moot = []
    latest_findings = latest.get("findings")
    if isinstance(latest_findings, dict):
        raw_resolved = latest_findings.get("resolved", [])
        if isinstance(raw_resolved, list):
            latest_resolved = [item for item in raw_resolved if isinstance(item, dict)]
        raw_moot = latest_findings.get("moot", [])
        if isinstance(raw_moot, list):
            latest_moot = [item for item in raw_moot if isinstance(item, dict)]

    pass_history: list[PassHistoryEntry] = []
    for pass_record in recent_passes:
        pass_history.append(
            {
                "review_pass_number": pass_record.get("review_pass_number"),
                "recorded_at_utc": pass_record.get("recorded_at_utc"),
                "mode": pass_record.get("mode"),
                "recommendation": pass_record.get("recommendation"),
                "artifact_path": pass_record.get("artifact_path"),
            }
        )

    latest_context: ReviewPassRecord = {}
    for key in (
        "mode",
        "recommendation",
        "scope_summary",
        "business_logic_summary",
        "cross_repo_summary",
        "no_author_claims",
        "no_findings_after_full_review",
        "backend_handoff",
        "entries",
    ):
        value = latest.get(key)
        if value:
            latest_context[key] = value
    merged_author_claims = merge_author_claim_history(
        passes, max_items=open_findings_limit
    )
    if merged_author_claims:
        latest_context["author_claims_checked"] = merged_author_claims
    merged_comment_context = merge_comment_context_history(
        passes,
        max_threads=open_findings_limit,
        max_items_per_bucket=open_findings_limit,
    )
    if merged_comment_context is not None:
        latest_context["comment_context"] = merged_comment_context
    merged_teaching_points = merge_teaching_points_history(
        passes, max_items=open_findings_limit
    )
    if merged_teaching_points:
        latest_context["teaching_points"] = merged_teaching_points
    merged_inline_targets = [
        target
        for target in merge_inline_targets_history(
            passes, max_items=open_findings_limit
        )
        if scoped_identity_key(
            target["repo"], target["pr_number"], target["finding_id"]
        )
        in open_findings
    ]
    if merged_inline_targets:
        latest_context["inline_comment_targets"] = merged_inline_targets

    selected_open_finding_keys = (
        open_finding_order
        if open_findings_limit is None
        else open_finding_order[-open_findings_limit:]
    )
    recent_open_findings = [
        open_findings[key] for key in selected_open_finding_keys if key in open_findings
    ]

    summary: ReviewContextSummary = {
        "batch_key": payload.get("batch_key"),
        "worktree_path": payload.get("worktree_path"),
        "artifact_path": payload.get("artifact_path"),
        "review_pass_number": payload.get("review_pass_number", 0),
        "posting_status": payload.get("posting_status", "not_posted"),
        "prs": payload.get("prs", []),
        "linked_batch": payload.get("linked_batch"),
        "pass_history": pass_history,
        "latest_context": latest_context,
        "open_finding_count": len(open_findings),
        "open_findings": recent_open_findings,
        "latest_resolved_findings": (
            latest_resolved
            if open_findings_limit is None
            else latest_resolved[:open_findings_limit]
        ),
        "latest_moot_findings": (
            latest_moot
            if open_findings_limit is None
            else latest_moot[:open_findings_limit]
        ),
    }
    click.echo(json.dumps(summary, indent=2, sort_keys=True))


def build_live_state_comparison(
    state_path: Path, pr_context_path: Path
) -> tuple[ReviewStateRecord, ReviewPassRecord, list[ReviewPassEntry], list[dict[str, object]]]:
    path = state_path.expanduser().resolve()
    payload = read_json(path)
    known_prs = parse_prs_from_state(payload)

    raw_passes = payload.get("passes", [])
    if not isinstance(raw_passes, list):
        raise click.ClickException("Existing state has non-list `passes` field.")
    passes = [item for item in raw_passes if isinstance(item, dict)]
    latest_pass = latest_substantive_pass(passes)
    if latest_pass is None:
        raise click.ClickException(
            "Cannot compare live state before at least one substantive review pass is recorded."
        )
    latest_entries = latest_pass.get("entries")
    if not isinstance(latest_entries, list) or not latest_entries:
        raise click.ClickException(
            "Latest recorded pass does not contain valid `entries`."
        )
    normalized_latest_entries = normalize_persisted_review_entries(
        latest_entries, known_prs, "latest_pass.entries"
    )
    ensure_entries_have_pr_lifecycle(
        normalized_latest_entries,
        "Latest substantive pass entries",
    )
    supplied_artifact = parse_live_pr_context_artifact(pr_context_path, known_prs)
    pr_urls = [
        supplied_artifact[identity]["pr_url"] for identity in sorted(supplied_artifact)
    ]
    live_metadata_map = fetch_live_pr_context_from_github(pr_urls, known_prs)

    latest_map = entry_identity_map(normalized_latest_entries)
    live_map: dict[tuple[str, int], ReviewPassEntry] = {}
    for identity, latest_entry in latest_map.items():
        live_metadata = live_metadata_map[identity]
        live_map[identity] = {
            "repo": identity[0],
            "pr_number": identity[1],
            "base_branch": live_metadata["base_branch"],
            "head_sha": live_metadata["head_sha"],
            "merge_base": latest_entry["merge_base"],
            "pr_state": live_metadata["pr_state"],
            "is_draft": live_metadata["is_draft"],
        }
    mismatches: list[dict[str, object]] = []
    for identity in sorted(latest_map):
        latest_entry = latest_map[identity]
        live_entry = live_map[identity]
        drift: dict[str, object] = {
            "repo": identity[0],
            "pr_number": identity[1],
            "expected_head_sha": latest_entry["head_sha"],
            "actual_head_sha": live_entry["head_sha"],
            "expected_base_branch": latest_entry["base_branch"],
            "actual_base_branch": live_entry["base_branch"],
            "expected_pr_state": latest_entry["pr_state"],
            "actual_pr_state": live_entry["pr_state"],
            "expected_is_draft": latest_entry["is_draft"],
            "actual_is_draft": live_entry["is_draft"],
        }
        if latest_entry["head_sha"] != live_entry["head_sha"]:
            drift["status"] = "head_sha_mismatch"
            mismatches.append(drift)
            continue
        if latest_entry["base_branch"] != live_entry["base_branch"]:
            drift["status"] = "base_branch_mismatch"
            mismatches.append(drift)
            continue
        if latest_entry["pr_state"] != live_entry["pr_state"]:
            drift["status"] = "pr_state_mismatch"
            mismatches.append(drift)
            continue
        if latest_entry["is_draft"] != live_entry["is_draft"]:
            drift["status"] = "draft_state_mismatch"
            mismatches.append(drift)

    return (
        payload,
        latest_pass,
        [live_map[identity] for identity in sorted(live_map)],
        mismatches,
    )


@cli.command("report-live-drift")
@click.option(
    "--state-path", type=click.Path(path_type=Path, exists=True), required=True
)
@click.option(
    "--pr-context-path",
    type=click.Path(path_type=Path, exists=True),
    required=True,
    help="Structured output from fetch_review_threads.py for the current live PR state.",
)
def report_live_drift(state_path: Path, pr_context_path: Path) -> None:
    """Report live PR drift for reassessment without writing a validation token."""

    _payload, latest_pass, live_entries, mismatches = build_live_state_comparison(
        state_path, pr_context_path
    )
    click.echo(
        json.dumps(
            {
                "status": "drifted" if mismatches else "matched",
                "validated_against_pass_number": require_non_boolean_int(
                    latest_pass.get("review_pass_number"),
                    "latest_pass.review_pass_number",
                ),
                "entries": live_entries,
                "mismatches": mismatches,
            },
            indent=2,
            sort_keys=True,
        )
    )


@cli.command("validate-live-state")
@click.option(
    "--state-path", type=click.Path(path_type=Path, exists=True), required=True
)
@click.option(
    "--pr-context-path",
    type=click.Path(path_type=Path, exists=True),
    required=True,
    help="Structured output from fetch_review_threads.py for the current live PR state.",
)
def validate_live_state(state_path: Path, pr_context_path: Path) -> None:
    """Fail closed if live PR refs drifted from the latest recorded batch state."""

    path = state_path.expanduser().resolve()
    payload, latest_pass, live_entries, mismatches = build_live_state_comparison(
        path, pr_context_path
    )

    if mismatches:
        mismatch_json = json.dumps(mismatches, indent=2, sort_keys=True)
        raise click.ClickException(
            "Live PR state drifted from the latest recorded batch identity. "
            "Record a new substantive pass before reassessment or posting.\n"
            f"{mismatch_json}"
        )

    validation_record: LiveValidationRecord = {
        "token": uuid4().hex,
        "validated_at_utc": utc_now(),
        "validated_against_pass_number": require_non_boolean_int(
            latest_pass.get("review_pass_number"), "latest_pass.review_pass_number"
        ),
        "entries": live_entries,
        "source_artifact_path": str(pr_context_path.expanduser().resolve()),
    }
    payload["pending_live_validation"] = validation_record
    payload["updated_at_utc"] = utc_now()
    atomic_write_json(path, payload)

    click.echo(
        json.dumps(
            {
                "status": "matched",
                "token": validation_record["token"],
                "validated_against_pass_number": validation_record[
                    "validated_against_pass_number"
                ],
                "entries": validation_record["entries"],
            },
            indent=2,
            sort_keys=True,
        )
    )


@cli.command("record-pass")
@click.option(
    "--state-path", type=click.Path(path_type=Path, exists=True), required=True
)
@click.option(
    "--review-target",
    "review_targets",
    multiple=True,
    required=True,
    help="Repeat as repo:pr_number:base_branch:head_sha:merge_base.",
)
@click.option("--artifact-path", type=click.Path(path_type=Path), required=True)
@click.option("--posting-status", default="not_posted", show_default=True)
@click.option(
    "--compatibility-only",
    is_flag=True,
    default=False,
    help="Allow this legacy compatibility write path for migration or recovery only.",
)
@click.option(
    "--justification",
    default=None,
    help="Required when using `--compatibility-only`; explains why `record-review` cannot be used.",
)
def record_pass(
    state_path: Path,
    review_targets: tuple[str, ...],
    artifact_path: Path,
    posting_status: str,
    compatibility_only: bool,
    justification: str | None,
) -> None:
    """Record one completed review pass into structured local state.

    This command intentionally refuses to record a pass for a PR that is not
    part of the batch. That keeps reassessment history attached to the right
    review target.

    `record-pass` is compatibility-only. Normal review runs must use
    `record-review`, which persists evidence and the structured context needed
    for reassessment/posting.
    """

    if not compatibility_only:
        raise click.ClickException(
            "`record-pass` is disabled for normal review runs. Use "
            "`record-review`, or rerun with `--compatibility-only --justification ...` "
            "for a migration/recovery case."
        )
    if justification is None or not justification.strip():
        raise click.ClickException(
            "`record-pass --compatibility-only` requires a non-empty `--justification`."
        )

    path = state_path.expanduser().resolve()
    payload = read_json(path)
    known_prs = parse_prs_from_state(payload)
    entries: list[ReviewPassEntry] = []
    seen_targets: set[tuple[str, int]] = set()
    for raw in review_targets:
        entry = parse_review_target(raw)
        identity = (entry["repo"], entry["pr_number"])
        if identity not in known_prs:
            raise click.ClickException(
                f"{entry['repo']}:{entry['pr_number']} is not part of this review batch."
            )
        if identity in seen_targets:
            raise click.ClickException(
                f"Duplicate --review-target entry: {entry['repo']}:{entry['pr_number']}"
            )
        seen_targets.add(identity)
        entries.append(entry)
    ensure_full_batch_coverage(seen_targets, known_prs, "`record-pass`")
    artifact_path = Path(artifact_path).expanduser().resolve()
    ensure_artifact_exists(artifact_path)
    posting_status = require_allowed_value(
        posting_status, ALLOWED_POSTING_STATUSES, "posting_status"
    )
    review_pass_number = next_review_pass_number(payload, path)
    now = utc_now()

    pass_record: ReviewPassRecord = {
        "review_pass_number": review_pass_number,
        "recorded_at_utc": now,
        "artifact_path": str(artifact_path),
        "posting_status": posting_status,
        "entries": entries,
        "mode": COMPATIBILITY_MODE,
    }

    passes = payload.setdefault("passes", [])
    if not isinstance(passes, list):
        raise click.ClickException("Existing state has non-list `passes` field.")
    passes.append(pass_record)
    payload["review_pass_number"] = review_pass_number
    payload["updated_at_utc"] = now
    payload["artifact_path"] = str(artifact_path)
    payload["posting_status"] = posting_status
    payload.pop("pending_live_validation", None)

    atomic_write_json(path, payload)
    click.echo(json.dumps(pass_record, indent=2, sort_keys=True))


@cli.command("record-review")
@click.option(
    "--state-path", type=click.Path(path_type=Path, exists=True), required=True
)
def record_review(state_path: Path) -> None:
    """Record one completed review pass plus compact review context.

    Read the review payload from stdin JSON. This is the preferred write path
    after a full status/review/reassess/post run because it persists the small,
    high-signal context that later passes should reuse.
    """

    path = state_path.expanduser().resolve()
    payload = read_json(path)
    known_prs = parse_prs_from_state(payload)
    review_payload = load_review_payload_from_stdin()

    mode = require_allowed_value(
        require_non_empty_string(review_payload.get("mode"), "mode"),
        PUBLIC_MODES,
        "mode",
    )

    entries = normalize_review_entries(review_payload.get("entries"), known_prs)
    entry_map = entry_identity_map(entries)
    artifact_path = (
        Path(
            require_non_empty_string(
                review_payload.get("artifact_path"), "artifact_path"
            )
        )
        .expanduser()
        .resolve()
    )
    posting_status = require_allowed_value(
        require_non_empty_string(review_payload.get("posting_status"), "posting_status"),
        ALLOWED_POSTING_STATUSES,
        "posting_status",
    )
    recommendation = require_allowed_value(
        require_non_empty_string(review_payload.get("recommendation"), "recommendation"),
        ALLOWED_RECOMMENDATIONS,
        "recommendation",
    )
    validation_token = optional_non_empty_string(
        review_payload.get("validation_token"), "validation_token"
    )
    scope_summary = require_non_empty_string(
        review_payload.get("scope_summary"), "scope_summary"
    )
    business_logic_summary = optional_non_empty_string(
        review_payload.get("business_logic_summary"), "business_logic_summary"
    )
    cross_repo_summary = optional_non_empty_string(
        review_payload.get("cross_repo_summary"), "cross_repo_summary"
    )
    no_author_claims = bool(
        optional_bool(review_payload.get("no_author_claims"), "no_author_claims")
        or False
    )
    no_findings_after_full_review = bool(
        optional_bool(
            review_payload.get("no_findings_after_full_review"),
            "no_findings_after_full_review",
        )
        or False
    )
    findings = normalize_findings(review_payload.get("findings"), known_prs)
    all_finding_ids = {
        scoped_identity_key(finding["repo"], finding["pr_number"], finding["id"])
        for bucket in FINDING_BUCKETS
        for finding in findings.get(bucket, [])
        if "id" in finding and "repo" in finding and "pr_number" in finding
    }
    open_finding_ids = {
        scoped_identity_key(finding["repo"], finding["pr_number"], finding["id"])
        for bucket in ("new", "carried_forward")
        for finding in findings.get(bucket, [])
        if "id" in finding and "repo" in finding and "pr_number" in finding
    }
    author_claims_checked = normalize_author_claims(
        review_payload.get("author_claims_checked"), known_prs
    )
    backend_handoff = normalize_backend_handoff(
        review_payload.get("backend_handoff"),
        known_prs,
        open_finding_ids,
        entry_map,
        recommendation,
        payload.get("worktree_path"),
    )
    comment_context = normalize_comment_context(
        review_payload.get("comment_context"), known_prs, all_finding_ids
    )
    teaching_points = normalize_string_list(
        review_payload.get("teaching_points"), "teaching_points"
    )
    inline_comment_targets = normalize_inline_comment_targets(
        review_payload.get("inline_comment_targets"), known_prs, open_finding_ids
    )
    existing_passes = payload.get("passes", [])
    if not isinstance(existing_passes, list):
        raise click.ClickException("Existing state has non-list `passes` field.")
    persisted_passes = [
        item for item in existing_passes if isinstance(item, dict)
    ]
    pending_live_validation = payload.get("pending_live_validation")
    if pending_live_validation is not None and not isinstance(
        pending_live_validation, dict
    ):
        raise click.ClickException(
            "Existing state has invalid `pending_live_validation` field."
        )

    validate_review_requirements(
        mode=mode,
        posting_status=posting_status,
        recommendation=recommendation,
        artifact_path=artifact_path,
        entries=entries,
        findings=findings,
        no_findings_after_full_review=no_findings_after_full_review,
        author_claims_checked=author_claims_checked,
        no_author_claims=no_author_claims,
        comment_context=comment_context,
        backend_handoff=backend_handoff,
        known_prs=known_prs,
        existing_passes=persisted_passes,
        pending_live_validation=pending_live_validation,
        validation_token=validation_token,
    )

    review_pass_number = next_review_pass_number(payload, path)
    now = utc_now()

    pass_record: ReviewPassRecord = {
        "review_pass_number": review_pass_number,
        "recorded_at_utc": now,
        "artifact_path": str(artifact_path),
        "posting_status": posting_status,
        "entries": entries,
        "mode": mode,
        "recommendation": recommendation,
        "scope_summary": scope_summary,
        "findings": findings,
    }
    if business_logic_summary is not None:
        pass_record["business_logic_summary"] = business_logic_summary
    if cross_repo_summary is not None:
        pass_record["cross_repo_summary"] = cross_repo_summary
    if no_author_claims:
        pass_record["no_author_claims"] = True
    if no_findings_after_full_review:
        pass_record["no_findings_after_full_review"] = True
    if author_claims_checked:
        pass_record["author_claims_checked"] = author_claims_checked
    if backend_handoff is not None:
        pass_record["backend_handoff"] = backend_handoff
    if comment_context is not None:
        pass_record["comment_context"] = comment_context
    if teaching_points:
        pass_record["teaching_points"] = teaching_points
    if inline_comment_targets:
        pass_record["inline_comment_targets"] = inline_comment_targets

    passes = payload.setdefault("passes", [])
    if not isinstance(passes, list):
        raise click.ClickException("Existing state has non-list `passes` field.")
    passes.append(pass_record)
    payload["review_pass_number"] = review_pass_number
    payload["updated_at_utc"] = now
    payload["artifact_path"] = str(artifact_path)
    payload["posting_status"] = posting_status
    payload.pop("pending_live_validation", None)

    atomic_write_json(path, payload)
    click.echo(json.dumps(pass_record, indent=2, sort_keys=True))


if __name__ == "__main__":
    cli()
