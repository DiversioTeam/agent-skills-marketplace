#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "click>=8.1,<9",
# ]
# ///
"""Fetch thread-aware GitHub PR review context for monolith review orchestration.

Why this helper exists:
- flat PR comment surfaces do not preserve review-thread resolution state
- world-class review requires reading resolved and outdated threads, not just the
  latest diff or top-level comments
- the orchestrator should own a deterministic acquisition path for review
  threads instead of relying on ad hoc `gh api graphql` commands in chat

Mental model:
    PR URL(s)
        -> thread-aware GitHub read
        -> normalized review context JSON
        -> deterministic input for deep review and persistent review memory
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Literal, TypedDict
from urllib.parse import urlparse

import click


PR_PATH_PARTS = 4
THREAD_STATUS = {True: "resolved", False: "open"}
KNOWN_REPOS: dict[str, tuple[str, str]] = {
    "Django4Lyfe": ("bk", "backend"),
    "Diversio-Frontend": ("fe", "frontend"),
    "Optimo-Frontend": ("of", "optimo-frontend"),
    "diversio-ds": ("ds", "design-system"),
    "infrastructure": ("infra", "infrastructure"),
    "diversio-serverless": ("sls", "diversio-serverless"),
}

MAIN_QUERY = """\
query(
  $owner: String!,
  $repo: String!,
  $number: Int!,
  $commentsCursor: String,
  $reviewsCursor: String,
  $threadsCursor: String
) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      number
      url
      title
      state
      body
      baseRefName
      headRefName
      headRefOid
      author { login }
      comments(first: 100, after: $commentsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          databaseId
          body
          createdAt
          updatedAt
          author { login }
        }
      }
      reviews(first: 100, after: $reviewsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          state
          body
          submittedAt
          author { login }
        }
      }
      reviewThreads(first: 100, after: $threadsCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          diffSide
          startLine
          startDiffSide
          originalLine
          originalStartLine
          resolvedBy { login }
          comments(first: 100) {
            totalCount
            pageInfo { hasNextPage endCursor }
            nodes {
              id
              databaseId
              body
              createdAt
              updatedAt
              author { login }
              replyTo { id }
              pullRequestReview {
                id
                state
                submittedAt
                author { login }
              }
            }
          }
        }
      }
    }
  }
}
"""

THREAD_COMMENTS_QUERY = """\
query($threadId: ID!, $commentsCursor: String) {
  node(id: $threadId) {
    ... on PullRequestReviewThread {
      id
      isResolved
      isOutdated
      path
      line
      diffSide
      startLine
      startDiffSide
      originalLine
      originalStartLine
      resolvedBy { login }
      comments(first: 100, after: $commentsCursor) {
        totalCount
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          databaseId
          body
          createdAt
          updatedAt
          author { login }
          replyTo { id }
          pullRequestReview {
            id
            state
            submittedAt
            author { login }
          }
        }
      }
    }
  }
}
"""


class PageInfo(TypedDict):
    hasNextPage: bool
    endCursor: str | None


class AuthorRecord(TypedDict):
    login: str | None


class RawReplyTarget(TypedDict, total=False):
    id: str


class RawReviewAuthor(TypedDict, total=False):
    login: str | None


class RawPullRequestReview(TypedDict, total=False):
    id: str
    state: str | None
    submittedAt: str | None
    author: RawReviewAuthor | None


class RawThreadCommentNode(TypedDict, total=False):
    id: str
    databaseId: int | None
    body: str
    createdAt: str
    updatedAt: str
    author: AuthorRecord | None
    replyTo: RawReplyTarget | None
    pullRequestReview: RawPullRequestReview | None


class RawThreadCommentConnection(TypedDict):
    totalCount: int
    pageInfo: PageInfo
    nodes: list[RawThreadCommentNode]


class RawThreadNode(TypedDict, total=False):
    id: str
    isResolved: bool
    isOutdated: bool
    path: str | None
    line: int | None
    diffSide: str | None
    startLine: int | None
    startDiffSide: str | None
    originalLine: int | None
    originalStartLine: int | None
    resolvedBy: AuthorRecord | None
    comments: RawThreadCommentConnection


class RawIssueCommentNode(TypedDict, total=False):
    id: str
    databaseId: int | None
    body: str
    createdAt: str
    updatedAt: str
    author: AuthorRecord | None


class RawReviewNode(TypedDict, total=False):
    id: str
    state: str | None
    body: str | None
    submittedAt: str | None
    author: AuthorRecord | None


class RawConnectionIssueComments(TypedDict):
    pageInfo: PageInfo
    nodes: list[RawIssueCommentNode]


class RawConnectionReviews(TypedDict):
    pageInfo: PageInfo
    nodes: list[RawReviewNode]


class RawConnectionThreads(TypedDict):
    pageInfo: PageInfo
    nodes: list[RawThreadNode]


class RawPullRequest(TypedDict, total=False):
    number: int
    url: str
    title: str
    state: str
    body: str | None
    baseRefName: str | None
    headRefName: str | None
    headRefOid: str | None
    author: AuthorRecord | None
    comments: RawConnectionIssueComments
    reviews: RawConnectionReviews
    reviewThreads: RawConnectionThreads


class RawRepositoryPayload(TypedDict, total=False):
    pullRequest: RawPullRequest | None


class RawGraphQLData(TypedDict, total=False):
    repository: RawRepositoryPayload | None


class RawGraphQLError(TypedDict, total=False):
    message: str


class GraphQLResponse(TypedDict, total=False):
    data: RawGraphQLData
    errors: list[RawGraphQLError]


class PullRequestMetadata(TypedDict, total=False):
    owner: str
    repo: str
    pr_number: int
    url: str
    title: str
    state: str
    body: str
    author_login: str | None
    base_ref_name: str | None
    head_ref_name: str | None
    head_ref_oid: str | None
    alias: str | None
    submodule_path: str | None


class ConversationComment(TypedDict, total=False):
    node_id: str
    database_id: int | None
    body: str
    created_at: str
    updated_at: str
    author_login: str | None


class ReviewSubmission(TypedDict, total=False):
    node_id: str
    state: str | None
    body: str | None
    submitted_at: str | None
    author_login: str | None


class ThreadCommentReview(TypedDict, total=False):
    node_id: str
    state: str | None
    submitted_at: str | None
    author_login: str | None


class ThreadComment(TypedDict, total=False):
    node_id: str
    database_id: int | None
    body: str
    created_at: str
    updated_at: str
    author_login: str | None
    reply_to_node_id: str | None
    review: ThreadCommentReview | None


class ReviewThread(TypedDict, total=False):
    repo: str
    pr_number: int
    thread_id: str
    status: Literal["open", "resolved"]
    is_resolved: bool
    is_outdated: bool
    path: str | None
    line: int | None
    diff_side: str | None
    start_line: int | None
    start_diff_side: str | None
    original_line: int | None
    original_start_line: int | None
    resolved_by_login: str | None
    last_seen_head_sha: str | None
    comment_ids: list[int]
    comments: list[ThreadComment]
    total_comment_count: int


class PullRequestSummary(TypedDict):
    conversation_comment_count: int
    review_count: int
    review_thread_count: int
    open_thread_count: int
    resolved_thread_count: int
    outdated_thread_count: int
    review_thread_comment_count: int


class PullRequestReviewContext(TypedDict):
    pull_request: PullRequestMetadata
    conversation_comments: list[ConversationComment]
    reviews: list[ReviewSubmission]
    review_threads: list[ReviewThread]
    summary: PullRequestSummary


class FetchResult(TypedDict):
    source: str
    pull_requests: list[PullRequestReviewContext]


@dataclass(frozen=True)
class PullRequestRef:
    owner: str
    repo: str
    pr_number: int
    pr_url: str
    alias: str | None
    submodule_path: str | None


def next_page_cursor(page_info: PageInfo, field_name: str) -> str | None:
    if not page_info["hasNextPage"]:
        return None
    end_cursor = page_info["endCursor"]
    if end_cursor is None:
        raise click.ClickException(
            f"{field_name} reported hasNextPage=true without an endCursor."
        )
    return end_cursor


def run_command(command: list[str], stdin: str | None = None) -> str:
    result = subprocess.run(
        command,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise click.ClickException(
            result.stderr.strip() or f"Command failed: {' '.join(command)}"
        )
    return result.stdout


def run_json(command: list[str], stdin: str | None = None) -> object:
    output = run_command(command, stdin=stdin)
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Command returned invalid JSON: {exc}") from exc


def require_dict(value: object, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise click.ClickException(f"Expected object for `{field_name}`.")
    return value


def require_list(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise click.ClickException(f"Expected list for `{field_name}`.")
    return value


def require_str(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise click.ClickException(f"Expected non-empty string for `{field_name}`.")
    return value


def optional_str(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise click.ClickException(f"Expected string or null for `{field_name}`.")
    return value


def optional_int(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise click.ClickException(f"Expected integer or null for `{field_name}`.")
    return value


def require_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise click.ClickException(f"Expected integer for `{field_name}`.")
    return value


def require_bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise click.ClickException(f"Expected boolean for `{field_name}`.")
    return value


def parse_pr_url(pr_url: str) -> PullRequestRef:
    parsed = urlparse(pr_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "github.com":
        raise click.ClickException(f"Unsupported PR URL: {pr_url}")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < PR_PATH_PARTS or parts[2] != "pull":
        raise click.ClickException(f"Unsupported PR URL path: {pr_url}")

    owner = parts[0]
    repo = parts[1]
    try:
        pr_number = int(parts[3])
    except ValueError as exc:
        raise click.ClickException(f"Invalid PR number in URL: {pr_url}") from exc

    alias: str | None = None
    submodule_path: str | None = None
    if repo in KNOWN_REPOS:
        alias, submodule_path = KNOWN_REPOS[repo]

    return PullRequestRef(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        pr_url=pr_url,
        alias=alias,
        submodule_path=submodule_path,
    )


def ensure_unique_prs(pr_refs: list[PullRequestRef]) -> list[PullRequestRef]:
    seen: set[tuple[str, str, int]] = set()
    unique: list[PullRequestRef] = []
    for pr_ref in pr_refs:
        identity = (pr_ref.owner, pr_ref.repo, pr_ref.pr_number)
        if identity in seen:
            raise click.ClickException(
                f"Duplicate PR input: {pr_ref.owner}/{pr_ref.repo}#{pr_ref.pr_number}"
            )
        seen.add(identity)
        unique.append(pr_ref)
    return unique


def ensure_gh_authenticated() -> None:
    run_command(["gh", "auth", "status"])


def call_graphql(query: str, fields: dict[str, str]) -> GraphQLResponse:
    command = ["gh", "api", "graphql", "-F", "query=@-"]
    for key, value in fields.items():
        command.extend(["-F", f"{key}={value}"])
    payload = run_json(command, stdin=query)
    response = require_dict(payload, "graphql_response")
    errors = response.get("errors")
    if isinstance(errors, list) and errors:
        raise click.ClickException(json.dumps(errors, indent=2))
    return response


def parse_page_info(value: object, field_name: str) -> PageInfo:
    data = require_dict(value, field_name)
    return {
        "hasNextPage": require_bool(
            data.get("hasNextPage"), f"{field_name}.hasNextPage"
        ),
        "endCursor": optional_str(data.get("endCursor"), f"{field_name}.endCursor"),
    }


def parse_author_login(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    data = require_dict(value, field_name)
    return optional_str(data.get("login"), f"{field_name}.login")


def parse_review_link(value: object, field_name: str) -> ThreadCommentReview | None:
    if value is None:
        return None
    data = require_dict(value, field_name)
    return {
        "node_id": require_str(data.get("id"), f"{field_name}.id"),
        "state": optional_str(data.get("state"), f"{field_name}.state"),
        "submitted_at": optional_str(
            data.get("submittedAt"), f"{field_name}.submittedAt"
        ),
        "author_login": parse_author_login(data.get("author"), f"{field_name}.author"),
    }


def parse_thread_comment(value: object, field_name: str) -> ThreadComment:
    data = require_dict(value, field_name)
    reply_to_value = data.get("replyTo")
    reply_to_node_id: str | None = None
    if reply_to_value is not None:
        reply_to_node_id = require_str(
            require_dict(reply_to_value, f"{field_name}.replyTo").get("id"),
            f"{field_name}.replyTo.id",
        )
    return {
        "node_id": require_str(data.get("id"), f"{field_name}.id"),
        "database_id": optional_int(data.get("databaseId"), f"{field_name}.databaseId"),
        "body": require_str(data.get("body"), f"{field_name}.body"),
        "created_at": require_str(data.get("createdAt"), f"{field_name}.createdAt"),
        "updated_at": require_str(data.get("updatedAt"), f"{field_name}.updatedAt"),
        "author_login": parse_author_login(data.get("author"), f"{field_name}.author"),
        "reply_to_node_id": reply_to_node_id,
        "review": parse_review_link(
            data.get("pullRequestReview"), f"{field_name}.pullRequestReview"
        ),
    }


def parse_thread_comment_connection(
    value: object, field_name: str
) -> tuple[list[ThreadComment], PageInfo, int]:
    data = require_dict(value, field_name)
    nodes = [
        parse_thread_comment(node, f"{field_name}.nodes[{index}]")
        for index, node in enumerate(
            require_list(data.get("nodes"), f"{field_name}.nodes")
        )
    ]
    page_info = parse_page_info(data.get("pageInfo"), f"{field_name}.pageInfo")
    total_count = require_int(data.get("totalCount"), f"{field_name}.totalCount")
    return nodes, page_info, total_count


def fetch_all_thread_comments(
    thread_id: str,
    initial_comments: list[ThreadComment] | None = None,
    next_cursor: str | None = None,
    total_count: int = 0,
) -> tuple[list[ThreadComment], int]:
    comments: list[ThreadComment] = list(initial_comments or [])
    cursor = next_cursor
    while True:
        if cursor is None:
            raise click.ClickException(
                f"Thread `{thread_id}` reported another page without an end cursor."
            )
        fields = {"threadId": thread_id}
        fields["commentsCursor"] = cursor
        response = call_graphql(THREAD_COMMENTS_QUERY, fields)
        data = require_dict(response.get("data"), "graphql_response.data")
        node = require_dict(data.get("node"), "graphql_response.data.node")
        thread_comments, page_info, total_count = parse_thread_comment_connection(
            node.get("comments"), "graphql_response.data.node.comments"
        )
        comments.extend(thread_comments)
        if not page_info["hasNextPage"]:
            break
        cursor = next_page_cursor(page_info, f"thread `{thread_id}` comments.pageInfo")
    return comments, total_count


def parse_issue_comment(value: object, field_name: str) -> ConversationComment:
    data = require_dict(value, field_name)
    return {
        "node_id": require_str(data.get("id"), f"{field_name}.id"),
        "database_id": optional_int(data.get("databaseId"), f"{field_name}.databaseId"),
        "body": require_str(data.get("body"), f"{field_name}.body"),
        "created_at": require_str(data.get("createdAt"), f"{field_name}.createdAt"),
        "updated_at": require_str(data.get("updatedAt"), f"{field_name}.updatedAt"),
        "author_login": parse_author_login(data.get("author"), f"{field_name}.author"),
    }


def parse_review_submission(value: object, field_name: str) -> ReviewSubmission:
    data = require_dict(value, field_name)
    body = data.get("body")
    return {
        "node_id": require_str(data.get("id"), f"{field_name}.id"),
        "state": optional_str(data.get("state"), f"{field_name}.state"),
        "body": optional_str(body, f"{field_name}.body"),
        "submitted_at": optional_str(
            data.get("submittedAt"), f"{field_name}.submittedAt"
        ),
        "author_login": parse_author_login(data.get("author"), f"{field_name}.author"),
    }


def parse_review_thread(
    value: object,
    field_name: str,
    repo: str,
    pr_number: int,
    head_sha: str | None,
) -> ReviewThread:
    data = require_dict(value, field_name)
    is_resolved = require_bool(data.get("isResolved"), f"{field_name}.isResolved")
    is_outdated = require_bool(data.get("isOutdated"), f"{field_name}.isOutdated")
    thread_id = require_str(data.get("id"), f"{field_name}.id")
    comments, page_info, total_count = parse_thread_comment_connection(
        data.get("comments"), f"{field_name}.comments"
    )
    if page_info["hasNextPage"]:
        comments, total_count = fetch_all_thread_comments(
            thread_id,
            initial_comments=comments,
            next_cursor=next_page_cursor(page_info, f"{field_name}.comments.pageInfo"),
            total_count=total_count,
        )
    comment_ids = [
        comment["database_id"]
        for comment in comments
        if comment.get("database_id") is not None
    ]
    return {
        "repo": repo,
        "pr_number": pr_number,
        "thread_id": thread_id,
        "status": THREAD_STATUS[is_resolved],
        "is_resolved": is_resolved,
        "is_outdated": is_outdated,
        "path": optional_str(data.get("path"), f"{field_name}.path"),
        "line": optional_int(data.get("line"), f"{field_name}.line"),
        "diff_side": optional_str(data.get("diffSide"), f"{field_name}.diffSide"),
        "start_line": optional_int(data.get("startLine"), f"{field_name}.startLine"),
        "start_diff_side": optional_str(
            data.get("startDiffSide"), f"{field_name}.startDiffSide"
        ),
        "original_line": optional_int(
            data.get("originalLine"), f"{field_name}.originalLine"
        ),
        "original_start_line": optional_int(
            data.get("originalStartLine"), f"{field_name}.originalStartLine"
        ),
        "resolved_by_login": parse_author_login(
            data.get("resolvedBy"), f"{field_name}.resolvedBy"
        ),
        "last_seen_head_sha": head_sha,
        "comment_ids": comment_ids,
        "comments": comments,
        "total_comment_count": total_count,
    }


def fetch_pull_request_context(pr_ref: PullRequestRef) -> PullRequestReviewContext:
    conversation_comments: list[ConversationComment] = []
    reviews: list[ReviewSubmission] = []
    review_threads: list[ReviewThread] = []
    seen_conversation_comment_ids: set[str] = set()
    seen_review_ids: set[str] = set()
    seen_thread_ids: set[str] = set()

    comments_cursor: str | None = None
    reviews_cursor: str | None = None
    threads_cursor: str | None = None

    metadata: PullRequestMetadata | None = None

    while True:
        fields = {
            "owner": pr_ref.owner,
            "repo": pr_ref.repo,
            "number": str(pr_ref.pr_number),
        }
        if comments_cursor is not None:
            fields["commentsCursor"] = comments_cursor
        if reviews_cursor is not None:
            fields["reviewsCursor"] = reviews_cursor
        if threads_cursor is not None:
            fields["threadsCursor"] = threads_cursor

        response = call_graphql(MAIN_QUERY, fields)
        data = require_dict(response.get("data"), "graphql_response.data")
        repository = require_dict(
            data.get("repository"), "graphql_response.data.repository"
        )
        pull_request = require_dict(
            repository.get("pullRequest"),
            "graphql_response.data.repository.pullRequest",
        )

        if metadata is None:
            metadata = {
                "owner": pr_ref.owner,
                "repo": pr_ref.repo,
                "pr_number": require_int(
                    pull_request.get("number"), "pull_request.number"
                ),
                "url": require_str(pull_request.get("url"), "pull_request.url"),
                "title": require_str(pull_request.get("title"), "pull_request.title"),
                "state": require_str(pull_request.get("state"), "pull_request.state"),
                "body": optional_str(pull_request.get("body"), "pull_request.body")
                or "",
                "author_login": parse_author_login(
                    pull_request.get("author"), "pull_request.author"
                ),
                "base_ref_name": optional_str(
                    pull_request.get("baseRefName"), "pull_request.baseRefName"
                ),
                "head_ref_name": optional_str(
                    pull_request.get("headRefName"), "pull_request.headRefName"
                ),
                "head_ref_oid": optional_str(
                    pull_request.get("headRefOid"), "pull_request.headRefOid"
                ),
                "alias": pr_ref.alias,
                "submodule_path": pr_ref.submodule_path,
            }

        comment_nodes = require_dict(
            pull_request.get("comments"), "pull_request.comments"
        )
        review_nodes = require_dict(pull_request.get("reviews"), "pull_request.reviews")
        thread_nodes = require_dict(
            pull_request.get("reviewThreads"), "pull_request.reviewThreads"
        )

        for index, node in enumerate(
            require_list(comment_nodes.get("nodes"), "pull_request.comments.nodes")
        ):
            parsed_comment = parse_issue_comment(
                node, f"pull_request.comments.nodes[{index}]"
            )
            comment_id = parsed_comment["node_id"]
            if comment_id in seen_conversation_comment_ids:
                continue
            seen_conversation_comment_ids.add(comment_id)
            conversation_comments.append(parsed_comment)

        for index, node in enumerate(
            require_list(review_nodes.get("nodes"), "pull_request.reviews.nodes")
        ):
            parsed_review = parse_review_submission(
                node, f"pull_request.reviews.nodes[{index}]"
            )
            review_id = parsed_review["node_id"]
            if review_id in seen_review_ids:
                continue
            seen_review_ids.add(review_id)
            reviews.append(parsed_review)

        head_sha = metadata.get("head_ref_oid")
        for index, node in enumerate(
            require_list(thread_nodes.get("nodes"), "pull_request.reviewThreads.nodes")
        ):
            thread_data = require_dict(
                node, f"pull_request.reviewThreads.nodes[{index}]"
            )
            thread_id = require_str(
                thread_data.get("id"), f"pull_request.reviewThreads.nodes[{index}].id"
            )
            if thread_id in seen_thread_ids:
                continue
            seen_thread_ids.add(thread_id)
            review_threads.append(
                parse_review_thread(
                    thread_data,
                    f"pull_request.reviewThreads.nodes[{index}]",
                    repo=pr_ref.repo,
                    pr_number=pr_ref.pr_number,
                    head_sha=head_sha,
                )
            )

        comment_page_info = parse_page_info(
            comment_nodes.get("pageInfo"), "pull_request.comments.pageInfo"
        )
        review_page_info = parse_page_info(
            review_nodes.get("pageInfo"), "pull_request.reviews.pageInfo"
        )
        thread_page_info = parse_page_info(
            thread_nodes.get("pageInfo"), "pull_request.reviewThreads.pageInfo"
        )

        comments_cursor = next_page_cursor(
            comment_page_info, "pull_request.comments.pageInfo"
        )
        reviews_cursor = next_page_cursor(
            review_page_info, "pull_request.reviews.pageInfo"
        )
        threads_cursor = next_page_cursor(
            thread_page_info, "pull_request.reviewThreads.pageInfo"
        )

        if (
            comments_cursor is None
            and reviews_cursor is None
            and threads_cursor is None
        ):
            break

    if metadata is None:
        raise click.ClickException(
            f"Failed to fetch PR context for {pr_ref.owner}/{pr_ref.repo}#{pr_ref.pr_number}."
        )

    summary: PullRequestSummary = {
        "conversation_comment_count": len(conversation_comments),
        "review_count": len(reviews),
        "review_thread_count": len(review_threads),
        "open_thread_count": sum(
            1 for thread in review_threads if not thread["is_resolved"]
        ),
        "resolved_thread_count": sum(
            1 for thread in review_threads if thread["is_resolved"]
        ),
        "outdated_thread_count": sum(
            1 for thread in review_threads if thread["is_outdated"]
        ),
        "review_thread_comment_count": sum(
            thread["total_comment_count"] for thread in review_threads
        ),
    }
    return {
        "pull_request": metadata,
        "conversation_comments": conversation_comments,
        "reviews": reviews,
        "review_threads": review_threads,
        "summary": summary,
    }


@click.command()
@click.option(
    "--pr-url",
    "pr_urls",
    multiple=True,
    required=True,
    help="Repeat for each GitHub PR URL to fetch.",
)
def main(pr_urls: tuple[str, ...]) -> None:
    """Fetch thread-aware PR review context for one PR or a linked PR set."""

    ensure_gh_authenticated()
    pr_refs = ensure_unique_prs([parse_pr_url(pr_url) for pr_url in pr_urls])
    pr_refs.sort(key=lambda pr_ref: ((pr_ref.alias or pr_ref.repo), pr_ref.pr_number))

    payload: FetchResult = {
        "source": "gh_graphql_review_threads",
        "pull_requests": [fetch_pull_request_context(pr_ref) for pr_ref in pr_refs],
    }
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
