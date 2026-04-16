from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "monolith-review-orchestrator"
    / "skills"
    / "monolith-review-orchestrator"
    / "scripts"
    / "prepare_review_worktree.py"
)


def run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


class PrepareReviewWorktreeTests(unittest.TestCase):
    def test_repair_dirty_reuse_recreates_registered_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "monolith"
            root.mkdir(parents=True, exist_ok=True)

            self._run_git(["init"], cwd=root)
            self._run_git(["config", "user.name", "Codex Test"], cwd=root)
            self._run_git(["config", "user.email", "codex@example.com"], cwd=root)

            tracked_file = root / "README.md"
            tracked_file.write_text("root\n", encoding="utf-8")
            self._run_git(["add", "README.md"], cwd=root)
            self._run_git(["commit", "-m", "initial"], cwd=root)

            worktree_path = Path(temp_dir) / "monolith-review-bk1"
            self._run_git(
                ["worktree", "add", "--detach", str(worktree_path), "HEAD"],
                cwd=root,
            )

            dirty_file = worktree_path / "README.md"
            dirty_file.write_text("dirty\n", encoding="utf-8")

            result = run_command(
                [
                    "uv",
                    "run",
                    "--quiet",
                    "--script",
                    str(SCRIPT_PATH),
                    "--monolith-root",
                    str(root),
                    "--worktree-path",
                    str(worktree_path),
                    "--start-ref",
                    "HEAD",
                    "--repair-dirty-reuse",
                ],
                cwd=root,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["action"], "recreated_dirty")
            self.assertFalse(payload["dirty"])

            status_result = self._run_git(["status", "--short"], cwd=worktree_path)
            self.assertEqual(status_result.stdout.strip(), "")
            self.assertEqual(dirty_file.read_text(encoding="utf-8"), "root\n")

    def _run_git(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        result = run_command(["git", *args], cwd=cwd)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return result


if __name__ == "__main__":
    unittest.main()
