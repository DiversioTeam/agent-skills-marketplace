from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import patch


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "monolith-review-orchestrator"
    / "skills"
    / "monolith-review-orchestrator"
    / "scripts"
    / "resolve_review_batch.py"
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

    def fake_echo(*_args: object, **_kwargs: object) -> None:
        return None

    def fake_path(*_args: object, **_kwargs: object) -> object:
        return object()

    class FakeChoice:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

    fake_click.ClickException = FakeClickException
    fake_click.command = fake_command
    fake_click.option = fake_option
    fake_click.echo = fake_echo
    fake_click.Path = fake_path
    fake_click.Choice = FakeChoice
    return fake_click


def load_module_under_test() -> object:
    spec = importlib.util.spec_from_file_location("resolve_review_batch", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {MODULE_PATH}")

    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {"click": build_fake_click(), spec.name: module},
        clear=False,
    ):
        spec.loader.exec_module(module)
    return module


RESOLVE_REVIEW_BATCH = load_module_under_test()


class ResolveReviewBatchTests(unittest.TestCase):
    def test_parse_pr_url_supports_monolith_without_submodule_path(self) -> None:
        payload = RESOLVE_REVIEW_BATCH.parse_pr_url(
            "https://github.com/DiversioTeam/monolith/pull/123"
        )
        self.assertEqual(payload["alias"], "mono")
        self.assertIsNone(payload["submodule_path"])
        self.assertEqual(payload["entry_key"], "mono123")

    def test_parse_pr_url_preserves_backend_mapping(self) -> None:
        payload = RESOLVE_REVIEW_BATCH.parse_pr_url(
            "https://github.com/DiversioTeam/Django4Lyfe/pull/2836"
        )
        self.assertEqual(payload["alias"], "bk")
        self.assertEqual(payload["submodule_path"], "backend")
        self.assertEqual(payload["entry_key"], "bk2836")

    def test_parse_pr_url_supports_agent_skills_marketplace(self) -> None:
        payload = RESOLVE_REVIEW_BATCH.parse_pr_url(
            "https://github.com/DiversioTeam/agent-skills-marketplace/pull/59"
        )
        self.assertEqual(payload["alias"], "asm")
        self.assertEqual(payload["submodule_path"], "agent-skills-marketplace")
        self.assertEqual(payload["entry_key"], "asm59")

    def test_review_and_worktree_roots_are_applied(self) -> None:
        monolith_root = Path("/tmp/monolith-root")
        review_root = Path("/tmp/review-root")
        worktree_root = Path("/tmp/worktree-root")
        pr_urls = ("https://github.com/DiversioTeam/monolith/pull/123",)

        with patch.object(
            RESOLVE_REVIEW_BATCH,
            "validate_monolith_root",
            return_value=monolith_root,
        ):
            items = [RESOLVE_REVIEW_BATCH.parse_pr_url(pr_url) for pr_url in pr_urls]
            items.sort(key=lambda item: (str(item["alias"]), int(item["pr_number"])))

            batch_key = "-".join(str(item["entry_key"]) for item in items)
            resolved_worktree_root = worktree_root.expanduser().resolve()
            worktree_path = resolved_worktree_root / f"monolith-review-{batch_key}"
            resolved_review_root = review_root.expanduser().resolve()
            review_dir = resolved_review_root / batch_key

            payload: RESOLVE_REVIEW_BATCH.ReviewBatchPayload = {
                "batch_key": batch_key,
                "monolith_root": str(monolith_root),
                "worktree_path": str(worktree_path),
                "review_dir": str(review_dir),
                "artifact_path": str(review_dir / f"review-{batch_key}.md"),
                "reassess_artifact_path": str(review_dir / f"review-{batch_key}-reassess.md"),
                "state_path": str(review_dir / ".state" / f"review-{batch_key}.json"),
                "prs": items,
            }

        self.assertEqual(
            payload["worktree_path"],
            str(resolved_worktree_root / "monolith-review-mono123"),
        )
        self.assertEqual(payload["review_dir"], str(resolved_review_root / "mono123"))
        self.assertEqual(
            payload["artifact_path"],
            str(resolved_review_root / "mono123" / "review-mono123.md"),
        )
        self.assertEqual(
            payload["state_path"],
            str(resolved_review_root / "mono123" / ".state" / "review-mono123.json"),
        )


if __name__ == "__main__":
    unittest.main()
