#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class SessionRow:
    tool: str
    session_id: str
    start: dt.datetime | None
    end: dt.datetime | None
    branch: str | None
    cwd: str | None
    summary: str | None
    source: str


_URL_RE = re.compile(r"https?://\S+")
_REDACT_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)github_pat_[A-Za-z0-9_]{10,}"), "[REDACTED_GITHUB_PAT]"),
    (re.compile(r"(?i)ghp_[A-Za-z0-9]{10,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(?i)gho_[A-Za-z0-9]{10,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(?i)ghu_[A-Za-z0-9]{10,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(?i)ghs_[A-Za-z0-9]{10,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(?i)sk-[A-Za-z0-9]{10,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"(?i)pk_[A-Za-z0-9]{10,}"), "[REDACTED_API_TOKEN]"),
    (re.compile(r"(?i)AIza[0-9A-Za-z_-]{20,}"), "[REDACTED_GCP_API_KEY]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_ACCESS_KEY_ID]"),
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"
        ),
        "[REDACTED_PRIVATE_KEY_BLOCK]",
    ),
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "[REDACTED_JWT]",
    ),
    (re.compile(r"(?i)xox[baprs]-[A-Za-z0-9-]{10,}"), "[REDACTED_SLACK_TOKEN]"),
]


def _git_root(path: Path) -> Path | None:
    try:
        cp = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except Exception:
        return None
    root = cp.stdout.strip()
    if not root:
        return None
    try:
        return Path(root).resolve()
    except Exception:
        return None


def _resolve_project_filter_root(project_path: Path) -> Path:
    return _git_root(project_path) or project_path


def _cwd_matches_project(cwd: str | None, project_root: Path) -> bool:
    if not cwd:
        return False
    try:
        cwd_path = Path(cwd).expanduser().resolve()
    except Exception:
        return False
    try:
        cwd_path.relative_to(project_root)
        return True
    except Exception:
        return False


def _parse_iso8601(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = dt.datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except Exception:
        return None


def _to_local(dt_value: dt.datetime | None) -> str:
    if not dt_value:
        return "-"
    try:
        local = dt_value.astimezone()
    except Exception:
        local = dt_value
    return local.strftime("%Y-%m-%d %H:%M")


def _human_age(dt_value: dt.datetime | None, now: dt.datetime) -> str:
    if not dt_value:
        return "-"
    try:
        delta = now - dt_value.astimezone(dt.timezone.utc)
    except Exception:
        return "-"
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "in future"
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    if days:
        return f"{days}d ago"
    if hours:
        return f"{hours}h ago"
    if minutes:
        return f"{minutes}m ago"
    return f"{seconds}s ago"


def _redact(text: str | None) -> str | None:
    if text is None:
        return None
    redacted = _URL_RE.sub("[URL]", text)
    for pattern, replacement in _REDACT_REPLACEMENTS:
        redacted = pattern.sub(replacement, redacted)
    home = str(Path.home())
    if home:
        redacted = redacted.replace(home, "~")
    return redacted


def _first_non_trivial_line(text: str) -> str:
    skip_prefixes = (
        "# agents.md instructions",
        "<environment_context",
        "<instructions",
        "user arguments:",
    )
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith(skip_prefixes):
            continue
        if line.startswith("```"):
            continue
        return line
    return (text.strip().splitlines() or [""])[0].strip()


def _read_first_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            first = handle.readline()
            if not first:
                return None
            return json.loads(first)
    except Exception:
        return None


def _read_last_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            if size == 0:
                return None
            chunk = b""
            step = 4096
            while size > 0:
                read_size = min(step, size)
                size -= read_size
                handle.seek(size)
                chunk = handle.read(read_size) + chunk
                if b"\n" in chunk:
                    break
            lines = [line for line in chunk.splitlines() if line.strip()]
            if not lines:
                return None
            return json.loads(lines[-1].decode("utf-8", errors="replace"))
    except Exception:
        return None


def _iter_recent_files(root: Path, pattern_suffix: str, scan_limit: int) -> list[Path]:
    files: list[Path] = []
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if not filename.endswith(pattern_suffix):
                continue
            files.append(Path(dirpath) / filename)
    files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    if scan_limit > 0:
        return files[:scan_limit]
    return files


def _extract_codex_prompt_snippet(path: Path, max_lines: int = 80) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for idx, line in enumerate(handle):
                if idx > max_lines:
                    break
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                payload = obj.get("payload") or {}
                if (
                    obj.get("type") == "response_item"
                    and payload.get("type") == "message"
                    and payload.get("role") == "user"
                ):
                    content = payload.get("content") or []
                    texts: list[str] = []
                    for item in content:
                        if not isinstance(item, dict):
                            continue
                        if item.get("type") in {"input_text", "text"}:
                            texts.append(str(item.get("text") or ""))
                    combined = "\n".join(texts).strip()
                    if combined:
                        snippet = _first_non_trivial_line(combined)
                        snippet = _redact(snippet)
                        return snippet[:140] if snippet else None
        return None
    except Exception:
        return None


def _list_codex_sessions(project_path: Path, scan_limit: int) -> list[SessionRow]:
    codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    sessions_root = codex_home / "sessions"
    if not sessions_root.exists():
        return []

    rows: list[SessionRow] = []
    for session_file in _iter_recent_files(sessions_root, ".jsonl", scan_limit=scan_limit):
        first = _read_first_json(session_file)
        if not first or first.get("type") != "session_meta":
            continue
        payload = first.get("payload") or {}
        cwd = payload.get("cwd")
        if not _cwd_matches_project(cwd, project_path):
            continue

        session_id = payload.get("id") or "-"
        start = _parse_iso8601(payload.get("timestamp") or first.get("timestamp"))
        last = _read_last_json(session_file)
        end = _parse_iso8601((last or {}).get("timestamp"))
        summary = _extract_codex_prompt_snippet(session_file)
        rows.append(
            SessionRow(
                tool="codex",
                session_id=str(session_id),
                start=start,
                end=end,
                branch=None,
                cwd=cwd,
                summary=summary,
                source=str(session_file),
            )
        )
    return rows


def _extract_claude_prompt_snippet(path: Path, max_lines: int = 60) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for idx, line in enumerate(handle):
                if idx > max_lines:
                    break
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") != "user":
                    continue
                message = obj.get("message") or {}
                content = message.get("content")
                if isinstance(content, str):
                    text = content.strip()
                else:
                    text = ""
                if text:
                    snippet = _first_non_trivial_line(text)
                    snippet = _redact(snippet)
                    return snippet[:140] if snippet else None
        return None
    except Exception:
        return None


def _list_claude_sessions(project_path: Path, scan_limit: int) -> list[SessionRow]:
    claude_home = Path(os.environ.get("CLAUDE_HOME") or (Path.home() / ".claude"))
    projects_root = claude_home / "projects"
    if not projects_root.exists():
        return []

    project_key = "-" + str(project_path).lstrip(os.sep).replace(os.sep, "-")
    project_dir = projects_root / project_key

    def iter_transcripts() -> list[Path]:
        if project_dir.exists():
            files = [p for p in project_dir.glob("*.jsonl") if p.is_file()]
            files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
            return files[:scan_limit] if scan_limit > 0 else files

        per_project = max(1, min(30, scan_limit))
        candidates: list[Path] = []
        for maybe_project in projects_root.iterdir():
            if not maybe_project.is_dir():
                continue
            files = [p for p in maybe_project.glob("*.jsonl") if p.is_file()]
            files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
            candidates.extend(files[:per_project])
        candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        return candidates[:scan_limit] if scan_limit > 0 else candidates

    grouped: dict[str, dict[str, Any]] = {}
    for transcript in iter_transcripts():
        first = _read_first_json(transcript)
        if not first:
            continue
        session_id = first.get("sessionId")
        if not session_id:
            continue
        cwd = first.get("cwd")
        if not _cwd_matches_project(cwd, project_path):
            continue

        start = _parse_iso8601(first.get("timestamp"))
        last = _read_last_json(transcript)
        end = _parse_iso8601((last or {}).get("timestamp"))
        branch = first.get("gitBranch")
        snippet = _extract_claude_prompt_snippet(transcript)

        key = str(session_id)
        entry = grouped.get(key)
        if entry is None:
            entry = {
                "session_id": key,
                "cwd": cwd,
                "branch": branch,
                "start": start,
                "end": end,
                "snippet": snippet,
                "sources": [],
            }
            grouped[key] = entry

        entry["sources"].append(str(transcript))
        entry["branch"] = entry.get("branch") or branch
        entry["cwd"] = entry.get("cwd") or cwd
        entry["snippet"] = entry.get("snippet") or snippet
        if start and (entry.get("start") is None or start < entry["start"]):
            entry["start"] = start
        if end and (entry.get("end") is None or end > entry["end"]):
            entry["end"] = end

    rows: list[SessionRow] = []
    for session_id, info in grouped.items():
        rows.append(
            SessionRow(
                tool="claude",
                session_id=session_id,
                start=info.get("start"),
                end=info.get("end"),
                branch=info.get("branch"),
                cwd=info.get("cwd"),
                summary=info.get("snippet"),
                source=str(info.get("sources", ["-"])[0]),
            )
        )
    return rows


def _print_markdown(rows: list[SessionRow]) -> None:
    now = dt.datetime.now(tz=dt.timezone.utc)
    print("| # | Tool | Last active | Start | Branch | Session ID | Summary |")
    print("| -: | --- | --- | --- | --- | --- | --- |")
    for idx, row in enumerate(rows, start=1):
        last_active = _human_age(row.end or row.start, now)
        start = _to_local(row.start)
        branch = row.branch or "-"
        summary = row.summary or "-"
        print(
            f"| {idx} | `{row.tool}` | {last_active} | `{start}` | `{branch}` | `{row.session_id}` | {summary} |"
        )
    print()
    print("Pick sessions by ID:")
    print("- Codex: `codex resume <session-id>`")
    print("- Claude Code: `claude -r <session-id>`")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="List recent Codex + Claude Code sessions for the current project with human-readable metadata."
    )
    parser.add_argument(
        "--project",
        default=os.getcwd(),
        help="Project path to filter sessions by (defaults to current working directory).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Max rows to print after filtering (default: 15).",
    )
    parser.add_argument(
        "--scan",
        type=int,
        default=250,
        help="Max transcript files to inspect per tool before filtering (default: 250).",
    )
    parser.add_argument(
        "--tool",
        choices=["all", "codex", "claude"],
        default="all",
        help="Which tool's sessions to include (default: all).",
    )
    args = parser.parse_args(argv)

    project_path = _resolve_project_filter_root(Path(args.project).expanduser().resolve())
    scan_limit = max(0, int(args.scan))
    rows: list[SessionRow] = []

    if args.tool in {"all", "codex"}:
        rows.extend(_list_codex_sessions(project_path=project_path, scan_limit=scan_limit))
    if args.tool in {"all", "claude"}:
        rows.extend(_list_claude_sessions(project_path=project_path, scan_limit=scan_limit))

    rows.sort(key=lambda r: (r.end or r.start or dt.datetime.min.replace(tzinfo=dt.timezone.utc)), reverse=True)
    _print_markdown(rows[: max(0, int(args.limit))])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
