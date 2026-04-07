from __future__ import annotations

import sys
import importlib.util
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
    / "fetch_review_threads.py"
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

    fake_click.ClickException = FakeClickException
    fake_click.command = fake_command
    fake_click.option = fake_option
    fake_click.echo = fake_echo
    return fake_click


def load_module_under_test() -> object:
    spec = importlib.util.spec_from_file_location("fetch_review_threads", MODULE_PATH)
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


FETCH_REVIEW_THREADS = load_module_under_test()


class FetchReviewThreadsTests(unittest.TestCase):
    def make_response(
        self,
        *,
        comment_ids: list[str],
        comment_has_next_page: bool,
        comment_end_cursor: str | None,
        review_ids: list[str],
        review_has_next_page: bool,
        review_end_cursor: str | None,
        thread_ids: list[str],
        thread_has_next_page: bool,
        thread_end_cursor: str | None,
    ) -> object:
        return {
            "data": {
                "repository": {
                    "pullRequest": {
                        "number": 50,
                        "url": "https://github.com/DiversioTeam/agent-skills-marketplace/pull/50",
                        "title": "Thread helper test",
                        "state": "OPEN",
                        "body": "body",
                        "baseRefName": "main",
                        "headRefName": "branch",
                        "headRefOid": "abc123",
                        "author": {"login": "ashwch"},
                        "comments": {
                            "pageInfo": {
                                "hasNextPage": comment_has_next_page,
                                "endCursor": comment_end_cursor,
                            },
                            "nodes": [
                                {
                                    "id": comment_id,
                                    "databaseId": index + 1,
                                    "body": f"comment-{comment_id}",
                                    "createdAt": "2026-04-07T00:00:00Z",
                                    "updatedAt": "2026-04-07T00:00:00Z",
                                    "author": {"login": "reviewer"},
                                }
                                for index, comment_id in enumerate(comment_ids)
                            ],
                        },
                        "reviews": {
                            "pageInfo": {
                                "hasNextPage": review_has_next_page,
                                "endCursor": review_end_cursor,
                            },
                            "nodes": [
                                {
                                    "id": review_id,
                                    "state": "COMMENTED",
                                    "body": f"review-{review_id}",
                                    "submittedAt": "2026-04-07T00:00:00Z",
                                    "author": {"login": "reviewer"},
                                }
                                for review_id in review_ids
                            ],
                        },
                        "reviewThreads": {
                            "pageInfo": {
                                "hasNextPage": thread_has_next_page,
                                "endCursor": thread_end_cursor,
                            },
                            "nodes": [
                                {
                                    "id": thread_id,
                                    "isResolved": False,
                                    "isOutdated": False,
                                    "path": "plugins/example.py",
                                    "line": 10,
                                    "diffSide": "RIGHT",
                                    "startLine": 10,
                                    "startDiffSide": "RIGHT",
                                    "originalLine": 10,
                                    "originalStartLine": 10,
                                    "resolvedBy": None,
                                    "comments": {
                                        "totalCount": 1,
                                        "pageInfo": {
                                            "hasNextPage": False,
                                            "endCursor": None,
                                        },
                                        "nodes": [
                                            {
                                                "id": f"comment-{thread_id}",
                                                "databaseId": 100,
                                                "body": "thread-comment",
                                                "createdAt": "2026-04-07T00:00:00Z",
                                                "updatedAt": "2026-04-07T00:00:00Z",
                                                "author": {"login": "reviewer"},
                                                "replyTo": None,
                                                "pullRequestReview": None,
                                            }
                                        ],
                                    },
                                }
                                for thread_id in thread_ids
                            ],
                        },
                    }
                }
            }
        }

    def make_thread_comments_response(
        self,
        *,
        thread_id: str,
        comment_ids: list[str],
        start_database_id: int,
        has_next_page: bool,
        end_cursor: str | None,
    ) -> object:
        return {
            "data": {
                "node": {
                    "id": thread_id,
                    "isResolved": False,
                    "isOutdated": False,
                    "path": "plugins/example.py",
                    "line": 10,
                    "diffSide": "RIGHT",
                    "startLine": 10,
                    "startDiffSide": "RIGHT",
                    "originalLine": 10,
                    "originalStartLine": 10,
                    "resolvedBy": None,
                    "comments": {
                        "totalCount": 2,
                        "pageInfo": {
                            "hasNextPage": has_next_page,
                            "endCursor": end_cursor,
                        },
                        "nodes": [
                            {
                                "id": comment_id,
                                "databaseId": start_database_id + index,
                                "body": f"thread-comment-{comment_id}",
                                "createdAt": "2026-04-07T00:00:00Z",
                                "updatedAt": "2026-04-07T00:00:00Z",
                                "author": {"login": "reviewer"},
                                "replyTo": None,
                                "pullRequestReview": None,
                            }
                            for index, comment_id in enumerate(comment_ids)
                        ],
                    },
                }
            }
        }

    def test_fetch_pull_request_context_dedupes_non_paginated_connections(self) -> None:
        responses = [
            self.make_response(
                comment_ids=["C1"],
                comment_has_next_page=True,
                comment_end_cursor="comments-page-2",
                review_ids=["R1"],
                review_has_next_page=False,
                review_end_cursor=None,
                thread_ids=["T1"],
                thread_has_next_page=False,
                thread_end_cursor=None,
            ),
            self.make_response(
                comment_ids=["C2"],
                comment_has_next_page=False,
                comment_end_cursor=None,
                review_ids=["R1"],
                review_has_next_page=False,
                review_end_cursor=None,
                thread_ids=["T1"],
                thread_has_next_page=False,
                thread_end_cursor=None,
            ),
        ]
        pr_ref = FETCH_REVIEW_THREADS.PullRequestRef(
            owner="DiversioTeam",
            repo="agent-skills-marketplace",
            pr_number=50,
            pr_url="https://github.com/DiversioTeam/agent-skills-marketplace/pull/50",
            alias=None,
            submodule_path=None,
        )

        with patch.object(
            FETCH_REVIEW_THREADS,
            "call_graphql",
            side_effect=responses,
        ):
            result = FETCH_REVIEW_THREADS.fetch_pull_request_context(pr_ref)

        self.assertEqual(result["summary"]["conversation_comment_count"], 2)
        self.assertEqual(result["summary"]["review_count"], 1)
        self.assertEqual(result["summary"]["review_thread_count"], 1)
        self.assertEqual([review["node_id"] for review in result["reviews"]], ["R1"])
        self.assertEqual(
            [thread["thread_id"] for thread in result["review_threads"]], ["T1"]
        )

    def test_fetch_pull_request_context_fails_when_page_cursor_is_missing(self) -> None:
        response = self.make_response(
            comment_ids=["C1"],
            comment_has_next_page=True,
            comment_end_cursor=None,
            review_ids=[],
            review_has_next_page=False,
            review_end_cursor=None,
            thread_ids=[],
            thread_has_next_page=False,
            thread_end_cursor=None,
        )
        pr_ref = FETCH_REVIEW_THREADS.PullRequestRef(
            owner="DiversioTeam",
            repo="agent-skills-marketplace",
            pr_number=50,
            pr_url="https://github.com/DiversioTeam/agent-skills-marketplace/pull/50",
            alias=None,
            submodule_path=None,
        )

        with patch.object(
            FETCH_REVIEW_THREADS,
            "call_graphql",
            return_value=response,
        ):
            with self.assertRaises(
                FETCH_REVIEW_THREADS.click.ClickException
            ) as exc_info:
                FETCH_REVIEW_THREADS.fetch_pull_request_context(pr_ref)

        self.assertIn("pull_request.comments.pageInfo", str(exc_info.exception))
        self.assertIn("endCursor", str(exc_info.exception))

    def test_fetch_pull_request_context_follows_thread_comment_pagination(self) -> None:
        main_response = self.make_response(
            comment_ids=[],
            comment_has_next_page=False,
            comment_end_cursor=None,
            review_ids=[],
            review_has_next_page=False,
            review_end_cursor=None,
            thread_ids=["T1"],
            thread_has_next_page=False,
            thread_end_cursor=None,
        )
        main_response["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"][0][
            "comments"
        ] = {
            "totalCount": 2,
            "pageInfo": {"hasNextPage": True, "endCursor": "thread-page-2"},
            "nodes": [
                {
                    "id": "TC1",
                    "databaseId": 101,
                    "body": "thread-comment-TC1",
                    "createdAt": "2026-04-07T00:00:00Z",
                    "updatedAt": "2026-04-07T00:00:00Z",
                    "author": {"login": "reviewer"},
                    "replyTo": None,
                    "pullRequestReview": None,
                }
            ],
        }
        responses = [
            main_response,
            self.make_thread_comments_response(
                thread_id="T1",
                comment_ids=["TC1"],
                start_database_id=101,
                has_next_page=True,
                end_cursor="thread-page-2",
            ),
            self.make_thread_comments_response(
                thread_id="T1",
                comment_ids=["TC2"],
                start_database_id=102,
                has_next_page=False,
                end_cursor=None,
            ),
        ]
        pr_ref = FETCH_REVIEW_THREADS.PullRequestRef(
            owner="DiversioTeam",
            repo="agent-skills-marketplace",
            pr_number=50,
            pr_url="https://github.com/DiversioTeam/agent-skills-marketplace/pull/50",
            alias=None,
            submodule_path=None,
        )

        with patch.object(
            FETCH_REVIEW_THREADS,
            "call_graphql",
            side_effect=responses,
        ):
            result = FETCH_REVIEW_THREADS.fetch_pull_request_context(pr_ref)

        thread = result["review_threads"][0]
        self.assertEqual(thread["total_comment_count"], 2)
        self.assertEqual(
            [comment["node_id"] for comment in thread["comments"]], ["TC1", "TC2"]
        )
        self.assertEqual(thread["comment_ids"], [101, 102])


if __name__ == "__main__":
    unittest.main()
