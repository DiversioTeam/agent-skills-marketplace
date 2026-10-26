"""The PR description's "Agent sessions" section: what counts as present, and how to write it."""

from __future__ import annotations

import re

SECTION_HEADING = "## Agent sessions"
LINK = re.compile(r"https://internal-share\.diversio\.com/session-[A-Za-z0-9._%-]+\.html")
# The explicit declaration for PRs no agent worked on. It needs a reason.
DECLARATION = re.compile(r"^\s*(?:[-*]\s*)?No agent session:\s*\S.{2,}$", re.MULTILINE | re.IGNORECASE)
_SECTION = re.compile(r"^## Agent sessions[ \t]*\n[\s\S]*?(?=^## |\Z)", re.MULTILINE)


def has_transcript(body: str) -> bool:
    return bool(LINK.search(body) or DECLARATION.search(body))


def section(links: list[tuple[str, str]], note: str = "") -> str:
    """Markdown for the section. `links` holds (label, url) pairs."""
    lines = [SECTION_HEADING, ""]
    lines += [f"- [{label}]({url})" for label, url in links]
    lines += ["", note.strip()] if note.strip() else []
    lines += ["", "Redacted transcripts of the agent sessions behind this PR (Diversio staff only)."]
    return "\n".join(lines).rstrip() + "\n"


def upsert(body: str, new_section: str) -> str:
    """Replace an existing Agent sessions section, or append one at the end."""
    if _SECTION.search(body):
        return _SECTION.sub(lambda _match: new_section + "\n", body, count=1).rstrip() + "\n"
    return f"{body.rstrip()}\n\n{new_section}" if body.strip() else new_section
