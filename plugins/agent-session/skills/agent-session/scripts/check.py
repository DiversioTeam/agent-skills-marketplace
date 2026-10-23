"""`agent-session check`: does a published transcript cover this branch's HEAD?

Repos run it as an ordinary local-ci step, so it reads git, gh and the local record itself. Its output is a contract for
coding agents and people (pinned by tests): the first line starts with `agent-session: ok|missing|stale|unlinked|
unverified`, and a failure is followed by `fix:` (the exact command), `next:`, and the declaration alternative.
With an open PR its body is authoritative; without one, the local record (store.py) is. A failed PR lookup fails closed.
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


def decide(check: Input) -> Result:
    head = check.head[:12]
    where = f"for {check.repo_slug} branch {check.branch}" + (f" PR #{check.pr[0]}" if check.pr else "")
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


def open_pr(repo_slug: str, branch: str) -> tuple[tuple[int, str] | None, str]:
    """The branch's open PR as (number, body), or None; an error string when GitHub could not be asked."""
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
    return (int(pulls[0]["number"]), str(pulls[0].get("body") or "")), ""
