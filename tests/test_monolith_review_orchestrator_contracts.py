from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_STATE_PATH = (
    REPO_ROOT
    / "plugins"
    / "monolith-review-orchestrator"
    / "skills"
    / "monolith-review-orchestrator"
    / "scripts"
    / "review_state.py"
)
PREPARE_WORKTREE_PATH = (
    REPO_ROOT
    / "plugins"
    / "monolith-review-orchestrator"
    / "skills"
    / "monolith-review-orchestrator"
    / "scripts"
    / "prepare_review_worktree.py"
)


def build_fake_click() -> ModuleType:
    fake_click = ModuleType("click")

    class FakeClickException(Exception):
        pass

    def fake_command(*_args: object, **_kwargs: object):
        def decorator(function: object) -> object:
            return function

        return decorator

    def fake_option(*_args: object, **_kwargs: object):
        def decorator(function: object) -> object:
            return function

        return decorator

    def fake_group(*_args: object, **_kwargs: object):
        def decorator(function: object) -> object:
            function.command = fake_command  # type: ignore[attr-defined]
            return function

        return decorator

    def fake_echo(*_args: object, **_kwargs: object) -> None:
        return None

    class FakePath:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

    class FakeChoice:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

    fake_click.ClickException = FakeClickException
    fake_click.command = fake_command
    fake_click.option = fake_option
    fake_click.group = fake_group
    fake_click.echo = fake_echo
    fake_click.Path = FakePath
    fake_click.Choice = FakeChoice
    return fake_click


def load_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")

    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {"click": build_fake_click(), spec.name: module},
        clear=False,
    ):
        spec.loader.exec_module(module)
    return module


REVIEW_STATE = load_module("review_state", REVIEW_STATE_PATH)
PREPARE_WORKTREE = load_module("prepare_review_worktree", PREPARE_WORKTREE_PATH)


class ReviewStateContractTests(unittest.TestCase):
    def test_validate_v1_batch_scope_accepts_agent_skills_marketplace(self) -> None:
        REVIEW_STATE.validate_v1_batch_scope(
            [{"repo": "agent-skills-marketplace", "pr_number": 59}],
            "test identities",
        )

    def test_backend_handoff_pr_url_requires_exact_pr_number(self) -> None:
        REVIEW_STATE.validate_backend_handoff_pr_url(
            "https://github.com/DiversioTeam/Django4Lyfe/pull/1/files",
            "Django4Lyfe",
            1,
        )

        with self.assertRaises(REVIEW_STATE.click.ClickException) as exc_info:
            REVIEW_STATE.validate_backend_handoff_pr_url(
                "https://github.com/DiversioTeam/Django4Lyfe/pull/12",
                "Django4Lyfe",
                1,
            )

        self.assertIn("Django4Lyfe#1", str(exc_info.exception))

    def test_parse_live_pr_context_artifact_rejects_wrong_source(self) -> None:
        payload = {
            "source": "hand_written_json",
            "pull_requests": [
                {
                    "pull_request": {
                        "repo": "Django4Lyfe",
                        "pr_number": 1,
                        "url": "https://github.com/DiversioTeam/Django4Lyfe/pull/1",
                        "base_ref_name": "main",
                        "head_ref_oid": "abc123",
                        "state": "OPEN",
                        "is_draft": False,
                    }
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_path = Path(temp_dir) / "pr-context.json"
            artifact_path.write_text(json.dumps(payload))

            with self.assertRaises(REVIEW_STATE.click.ClickException) as exc_info:
                REVIEW_STATE.parse_live_pr_context_artifact(
                    artifact_path,
                    {("Django4Lyfe", 1)},
                )

        self.assertIn("fetch_review_threads.py", str(exc_info.exception))


class PrepareReviewWorktreeContractTests(unittest.TestCase):
    def test_worktree_is_clean_when_only_review_target_sha_differs(self) -> None:
        worktree_path = Path("/tmp/monolith-review-batch")

        def fake_run_command(cmd: list[str], cwd: Path | None = None) -> object:
            command_key = tuple(cmd)
            if command_key == (
                "git",
                "status",
                "--short",
                "--ignore-submodules=none",
            ) and cwd == worktree_path:
                return PREPARE_WORKTREE.subprocess.CompletedProcess(
                    cmd, 0, stdout=" M agent-skills-marketplace\n", stderr=""
                )
            if command_key == (
                "git",
                "status",
                "--short",
                "--ignore-submodules=none",
            ) and cwd == worktree_path / "agent-skills-marketplace":
                return PREPARE_WORKTREE.subprocess.CompletedProcess(
                    cmd, 0, stdout="", stderr=""
                )
            raise AssertionError(f"Unexpected command: cmd={cmd!r} cwd={cwd!r}")

        with patch.object(
            PREPARE_WORKTREE,
            "run_command",
            side_effect=fake_run_command,
        ):
            dirty = PREPARE_WORKTREE.worktree_is_dirty(
                worktree_path, {"agent-skills-marketplace"}
            )

        self.assertFalse(dirty)

    def test_worktree_is_dirty_when_review_target_has_local_edits(self) -> None:
        worktree_path = Path("/tmp/monolith-review-batch")

        def fake_run_command(cmd: list[str], cwd: Path | None = None) -> object:
            command_key = tuple(cmd)
            if command_key == (
                "git",
                "status",
                "--short",
                "--ignore-submodules=none",
            ) and cwd == worktree_path:
                return PREPARE_WORKTREE.subprocess.CompletedProcess(
                    cmd, 0, stdout=" M agent-skills-marketplace\n", stderr=""
                )
            if command_key == (
                "git",
                "status",
                "--short",
                "--ignore-submodules=none",
            ) and cwd == worktree_path / "agent-skills-marketplace":
                return PREPARE_WORKTREE.subprocess.CompletedProcess(
                    cmd, 0, stdout=" M plugins/example.py\n", stderr=""
                )
            raise AssertionError(f"Unexpected command: cmd={cmd!r} cwd={cwd!r}")

        with patch.object(
            PREPARE_WORKTREE,
            "run_command",
            side_effect=fake_run_command,
        ):
            dirty = PREPARE_WORKTREE.worktree_is_dirty(
                worktree_path, {"agent-skills-marketplace"}
            )

        self.assertTrue(dirty)

    def test_infer_pr_remote_name_does_not_treat_branch_prefix_as_remote(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch.object(
                PREPARE_WORKTREE,
                "list_remotes",
                return_value=["origin"],
            ):
                remote_name = PREPARE_WORKTREE.infer_pr_remote_name(
                    repo_path,
                    "feature/foo",
                )

        self.assertEqual(remote_name, "origin")

    def test_infer_pr_remote_name_uses_actual_remote_prefix_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            with patch.object(
                PREPARE_WORKTREE,
                "list_remotes",
                return_value=["origin", "upstream"],
            ):
                remote_name = PREPARE_WORKTREE.infer_pr_remote_name(
                    repo_path,
                    "upstream/feature/foo",
                )

        self.assertEqual(remote_name, "upstream")


if __name__ == "__main__":
    unittest.main()
