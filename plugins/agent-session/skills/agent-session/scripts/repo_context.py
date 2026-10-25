"""What the transcript is for: the repository, its worktrees, the branch, and the PR."""

from __future__ import annotations

import re
import subprocess
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BRANCHES = {"main", "master", "develop", "dev", "staging", "production", "release", "trunk"}
# Sessions can start before the branch does (planning on the default branch), so look back a little further.
LOOKBACK_SECONDS = 2 * 24 * 60 * 60


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False, timeout=30)
    return completed.stdout.strip() if completed.returncode == 0 else ""


def is_recent(path: Path, since: float) -> bool:
    """True when a JSONL session was written to since `since`. The modification time alone is not enough (copies and
    migrations touch old files), so the last record's timestamp must agree when it has one."""
    try:
        if path.stat().st_mtime < since:
            return False
        with path.open("rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(handle.tell() - 65536, 0))
            lines = handle.read().splitlines()
    except OSError:
        return False
    for line in reversed(lines):
        match = re.search(rb'"timestamp"\s*:\s*"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
        if match:
            stamp = datetime.fromisoformat(match.group(1).decode()).replace(tzinfo=timezone.utc).timestamp()
            return stamp >= since
    return True


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
    # The commits a transcript covers: base (where the branch left the default branch) to head, oldest first.
    head: str = ""
    base: str = ""
    commits: list[str] = field(default_factory=list)
    # The branch checked out in each worktree, for harnesses that do not record the branch (Pi, Codex).
    worktree_branches: dict[str, str] = field(default_factory=dict)

    def worktrees_on_branch(self) -> set[str]:
        return {path for path, branch in self.worktree_branches.items() if branch == self.branch}

    def in_worktree_on_branch(self, cwd: str) -> bool:
        """Whether a session's directory is a worktree on the branch, or inside one. The most specific registered worktree
        containing it owns it, so a worktree nested inside one on the branch keeps its own branch."""
        owners = [path for path in self.worktree_branches if cwd == path or cwd.startswith(path.rstrip("/") + "/")] if cwd else []
        return bool(owners) and self.worktree_branches[max(owners, key=len)] == self.branch

    def in_repo(self, cwd: str) -> bool:
        """Whether a directory is inside one of this repository's worktrees."""
        return any(cwd == str(path) or cwd.startswith(str(path).rstrip("/") + "/") for path in self.worktrees) if cwd else False

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

    def evidence_pattern(self, branch: bool = True) -> re.Pattern[str] | None:
        """The markers as whole tokens (`pull/7` is not `pull/74`, `feature/x` is not `feature/x-2`), plus Claude Code's
        structured `pr-link` record for this PR. Without `branch`, only what names this repository: the PR's URL and
        record (a branch name alone is shared by every repository with a branch of that name)."""
        markers = self.evidence_markers() if branch else [marker for marker in self.evidence_markers() if marker != self.branch]
        parts = [rf"(?<![\w.-]){re.escape(marker)}(?![\w-])" for marker in markers]
        if self.pr and self.repo_slug:
            parts.append(rf'"prNumber":\s*"?{self.pr}\b[^\n]*"prRepository":\s*"{re.escape(self.repo_slug)}"')
            parts.append(rf'"prRepository":\s*"{re.escape(self.repo_slug)}"[^\n]*"prNumber":\s*"?{self.pr}\b')
        return re.compile("|".join(parts)) if parts else None

    @classmethod
    def detect(cls, cwd: Path, branch: str | None = None, pr: int | None = None) -> RepoContext:
        root = Path(_git(cwd, "rev-parse", "--show-toplevel") or cwd)
        branch = branch or _git(root, "branch", "--show-current")
        slug = parse_repo_slug(_git(root, "remote", "get-url", "origin"))
        default = _git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").removeprefix("origin/") or "main"
        porcelain = _git(root, "worktree", "list", "--porcelain").splitlines()
        worktrees = [Path(line.removeprefix("worktree ")) for line in porcelain if line.startswith("worktree ")] or [root]
        worktree_branches: dict[str, str] = {}
        current = ""
        for line in porcelain:
            if line.startswith("worktree "):
                current = line.removeprefix("worktree ")
                worktree_branches[current] = ""  # detached until a branch line says otherwise
            elif line.startswith("branch refs/heads/") and current:
                worktree_branches[current] = line.removeprefix("branch refs/heads/")
        since = 0.0
        base = _git(root, "merge-base", f"origin/{default}", branch) if branch else ""
        first = _git(root, "log", "--format=%ct", "--reverse", f"{base}..{branch}").splitlines() if base else []
        if first and first[0].isdigit():
            since = float(first[0]) - LOOKBACK_SECONDS
        else:
            since = time.time() - 14 * 24 * 60 * 60
        head = _git(root, "rev-parse", "HEAD")
        commits = _git(root, "rev-list", "--reverse", "--max-count=500", f"{base}..{head}").splitlines() if base and head else []
        return cls(root=root, branch=branch, repo_slug=slug, default_branch=default, pr=pr, worktrees=worktrees, since=since,
                   head=head, base=base, commits=commits, worktree_branches=worktree_branches)
