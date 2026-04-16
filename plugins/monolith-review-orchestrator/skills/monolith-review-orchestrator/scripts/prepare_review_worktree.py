#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "click>=8.1,<9",
# ]
# ///
"""Prepare or reuse one deterministic monolith review worktree.

Why this helper exists:
- `scripts/create_worktree.py` is interactive and aimed at humans
- the review harness needs deterministic automation
- review prep should stay narrow and avoid mutating unrelated submodules
- deep review must fail closed if the local code is not on the exact PR head

Mental model:
    "Give me exactly one detached review worktree for this batch, or reuse the
    existing one if it is already registered and safe. Then put each review
    submodule on the exact PR head SHA we claim to review."
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TypedDict

import click


class ReviewTarget(TypedDict):
    submodule_path: str
    pr_number: int
    expected_head_sha: str
    preferred_ref: str | None


def run_command(
    cmd: list[str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def list_worktrees(monolith_root: Path) -> set[Path]:
    """Return the set of paths Git currently recognizes as worktrees."""

    result = run_command(["git", "worktree", "list", "--porcelain"], cwd=monolith_root)
    if result.returncode != 0:
        raise click.ClickException(result.stderr.strip() or "Failed to list worktrees.")
    paths: set[Path] = set()
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            paths.add(Path(line.removeprefix("worktree ").strip()).resolve())
    return paths


def worktree_is_dirty(worktree_path: Path) -> bool:
    """Return whether the target worktree currently has local changes."""

    result = run_command(["git", "status", "--short"], cwd=worktree_path)
    if result.returncode != 0:
        raise click.ClickException(
            result.stderr.strip()
            or f"Failed to inspect worktree status for {worktree_path}"
        )
    return bool(result.stdout.strip())


def parse_review_target(raw_value: str) -> ReviewTarget:
    parts = raw_value.split(":", 3)
    if len(parts) not in {3, 4}:
        raise click.ClickException(
            "Invalid `--review-target` value. Use "
            "submodule_path:pr_number:expected_head_sha[:preferred_ref]."
        )

    submodule_path = parts[0].strip()
    pr_number_text = parts[1].strip()
    expected_head_sha = parts[2].strip()
    preferred_ref = parts[3].strip() if len(parts) == 4 and parts[3].strip() else None

    if not submodule_path or not expected_head_sha:
        raise click.ClickException(
            "Invalid `--review-target` value. `submodule_path` and "
            "`expected_head_sha` must be non-empty."
        )

    try:
        pr_number = int(pr_number_text)
    except ValueError as exc:
        raise click.ClickException(
            "Invalid `--review-target` value. `pr_number` must be an integer."
        ) from exc
    if isinstance(pr_number, bool) or pr_number < 1:
        raise click.ClickException(
            "Invalid `--review-target` value. `pr_number` must be a positive integer."
        )

    return {
        "submodule_path": submodule_path,
        "pr_number": pr_number,
        "expected_head_sha": expected_head_sha,
        "preferred_ref": preferred_ref,
    }


def ensure_unique_review_targets(review_targets: list[ReviewTarget]) -> list[ReviewTarget]:
    seen_targets: dict[str, ReviewTarget] = {}
    for review_target in review_targets:
        submodule_path = review_target["submodule_path"]
        existing_target = seen_targets.get(submodule_path)
        if existing_target is None:
            seen_targets[submodule_path] = review_target
            continue
        raise click.ClickException(
            "Conflicting `--review-target` values for submodule "
            f"`{submodule_path}`. Existing target expects "
            f"PR #{existing_target['pr_number']} at `{existing_target['expected_head_sha']}`"
            f"{' via ' + existing_target['preferred_ref'] if existing_target.get('preferred_ref') else ''}; "
            f"new target expects PR #{review_target['pr_number']} at "
            f"`{review_target['expected_head_sha']}`"
            f"{' via ' + review_target['preferred_ref'] if review_target.get('preferred_ref') else ''}."
        )
    return review_targets


def rev_parse_commit(repo_path: Path, ref: str) -> str | None:
    result = run_command(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=repo_path)
    if result.returncode != 0:
        return None
    resolved = result.stdout.strip()
    return resolved or None


def list_remotes(repo_path: Path) -> list[str]:
    result = run_command(["git", "remote"], cwd=repo_path)
    if result.returncode != 0:
        raise click.ClickException(
            result.stderr.strip() or f"Failed to list remotes for `{repo_path}`."
        )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def infer_pr_remote_name(repo_path: Path, preferred_ref: str | None) -> str:
    remotes = list_remotes(repo_path)
    if preferred_ref is not None:
        if preferred_ref.startswith("refs/remotes/"):
            parts = preferred_ref.split("/", 3)
            if len(parts) >= 4 and parts[2] in remotes:
                return parts[2]
        if "/" in preferred_ref and not preferred_ref.startswith("refs/"):
            candidate_remote = preferred_ref.split("/", 1)[0]
            if candidate_remote in remotes:
                return candidate_remote

    if "origin" in remotes:
        return "origin"
    if len(remotes) == 1:
        return remotes[0]
    raise click.ClickException(
        "Could not infer which remote should serve GitHub pull refs for "
        f"`{repo_path}`. Pass `preferred_ref` with an explicit remote-qualified "
        "name such as `origin/branch`."
    )


def checkout_exact_review_ref(worktree_path: Path, review_target: ReviewTarget) -> dict[str, object]:
    submodule_root = worktree_path / review_target["submodule_path"]
    if not submodule_root.exists():
        raise click.ClickException(
            f"Expected initialized submodule path `{submodule_root}` does not exist."
        )

    fetch_all_result = run_command(["git", "fetch", "--all", "--prune"], cwd=submodule_root)
    if fetch_all_result.returncode != 0:
        raise click.ClickException(
            fetch_all_result.stderr.strip()
            or f"Failed to fetch remotes for `{review_target['submodule_path']}`."
        )

    expected_head_sha = review_target["expected_head_sha"]
    preferred_ref = review_target.get("preferred_ref")
    checkout_ref: str | None = None
    checkout_source = "unknown"

    candidate_refs: list[str] = []
    if preferred_ref is not None:
        candidate_refs.extend(
            [
                preferred_ref,
                f"origin/{preferred_ref}",
                f"refs/remotes/origin/{preferred_ref}",
            ]
        )

    for candidate_ref in candidate_refs:
        resolved_sha = rev_parse_commit(submodule_root, candidate_ref)
        if resolved_sha == expected_head_sha:
            checkout_ref = candidate_ref
            checkout_source = "preferred_ref"
            break

    if checkout_ref is None:
        pr_remote_name = infer_pr_remote_name(submodule_root, preferred_ref)
        fetch_pr_result = run_command(
            ["git", "fetch", pr_remote_name, f"pull/{review_target['pr_number']}/head"],
            cwd=submodule_root,
        )
        if fetch_pr_result.returncode != 0:
            raise click.ClickException(
                fetch_pr_result.stderr.strip()
                or (
                    "Failed to fetch exact PR head for "
                    f"`{review_target['submodule_path']}` via "
                    f"`{pr_remote_name}:pull/{review_target['pr_number']}/head`."
                )
            )
        fetch_head_sha = rev_parse_commit(submodule_root, "FETCH_HEAD")
        if fetch_head_sha != expected_head_sha:
            raise click.ClickException(
                f"`{review_target['submodule_path']}` fetched PR head SHA "
                f"`{fetch_head_sha}` but expected `{expected_head_sha}`."
            )
        checkout_ref = "FETCH_HEAD"
        checkout_source = f"{pr_remote_name}_pull_ref"

    checkout_result = run_command(["git", "switch", "--detach", checkout_ref], cwd=submodule_root)
    if checkout_result.returncode != 0:
        raise click.ClickException(
            checkout_result.stderr.strip()
            or f"Failed to detach `{review_target['submodule_path']}` at `{checkout_ref}`."
        )

    actual_head_sha = rev_parse_commit(submodule_root, "HEAD")
    if actual_head_sha != expected_head_sha:
        raise click.ClickException(
            f"`{review_target['submodule_path']}` checked out `{actual_head_sha}` but "
            f"expected `{expected_head_sha}`."
        )

    return {
        "submodule_path": review_target["submodule_path"],
        "pr_number": review_target["pr_number"],
        "preferred_ref": preferred_ref,
        "expected_head_sha": expected_head_sha,
        "actual_head_sha": actual_head_sha,
        "checkout_ref": checkout_ref,
        "checkout_source": checkout_source,
        "status": "matched",
    }


@click.command()
@click.option(
    "--monolith-root", type=click.Path(path_type=Path, file_okay=False), required=True
)
@click.option(
    "--worktree-path", type=click.Path(path_type=Path, file_okay=False), required=True
)
@click.option("--start-ref", default="HEAD", show_default=True)
@click.option(
    "--submodule-path",
    "submodule_paths",
    multiple=True,
    help="Repeat for each review-batch submodule path to initialize.",
)
@click.option(
    "--review-target",
    "review_targets",
    multiple=True,
    help=(
        "Repeat as submodule_path:pr_number:expected_head_sha[:preferred_ref] "
        "to fetch and detach the exact PR head under review."
    ),
)
@click.option(
    "--allow-dirty-reuse/--no-allow-dirty-reuse", default=False, show_default=True
)
def main(
    monolith_root: Path,
    worktree_path: Path,
    start_ref: str,
    submodule_paths: tuple[str, ...],
    review_targets: tuple[str, ...],
    allow_dirty_reuse: bool,
) -> None:
    """Create or reuse one deterministic monolith review worktree."""

    root = monolith_root.expanduser().resolve()
    target = worktree_path.expanduser().resolve()
    registered_worktrees = list_worktrees(root)
    parsed_review_targets = ensure_unique_review_targets(
        [parse_review_target(raw_value) for raw_value in review_targets]
    )
    target_submodule_paths = [entry["submodule_path"] for entry in parsed_review_targets]
    unique_submodule_paths = tuple(dict.fromkeys((*submodule_paths, *target_submodule_paths)))

    action: str
    if target.exists():
        if target not in registered_worktrees:
            raise click.ClickException(
                f"{target} exists but is not a registered git worktree."
            )
        dirty = worktree_is_dirty(target)
        if dirty and not allow_dirty_reuse:
            raise click.ClickException(
                f"{target} has local changes and dirty reuse was not allowed."
            )
        action = "reused"
    else:
        create_result = run_command(
            ["git", "worktree", "add", "--detach", str(target), start_ref],
            cwd=root,
        )
        if create_result.returncode != 0:
            raise click.ClickException(
                create_result.stderr.strip() or f"Failed to create {target}"
            )
        action = "created"

    if unique_submodule_paths:
        submodule_result = run_command(
            ["git", "submodule", "update", "--init", "--", *unique_submodule_paths],
            cwd=target,
        )
        if submodule_result.returncode != 0:
            raise click.ClickException(
                submodule_result.stderr.strip()
                or "Failed to initialize review-batch submodules."
            )

    review_target_results = [
        checkout_exact_review_ref(target, review_target)
        for review_target in parsed_review_targets
    ]
    dirty = worktree_is_dirty(target)

    payload = {
        "action": action,
        "worktree_path": str(target),
        "dirty": dirty,
        "start_ref": start_ref,
        "submodule_paths": list(unique_submodule_paths),
        "review_targets": review_target_results,
    }
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
