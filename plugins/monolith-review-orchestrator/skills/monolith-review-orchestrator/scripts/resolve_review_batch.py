#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "click>=8.1,<9",
# ]
# ///
"""Resolve one deterministic monolith review batch.

Why this helper exists:
- the model should not improvise worktree names, artifact paths, or batch keys
- reassessment needs one stable local identity for "this review run"
- v1 scope limits should be enforced by code, not left to prompt wording

Mental model:
    input PR URLs
        -> stable batch key
        -> stable worktree path
        -> stable artifact path
        -> stable state path
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

import click


MONOLITH_ROOT_MARKERS: tuple[str, ...] = (
    ".gitmodules",
    ".submodule-branches",
    "scripts/create_worktree.py",
    "scripts/update_submodules.py",
    "docs/github-first-branch-and-pr-conventions.md",
)
ALLOWED_MODES: set[str] = {"status", "review", "reassess", "post"}
REPO_MAP: dict[tuple[str, str], tuple[str, str | None]] = {
    ("DiversioTeam", "monolith"): ("mono", None),
    ("DiversioTeam", "Django4Lyfe"): ("bk", "backend"),
    ("DiversioTeam", "Diversio-Frontend"): ("fe", "frontend"),
    ("DiversioTeam", "Optimo-Frontend"): ("of", "optimo-frontend"),
    ("DiversioTeam", "diversio-ds"): ("ds", "design-system"),
    ("DiversioTeam", "infrastructure"): ("infra", "infrastructure"),
    ("DiversioTeam", "diversio-serverless"): ("sls", "diversio-serverless"),
}
PR_PATH_PATTERN = re.compile(
    r"^/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)(?:/.*)?$"
)


class PullRequestTarget(TypedDict):
    owner: str
    repo: str
    pr_number: int
    alias: str
    submodule_path: str | None
    pr_url: str
    entry_key: str


class BatchPrIdentity(TypedDict):
    repo: str
    pr_number: int


class ReviewBatchPayload(TypedDict):
    batch_key: str
    mode: str
    monolith_root: str
    worktree_path: str
    review_dir: str
    artifact_path: str
    reassess_artifact_path: str
    state_path: str
    link_type: str
    is_explicitly_linked: bool
    linked_pair_reason: str | None
    cross_repo_dependency_summary: str | None
    authoritative_pr: BatchPrIdentity | None
    prs: list[PullRequestTarget]


def has_monolith_markers(root: Path) -> bool:
    return all((root / marker).exists() for marker in MONOLITH_ROOT_MARKERS)


def discover_monolith_root_from_siblings(start: Path) -> Path | None:
    current = start.expanduser().resolve()
    for candidate in (current, *current.parents):
        parent = candidate.parent
        if not parent.exists() or not parent.is_dir():
            continue
        matches = [
            child
            for child in parent.iterdir()
            if child.is_dir() and has_monolith_markers(child)
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise click.ClickException(
                "Could not uniquely resolve the monolith root from sibling review "
                f"worktree `{current}`. Matching roots: "
                f"{', '.join(str(match) for match in sorted(matches))}."
            )
    return None


def validate_monolith_root(root: Path) -> Path:
    missing_markers = [
        marker for marker in MONOLITH_ROOT_MARKERS if not (root / marker).exists()
    ]
    if missing_markers:
        sibling_match = discover_monolith_root_from_siblings(root)
        if sibling_match is not None:
            return sibling_match
        required_markers = ", ".join(MONOLITH_ROOT_MARKERS)
        raise click.ClickException(
            "Could not validate monolith root "
            f"`{root}`. Expected to find all required markers: {required_markers}. "
            f"Missing markers: {', '.join(sorted(missing_markers))}."
        )
    return root


def discover_monolith_root(start: Path) -> Path:
    current = start.expanduser().resolve()
    for candidate in (current, *current.parents):
        if has_monolith_markers(candidate):
            return candidate
    sibling_match = discover_monolith_root_from_siblings(current)
    if sibling_match is not None:
        return sibling_match
    required_markers = ", ".join(MONOLITH_ROOT_MARKERS)
    raise click.ClickException(
        "Could not discover monolith root from "
        f"`{current}`. Expected to find all required markers in that directory "
        f"or one of its parents: {required_markers}. Run this command from "
        "within a monolith checkout or provide an explicit monolith root."
    )


def parse_pr_url(pr_url: str) -> PullRequestTarget:
    """Parse one GitHub PR URL into monolith-local review metadata."""

    parsed = urlparse(pr_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "github.com":
        raise click.ClickException(f"Unsupported PR URL: {pr_url}")
    match = PR_PATH_PATTERN.match(parsed.path)
    if match is None:
        raise click.ClickException(f"Unsupported PR URL path: {pr_url}")

    owner = match.group("owner")
    repo_name = match.group("repo")
    repo_key = (owner, repo_name)
    if repo_key not in REPO_MAP:
        known = ", ".join(f"{known_owner}/{repo}" for known_owner, repo in sorted(REPO_MAP))
        raise click.ClickException(
            f"Unknown monolith review target `{owner}/{repo_name}` in {pr_url}. "
            f"Known targets: {known}"
        )

    alias, submodule_path = REPO_MAP[repo_key]
    pr_number = int(match.group("number"))
    return {
        "owner": owner,
        "repo": repo_name,
        "pr_number": pr_number,
        "alias": alias,
        "submodule_path": submodule_path,
        "pr_url": pr_url,
        "entry_key": f"{alias}{pr_number}",
    }


def parse_authoritative_pr(
    raw_value: str, items: list[PullRequestTarget]
) -> BatchPrIdentity:
    allowed = {(item["repo"], item["pr_number"]) for item in items}

    if raw_value.startswith("http://") or raw_value.startswith("https://"):
        parsed_target = parse_pr_url(raw_value)
        identity = (parsed_target["repo"], parsed_target["pr_number"])
    else:
        if ":" not in raw_value:
            raise click.ClickException(
                "Invalid `--authoritative-pr` value. Use repo:number or one of the "
                "batch PR URLs."
            )
        repo, pr_number_text = raw_value.split(":", 1)
        try:
            pr_number = int(pr_number_text)
        except ValueError as exc:
            raise click.ClickException(
                "Invalid `--authoritative-pr` value. PR number must be an integer."
            ) from exc
        identity = (repo, pr_number)

    if identity not in allowed:
        allowed_text = ", ".join(
            f"{repo}:{pr_number}" for repo, pr_number in sorted(allowed)
        )
        raise click.ClickException(
            "`--authoritative-pr` must point at one of the batch PRs. "
            f"Allowed values: {allowed_text}."
        )
    return {"repo": identity[0], "pr_number": identity[1]}


def reviews_root(worktree_root: Path) -> Path:
    """Return the review-artifact directory for one resolved worktree root."""

    return worktree_root / "reviews"


@click.command()
@click.option(
    "--monolith-root",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
)
@click.option(
    "--pr-url",
    "pr_urls",
    multiple=True,
    required=True,
    help="One or more GitHub PR URLs.",
)
@click.option(
    "--mode",
    type=click.Choice(sorted(ALLOWED_MODES), case_sensitive=False),
    required=True,
    help="Resolved execution mode for this batch.",
)
@click.option(
    "--linked-pair-reason",
    default=None,
    help="Required for linked cross-repo pairs; explains why the PRs must be reviewed together.",
)
@click.option(
    "--cross-repo-dependency-summary",
    default=None,
    help="Optional machine-readable summary of the cross-repo dependency.",
)
@click.option(
    "--authoritative-pr",
    default=None,
    help="Required for linked pairs; use repo:number or one of the batch PR URLs.",
)
@click.option(
    "--review-root",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help=(
        "Optional base directory for review artifacts/state. When omitted, "
        "artifacts live under <worktree>/reviews."
    ),
)
@click.option(
    "--worktree-root",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help=(
        "Optional base directory for deterministic review worktrees. When omitted, "
        "worktrees live as siblings to the monolith root."
    ),
)
def main(
    monolith_root: Path,
    pr_urls: tuple[str, ...],
    mode: str,
    linked_pair_reason: str | None,
    cross_repo_dependency_summary: str | None,
    authoritative_pr: str | None,
    review_root: Path | None,
    worktree_root: Path | None,
) -> None:
    """Resolve one deterministic review batch and print JSON."""

    if monolith_root is None:
        root = discover_monolith_root(Path.cwd())
    else:
        root = validate_monolith_root(monolith_root.expanduser().resolve())
    normalized_mode = mode.lower()
    items = [parse_pr_url(pr_url) for pr_url in pr_urls]
    seen_identities: set[tuple[str, int]] = set()
    for item in items:
        identity = (str(item["repo"]), int(item["pr_number"]))
        if identity in seen_identities:
            raise click.ClickException(
                f"Duplicate PR input: {identity[0]}#{identity[1]}"
            )
        seen_identities.add(identity)
    items.sort(key=lambda item: (str(item["alias"]), int(item["pr_number"])))

    if len(items) > 2:
        raise click.ClickException(
            "V1 only supports one PR or one explicitly linked cross-repo PR pair."
        )
    if len(items) == 2 and str(items[0]["repo"]) == str(items[1]["repo"]):
        raise click.ClickException(
            "V1 linked pairs must be cross-repo. Use a single PR batch for same-repo review."
        )

    link_type = "single_pr"
    is_explicitly_linked = False
    normalized_link_reason: str | None = None
    normalized_dependency_summary: str | None = None
    authoritative_identity: BatchPrIdentity | None = None
    if len(items) == 2:
        normalized_link_reason = (linked_pair_reason or "").strip()
        if not normalized_link_reason:
            raise click.ClickException(
                "Linked cross-repo review batches require `--linked-pair-reason`."
            )
        normalized_dependency_summary = (
            (cross_repo_dependency_summary or "").strip() or normalized_link_reason
        )
        if authoritative_pr is None or not authoritative_pr.strip():
            raise click.ClickException(
                "Linked cross-repo review batches require `--authoritative-pr`."
            )
        authoritative_identity = parse_authoritative_pr(authoritative_pr.strip(), items)
        link_type = "explicit_cross_repo_pair"
        is_explicitly_linked = True
    elif any(
        value
        for value in (
            linked_pair_reason,
            cross_repo_dependency_summary,
            authoritative_pr,
        )
    ):
        raise click.ClickException(
            "Linked-pair metadata is only valid when the batch contains two cross-repo PRs."
        )

    batch_key = "-".join(str(item["entry_key"]) for item in items)
    resolved_worktree_root = root.parent if worktree_root is None else worktree_root.expanduser().resolve()
    worktree_path = resolved_worktree_root / f"monolith-review-{batch_key}"
    if review_root is None:
        review_dir = reviews_root(worktree_path)
    else:
        review_dir = review_root.expanduser().resolve() / batch_key
    artifact_path = review_dir / f"review-{batch_key}.md"
    reassess_artifact_path = review_dir / f"review-{batch_key}-reassess.md"
    state_dir = review_dir / ".state"
    state_path = state_dir / f"review-{batch_key}.json"

    payload: ReviewBatchPayload = {
        "batch_key": batch_key,
        "mode": normalized_mode,
        "monolith_root": str(root),
        "worktree_path": str(worktree_path),
        "review_dir": str(review_dir),
        "artifact_path": str(artifact_path),
        "reassess_artifact_path": str(reassess_artifact_path),
        "state_path": str(state_path),
        "link_type": link_type,
        "is_explicitly_linked": is_explicitly_linked,
        "linked_pair_reason": normalized_link_reason,
        "cross_repo_dependency_summary": normalized_dependency_summary,
        "authoritative_pr": authoritative_identity,
        "prs": items,
    }
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
