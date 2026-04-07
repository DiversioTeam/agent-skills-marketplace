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
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal, TypedDict

import click


SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS: set[int] = {1, SCHEMA_VERSION}
ALLOWED_MODES: set[str] = {"status", "review", "reassess", "post"}
CONTEXT_LIST_FIELDS: tuple[str, ...] = (
    "still_legit",
    "moot_or_resolved",
    "resolved_for_context",
    "follow_up",
)

FINDING_BUCKETS: tuple[str, ...] = ("new", "carried_forward", "resolved", "moot")
ReviewThreadStatus = Literal["open", "resolved", "moot"]


class ReviewBatchIdentity(TypedDict):
    repo: str
    pr_number: int


class ReviewPassEntry(TypedDict):
    repo: str
    pr_number: int
    base_branch: str
    head_sha: str
    merge_base: str


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
    moot_or_resolved: list[str]
    resolved_for_context: list[str]
    follow_up: list[str]


class InlineCommentTarget(TypedDict, total=False):
    repo: str
    pr_number: int
    finding_id: str
    path: str
    line: int
    summary: str


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
    author_claims_checked: list[AuthorClaimCheck]
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
    passes: list[ReviewPassRecord]


class ReviewPayloadInput(TypedDict, total=False):
    mode: str
    artifact_path: str
    posting_status: str
    recommendation: str
    scope_summary: str
    business_logic_summary: str
    cross_repo_summary: str
    author_claims_checked: list[AuthorClaimCheck]
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
    pass_history: list[PassHistoryEntry]
    latest_context: ReviewPassRecord
    open_finding_count: int
    open_findings: list[ReviewFinding]
    latest_resolved_findings: list[ReviewFinding]
    latest_moot_findings: list[ReviewFinding]


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


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
    normalized = normalize_state_record(data, schema_version=raw_schema_version)
    parse_prs_from_state(normalized)
    return normalized


def normalize_state_record(payload: object, schema_version: int) -> ReviewStateRecord:
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

    raw_review_pass_number = payload.get("review_pass_number")
    if raw_review_pass_number is not None:
        normalized["review_pass_number"] = require_non_boolean_int(
            raw_review_pass_number, "review_pass_number"
        )

    prs = normalize_review_batch_identities(payload.get("prs"))
    normalized["prs"] = prs
    known_prs = {(entry["repo"], entry["pr_number"]) for entry in prs}

    raw_passes = payload.get("passes")
    if raw_passes is not None:
        if not isinstance(raw_passes, list):
            raise click.ClickException("State file has non-list `passes` field.")
        normalized["passes"] = [
            normalize_persisted_review_pass(item, index, known_prs)
            for index, item in enumerate(raw_passes)
        ]

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
    return normalized


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

    return {
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

    return normalized or None


def normalize_findings(
    value: object, known_prs: set[tuple[str, int]]
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
                "summary",
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
            bucket_entries.append(finding)
        normalized[bucket] = bucket_entries
    return normalized


def normalize_inline_comment_targets(
    value: object,
    known_prs: set[tuple[str, int]],
    allowed_finding_ids: set[str],
) -> list[InlineCommentTarget]:
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
            "summary": require_non_empty_string(
                item.get("summary"), f"inline_comment_targets[{index}].summary"
            ),
        }
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
        normalized.append(target)
    return normalized


def normalize_persisted_review_entries(
    value: object,
    known_prs: set[tuple[str, int]],
    field_name: str,
) -> list[ReviewPassEntry]:
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
    ensure_full_batch_coverage(seen_targets, known_prs, field_name)
    return normalized


def normalize_persisted_review_pass(
    value: object,
    index: int,
    known_prs: set[tuple[str, int]],
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
    recorded_at_utc = require_non_empty_string(
        value.get("recorded_at_utc"), f"passes[{index}].recorded_at_utc"
    )
    review_pass_number = require_non_boolean_int(
        value.get("review_pass_number"), f"passes[{index}].review_pass_number"
    )
    entries = normalize_persisted_review_entries(
        value.get("entries"), known_prs, f"passes[{index}].entries"
    )

    normalized: ReviewPassRecord = {
        "artifact_path": artifact_path,
        "posting_status": posting_status,
        "recorded_at_utc": recorded_at_utc,
        "review_pass_number": review_pass_number,
        "entries": entries,
    }

    mode = optional_non_empty_string(value.get("mode"), f"passes[{index}].mode")
    if mode is not None:
        if mode not in ALLOWED_MODES:
            allowed_modes = ", ".join(sorted(ALLOWED_MODES))
            raise click.ClickException(
                f"State file field `passes[{index}].mode` must be one of: {allowed_modes}."
            )
        normalized["mode"] = mode

    recommendation = optional_non_empty_string(
        value.get("recommendation"), f"passes[{index}].recommendation"
    )
    if recommendation is not None:
        normalized["recommendation"] = recommendation

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

    findings = normalize_findings(value.get("findings"), known_prs)
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

    author_claims_checked = normalize_author_claims(
        value.get("author_claims_checked"), known_prs
    )
    if author_claims_checked:
        normalized["author_claims_checked"] = author_claims_checked

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
    merged: CommentContext = {}
    merged_threads: dict[str, ReviewThreadContext] = {}
    thread_order: list[str] = []

    for pass_record in passes:
        context = pass_record.get("comment_context")
        if not isinstance(context, dict):
            continue

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

        for key in CONTEXT_LIST_FIELDS:
            raw_items = context.get(key, [])
            if not isinstance(raw_items, list):
                continue
            valid_items = [
                item for item in raw_items if isinstance(item, str) and item.strip()
            ]
            if not valid_items:
                continue
            merged[key] = merge_unique_strings(merged.get(key, []), valid_items)

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
def init_state(
    state_path: Path,
    batch_key: str,
    worktree_path: Path,
    artifact_path: Path,
    force: bool,
    prs: tuple[str, ...],
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
    recent_passes = passes if max_pass_history <= 0 else passes[-max_pass_history:]
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

    latest = passes[-1] if passes else {}
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
        "entries",
    ):
        value = latest.get(key)
        if value:
            latest_context[key] = value
    merged_author_claims = merge_author_claim_history(
        recent_passes, max_items=max_open_findings
    )
    if merged_author_claims:
        latest_context["author_claims_checked"] = merged_author_claims
    merged_comment_context = merge_comment_context_history(
        recent_passes,
        max_threads=max_open_findings,
        max_items_per_bucket=max_open_findings,
    )
    if merged_comment_context is not None:
        latest_context["comment_context"] = merged_comment_context
    merged_teaching_points = merge_teaching_points_history(
        recent_passes, max_items=max_open_findings
    )
    if merged_teaching_points:
        latest_context["teaching_points"] = merged_teaching_points
    merged_inline_targets = [
        target
        for target in merge_inline_targets_history(
            recent_passes, max_items=max_open_findings
        )
        if scoped_identity_key(
            target["repo"], target["pr_number"], target["finding_id"]
        )
        in open_findings
    ]
    if merged_inline_targets:
        latest_context["inline_comment_targets"] = merged_inline_targets

    recent_open_findings = [
        open_findings[key]
        for key in open_finding_order[-max_open_findings:]
        if key in open_findings
    ]

    summary: ReviewContextSummary = {
        "batch_key": payload.get("batch_key"),
        "worktree_path": payload.get("worktree_path"),
        "artifact_path": payload.get("artifact_path"),
        "review_pass_number": payload.get("review_pass_number", 0),
        "posting_status": payload.get("posting_status", "not_posted"),
        "prs": payload.get("prs", []),
        "pass_history": pass_history,
        "latest_context": latest_context,
        "open_finding_count": len(open_findings),
        "open_findings": recent_open_findings,
        "latest_resolved_findings": latest_resolved[:max_open_findings],
        "latest_moot_findings": latest_moot[:max_open_findings],
    }
    click.echo(json.dumps(summary, indent=2, sort_keys=True))


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
def record_pass(
    state_path: Path,
    review_targets: tuple[str, ...],
    artifact_path: Path,
    posting_status: str,
) -> None:
    """Record one completed review pass into structured local state.

    This command intentionally refuses to record a pass for a PR that is not
    part of the batch. That keeps reassessment history attached to the right
    review target.

    Prefer `record-review` for normal usage because it can also persist compact
    review context, stable finding IDs, comment-legitimacy notes, and inline
    comment plans.
    """

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
    review_pass_number = next_review_pass_number(payload, path)
    now = utc_now()

    pass_record: ReviewPassRecord = {
        "review_pass_number": review_pass_number,
        "recorded_at_utc": now,
        "artifact_path": str(Path(artifact_path).expanduser().resolve()),
        "posting_status": posting_status,
        "entries": entries,
    }

    passes = payload.setdefault("passes", [])
    if not isinstance(passes, list):
        raise click.ClickException("Existing state has non-list `passes` field.")
    passes.append(pass_record)
    payload["review_pass_number"] = review_pass_number
    payload["updated_at_utc"] = now
    payload["artifact_path"] = str(Path(artifact_path).expanduser().resolve())
    payload["posting_status"] = posting_status

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

    mode = require_non_empty_string(review_payload.get("mode"), "mode")
    if mode not in ALLOWED_MODES:
        allowed_modes = ", ".join(sorted(ALLOWED_MODES))
        raise click.ClickException(
            f"Review payload field `mode` must be one of: {allowed_modes}."
        )

    entries = normalize_review_entries(review_payload.get("entries"), known_prs)
    artifact_path = (
        Path(
            require_non_empty_string(
                review_payload.get("artifact_path"), "artifact_path"
            )
        )
        .expanduser()
        .resolve()
    )
    posting_status = require_non_empty_string(
        review_payload.get("posting_status"), "posting_status"
    )
    recommendation = require_non_empty_string(
        review_payload.get("recommendation"), "recommendation"
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
    comment_context = normalize_comment_context(
        review_payload.get("comment_context"), known_prs, all_finding_ids
    )
    teaching_points = normalize_string_list(
        review_payload.get("teaching_points"), "teaching_points"
    )
    inline_comment_targets = normalize_inline_comment_targets(
        review_payload.get("inline_comment_targets"), known_prs, open_finding_ids
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
    if author_claims_checked:
        pass_record["author_claims_checked"] = author_claims_checked
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

    atomic_write_json(path, payload)
    click.echo(json.dumps(pass_record, indent=2, sort_keys=True))


if __name__ == "__main__":
    cli()
