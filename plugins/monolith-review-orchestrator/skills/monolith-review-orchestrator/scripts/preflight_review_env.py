#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "click>=8.1,<9",
# ]
# ///
"""Fail-fast preflight checks for the monolith review orchestrator.

Why this helper exists:
- the orchestrator is monolith-local, not a generic repo skill
- review runs should fail early if the machine is missing monolith markers or
  core tools
- the rest of the workflow becomes misleading if we only discover those
  problems after worktree or GitHub steps have started

Mental model:
    "Before we reason about PRs, verify that this machine can safely run the
    monolith review harness at all."
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import click


REQUIRED_TOOLS: tuple[str, ...] = ("git", "uv")
ALLOWED_MODES: tuple[str, ...] = ("status", "review", "reassess", "post")
MONOLITH_MARKERS: tuple[str, ...] = (
    ".gitmodules",
    ".submodule-branches",
    "scripts/create_worktree.py",
    "scripts/update_submodules.py",
    "docs/github-first-branch-and-pr-conventions.md",
)


def run_command(
    cmd: list[str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def resolve_root(candidate: Path) -> Path:
    path = candidate.expanduser().resolve()
    if path.is_file():
        return path.parent
    return path


def has_monolith_markers(path: Path) -> bool:
    return all((path / marker).exists() for marker in MONOLITH_MARKERS)


def discover_monolith_root_from_siblings(start: Path) -> Path | None:
    current = resolve_root(start)
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


def discover_monolith_root(start: Path) -> Path:
    """Walk upward until we find the real monolith root markers.

    This lets the helper work even when invoked from inside the marketplace
    submodule instead of the monolith root itself.
    """

    current = resolve_root(start)
    for candidate in (current, *current.parents):
        if has_monolith_markers(candidate):
            return candidate
    sibling_match = discover_monolith_root_from_siblings(current)
    if sibling_match is not None:
        return sibling_match
    return current


@click.command()
@click.option(
    "--monolith-root",
    type=click.Path(path_type=Path, file_okay=False),
    default=discover_monolith_root(Path.cwd()),
    show_default=True,
    help="Monolith root or one of its sibling review worktrees.",
)
@click.option(
    "--require-github-auth/--no-require-github-auth",
    default=None,
    help=(
        "Override GitHub auth inference. By default, GitHub auth is required "
        "whenever a mode or PR URL is provided."
    ),
)
@click.option(
    "--mode",
    type=click.Choice(ALLOWED_MODES, case_sensitive=False),
    default=None,
    help="Resolved execution mode for the run being preflighted.",
)
@click.option(
    "--pr-url",
    "pr_urls",
    multiple=True,
    help="Repeat for each PR URL this run intends to inspect or post against.",
)
def main(
    monolith_root: Path,
    require_github_auth: bool | None,
    mode: str | None,
    pr_urls: tuple[str, ...],
) -> None:
    """Verify that the local environment can run the monolith review harness."""

    root = discover_monolith_root(monolith_root)
    errors: list[str] = []
    normalized_mode = mode.lower() if mode is not None else None
    github_required = (
        require_github_auth
        if require_github_auth is not None
        else bool(pr_urls or normalized_mode is not None)
    )

    if not (root / ".git").exists():
        errors.append(f"{root} is not a git repository.")

    missing_markers = [
        marker for marker in MONOLITH_MARKERS if not (root / marker).exists()
    ]
    if missing_markers:
        errors.append("Missing monolith markers: " + ", ".join(sorted(missing_markers)))

    for tool_name in REQUIRED_TOOLS:
        if shutil.which(tool_name) is None:
            errors.append(f"Required tool not found on PATH: {tool_name}")

    worktree_result = run_command(["git", "worktree", "list", "--porcelain"], cwd=root)
    if worktree_result.returncode != 0:
        errors.append("`git worktree list --porcelain` failed.")

    sibling_dir = root.parent
    if not sibling_dir.exists() or not sibling_dir.is_dir():
        errors.append(f"Sibling worktree parent is not usable: {sibling_dir}")

    if github_required:
        if shutil.which("gh") is None:
            errors.append("GitHub auth required but `gh` is not installed.")
        else:
            auth_result = run_command(["gh", "auth", "status"], cwd=root)
            if auth_result.returncode != 0:
                errors.append("GitHub auth required but `gh auth status` failed.")

    if errors:
        for error in errors:
            click.echo(f"ERROR: {error}", err=True)
        raise SystemExit(1)

    click.echo(f"OK: monolith root={root}")
    click.echo(f"OK: sibling worktree parent={sibling_dir}")
    if normalized_mode is not None:
        click.echo(f"OK: mode={normalized_mode}")
    if pr_urls:
        click.echo(f"OK: pr_url_count={len(pr_urls)}")
    if github_required:
        click.echo("OK: GitHub auth available")


if __name__ == "__main__":
    main()
