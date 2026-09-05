"""Exercise the shipped scope CLI against temporary Git histories only."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCOPE_SCRIPT = (
    Path(__file__).parents[1]
    / "plugins/backend-release/skills/release-manager/scripts/get_release_scope.py"
)


class ReleaseScopeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repository = Path(self.directory.name)
        # Inherited GIT_DIR/GIT_WORK_TREE must never redirect fixtures into a real checkout.
        self.environment = {
            name: value
            for name, value in os.environ.items()
            if not name.startswith("GIT_")
        }
        self.environment.update(
            {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        )
        self.get_git_output("init", "-b", "master")
        self.get_git_output("config", "user.name", "Release scope test")
        self.get_git_output("config", "user.email", "release-scope@example.invalid")
        self.get_git_output("config", "core.hooksPath", os.devnull)
        self.add_commit("initial")

    def get_git_output(self, *arguments):
        return subprocess.check_output(
            ["git", *arguments],
            cwd=self.repository,
            env=self.environment,
            text=True,
            stderr=subprocess.PIPE,
        ).strip()

    def add_commit(self, name):
        (self.repository / name).write_text(name)
        self.get_git_output("add", name)
        self.get_git_output("commit", "-m", name)
        return self.get_git_output("rev-parse", "HEAD")

    def get_scope_result(self, base, source):
        return subprocess.run(
            [sys.executable, str(SCOPE_SCRIPT), base, source],
            cwd=self.repository,
            env=self.environment,
            text=True,
            capture_output=True,
        )

    def get_scope(self, base, source):
        result = self.get_scope_result(base, source)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_late_release_commits_remain_pending_and_publication_uses_merged_sha(self):
        base_sha = self.get_git_output("rev-parse", "master")
        self.get_git_output("checkout", "-b", "release")
        candidate_sha = self.add_commit("early-change")
        captured_scope = self.get_scope("master", "release")
        self.assertEqual(captured_scope["source_only_commits"], [candidate_sha])

        self.get_git_output("checkout", "-b", "candidate", base_sha)
        self.get_git_output(
            "merge", "--no-ff", candidate_sha, "-m", "Capture candidate"
        )
        self.get_git_output("checkout", "release")
        late_sha = self.add_commit("late-change-before-production-merge")
        self.get_git_output("checkout", "master")
        self.get_git_output("merge", "--no-ff", "candidate", "-m", "Release PR merge")
        release_commit_sha = self.get_git_output("rev-parse", "HEAD")
        self.assertEqual(
            self.get_scope("master", "release")["source_only_commits"], [late_sha]
        )
        self.assertEqual(self.get_scope(base_sha, candidate_sha), captured_scope)

        self.add_commit("unrelated-later-master-change")
        self.get_git_output("tag", "test-release", release_commit_sha)
        self.assertEqual(
            self.get_git_output("rev-parse", "test-release^{commit}"),
            release_commit_sha,
        )
        self.assertNotEqual(
            self.get_git_output("rev-parse", "test-release^{commit}"),
            self.get_git_output("rev-parse", "master"),
        )
        self.assertEqual(
            self.get_scope(release_commit_sha, late_sha)["source_only_commits"],
            [late_sha],
        )

    def test_tree_and_ancestry_evidence_do_not_claim_patch_novelty(self):
        base_sha = self.get_git_output("rev-parse", "HEAD")
        self.assertFalse(self.get_scope(base_sha, base_sha)["tree_changed"])
        self.get_git_output("checkout", "-b", "release")
        feature_sha = self.add_commit("feature")
        self.get_git_output("checkout", "master")
        self.add_commit("temporary-master-change")
        self.get_git_output("revert", "--no-edit", "HEAD")
        self.get_git_output("cherry-pick", feature_sha)
        scope = self.get_scope("master", "release")
        self.assertFalse(scope["tree_changed"])
        self.assertEqual(scope["source_only_commits"], [feature_sha])
        self.get_git_output("checkout", "release")
        self.get_git_output("revert", "--no-edit", feature_sha)
        reverted_scope = self.get_scope(base_sha, "release")
        self.assertFalse(reverted_scope["tree_changed"])
        self.assertEqual(len(reverted_scope["source_only_commits"]), 2)

    def test_incomplete_or_invalid_history_fails_without_scope_output(self):
        for invalid_revision in ["does-not-exist", "--all"]:
            result = self.get_scope_result(invalid_revision, "master")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
        self.get_git_output("checkout", "--orphan", "unrelated")
        self.add_commit("unrelated-root")
        result = self.get_scope_result("master", "unrelated")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("common history", result.stderr)
        (self.repository / ".git/shallow").write_text(
            self.get_git_output("rev-parse", "HEAD") + "\n"
        )
        result = self.get_scope_result("master", "unrelated")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Full Git history", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
