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

Mental model:
    "Give me exactly one detached review worktree for this batch, or reuse the
    existing one if it is already registered and safe."
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import click


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


@click.command()
@click.option(
    "--monolith-root", type=click.Path(path_type=Path, file_okay=False), required=True
)
@click.option(
    "--worktree-path", type=click.Path(path_type=Path, file_okay=False), required=True
)
@click.option("--start-ref", default="HEAD", show_default=True)
@click.option(
    "--allow-dirty-reuse/--no-allow-dirty-reuse", default=False, show_default=True
)
def main(
    monolith_root: Path,
    worktree_path: Path,
    start_ref: str,
    allow_dirty_reuse: bool,
) -> None:
    """Create or reuse one deterministic monolith review worktree."""

    root = monolith_root.expanduser().resolve()
    target = worktree_path.expanduser().resolve()
    registered_worktrees = list_worktrees(root)

    action: str
    if target.exists():
        if target not in registered_worktrees:
            raise click.ClickException(
                f"{target} exists but is not a registered git worktree."
            )
        # Reused worktrees are the risky case: we should reject dirtiness before
        # running any submodule command that could mutate local state.
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
        dirty = False

    submodule_result = run_command(
        ["git", "submodule", "update", "--init", "--recursive"],
        cwd=target,
    )
    if submodule_result.returncode != 0:
        raise click.ClickException(
            submodule_result.stderr.strip() or "Failed to initialize submodules."
        )

    # Report final dirtiness after submodule init too. A clean create should
    # usually stay clean, but surfacing the real post-init state makes the
    # helper easier to trust when something unusual happens.
    dirty = worktree_is_dirty(target)

    payload = {
        "action": action,
        "worktree_path": str(target),
        "dirty": dirty,
        "start_ref": start_ref,
    }
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
