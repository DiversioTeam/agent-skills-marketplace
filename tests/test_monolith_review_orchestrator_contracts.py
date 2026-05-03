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

    def test_read_json_synthesizes_legacy_summary_for_schema_two_findings(self) -> None:
        payload = {
            "schema_version": 2,
            "batch_key": "asm-59",
            "created_at_utc": "2026-04-24T00:00:00Z",
            "updated_at_utc": "2026-04-24T00:00:00Z",
            "worktree_path": "/tmp/monolith-review-asm-59",
            "artifact_path": "/tmp/monolith-review-asm-59/review.md",
            "posting_status": "not_posted",
            "prs": [{"repo": "agent-skills-marketplace", "pr_number": 59}],
            "passes": [
                {
                    "artifact_path": "/tmp/monolith-review-asm-59/review.md",
                    "posting_status": "not_posted",
                    "recorded_at_utc": "2026-04-24T00:00:00Z",
                    "review_pass_number": 1,
                    "entries": [
                        {
                            "repo": "agent-skills-marketplace",
                            "pr_number": 59,
                            "base_branch": "main",
                            "head_sha": "6557e6c",
                            "merge_base": "9d1c6e1c",
                        }
                    ],
                    "findings": {
                        "new": [
                            {
                                "id": "legacy-finding-without-summary",
                                "path": "plugins/example.py",
                            }
                        ],
                        "carried_forward": [],
                        "resolved": [],
                        "moot": [],
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "state.json"
            state_path.write_text(json.dumps(payload), encoding="utf-8")

            normalized = REVIEW_STATE.read_json(state_path)

        finding = normalized["passes"][0]["findings"]["new"][0]
        self.assertEqual(
            finding["summary"],
            "Legacy finding `legacy-finding-without-summary` (plugins/example.py)",
        )
        self.assertEqual(normalized["schema_version"], REVIEW_STATE.SCHEMA_VERSION)

    def test_read_json_accepts_legacy_schema_two_review_pass_without_new_proof_fields(
        self,
    ) -> None:
        payload = {
            "schema_version": 2,
            "batch_key": "asm-59",
            "created_at_utc": "2026-04-24T00:00:00Z",
            "updated_at_utc": "2026-04-24T00:00:00Z",
            "worktree_path": "/tmp/monolith-review-asm-59",
            "artifact_path": "/tmp/monolith-review-asm-59/review.md",
            "posting_status": "not_posted",
            "prs": [{"repo": "agent-skills-marketplace", "pr_number": 59}],
            "passes": [
                {
                    "artifact_path": "/tmp/monolith-review-asm-59/review.md",
                    "posting_status": "not_posted",
                    "recorded_at_utc": "2026-04-24T00:00:00Z",
                    "review_pass_number": 1,
                    "mode": "review",
                    "recommendation": "comment",
                    "scope_summary": "Legacy schema-2 review pass.",
                    "entries": [
                        {
                            "repo": "agent-skills-marketplace",
                            "pr_number": 59,
                            "base_branch": "main",
                            "head_sha": "2769963",
                            "merge_base": "6557e6c",
                        }
                    ],
                    "findings": {
                        "new": [],
                        "carried_forward": [],
                        "resolved": [],
                        "moot": [],
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "state.json"
            state_path.write_text(json.dumps(payload), encoding="utf-8")

            normalized = REVIEW_STATE.read_json(state_path)

        review_pass = normalized["passes"][0]
        self.assertEqual(review_pass["mode"], "review")
        self.assertTrue(review_pass["no_findings_after_full_review"])
        self.assertTrue(review_pass["no_author_claims"])

    def test_read_json_accepts_legacy_schema_two_status_pass_without_comment_context(
        self,
    ) -> None:
        payload = {
            "schema_version": 2,
            "batch_key": "asm-59",
            "created_at_utc": "2026-04-27T00:00:00Z",
            "updated_at_utc": "2026-04-27T00:00:00Z",
            "worktree_path": "/tmp/monolith-review-asm-59",
            "artifact_path": "/tmp/monolith-review-asm-59/review.md",
            "posting_status": "not_posted",
            "prs": [{"repo": "agent-skills-marketplace", "pr_number": 59}],
            "passes": [
                {
                    "artifact_path": "/tmp/monolith-review-asm-59/review.md",
                    "posting_status": "not_posted",
                    "recorded_at_utc": "2026-04-27T00:00:00Z",
                    "review_pass_number": 1,
                    "mode": "status",
                    "recommendation": "comment",
                    "scope_summary": "Legacy schema-2 status pass.",
                    "entries": [
                        {
                            "repo": "agent-skills-marketplace",
                            "pr_number": 59,
                            "base_branch": "main",
                            "head_sha": "b8c36a1",
                            "merge_base": "6557e6c",
                        }
                    ],
                    "findings": {
                        "new": [],
                        "carried_forward": [],
                        "resolved": [],
                        "moot": [],
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "state.json"
            state_path.write_text(json.dumps(payload), encoding="utf-8")

            normalized = REVIEW_STATE.read_json(state_path)

        review_pass = normalized["passes"][0]
        self.assertEqual(review_pass["mode"], "status")
        self.assertNotIn("comment_context", review_pass)

    def test_normalize_findings_still_requires_summary_for_current_writes(self) -> None:
        with self.assertRaises(REVIEW_STATE.click.ClickException) as exc_info:
            REVIEW_STATE.normalize_findings(
                {"new": [{"id": "missing-summary"}]},
                {("agent-skills-marketplace", 59)},
            )

        self.assertIn("findings.new[0].summary", str(exc_info.exception))

    def test_current_status_payloads_still_require_status_assessment(self) -> None:
        with self.assertRaises(REVIEW_STATE.click.ClickException) as exc_info:
            REVIEW_STATE.validate_review_requirements(
                mode="status",
                posting_status="not_posted",
                recommendation="comment",
                artifact_path=Path("/tmp/review.md"),
                entries=[
                    {
                        "repo": "agent-skills-marketplace",
                        "pr_number": 59,
                        "base_branch": "main",
                        "head_sha": "b8c36a1",
                        "merge_base": "6557e6c",
                        "pr_state": "OPEN",
                        "is_draft": False,
                    }
                ],
                findings={
                    "new": [],
                    "carried_forward": [],
                    "resolved": [],
                    "moot": [],
                },
                no_findings_after_full_review=False,
                author_claims_checked=[],
                no_author_claims=False,
                comment_context={"summary": "Legacy-free current status payload."},
                backend_handoff=None,
                known_prs={("agent-skills-marketplace", 59)},
                existing_passes=[],
                enforce_artifact_existence=False,
            )

        self.assertIn("must classify current state", str(exc_info.exception))

    def test_merge_comment_context_history_uses_latest_current_status_buckets(self) -> None:
        merged = REVIEW_STATE.merge_comment_context_history(
            [
                {
                    "comment_context": {
                        "thread_source": "gh_graphql",
                        "summary": "Initial review",
                        "still_legit": ["Old issue still looked open."],
                        "resolved_for_context": ["Older durable context."],
                    }
                },
                {
                    "comment_context": {
                        "thread_source": "gh_graphql",
                        "summary": "Latest review",
                        "moot_or_no_longer_applicable": [
                            "The old issue is now fixed."
                        ],
                        "resolved_for_context": ["New durable context."],
                    }
                },
            ]
        )

        assert merged is not None
        self.assertNotIn("still_legit", merged)
        self.assertEqual(
            merged["moot_or_no_longer_applicable"],
            ["The old issue is now fixed."],
        )
        self.assertEqual(
            merged["resolved_for_context"],
            ["Older durable context.", "New durable context."],
        )
        self.assertEqual(merged["summary"], "Latest review")

    def test_merge_comment_context_history_drops_old_current_status_when_latest_has_none(
        self,
    ) -> None:
        merged = REVIEW_STATE.merge_comment_context_history(
            [
                {
                    "comment_context": {
                        "still_legit": ["Old issue still looked open."],
                        "resolved_for_context": ["Older durable context."],
                    }
                },
                {
                    "comment_context": {
                        "resolved_for_context": ["Latest pass recorded the fix."],
                    }
                },
            ]
        )

        assert merged is not None
        self.assertNotIn("still_legit", merged)
        self.assertEqual(
            merged["resolved_for_context"],
            ["Older durable context.", "Latest pass recorded the fix."],
        )

    def test_report_live_drift_returns_drift_payload_without_raising(self) -> None:
        payload = {
            "schema_version": 3,
            "batch_key": "asm-59",
            "created_at_utc": "2026-04-24T00:00:00Z",
            "updated_at_utc": "2026-04-24T00:00:00Z",
            "worktree_path": "/tmp/monolith-review-asm-59",
            "artifact_path": "/tmp/monolith-review-asm-59/review.md",
            "posting_status": "not_posted",
            "review_pass_number": 1,
            "prs": [{"repo": "agent-skills-marketplace", "pr_number": 59}],
            "passes": [
                {
                    "artifact_path": "/tmp/monolith-review-asm-59/review.md",
                    "posting_status": "not_posted",
                    "recorded_at_utc": "2026-04-24T00:00:00Z",
                    "review_pass_number": 1,
                    "mode": "reassess",
                    "recommendation": "request_changes",
                    "scope_summary": "Latest reassessment",
                    "entries": [
                        {
                            "repo": "agent-skills-marketplace",
                            "pr_number": 59,
                            "base_branch": "main",
                            "head_sha": "expected-sha",
                            "merge_base": "merge-base",
                            "pr_state": "OPEN",
                            "is_draft": False,
                        }
                    ],
                    "no_author_claims": True,
                    "comment_context": {
                        "thread_source": "gh_graphql",
                        "summary": "Reviewed thread history.",
                        "still_legit": ["One finding is still open."],
                    },
                    "findings": {
                        "new": [
                            {
                                "repo": "agent-skills-marketplace",
                                "pr_number": 59,
                                "id": "open-finding",
                                "summary": "One finding is still open.",
                            }
                        ],
                        "carried_forward": [],
                        "resolved": [],
                        "moot": [],
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "state.json"
            pr_context_path = Path(temp_dir) / "pr-context.json"
            state_path.write_text(json.dumps(payload), encoding="utf-8")
            pr_context_path.write_text("{}", encoding="utf-8")
            outputs: list[str] = []

            with patch.object(
                REVIEW_STATE,
                "parse_live_pr_context_artifact",
                return_value={
                    ("agent-skills-marketplace", 59): {
                        "pr_url": "https://github.com/DiversioTeam/agent-skills-marketplace/pull/59"
                    }
                },
            ), patch.object(
                REVIEW_STATE,
                "fetch_live_pr_context_from_github",
                return_value={
                    ("agent-skills-marketplace", 59): {
                        "base_branch": "main",
                        "head_sha": "actual-sha",
                        "pr_state": "OPEN",
                        "is_draft": False,
                    }
                },
            ), patch.object(REVIEW_STATE.click, "echo", side_effect=outputs.append):
                REVIEW_STATE.report_live_drift(state_path, pr_context_path)

        self.assertEqual(len(outputs), 1)
        result = json.loads(outputs[0])
        self.assertEqual(result["status"], "drifted")
        self.assertEqual(result["mismatches"][0]["status"], "head_sha_mismatch")

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
