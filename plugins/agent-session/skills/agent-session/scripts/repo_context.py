"""What the transcript is for: the repository, its worktrees, the branch, and the PR."""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BRANCHES = {"main", "master", "develop", "dev", "staging", "production", "release", "trunk"}
# Sessions can start before the branch does (planning on the default branch), so look back a little further.
LOOKBACK_SECONDS = 2 * 24 * 60 * 60


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False, timeout=30)
    return completed.stdout.strip() if completed.returncode == 0 else ""


def parse_repo_slug(remote_url: str) -> str:
    match = re.search(r"github\.com[:/](?P<slug>[^/\s]+/[^/\s]+?)(?:\.git)?/?$", remote_url.strip())
    return match.group("slug") if match else ""


@dataclass
class RepoContext:
    root: Path
    branch: str
    repo_slug: str = ""
    default_branch: str = "main"
    pr: int | None = None
    worktrees: list[Path] = field(default_factory=list)
    since: float = 0.0

    @property
    def repo_name(self) -> str:
        return self.repo_slug.split("/")[-1] if self.repo_slug else self.root.name

    def evidence_markers(self) -> list[str]:
        """Text that ties a transcript line to this work: the branch name and the PR's URL."""
        markers = []
        if self.branch and self.branch not in DEFAULT_BRANCHES and len(self.branch) >= 4:
            markers.append(self.branch)
        if self.pr and self.repo_slug:
            markers.append(f"github.com/{self.repo_slug}/pull/{self.pr}")
        return markers

    @classmethod
    def detect(cls, cwd: Path, branch: str | None = None, pr: int | None = None) -> RepoContext:
        root = Path(_git(cwd, "rev-parse", "--show-toplevel") or cwd)
        branch = branch or _git(root, "branch", "--show-current")
        slug = parse_repo_slug(_git(root, "remote", "get-url", "origin"))
        default = _git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").removeprefix("origin/") or "main"
        worktrees = [Path(line.removeprefix("worktree ")) for line in _git(root, "worktree", "list", "--porcelain").splitlines()
                     if line.startswith("worktree ")] or [root]
        since = 0.0
        base = _git(root, "merge-base", f"origin/{default}", branch) if branch else ""
        first = _git(root, "log", "--format=%ct", "--reverse", f"{base}..{branch}").splitlines() if base else []
        if first and first[0].isdigit():
            since = float(first[0]) - LOOKBACK_SECONDS
        else:
            since = time.time() - 14 * 24 * 60 * 60
        return cls(root=root, branch=branch, repo_slug=slug, default_branch=default, pr=pr, worktrees=worktrees, since=since)
