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
REPO_MAP: dict[str, tuple[str, str | None]] = {
    "monolith": ("mono", None),
    "Django4Lyfe": ("bk", "backend"),
    "Diversio-Frontend": ("fe", "frontend"),
    "Optimo-Frontend": ("of", "optimo-frontend"),
    "diversio-ds": ("ds", "design-system"),
    "infrastructure": ("infra", "infrastructure"),
    "diversio-serverless": ("sls", "diversio-serverless"),
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


class ReviewBatchPayload(TypedDict):
    batch_key: str
    monolith_root: str
    worktree_path: str
    review_dir: str
    artifact_path: str
    reassess_artifact_path: str
    state_path: str
    prs: list[PullRequestTarget]


def validate_monolith_root(root: Path) -> Path:
    missing_markers = [
        marker for marker in MONOLITH_ROOT_MARKERS if not (root / marker).exists()
    ]
    if missing_markers:
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
        if all((candidate / marker).exists() for marker in MONOLITH_ROOT_MARKERS):
            return candidate
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

    repo_name = match.group("repo")
    if repo_name not in REPO_MAP:
        known = ", ".join(sorted(REPO_MAP))
        raise click.ClickException(
            f"Unknown repo `{repo_name}` in {pr_url}. Known repos: {known}"
        )

    alias, submodule_path = REPO_MAP[repo_name]
    pr_number = int(match.group("number"))
    return {
        "owner": match.group("owner"),
        "repo": repo_name,
        "pr_number": pr_number,
        "alias": alias,
        "submodule_path": submodule_path,
        "pr_url": pr_url,
        "entry_key": f"{alias}{pr_number}",
    }


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
    review_root: Path | None,
    worktree_root: Path | None,
) -> None:
    """Resolve one deterministic review batch and print JSON."""

    if monolith_root is None:
        root = discover_monolith_root(Path.cwd())
    else:
        root = validate_monolith_root(monolith_root.expanduser().resolve())
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
        "monolith_root": str(root),
        "worktree_path": str(worktree_path),
        "review_dir": str(review_dir),
        "artifact_path": str(artifact_path),
        "reassess_artifact_path": str(reassess_artifact_path),
        "state_path": str(state_path),
        "prs": items,
    }
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
