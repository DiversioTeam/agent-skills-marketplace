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


# Each source owns its own lines: Courage's publish keeps the developer's link and the developer's `share` keeps Courage's.
COURAGE_LABEL = "Courage conversation transcript"
_LINK_LINE = re.compile(r"^- \[(?P<label>[^\]]+)\]\(https://internal-share\.diversio\.com/session-[^)]+\)\s*$", re.MULTILINE)


def upsert(body: str, new_section: str, keep_labels: tuple[str, ...] = (COURAGE_LABEL,)) -> str:
    """Replace an existing Agent sessions section, or append one at the end. Link lines from other sources (labels
    starting with one of `keep_labels`) in the old section are carried into the new one."""
    match = _SECTION.search(body)
    if not match:
        return f"{body.rstrip()}\n\n{new_section}" if body.strip() else new_section
    kept = [line.group(0) for line in _LINK_LINE.finditer(match.group(0)) if line.group("label").startswith(keep_labels)
            and line.group(0) not in new_section]
    if kept:
        lines = new_section.splitlines()
        position = max((index for index, line in enumerate(lines) if line.startswith("- ")), default=1) + 1
        new_section = "\n".join([*lines[:position], *kept, *lines[position:]]) + "\n"
    return _SECTION.sub(lambda _match: new_section + "\n", body, count=1).rstrip() + "\n"
