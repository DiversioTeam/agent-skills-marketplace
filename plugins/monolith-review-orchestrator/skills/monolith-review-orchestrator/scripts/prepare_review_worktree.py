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
import shutil
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


def create_worktree(monolith_root: Path, target: Path, start_ref: str) -> None:
    """Create one detached worktree at the target path."""

    create_result = run_command(
        ["git", "worktree", "add", "--detach", str(target), start_ref],
        cwd=monolith_root,
    )
    if create_result.returncode != 0:
        raise click.ClickException(
            create_result.stderr.strip() or f"Failed to create {target}"
        )


def remove_worktree(monolith_root: Path, target: Path) -> None:
    """Force-remove one registered worktree and clean up leftover files.

    Why this exists:
    deterministic worker-owned review worktrees may become dirty if a previous
    automation run crashes or is interrupted mid-flight. In that case the safest
    recovery is to throw away the worker-owned checkout and recreate it from the
    authoritative monolith state, while keeping review artifacts outside the
    worktree.
    """

    remove_result = run_command(
        ["git", "worktree", "remove", "--force", str(target)],
        cwd=monolith_root,
    )
    if remove_result.returncode != 0:
        raise click.ClickException(
            remove_result.stderr.strip() or f"Failed to remove dirty worktree {target}"
        )
    if target.exists():
        shutil.rmtree(target)


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
    "--submodule-path",
    "submodule_paths",
    multiple=True,
    help="Repeat for each review-batch submodule path to initialize.",
)
@click.option(
    "--allow-dirty-reuse/--no-allow-dirty-reuse", default=False, show_default=True
)
@click.option(
    "--repair-dirty-reuse/--no-repair-dirty-reuse", default=False, show_default=True
)
def main(
    monolith_root: Path,
    worktree_path: Path,
    start_ref: str,
    submodule_paths: tuple[str, ...],
    allow_dirty_reuse: bool,
    repair_dirty_reuse: bool,
) -> None:
    """Create or reuse one deterministic monolith review worktree."""

    root = monolith_root.expanduser().resolve()
    target = worktree_path.expanduser().resolve()
    registered_worktrees = list_worktrees(root)
    unique_submodule_paths = tuple(dict.fromkeys(submodule_paths))

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
            if repair_dirty_reuse:
                remove_worktree(root, target)
                create_worktree(root, target, start_ref)
                action = "recreated_dirty"
                dirty = False
            else:
                raise click.ClickException(
                    f"{target} has local changes and dirty reuse was not allowed."
                )
        else:
            action = "reused"
    else:
        create_worktree(root, target, start_ref)
        action = "created"
        dirty = False

    if target.exists() and action == "recreated_dirty":
        # The helper removed and recreated the worker-owned worktree above.
        # Refresh the registered worktree set only if future logic starts using
        # it again inside this command.
        registered_worktrees = list_worktrees(root)
        if target not in registered_worktrees:
            raise click.ClickException(
                f"{target} was recreated but is not registered as a git worktree."
            )

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

    # Report final dirtiness after submodule init too. A clean create should
    # usually stay clean, but surfacing the real post-init state makes the
    # helper easier to trust when something unusual happens.
    dirty = worktree_is_dirty(target)

    payload = {
        "action": action,
        "worktree_path": str(target),
        "dirty": dirty,
        "start_ref": start_ref,
        "submodule_paths": list(unique_submodule_paths),
    }
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
