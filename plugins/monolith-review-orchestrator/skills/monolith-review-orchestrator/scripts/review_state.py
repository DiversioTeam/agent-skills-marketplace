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
- the model should not hand-edit JSON blobs in chat and hope it stays coherent

Mental model:
    markdown = human-facing review artifact
    JSON state = machine-facing reassessment identity
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TypedDict

import click


SCHEMA_VERSION = 1


class ReviewBatchIdentity(TypedDict):
    repo: str
    pr_number: int


class ReviewPassRecord(TypedDict):
    review_pass_number: int
    recorded_at_utc: str
    artifact_path: str
    posting_status: str
    entries: list["ReviewPassEntry"]


class ReviewPassEntry(TypedDict):
    repo: str
    pr_number: int
    base_branch: str
    head_sha: str
    merge_base: str


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
    return data


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
        if not isinstance(repo, str) or not isinstance(pr_number, int):
            raise click.ClickException("State file has an invalid PR identity entry.")
        parsed.add((repo, pr_number))
    return parsed


@click.group()
def cli() -> None:
    """Manage structured local review state."""


@cli.command("init")
@click.option("--state-path", type=click.Path(path_type=Path), required=True)
@click.option("--batch-key", required=True)
@click.option("--worktree-path", type=click.Path(path_type=Path), required=True)
@click.option("--artifact-path", type=click.Path(path_type=Path), required=True)
@click.option(
    "--pr", "prs", multiple=True, required=True, help="Repeat as repo:number."
)
def init_state(
    state_path: Path,
    batch_key: str,
    worktree_path: Path,
    artifact_path: Path,
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
    atomic_write_json(Path(state_path).expanduser().resolve(), payload)
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
    return {
        "repo": repo,
        "pr_number": pr_number,
        "base_branch": base_branch,
        "head_sha": head_sha,
        "merge_base": merge_base,
    }


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
    review_pass_number = int(payload.get("review_pass_number", 0)) + 1
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


if __name__ == "__main__":
    cli()
