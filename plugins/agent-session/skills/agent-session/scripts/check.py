"""`agent-session check`: does a published transcript cover this branch's HEAD?

Repos run it as an ordinary local-ci step, so it reads git, gh and the local record itself. Its output is a contract for
coding agents and people (pinned by tests): the first line starts with `agent-session: ok|skipped|missing|stale|
unlinked|unverified`, and a failure is followed by `fix:` (the exact command), `next:`, and the declaration alternative.
With an open PR its body is authoritative; without one, the local record (store.py) is. A failed PR lookup fails closed.

local-ci also runs where no transcript belongs, and there the check passes as `skipped`: a cloud session (no developer
login to publish with), HEAD on an integration branch (main, master, dev, release*, ...) or already merged into one
(deploy triggers and release candidates), a promotion or release PR between integration branches, and a bot's PR.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import urllib.parse
from dataclasses import dataclass, field

LINK = re.compile(r"https://internal-share\.diversio\.com/(session-[A-Za-z0-9._%-]+\.html)")
COVERED_HEAD = re.compile(r"-h([0-9a-f]{12})-")
# Branches work is merged into, not done on: a default branch, or a release branch.
INTEGRATION = re.compile(r"^(?:main|master|dev|develop|development|staging|production|trunk|release(?:[/_.-].*)?)$")
# Branches release flows open promotion PRs from (backend-release: promote/YYYY.MM.DD, releases/...).
PROMOTION = re.compile(r"^(?:promote|promotion|releases?)[/_.-]")
DECLARATION = re.compile(r"^\s*(?:[-*]\s*)?No agent session:\s*\S.{2,}$", re.IGNORECASE | re.MULTILINE)


@dataclass
class Input:
    repo_root: str
    repo_slug: str
    branch: str
    head: str
    pr: tuple[int, str] | None = None  # (number, body)
    pr_lookup_error: str = ""
    published: dict | None = None
    cli: str = "agent-session"
    # The open PR's base branch and author ("login", and whether GitHub calls the account a bot).
    pr_base: str = ""
    pr_author: str = ""
    pr_author_is_bot: bool = False
    # Set when HEAD is detached but already on an integration branch (that branch's name).
    merged_into: str = ""
    remote: bool = False


@dataclass
class Result:
    ok: bool
    kind: str
    message: str
    lines: list[str] = field(default_factory=list)


def covered_heads(body: str) -> list[str]:
    heads = []
    for match in LINK.finditer(body):
        head = COVERED_HEAD.search(match.group(1))
        if head:
            heads.append(head.group(1))
    return heads


def _fail(check: Input, kind: str, detail: str, where: str) -> Result:
    share = f"{check.cli} share --repo {shlex.quote(check.repo_root)}"
    none = f"{check.cli} declare-none '<reason>' --repo {shlex.quote(check.repo_root)}"
    if check.pr:
        share += f" --pr {check.pr[0]}"
        none += f" --pr {check.pr[0]}"
    message = (f"agent-session: {kind} {detail} {where}\n"
               f"fix: {share}\n"
               "next: share renders a redacted preview, publishes it to internal-share, and puts its link in the PR body's "
               "\"## Agent sessions\" section; on a branch's first publish it stops (exit 3) for the developer's review, then rerun "
               "with --yes. Run local-ci again afterwards.\n"
               f"no agent worked on this branch: {none} (writes \"No agent session: <reason>\")")
    return Result(ok=False, kind=kind, message=message)


def skip_reason(check: Input) -> str:
    """Why no transcript belongs here, or ""."""
    if check.remote:
        return "a cloud session; transcripts are published from a developer's machine"
    if check.branch and INTEGRATION.match(check.branch):
        return f"HEAD is on the integration branch {check.branch}"
    if not check.branch and check.merged_into:
        return f"HEAD is already on the integration branch {check.merged_into}"
    if check.pr and INTEGRATION.match(check.pr_base) and PROMOTION.match(check.branch):
        return f"a promotion or release PR ({check.branch} into {check.pr_base})"
    if check.pr and check.pr_author_is_bot:
        return f"a bot's PR ({check.pr_author})"
    return ""


def decide(check: Input) -> Result:
    head = check.head[:12]
    where = f"for {check.repo_slug} branch {check.branch or 'detached HEAD'}" + (f" PR #{check.pr[0]}" if check.pr else "")
    skipped = skip_reason(check)
    if skipped:
        return Result(ok=True, kind="skipped", message=f"agent-session: skipped ({skipped}) {where}")
    if not check.branch:
        return _fail(check, "missing", "(detached HEAD; check out the PR's branch)", where)
    if check.pr_lookup_error:
        return Result(ok=False, kind="unverified", message=(
            f"agent-session: unverified ({check.pr_lookup_error}) {where}\n"
            "fix: gh auth login, then run local-ci again\n"
            "next: with the PR readable, the check compares the PR body's agent session link with HEAD"))
    published = check.published or {}
    published_here = not published.get("none") and str(published.get("head", "")).startswith(head) and bool(published.get("links"))
    if check.pr:
        body = check.pr[1]
        if DECLARATION.search(body):
            return Result(ok=True, kind="declared", message=f"agent-session: ok (declared no agent session) {where}")
        heads = covered_heads(body)
        if head in heads:
            return Result(ok=True, kind="ok", message=f"agent-session: ok (transcript covers HEAD {head}) {where}")
        if published_here:
            return _fail(check, "unlinked", f"(a transcript for HEAD {head} is published, but the PR body does not link it)", where)
        if heads:
            return _fail(check, "stale", f"(transcript covers {heads[-1]}, HEAD is {head})", where)
        return _fail(check, "missing", "(the PR body has no agent session link)", where)
    if published.get("none"):
        return Result(ok=True, kind="declared", message=f"agent-session: ok (declared no agent session) {where}")
    if published_here:
        return Result(ok=True, kind="ok", message=f"agent-session: ok (transcript covers HEAD {head}; no PR yet) {where}")
    if published.get("head"):
        return _fail(check, "stale", f"(transcript covers {str(published['head'])[:12]}, HEAD is {head})", where)
    return _fail(check, "missing", "(no transcript published for this branch)", where)


def open_pr(repo_slug: str, branch: str) -> tuple[dict | None, str]:
    """The branch's open PR (GitHub's pull object), or None; an error string when GitHub could not be asked."""
    owner = repo_slug.split("/")[0]
    path = f"repos/{repo_slug}/pulls?state=open&head={urllib.parse.quote(owner + ':' + branch, safe='')}"
    try:
        completed = subprocess.run(["gh", "api", "--hostname", "github.com", path], capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None, "gh is not installed or did not answer"
    if completed.returncode != 0:
        return None, "gh could not read the PR (check gh auth status)"
    try:
        pulls = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None, "GitHub returned an unreadable PR list"
    if not pulls:
        return None, ""
    return pulls[0], ""


def merged_into(repo_root: str) -> str:
    """The origin integration branch that already contains a detached HEAD, or ""."""
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", repo_root, *args], capture_output=True, text=True, timeout=60, check=False)
    refs = git("for-each-ref", "--format=%(refname:strip=3)", "refs/remotes/origin").stdout.split()
    for name in refs:
        if INTEGRATION.match(name) and git("merge-base", "--is-ancestor", "HEAD", f"origin/{name}").returncode == 0:
            return name
    return ""
