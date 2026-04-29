from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT
    / "plugins"
    / "monolith-review-orchestrator"
    / "skills"
    / "monolith-review-orchestrator"
    / "scripts"
    / "review_state.py"
)
BATCH_ARTIFACT_PATH = "/tmp/reviews/bk2912-mono291/review-bk2912-mono291.md"
BATCH_WORKTREE_PATH = "/tmp/worktrees/bk2912-mono291"


def write_json_payload(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def summarize_review_state(state_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "uv",
            "run",
            "--quiet",
            "--script",
            str(SCRIPT_PATH),
            "summarize-context",
            "--state-path",
            str(state_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def record_review_state(
    state_path: Path, payload: object
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "uv",
            "run",
            "--quiet",
            "--script",
            str(SCRIPT_PATH),
            "record-review",
            "--state-path",
            str(state_path),
        ],
        cwd=REPO_ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )


def partial_batch_entry_review_state_payload() -> dict[str, object]:
    return {
        "schema_version": 2,
        "batch_key": "bk2912-mono291",
        "created_at_utc": "2026-04-28T00:00:00Z",
        "updated_at_utc": "2026-04-28T00:00:00Z",
        "worktree_path": BATCH_WORKTREE_PATH,
        "artifact_path": BATCH_ARTIFACT_PATH,
        "review_pass_number": 1,
        "posting_status": "posted_review_comment",
        "prs": [
            {"repo": "Django4Lyfe", "pr_number": 2912},
            {"repo": "monolith", "pr_number": 291},
        ],
        "passes": [
            {
                "review_pass_number": 1,
                "recorded_at_utc": "2026-04-28T00:00:00Z",
                "artifact_path": BATCH_ARTIFACT_PATH,
                "posting_status": "posted_review_comment",
                "entries": [
                    {
                        "repo": "monolith",
                        "pr_number": 291,
                        "base_branch": "main",
                        "head_sha": "31865ba84716",
                        "merge_base": "merge-base-mono291",
                    }
                ],
                "mode": "review",
                "recommendation": "comment",
                "scope_summary": (
                    "Historical pass only covered the monolith side before the "
                    "current batch identity included the linked backend PR."
                ),
                "findings": {
                    "new": [],
                    "carried_forward": [],
                    "resolved": [],
                    "moot": [],
                },
            }
        ],
    }


class ReviewStateTests(unittest.TestCase):
    def test_summarize_allows_historical_pass_with_partial_batch_entries(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "review-bk2912-mono291.json"
            write_json_payload(state_path, partial_batch_entry_review_state_payload())

            result = summarize_review_state(state_path)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(
                payload["prs"],
                [
                    {"repo": "Django4Lyfe", "pr_number": 2912},
                    {"repo": "monolith", "pr_number": 291},
                ],
            )
            self.assertEqual(
                payload["latest_context"]["entries"],
                [
                    {
                        "repo": "monolith",
                        "pr_number": 291,
                        "base_branch": "main",
                        "head_sha": "31865ba84716",
                        "merge_base": "merge-base-mono291",
                    }
                ],
            )

    def test_record_review_still_rejects_partial_batch_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "review-bk2912-mono291.json"
            write_json_payload(
                state_path,
                {
                    "schema_version": 2,
                    "batch_key": "bk2912-mono291",
                    "created_at_utc": "2026-04-28T00:00:00Z",
                    "updated_at_utc": "2026-04-28T00:00:00Z",
                    "worktree_path": BATCH_WORKTREE_PATH,
                    "artifact_path": BATCH_ARTIFACT_PATH,
                    "review_pass_number": 0,
                    "posting_status": "not_posted",
                    "prs": [
                        {"repo": "Django4Lyfe", "pr_number": 2912},
                        {"repo": "monolith", "pr_number": 291},
                    ],
                },
            )

            result = record_review_state(
                state_path,
                {
                    "mode": "review",
                    "artifact_path": BATCH_ARTIFACT_PATH,
                    "posting_status": "not_posted",
                    "recommendation": "comment",
                    "scope_summary": "New writes still need every PR in the batch.",
                    "entries": [
                        {
                            "repo": "monolith",
                            "pr_number": 291,
                            "base_branch": "main",
                            "head_sha": "31865ba84716",
                            "merge_base": "merge-base-mono291",
                        }
                    ],
                    "findings": {
                        "new": [],
                        "carried_forward": [],
                        "resolved": [],
                        "moot": [],
                    },
                },
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Review payload `entries` is missing batch PRs: Django4Lyfe:2912",
                result.stderr,
            )


if __name__ == "__main__":
    unittest.main()
