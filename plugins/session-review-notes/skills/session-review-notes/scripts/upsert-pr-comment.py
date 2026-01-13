#!/usr/bin/env python3

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


MARKER = "<!-- diversio:session-review-notes -->"
STATE_PREFIX = "<!-- diversio:session-review-notes:state "
SESSIONS_START = "<!-- diversio:session-review-notes:sessions:start -->"
SESSIONS_END = "<!-- diversio:session-review-notes:sessions:end -->"
ENTRY_META_PREFIX = "<!-- diversio:session-review-notes:entry "

SCHEMA_VERSION = 2
# GitHub PR comments hard-fail near ~65k chars; keep a safety buffer for markup and future schema growth.
MAX_BODY_CHARS = 60000
MAX_PROMPTS_CHARS = 2000
MAX_TEXT_CHARS = 2000
MAX_LIST_ITEMS = 25
MAX_ITEM_CHARS = 280
MAX_SESSION_LABEL_CHARS = 80

STATE_RE = re.compile(r"<!-- diversio:session-review-notes:state\s+(\{.*?\})\s*-->")
ENTRY_META_RE = re.compile(r"<!-- diversio:session-review-notes:entry\s+(\{.*?\})\s*-->")


URL_RE = re.compile(r"https?://\S+")
REDACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)github_pat_[A-Za-z0-9_]{10,}"), "[REDACTED_GITHUB_PAT]"),
    (re.compile(r"(?i)gh[pousr]_[A-Za-z0-9]{10,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(?i)sk-[A-Za-z0-9]{10,}"), "[REDACTED_API_KEY]"),
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
    (
        re.compile(r"(?i)\bAuthorization:\s*(Bearer|Token)\s+\S+"),
        "Authorization: [REDACTED_AUTH]",
    ),
    (re.compile(r"(?i)xox[baprs]-[A-Za-z0-9-]{10,}"), "[REDACTED_SLACK_TOKEN]"),
]


def _run(cmd: list[str], *, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=check,
    )


def _gh(repo: str | None, args: list[str], *, check: bool = True, input_text: str | None = None) -> str:
    cmd = ["gh"]
    cmd.extend(args)
    if repo:
        # `-R` works for `gh api` and some other commands; safe to include only when applicable.
        if cmd[1] == "api":
            cmd[2:2] = ["-R", repo]
    cp = _run(cmd, check=check, input_text=input_text)
    return cp.stdout


def _gh_json(repo: str | None, args: list[str]) -> Any:
    return json.loads(_gh(repo, args))


def _gh_api_json(repo: str, endpoint: str) -> Any:
    return _gh_json(repo, ["api", endpoint])


def _gh_api_json_paginated(repo: str, endpoint: str) -> list[Any]:
    data = _gh_json(repo, ["api", endpoint, "--paginate", "--slurp"])
    if isinstance(data, list) and data and isinstance(data[0], list):
        flattened: list[Any] = []
        for page in data:
            flattened.extend(page)
        return flattened
    if isinstance(data, list):
        return data
    return [data]


def _gh_api_including_headers(repo: str, endpoint: str) -> tuple[dict[str, str], str]:
    raw = _gh(repo, ["api", "-i", endpoint])
    if "\r\n\r\n" in raw:
        header_blob, body = raw.split("\r\n\r\n", 1)
        header_lines = header_blob.split("\r\n")
    elif "\n\n" in raw:
        header_blob, body = raw.split("\n\n", 1)
        header_lines = header_blob.split("\n")
    else:
        return {}, raw

    headers: dict[str, str] = {}
    for line in header_lines:
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        headers[k.strip().lower()] = v.strip()
    return headers, body


def _redact(text: str, allowed_hosts: set[str]) -> str:
    def _sub_url(m: re.Match[str]) -> str:
        u = m.group(0)
        try:
            host = urlparse(u).netloc.lower()
        except Exception:
            host = ""
        return u if host in allowed_hosts else "[URL]"

    out = URL_RE.sub(_sub_url, text)
    for pattern, replacement in REDACT_PATTERNS:
        out = pattern.sub(replacement, out)
    home = str(Path.home())
    if home:
        out = out.replace(home, "~")
    return out


def _redact_obj(value: Any, allowed_hosts: set[str]) -> Any:
    if isinstance(value, str):
        return _redact(value, allowed_hosts)
    if isinstance(value, list):
        return [_redact_obj(v, allowed_hosts) for v in value]
    if isinstance(value, dict):
        return {k: _redact_obj(v, allowed_hosts) for k, v in value.items()}
    return value


def _parse_pr_arg(pr: str) -> tuple[str | None, int | None]:
    pr = pr.strip()
    if pr.isdigit():
        return None, int(pr)

    parsed = urlparse(pr)
    if not parsed.netloc:
        return None, None
    parts = [p for p in parsed.path.split("/") if p]
    # /{owner}/{repo}/pull/{number}
    if len(parts) >= 4 and parts[2] in {"pull", "pulls"} and parts[3].isdigit():
        owner, repo = parts[0], parts[1]
        return f"{owner}/{repo}", int(parts[3])
    return None, None


def _resolve_repo_fallback() -> str:
    data = _gh_json(None, ["repo", "view", "--json", "nameWithOwner"])
    return str(data["nameWithOwner"])


def _resolve_pr_number(repo: str, pr_arg: str) -> int:
    if pr_arg == "auto":
        try:
            data = _gh_json(None, ["pr", "view", "-R", repo, "--json", "number"])
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            extra = f"\n\n{stderr}" if stderr else ""
            raise SystemExit(
                "Unable to resolve the PR number automatically. "
                "Run this script from within the target repo, or provide an explicit PR number/URL via --pr."
                f"{extra}"
            ) from None
        return int(data["number"])

    _, pr_number = _parse_pr_arg(pr_arg)
    if pr_number is None:
        raise SystemExit("Could not parse --pr. Provide a PR number, PR URL, or use --pr auto.")
    return pr_number


def _detect_generator_version() -> str | None:
    try:
        script_path = Path(__file__).resolve()
        plugin_json = script_path.parents[4] / ".claude-plugin" / "plugin.json"
        if not plugin_json.exists():
            return None
        data = json.loads(plugin_json.read_text(encoding="utf-8"))
        version = data.get("version")
        if not version:
            return None
        return str(version)
    except Exception:
        return None


@dataclasses.dataclass(frozen=True)
class ExistingComment:
    comment_id: int
    body: str
    etag: str | None
    updated_at: str | None
    html_url: str | None
    marker_comment_ids: tuple[int, ...]


def _find_existing_comment(repo: str, pr_number: int) -> ExistingComment | None:
    comments = _gh_api_json_paginated(repo, f"repos/{repo}/issues/{pr_number}/comments")
    marked = [c for c in comments if isinstance(c.get("body"), str) and MARKER in c["body"]]
    if not marked:
        return None
    marker_comment_ids: list[int] = []
    for c in marked:
        try:
            marker_comment_ids.append(int(c.get("id")))
        except Exception:
            continue
    marked.sort(key=lambda c: str(c.get("updated_at") or ""))
    chosen = marked[-1]
    comment_id = int(chosen["id"])
    headers, body_text = _gh_api_including_headers(repo, f"repos/{repo}/issues/comments/{comment_id}")
    data = json.loads(body_text)
    return ExistingComment(
        comment_id=comment_id,
        body=str(data.get("body") or ""),
        etag=headers.get("etag"),
        updated_at=data.get("updated_at"),
        html_url=data.get("html_url"),
        marker_comment_ids=tuple(marker_comment_ids),
    )


def _extract_state_with_repairs(body: str) -> tuple[dict[str, Any], list[str]]:
    match = STATE_RE.search(body)
    if not match:
        return {}, ["Missing state marker; state reinitialized."]
    try:
        parsed = json.loads(match.group(1))
    except Exception:
        return {}, ["Invalid state marker JSON; state reinitialized."]
    if not isinstance(parsed, dict):
        return {}, ["Invalid state marker shape; state reinitialized."]
    return parsed, []


def _extract_sessions_block_with_repairs(body: str) -> tuple[str, list[str]]:
    start = body.find(SESSIONS_START)
    end = body.find(SESSIONS_END)
    if start == -1 or end == -1 or end < start:
        recovered: list[str] = []
        for match in re.finditer(re.escape(ENTRY_META_PREFIX), body):
            entry_start = match.start()
            entry_end = body.find("</details>", entry_start)
            if entry_end == -1:
                continue
            recovered.append(body[entry_start : entry_end + len("</details>")].strip())
        if recovered:
            return (
                "\n\n".join(recovered).strip("\n"),
                [
                    "Missing session markers; session log rebuilt by recovering existing entry markers.",
                ],
            )
        return "", ["Missing session markers; session log reinitialized."]
    block = body[start + len(SESSIONS_START) : end].strip("\n")

    repairs: list[str] = []
    if "Session log (cumulative)" in block and "<summary><strong>Session log" in block:
        repairs.append("Legacy session marker layout detected; migrated to canonical layout.")
        summary_end = block.find("</summary>")
        if summary_end != -1:
            block = block[summary_end + len("</summary>") :].strip()
        if block.endswith("</details>"):
            block = block[: -len("</details>")].rstrip()
    return block.strip("\n"), repairs


@dataclasses.dataclass(frozen=True)
class SessionKey:
    tool: str
    session_id: str


@dataclasses.dataclass(frozen=True)
class SessionEntry:
    key: SessionKey | None
    created_at: dt.datetime | None
    raw: str


def _parse_entries(entries_block: str) -> list[SessionEntry]:
    if ENTRY_META_PREFIX not in entries_block:
        stripped = entries_block.strip()
        return [SessionEntry(key=None, created_at=None, raw=stripped)] if stripped else []

    parts = entries_block.split(ENTRY_META_PREFIX)
    entries: list[SessionEntry] = []
    pre = parts[0].strip()
    if pre:
        entries.append(SessionEntry(key=None, created_at=None, raw=pre))

    for part in parts[1:]:
        raw = (ENTRY_META_PREFIX + part).strip()
        key: SessionKey | None = None
        created_at: dt.datetime | None = None
        match = ENTRY_META_RE.search(raw)
        if match:
            try:
                meta = json.loads(match.group(1))
                tool = str(meta.get("tool") or "").strip()
                session_id = str(meta.get("session_id") or "").strip()
                if tool and session_id:
                    key = SessionKey(tool=tool, session_id=session_id)
                created_at = _parse_iso8601(meta.get("created_at"))
            except Exception:
                key = None
        entries.append(SessionEntry(key=key, created_at=created_at, raw=raw))
    return entries


def _merge_entries(
    existing_entries_block: str,
    new_entry_raw: str,
    new_key: SessionKey,
    *,
    delta_empty: bool,
) -> str:
    existing_entries = _parse_entries(existing_entries_block)
    merged: list[str] = []

    if delta_empty:
        replaced = False
        for entry in existing_entries:
            if (not replaced) and entry.key == new_key:
                merged.append(new_entry_raw.strip())
                replaced = True
            else:
                merged.append(entry.raw.strip())
        if not replaced:
            merged.insert(0, new_entry_raw.strip())
    else:
        merged.append(new_entry_raw.strip())
        for entry in existing_entries:
            if entry.key == new_key:
                continue
            merged.append(entry.raw.strip())

    merged_clean = [m for m in merged if m.strip()]
    return "\n\n".join(merged_clean).strip() + ("\n" if merged_clean else "")


def _entries_to_block(entries: list[SessionEntry]) -> str:
    parts = [e.raw.strip() for e in entries if e.raw.strip()]
    if not parts:
        return ""
    return "\n\n".join(parts).strip() + "\n"


def _sort_entries(entries: list[SessionEntry]) -> list[SessionEntry]:
    if not entries:
        return []

    keyed = [e for e in entries if e.key]
    unkeyed = [e for e in entries if not e.key]

    keyed.sort(
        key=lambda e: e.created_at
        or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
        reverse=True,
    )
    return keyed + unkeyed


def _normalize_entries_block(
    entries_block: str, *, required_key: SessionKey | None = None, max_entries: int | None = None
) -> str:
    entries = _sort_entries(_parse_entries(entries_block))
    if max_entries is None or max_entries <= 0:
        return _entries_to_block(entries)

    required: list[SessionEntry] = []
    others: list[SessionEntry] = []
    for entry in entries:
        if required_key and entry.key == required_key:
            required.append(entry)
        else:
            others.append(entry)

    kept: list[SessionEntry] = []
    kept.extend(required)
    for entry in others:
        if len(kept) >= max_entries:
            break
        kept.append(entry)

    if required_key and not any(e.key == required_key for e in kept):
        for entry in entries:
            if entry.key == required_key:
                kept.insert(0, entry)
                break

    return _entries_to_block(kept)


def _count_entries(entries_block: str) -> tuple[int, int, int, list[dict[str, str]]]:
    total = 0
    codex = 0
    claude = 0
    included: list[dict[str, str]] = []
    for match in ENTRY_META_RE.finditer(entries_block):
        try:
            meta = json.loads(match.group(1))
            tool = str(meta.get("tool") or "").strip()
            session_id = str(meta.get("session_id") or "").strip()
        except Exception:
            continue
        if not tool or not session_id:
            continue
        total += 1
        if tool == "codex":
            codex += 1
        if tool == "claude":
            claude += 1
        included.append({"tool": tool, "id": session_id})
    # Deduplicate while preserving order
    seen = set()
    uniq: list[dict[str, str]] = []
    for item in included:
        key = (item["tool"], item["id"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return total, codex, claude, uniq


def _parse_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    except Exception:
        return None
    return None


def _merge_included_sessions(
    prev: Any, scanned: list[dict[str, str]]
) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    if isinstance(prev, list):
        for item in prev:
            if not isinstance(item, dict):
                continue
            tool = str(item.get("tool") or "").strip()
            sid = str(item.get("id") or item.get("session_id") or "").strip()
            if tool and sid:
                merged.append({"tool": tool, "id": sid})

    merged.extend(scanned)
    seen: set[tuple[str, str]] = set()
    uniq: list[dict[str, str]] = []
    for item in merged:
        key = (item["tool"], item["id"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return uniq


def _parse_iso8601(value: Any) -> dt.datetime | None:
    if not value:
        return None
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = dt.datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except Exception:
        return None


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return text[: max_chars - 3] + "..."


def _normalize_text(value: Any, *, max_chars: int) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return ""
    try:
        text = str(value)
    except Exception:
        return ""
    return _truncate(text.strip(), max_chars)


def _normalize_list(value: Any, *, max_items: int, max_item_chars: int) -> list[str]:
    if value is None:
        return []
    items: list[str] = []
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        raw_items = [value]
    else:
        raw_items = []

    for raw in raw_items:
        if raw is None:
            continue
        if isinstance(raw, (list, dict)):
            continue
        try:
            item = str(raw).strip()
        except Exception:
            continue
        if not item:
            continue
        items.append(_truncate(item, max_item_chars))
        if len(items) >= max_items:
            break
    return items


def _normalize_payload(payload_raw: Any) -> dict[str, Any]:
    if not isinstance(payload_raw, dict):
        raise SystemExit("Payload must be a JSON object.")

    normalized: dict[str, Any] = {}
    normalized["intent"] = _normalize_text(payload_raw.get("intent"), max_chars=MAX_TEXT_CHARS)
    normalized["risk"] = _normalize_text(payload_raw.get("risk"), max_chars=MAX_TEXT_CHARS)
    normalized["tests_summary"] = _normalize_text(payload_raw.get("tests_summary"), max_chars=MAX_TEXT_CHARS)
    normalized["prompts"] = _normalize_text(payload_raw.get("prompts"), max_chars=MAX_PROMPTS_CHARS)
    normalized["session_label"] = _truncate(
        _normalize_text(payload_raw.get("session_label"), max_chars=MAX_SESSION_LABEL_CHARS),
        MAX_SESSION_LABEL_CHARS,
    )
    normalized["delta_narrative"] = _normalize_text(payload_raw.get("delta_narrative"), max_chars=MAX_TEXT_CHARS)
    normalized["tests_markdown"] = _normalize_text(payload_raw.get("tests_markdown"), max_chars=MAX_TEXT_CHARS)
    normalized["notes"] = _normalize_text(payload_raw.get("notes"), max_chars=MAX_TEXT_CHARS)

    normalized["pr_scope_bullets"] = _normalize_list(
        payload_raw.get("pr_scope_bullets"), max_items=MAX_LIST_ITEMS, max_item_chars=MAX_ITEM_CHARS
    )
    normalized["hotspots"] = _normalize_list(
        payload_raw.get("hotspots"), max_items=MAX_LIST_ITEMS, max_item_chars=MAX_ITEM_CHARS
    )
    normalized["human_steering"] = _normalize_list(
        payload_raw.get("human_steering"), max_items=MAX_LIST_ITEMS, max_item_chars=MAX_ITEM_CHARS
    )
    normalized["decisions"] = _normalize_list(
        payload_raw.get("decisions"), max_items=MAX_LIST_ITEMS, max_item_chars=MAX_ITEM_CHARS
    )

    normalized["entry_created_at"] = _normalize_text(payload_raw.get("entry_created_at"), max_chars=64)
    return normalized


_TEST_ITEM_RE = re.compile(r"^\s*-\s*\[([xX ])\]\s*(.+?)\s*$")


def _parse_tests_markdown(tests_markdown: str) -> tuple[list[str], list[str]]:
    if not tests_markdown.strip():
        return [], []

    self_reported: list[str] = []
    not_run: list[str] = []
    for raw_line in tests_markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        match = _TEST_ITEM_RE.match(line)
        if match:
            checked = match.group(1).strip().lower() == "x"
            item = match.group(2).strip()
        else:
            if not line.lstrip().startswith("- "):
                continue
            checked = False
            item = line.lstrip()[2:].strip()
        if not item:
            continue
        item = _truncate(item, MAX_ITEM_CHARS)
        if checked:
            self_reported.append(item)
        else:
            not_run.append(item)
    return self_reported, not_run


def _render_tests_section(tests_markdown: str) -> str:
    self_reported, not_run = _parse_tests_markdown(tests_markdown)
    if not self_reported and not not_run:
        return "- None recorded"

    lines: list[str] = []
    if self_reported:
        lines.append("- Self-reported:")
        lines.extend([f"  - `{t}`" for t in self_reported])
    if not_run:
        lines.append("- Not run:")
        lines.extend([f"  - `{t}`" for t in not_run])
    return "\n".join(lines)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _render_bullets(lines: Iterable[str] | None) -> str:
    if not lines:
        return "- (not provided)"
    rendered = [f"- {line}" for line in lines if str(line).strip()]
    return "\n".join(rendered) if rendered else "- (not provided)"


def _render_comment(
    *,
    pr: dict[str, Any],
    payload: dict[str, Any],
    prev_head: str | None,
    head_sha: str,
    entries_block: str,
    delta_summary: str,
    delta_details: str,
    hotspot_map: str,
    provenance: str,
    now: dt.datetime,
    sessions_total: int,
    codex_count: int,
    claude_count: int,
    included_sessions: list[dict[str, str]],
    sessions_sha256: str | None,
    repair_count: int | None,
    last_repair_at: str | None,
    generator: str,
    generator_version: str | None,
) -> str:
    base_ref = str((pr.get("base") or {}).get("ref") or "")
    head_short = head_sha[:7]
    pr_url = str(pr.get("html_url") or "")

    pr_stats = (
        f'{int(pr.get("changed_files") or 0)} files • '
        f'+{int(pr.get("additions") or 0)} / -{int(pr.get("deletions") or 0)} • '
        f'{int(pr.get("commits") or 0)} commits'
    )

    state_obj: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "base": base_ref,
        "head": head_sha,
        "prev_head": prev_head,
        "rev": int(payload.get("_rev") or 0) or None,
        "sessions_total": sessions_total,
        "codex": codex_count,
        "claude": claude_count,
        "included_sessions": included_sessions,
        "sessions_sha256": sessions_sha256,
        "repair_count": repair_count,
        "last_repair_at": last_repair_at,
        "generator": generator,
        "generator_version": generator_version,
        "last_updated": now.isoformat(),
    }
    state_obj = {k: v for k, v in state_obj.items() if v is not None}
    state_line = f"{STATE_PREFIX}{json.dumps(state_obj, separators=(',',':'))} -->"

    intent = str(payload.get("intent") or "-")
    risk = str(payload.get("risk") or "-")
    tests_summary = str(payload.get("tests_summary") or "").strip()
    if tests_summary:
        tests_summary = f"Self-reported: {tests_summary}"
    else:
        tests_summary = "None recorded (see session log)"

    pr_scope_bullets = payload.get("pr_scope_bullets") or []
    hotspots = payload.get("hotspots") or []
    prompts = str(payload.get("prompts") or "").strip()

    updated_local = now.strftime("%Y-%m-%d %H:%M %Z").strip()

    return f"""{MARKER}
{state_line}

<div align="center">

## SESSION REVIEW NOTES
<sub>Single upserted PR comment • cumulative across Codex + Claude Code sessions</sub>

</div>

> [!IMPORTANT]
> This comment is **updated**, not duplicated. Re-run `/session-review-notes:generate` to update it. Please do not create a second “SESSION REVIEW NOTES” comment.

### Summary

| Field | Value |
| --- | --- |
| **Intent** | {intent} |
| **PR coverage** | `{base_ref}...{head_short}` |
| **PR size** | {pr_stats} |
| **Sessions** | `{sessions_total}` (Codex×`{codex_count}`, Claude×`{claude_count}`) |
| **Latest delta** | {delta_summary} |
| **Risk** | {risk} |
| **Tests** | {tests_summary} |

<details>
<summary><strong>What changed (full PR diff)</strong></summary>

{_render_bullets(pr_scope_bullets)}

</details>

<details>
<summary><strong>Hotspot map (deterministic)</strong></summary>

{hotspot_map}

</details>

<details>
<summary><strong>Review hotspots / risks</strong></summary>

{_render_bullets(hotspots)}

</details>

<details>
<summary><strong>Latest delta (since prior update)</strong></summary>

{delta_details}

</details>

<details>
<summary><strong>Provenance / integrity</strong></summary>

{provenance}

</details>

<details>
<summary><strong>Session log (cumulative)</strong> <sub>(newest first)</sub></summary>

{SESSIONS_START}
{entries_block.rstrip()}
{SESSIONS_END}

</details>

<details>
<summary><strong>Prompts (optional, redacted)</strong></summary>

```text
{prompts or "-"}
```

</details>

---

<sub>PR: {pr_url} • Last updated: {updated_local} • No secrets/tokens/credentials in this comment</sub>
"""


def _compute_delta(repo: str, prev_head: str | None, head_sha: str) -> tuple[str, str]:
    if not prev_head:
        return "n/a — first entry", "- n/a — first entry"
    if prev_head == head_sha:
        return "n/a — no PR head change since last update", "- n/a — no PR head change since last update"

    try:
        compare = _gh_api_json(repo, f"repos/{repo}/compare/{prev_head}...{head_sha}")
        files = compare.get("files") or []
        additions = sum(int(f.get("additions") or 0) for f in files)
        deletions = sum(int(f.get("deletions") or 0) for f in files)
        summary = f"`{len(files)}` files • +{additions} / -{deletions}"

        top = sorted(files, key=lambda f: int(f.get("changes") or 0), reverse=True)[:8]
        if not top:
            return summary, "- (no file-level delta available)"
        details = "\n".join(
            [
                f'- `{f.get("filename")}` (+{int(f.get("additions") or 0)}/-{int(f.get("deletions") or 0)})'
                for f in top
                if f.get("filename")
            ]
        )
        return summary, details or "- (no file-level delta available)"
    except Exception:
        return "(unable to compute compare)", "- (unable to compute compare)"


def _fetch_pr_files(repo: str, pr_number: int) -> list[dict[str, Any]]:
    try:
        return _gh_api_json_paginated(repo, f"repos/{repo}/pulls/{pr_number}/files?per_page=100")
    except Exception:
        return []


def _area_for_path(filename: str) -> str:
    if "/" not in filename:
        return "(root)"
    return filename.split("/", 1)[0] + "/"


def _render_hotspot_map(pr_files: list[dict[str, Any]]) -> str:
    if not pr_files:
        return "- (unable to compute)"

    grouped: dict[str, dict[str, Any]] = {}
    for f in pr_files:
        filename = f.get("filename")
        if not isinstance(filename, str) or not filename:
            continue
        area = _area_for_path(filename)
        stats = grouped.setdefault(area, {"files": set(), "additions": 0, "deletions": 0})
        stats["files"].add(filename)
        stats["additions"] += int(f.get("additions") or 0)
        stats["deletions"] += int(f.get("deletions") or 0)

    rows: list[tuple[str, int, int, int]] = []
    for area, stats in grouped.items():
        files_count = len(stats["files"])
        additions = int(stats["additions"])
        deletions = int(stats["deletions"])
        rows.append((area, files_count, additions, deletions))

    rows.sort(key=lambda r: (r[2] + r[3], r[1]), reverse=True)
    top = rows[:10]
    if not top:
        return "- (no file-level data available)"

    lines = [
        "| Area | Files | + | - |",
        "| --- | ---: | ---: | ---: |",
    ]
    for area, files_count, additions, deletions in top:
        lines.append(f"| `{area}` | {files_count} | {additions} | {deletions} |")
    return "\n".join(lines)


def _guess_session_id(tool: str, project_path: Path) -> str | None:
    # Best-effort only. If ambiguous, the caller should ask the user and/or run list-sessions.
    if tool == "codex":
        codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
        sessions_root = codex_home / "sessions"
        if not sessions_root.exists():
            return None
        newest: tuple[dt.datetime, str] | None = None
        for session_file in sessions_root.rglob("*.jsonl"):
            try:
                with session_file.open("r", encoding="utf-8", errors="replace") as handle:
                    first = json.loads(handle.readline() or "{}")
                if first.get("type") != "session_meta":
                    continue
                payload = first.get("payload") or {}
                cwd = str(payload.get("cwd") or "")
                if not cwd:
                    continue
                try:
                    cwd_path = Path(cwd).expanduser().resolve()
                except Exception:
                    continue
                try:
                    cwd_path.relative_to(project_path)
                except Exception:
                    if cwd_path != project_path:
                        continue
                session_id = str(payload.get("id") or "")
                if not session_id:
                    continue
                mtime = dt.datetime.fromtimestamp(session_file.stat().st_mtime, tz=dt.timezone.utc)
                if newest is None or mtime > newest[0]:
                    newest = (mtime, session_id)
            except Exception:
                continue
        return newest[1] if newest else None

    if tool == "claude":
        claude_home = Path(os.environ.get("CLAUDE_HOME") or (Path.home() / ".claude"))
        projects_root = claude_home / "projects"
        if not projects_root.exists():
            return None
        newest: tuple[dt.datetime, str] | None = None
        for transcript in projects_root.rglob("*.jsonl"):
            try:
                with transcript.open("r", encoding="utf-8", errors="replace") as handle:
                    first = json.loads(handle.readline() or "{}")
                session_id = str(first.get("sessionId") or "")
                cwd = str(first.get("cwd") or "")
                if not session_id or not cwd:
                    continue
                try:
                    cwd_path = Path(cwd).expanduser().resolve()
                except Exception:
                    continue
                try:
                    cwd_path.relative_to(project_path)
                except Exception:
                    if cwd_path != project_path:
                        continue
                mtime = dt.datetime.fromtimestamp(transcript.stat().st_mtime, tz=dt.timezone.utc)
                if newest is None or mtime > newest[0]:
                    newest = (mtime, session_id)
            except Exception:
                continue
        return newest[1] if newest else None

    return None


def _entry_present(body: str, key: SessionKey) -> bool:
    for match in ENTRY_META_RE.finditer(body):
        try:
            meta = json.loads(match.group(1))
        except Exception:
            continue
        if str(meta.get("tool") or "").strip() != key.tool:
            continue
        if str(meta.get("session_id") or "").strip() != key.session_id:
            continue
        return True
    return False


def _fetch_comment_body(repo: str, comment_id: int) -> dict[str, Any]:
    return _gh_api_json(repo, f"repos/{repo}/issues/comments/{comment_id}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Upsert the single 'SESSION REVIEW NOTES' PR comment (create-or-update) with deterministic merging."
    )
    parser.add_argument("--repo", help="owner/repo. Optional if running in a git repo with gh context.")
    parser.add_argument(
        "--pr",
        default="auto",
        help='PR number, PR URL, or "auto" (default: auto).',
    )
    parser.add_argument(
        "--payload",
        required=True,
        help="Path to JSON payload produced by the LLM (use '-' to read from stdin).",
    )
    parser.add_argument(
        "--tool",
        choices=["codex", "claude", "unknown"],
        default="unknown",
        help="Tool label for the current session entry (default: unknown).",
    )
    parser.add_argument(
        "--session-id",
        default="auto",
        help='Session ID for this entry, or "auto" to guess, or an explicit ID.',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render the comment body to stdout, but do not create/update on GitHub.",
    )
    args = parser.parse_args(argv)

    generator = "session-review-notes"
    generator_version = _detect_generator_version()

    repo_from_pr, _ = _parse_pr_arg(args.pr)
    repo = args.repo or repo_from_pr or _resolve_repo_fallback()
    pr_number = _resolve_pr_number(repo, args.pr)

    pr = _gh_api_json(repo, f"repos/{repo}/pulls/{pr_number}")
    pr_url = str(pr.get("html_url") or "")
    allowed_hosts: set[str] = {"github.com"}
    pr_host = urlparse(pr_url).netloc.lower()
    if pr_host:
        allowed_hosts.add(pr_host)

    head_sha = str((pr.get("head") or {}).get("sha") or "")
    if not head_sha:
        raise SystemExit("Unable to resolve PR head SHA from GitHub API.")

    pr_files = _fetch_pr_files(repo, pr_number)
    hotspot_map = _render_hotspot_map(pr_files)

    if args.payload == "-":
        payload_text = sys.stdin.read()
        if not payload_text.strip():
            raise SystemExit("No JSON payload provided on stdin.")
        payload_raw = json.loads(payload_text)
    else:
        payload_raw = json.loads(Path(args.payload).read_text(encoding="utf-8"))

    payload = _redact_obj(_normalize_payload(payload_raw), allowed_hosts)

    project_path = Path(os.getcwd()).resolve()
    session_id = args.session_id
    if session_id == "auto":
        guessed = _guess_session_id(args.tool, project_path)
        session_id = guessed or "unknown"

    now = dt.datetime.now().astimezone()
    entry_created_at = _parse_iso8601(payload.get("entry_created_at")) or now
    new_key = SessionKey(tool=args.tool, session_id=session_id)

    entry_meta = {
        "tool": args.tool,
        "session_id": session_id,
        "created_at": entry_created_at.isoformat(),
    }
    session_label = str(payload.get("session_label") or "session update")
    stamp = entry_created_at.astimezone().strftime("%Y-%m-%d %H:%M %Z").strip()

    human_steering = payload.get("human_steering") or []
    decisions = payload.get("decisions") or []
    tests_markdown = str(payload.get("tests_markdown") or "")
    delta_narrative = str(payload.get("delta_narrative") or "- (see delta section above)")
    notes = str(payload.get("notes") or "-")

    tests_section = _render_tests_section(tests_markdown)
    if not payload.get("tests_summary"):
        self_reported, not_run = _parse_tests_markdown(tests_markdown)
        if self_reported:
            sample = ", ".join([f"`{t}`" for t in self_reported[:3]])
            suffix = "…" if len(self_reported) > 3 else ""
            extra = f"; Not run: {len(not_run)}" if not_run else ""
            payload["tests_summary"] = _truncate(f"{sample}{suffix}{extra}", MAX_TEXT_CHARS)

    new_entry = f"""{ENTRY_META_PREFIX}{json.dumps(entry_meta, separators=(',',':'))} -->
<details>
<summary><strong>{stamp}</strong> • {args.tool} • {session_label}</summary>

**Human steering**
{_render_bullets(human_steering)}

**Delta**
{delta_narrative}

**Key decisions**
{_render_bullets(decisions)}

**Tests (this session)**
{tests_section}

**Notes**
{notes}

</details>
""".strip() + "\n"

    def build(existing: ExistingComment | None) -> tuple[str, int, str]:
        repairs: list[str] = []
        prev_state: dict[str, Any] = {}
        prev_head: str | None = None
        prev_rev = 0
        prev_repair_count = 0
        last_repair_at: str | None = None

        if existing:
            prev_state, state_repairs = _extract_state_with_repairs(existing.body)
            repairs.extend(state_repairs)
            entries_block_raw, session_repairs = _extract_sessions_block_with_repairs(existing.body)
            repairs.extend(session_repairs)
            prev_head = str(prev_state.get("head") or "") or None
            prev_rev = int(_parse_int(prev_state.get("rev")) or 0)
            prev_repair_count = int(_parse_int(prev_state.get("repair_count")) or 0)
            lr = prev_state.get("last_repair_at")
            if isinstance(lr, str) and lr.strip():
                last_repair_at = lr.strip()
        else:
            entries_block_raw = ""

        delta_summary, delta_details = _compute_delta(repo, prev_head, head_sha)
        delta_empty = bool(prev_head and prev_head == head_sha)

        entry_existed = any(e.key == new_key for e in _parse_entries(entries_block_raw))
        merged_entries_block = _merge_entries(entries_block_raw, new_entry, new_key, delta_empty=delta_empty)
        merged_entries_block = _normalize_entries_block(merged_entries_block, required_key=new_key)

        scanned_total, scanned_codex, scanned_claude, scanned_included = _count_entries(merged_entries_block)
        sessions_total = scanned_total
        codex_count = scanned_codex
        claude_count = scanned_claude

        prev_total = _parse_int(prev_state.get("sessions_total")) if "sessions_total" in prev_state else None
        prev_codex = _parse_int(prev_state.get("codex")) if "codex" in prev_state else None
        prev_claude = _parse_int(prev_state.get("claude")) if "claude" in prev_state else None

        if prev_total is not None:
            sessions_total = max(prev_total + (0 if entry_existed else 1), sessions_total)
        if prev_codex is not None:
            codex_count = max(prev_codex + (0 if (entry_existed or args.tool != "codex") else 1), codex_count)
        if prev_claude is not None:
            claude_count = max(prev_claude + (0 if (entry_existed or args.tool != "claude") else 1), claude_count)

        if sessions_total <= 0:
            sessions_total = max(scanned_total, 1)

        included_sessions = _merge_included_sessions(prev_state.get("included_sessions"), scanned_included)

        repair_count: int | None = None
        if existing:
            repair_count = prev_repair_count + (1 if repairs else 0)
            if repairs:
                last_repair_at = now.isoformat()
        elif repairs:
            repair_count = 1
            last_repair_at = now.isoformat()

        rev = prev_rev + 1
        payload["_rev"] = rev

        base_ref = str((pr.get("base") or {}).get("ref") or "")
        head_short = head_sha[:7]
        provenance_lines: list[str] = [
            f"- PR scope: GitHub diff `{base_ref}...{head_short}`",
        ]
        if prev_head:
            provenance_lines.append(f"- Delta: compare `{prev_head[:7]}...{head_short}`")
        else:
            provenance_lines.append("- Delta: n/a (first entry)")
        provenance_lines.append(f"- Generator: `{generator}` schema={SCHEMA_VERSION} rev={rev}")
        if generator_version:
            provenance_lines.append(f"- Generator version: `{generator_version}`")
        if existing and len(existing.marker_comment_ids) > 1:
            provenance_lines.append(
                f"- Duplicate marker comments: `{len(existing.marker_comment_ids)}` (updating most recent)."
            )
        if repairs:
            provenance_lines.append("- Repairs:")
            provenance_lines.extend([f"  - {r}" for r in repairs])

        final_entries_block = merged_entries_block
        truncated_notes: list[str] = []

        def render(entries_block: str) -> tuple[str, str]:
            sessions_sha = _sha256(entries_block.strip())
            body = _render_comment(
                pr=pr,
                payload=payload,
                prev_head=prev_head,
                head_sha=head_sha,
                entries_block=entries_block,
                delta_summary=delta_summary,
                delta_details=delta_details,
                hotspot_map=hotspot_map,
                provenance="\n".join(provenance_lines + truncated_notes) if provenance_lines else "-",
                now=now,
                sessions_total=sessions_total,
                codex_count=codex_count,
                claude_count=claude_count,
                included_sessions=included_sessions,
                sessions_sha256=sessions_sha,
                repair_count=repair_count,
                last_repair_at=last_repair_at,
                generator=generator,
                generator_version=generator_version,
            )
            return _redact(body, allowed_hosts), sessions_sha

        comment_body, sessions_sha256 = render(final_entries_block)
        if len(comment_body) > MAX_BODY_CHARS and payload.get("prompts"):
            payload["prompts"] = ""
            truncated_notes.append("- Prompts omitted to fit GitHub comment size limits.")
            comment_body, sessions_sha256 = render(final_entries_block)

        if len(comment_body) > MAX_BODY_CHARS:
            entries = _sort_entries(_parse_entries(final_entries_block))
            max_entries = len([e for e in entries if e.key]) + len([e for e in entries if not e.key])
            for keep in range(max_entries, 0, -1):
                candidate_block = _normalize_entries_block(
                    final_entries_block, required_key=new_key, max_entries=keep
                )
                candidate_body, candidate_sha = render(candidate_block)
                if len(candidate_body) <= MAX_BODY_CHARS:
                    if keep < max_entries:
                        truncated_notes.append(
                            f"- Session log truncated to last `{keep}` entries to fit GitHub comment size limits."
                        )
                        final_entries_block = candidate_block
                        comment_body, sessions_sha256 = render(final_entries_block)
                    break

        if len(comment_body) > MAX_BODY_CHARS:
            raise SystemExit(
                f"Generated comment is too large ({len(comment_body)} chars). Reduce payload verbosity and retry."
            )

        return comment_body, rev, sessions_sha256

    if args.dry_run:
        existing = _find_existing_comment(repo, pr_number)
        comment_body, _, _ = build(existing)
        print(comment_body)
        return 0

    for _ in range(3):
        existing = _find_existing_comment(repo, pr_number)
        comment_body, expected_rev, expected_sha = build(existing)

        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
            tmp.write(comment_body)
            tmp_path = tmp.name

        try:
            if existing:
                updated = _gh_json(
                    repo,
                    [
                        "api",
                        "-X",
                        "PATCH",
                        f"repos/{repo}/issues/comments/{existing.comment_id}",
                        "-F",
                        f"body=@{tmp_path}",
                    ],
                )
                comment_id = int(updated.get("id") or existing.comment_id)
            else:
                created = _gh_json(
                    repo,
                    [
                        "api",
                        "-X",
                        "POST",
                        f"repos/{repo}/issues/{pr_number}/comments",
                        "-F",
                        f"body=@{tmp_path}",
                    ],
                )
                comment_id = int(created.get("id"))

            fetched = _fetch_comment_body(repo, comment_id)
            fetched_body = str(fetched.get("body") or "")
            state, _ = _extract_state_with_repairs(fetched_body)
            fetched_rev = _parse_int(state.get("rev"))
            fetched_sha = str(state.get("sessions_sha256") or "")

            if fetched_rev == expected_rev and fetched_sha == expected_sha and _entry_present(fetched_body, new_key):
                print(fetched.get("html_url") or "updated")
                return 0
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    raise SystemExit("Failed to update PR comment after merge/verify retries.")


if __name__ == "__main__":
    raise SystemExit(main(list(sys.argv[1:])))
