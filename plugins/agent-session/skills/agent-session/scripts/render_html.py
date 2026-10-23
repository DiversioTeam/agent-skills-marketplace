"""Render selected transcript units as one self-contained, script-free HTML page (or several parts when large).

Every string from a transcript goes through `Page.text`, which redacts before it clips and escapes, so nothing reaches
the page unredacted. Folding uses <details>; the page has no JavaScript and loads nothing external, which is what the
server-side check (Courage) enforces.
"""

from __future__ import annotations

import html
import json
import re
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import datetime

from redaction import Redactor, looks_like_personal_rows
from repo_context import RepoContext
from session_model import Item, Tokens, ToolCall, Turn, Unit

MAX_PART_BYTES = 20 * 1024 * 1024
# Room in each part for the page around the sections: style, header, table of contents.
PAGE_OVERHEAD_BYTES = 64 * 1024
LIMITS = {"prompt": 20_000, "assistant": 20_000, "input": 3_000, "output": 4_000, "read": 2_000}
GENERATOR = "agent-session/1"


def _clip(text: str, limit: int, counts: Counter[str]) -> str:
    if len(text) <= limit:
        return text
    counts["clipped"] += 1
    head = int(limit * 0.7)
    tail = limit - head
    omitted = len(text) - head - tail
    return f"{text[:head]}\n… {omitted:,} characters omitted …\n{text[-tail:]}"


_FENCE = re.compile(r"```[^\n]*\n([\s\S]*?)(?:```|$)")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
_URL = re.compile(r"https?://[^\s<>\"']+[^\s<>\"'.,;:)\]]")
_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def _inline(escaped: str) -> str:
    escaped = _HEADING.sub(lambda match: f"<strong class=\"h\">{match.group(2)}</strong>", escaped)
    escaped = _BOLD.sub(r"<strong>\1</strong>", escaped)
    escaped = _URL.sub(lambda match: f"<a href=\"{match.group(0)}\" rel=\"noreferrer noopener\">{match.group(0)}</a>", escaped)
    return _INLINE_CODE.sub(r"<code>\1</code>", escaped)


def prose(text: str) -> str:
    """Escaped text with fenced code, inline code, bold, headings, and links. Input is already redacted."""
    parts: list[str] = []
    position = 0
    for match in _FENCE.finditer(text):
        parts.append(f"<div class=\"prose\">{_inline(html.escape(text[position:match.start()]))}</div>")
        parts.append(f"<pre class=\"code\">{html.escape(match.group(1))}</pre>")
        position = match.end()
    parts.append(f"<div class=\"prose\">{_inline(html.escape(text[position:]))}</div>")
    return "".join(part for part in parts if part not in ("<div class=\"prose\"></div>",))


def _time(timestamp: str) -> str:
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return timestamp


def _short_time(timestamp: str) -> str:
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%H:%M")
    except ValueError:
        return ""


@dataclass
class Page:
    context: RepoContext
    redactor: Redactor
    expires: str
    generated: str
    counts: Counter[str] = field(default_factory=Counter)
    withheld: Counter[str] = field(default_factory=Counter)

    def text(self, value: str, limit: int) -> str:
        return _clip(self.redactor.text(value), limit, self.counts)

    def line(self, value: str, limit: int) -> str:
        """A one-line summary of text shown in full elsewhere: redacted, but not counted twice."""
        first = value.strip().splitlines()[0] if value.strip() else ""
        quiet = Redactor(known_secrets=self.redactor.known_secrets, allowed_email_domains=self.redactor.allowed_email_domains)
        text = quiet.text(first)
        return text if len(text) <= limit else f"{text[:limit - 1]}…"

    # ---- Tool calls ----------------------------------------------------------------------------------------------

    def _summary(self, call: ToolCall) -> str:
        data = call.input
        for key in ("command", "cmd", "file_path", "path", "pattern", "url", "query", "description", "to", "skill"):
            value = data.get(key)
            if isinstance(value, list):
                value = " ".join(str(part) for part in value)
            if isinstance(value, str) and value.strip():
                return self.line(value, 160)
        return ""

    def _input(self, call: ToolCall) -> str:
        data = dict(call.input)
        if call.withheld == "credential file":
            for key in ("content", "new_string", "old_string", "edits", "new_source"):
                if key in data:
                    data[key] = "[withheld: credential file]"
        command = data.get("command") or data.get("cmd")
        if isinstance(command, str) and set(data) <= {"command", "cmd", "description", "timeout", "run_in_background"}:
            return self.text(command, LIMITS["input"])
        # Redact each string before serializing: JSON escaping (backslashes, quotes, newlines) would hide exact known values.
        return self.text(json.dumps(self._scrub(data), indent=2, ensure_ascii=False, default=str), LIMITS["input"])

    def _scrub(self, value: object) -> object:
        if isinstance(value, str):
            return self.redactor.text(value)
        if isinstance(value, list):
            return [self._scrub(item) for item in value]
        if isinstance(value, dict):
            return {key: self._scrub(item) for key, item in value.items()}
        return value

    def _output(self, call: ToolCall) -> tuple[str, str]:
        """(css class, escaped body) for a tool's output."""
        if call.withheld:
            self.withheld[call.withheld] += 1
            return "withheld", html.escape(f"Output withheld: {call.withheld}.")
        if call.output is None:
            return "empty", "No output recorded."
        if looks_like_personal_rows(call.output):
            self.withheld["looks like personal data"] += 1
            return "withheld", "Output withheld: looks like personal data."
        limit = LIMITS["read"] if call.name.lower() in ("read", "read_file", "view") else LIMITS["output"]
        return "output", html.escape(self.text(call.output, limit))

    def tool(self, call: ToolCall, depth: int) -> str:
        self.counts["tool_calls"] += 1
        css, output = self._output(call)
        flags = " error" if call.is_error else ""
        badge = "<span class=\"badge err\">error</span>" if call.is_error else ""
        badge += "<span class=\"badge held\">withheld</span>" if css == "withheld" else ""
        subagent = "".join(self.unit(child, depth + 1) for child in call.subagents)
        summary = html.escape(self._summary(call))
        return (f"<details class=\"tool{flags}\"><summary><span class=\"tname\">{html.escape(call.name)}</span>"
                f"<span class=\"targ\">{summary}</span>{badge}<span class=\"ts\">{_short_time(call.timestamp)}</span></summary>"
                f"<div class=\"io\"><div class=\"label\">Input</div><pre>{html.escape(self._input(call))}</pre>"
                f"<div class=\"label\">Output</div><pre class=\"{css}\">{output}</pre></div></details>{subagent}")

    # ---- Turns and units -----------------------------------------------------------------------------------------

    def item(self, item: Item, depth: int) -> str:
        if item.kind == "assistant":
            return f"<div class=\"assistant\">{prose(self.text(item.text, LIMITS['assistant']))}</div>"
        if item.kind == "note":
            return f"<p class=\"note\">{html.escape(item.text)}</p>"
        return self.tool(item.tool, depth) if item.tool else ""

    def turn(self, turn: Turn, depth: int, open_: bool) -> str:
        label = {"developer": "Developer", "teammate": f"Message from {turn.sender or 'teammate'}",
                 "agent": f"From {turn.sender or 'agent'}", "compaction": "Context compacted"}[turn.kind]
        first_line = self.line(turn.text, 140)
        prompt = ""
        if turn.text.strip():
            limit = 4_000 if turn.kind == "compaction" else LIMITS["prompt"]
            prompt = f"<div class=\"prompt {turn.kind}\"><div class=\"who\">{html.escape(label)}</div>{prose(self.text(turn.text, limit))}</div>"
        tools = sum(1 for item in turn.items if item.kind == "tool")
        tool_label = _plural(tools, "tool call")
        body = "".join(self.item(item, depth) for item in turn.items)
        self.counts["turns"] += 1
        return (f"<details class=\"turn\" id=\"turn-{turn.number}\"{' open' if open_ else ''}><summary>"
                f"<a class=\"num\" href=\"#turn-{turn.number}\">{turn.number}</a><span class=\"who-s {turn.kind}\">{html.escape(label)}</span>"
                f"<span class=\"first\">{html.escape(first_line)}</span><span class=\"meta\">{tool_label} · {_short_time(turn.timestamp)}</span>"
                f"</summary>{prompt}{body}</details>")

    def unit(self, unit: Unit, depth: int = 0) -> str:
        many = len(unit.turns) > 12
        turns = "".join(self.turn(turn, depth, not many or index < 5 or index >= len(unit.turns) - 3)
                        for index, turn in enumerate(unit.turns))
        gap = (f"<p class=\"note\">{unit.omitted_turns} earlier or later turns in this session were about other work and are not included.</p>"
               if unit.omitted_turns else "") + "".join(f"<p class=\"note\">{html.escape(note)}</p>" for note in unit.notes)
        tokens = unit.tokens
        meta = " · ".join(part for part in (unit.harness, ", ".join(unit.models), f"{_time(unit.started)} to {_short_time(unit.ended)}",
                                              f"{tokens.total:,} tokens" if tokens.total else "") if part)
        heading = f"<h{2 if depth == 0 else 3}>{html.escape(unit.title)}</h{2 if depth == 0 else 3}><p class=\"umeta\">{html.escape(meta)}</p>"
        if depth > 0:
            return (f"<details class=\"subagent\"><summary>{html.escape(unit.title)} · {_plural(len(unit.turns), 'turn')}"
                    f"{f' · {tokens.total:,} tokens' if tokens.total else ''}</summary>{gap}{turns}</details>")
        teammates = "".join(self.unit(teammate) for teammate in unit.teammates)
        return f"<section class=\"unit\" id=\"unit-{html.escape(unit.id)}\">{heading}{gap}{turns}</section>{teammates}"

    # ---- The page ------------------------------------------------------------------------------------------------

    def header(self, units: list[Unit], part: tuple[int, int], links: list[str]) -> str:
        context = self.context
        everything = [unit for top in units for unit in _walk(top)]
        tokens = Tokens()
        for unit in everything:
            tokens.add(unit.tokens)
        models = sorted({model for unit in everything for model in unit.models})
        harnesses = sorted({unit.harness for unit in everything})
        starts = sorted(unit.started for unit in everything if unit.started)
        ends = sorted(unit.ended for unit in everything if unit.ended)
        span = f"{_time(starts[0])} to {_time(ends[-1])}" if starts and ends else ""
        pr = f" · PR #{context.pr}" if context.pr else ""
        rows = [("Repository", context.repo_slug or context.repo_name), ("Branch", context.branch),
                ("Pull request", f"#{context.pr}" if context.pr else "not opened yet"),
                ("Covers", f"{context.base[:12] or 'start'}..{context.head[:12]} ({_plural(len(context.commits), 'commit')})" if context.head else ""),
                ("Agents", ", ".join(harnesses)),
                ("Models", ", ".join(models)), ("Time", span),
                ("Sessions", ", ".join(_plural(sum(1 for unit in everything if unit.kind == kind), kind)
                                       for kind in ("session", "teammate", "subagent"))),
                ("Tokens", f"{tokens.input:,} input, {tokens.output:,} output, {tokens.cache_read:,} cache read, {tokens.cache_write:,} cache write"),
                ("Generated", self.generated), ("Expires", self.expires)]
        table = "".join(f"<dt>{html.escape(name)}</dt><dd>{html.escape(value)}</dd>" for name, value in rows if value)
        toc = "".join(f"<li><a href=\"#unit-{html.escape(unit.id)}\">{html.escape(unit.title)}</a> · {_plural(len(unit.turns), 'turn')}</li>"
                      for unit in units)
        nav = ""
        if part[1] > 1:
            nav = "<p class=\"parts\">" + " · ".join(
                f"<a href=\"{html.escape(link)}\">Part {index + 1}</a>" if index + 1 != part[0] else f"<strong>Part {index + 1}</strong>"
                for index, link in enumerate(links)) + f" of {part[1]}</p>"
        return (f"<header><p class=\"kicker\">Agent session transcript</p><h1>{html.escape(context.repo_name)} · "
                f"{html.escape(context.branch)}{html.escape(pr)}</h1>{nav}<dl>{table}</dl>"
                f"<p class=\"notice\">This page reproduces the developer's prompts word for word, with the agents' replies and tool "
                f"activity. Secrets, credentials, customer emails and phone numbers, personal-data rows, and output from prod or "
                f"staging data access were removed on the developer's machine, and Courage checks the page again. It is visible to "
                f"Diversio staff only.</p><!--REDACTION--><nav><ul>{toc}</ul></nav></header>")

    def redaction_summary(self) -> str:
        replaced = {kind: count for kind, count in self.redactor.counts.items() if count}
        items = [f"{count} {kind.replace('_', ' ')}" for kind, count in sorted(replaced.items())]
        items += [f"{count} outputs withheld ({reason})" for reason, count in sorted(self.withheld.items())]
        if self.counts["clipped"]:
            items.append(f"{self.counts['clipped']} long texts clipped")
        body = ", ".join(items) if items else "nothing needed redacting"
        return f"<p class=\"redaction\"><strong>Redacted:</strong> {html.escape(body)}.</p>"


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _walk(unit: Unit):
    yield unit
    for turn in unit.turns:
        for item in turn.items:
            for child in item.tool.subagents if item.tool else []:
                yield from _walk(child)
    for teammate in unit.teammates:
        yield from _walk(teammate)


def number_turns(units: list[Unit]) -> None:
    """Number turns in the order the page shows them: subagents nested at their call, teammates after their session."""
    number = 0

    def visit(unit: Unit) -> None:
        nonlocal number
        for turn in unit.turns:
            number += 1
            turn.number = number
            for item in turn.items:
                for child in item.tool.subagents if item.tool else []:
                    visit(child)
        for teammate in unit.teammates:
            visit(teammate)

    for unit in units:
        visit(unit)


STYLE = """
:root{--bg:#fbfaf8;--fg:#1d1d1f;--muted:#6b6b70;--line:#e4e1dc;--card:#fff;--accent:#5b3fd6;--dev:#f1edff;--mate:#eaf6f0;
--agent:#f4f4f2;--code:#f5f3ef;--err:#b42318;--held:#8a5a00;--heldbg:#fff6e0}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#ececef;--muted:#a0a0a8;--line:#2c2c31;--card:#1c1c20;--accent:#a796ff;
--dev:#26213d;--mate:#16302a;--agent:#232327;--code:#202024;--err:#ff8a80;--held:#ffc75f;--heldbg:#2e2614}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",
Inter,sans-serif}main{max-width:980px;margin:0 auto;padding:24px 16px 80px}a{color:var(--accent)}
header{border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:24px}.kicker{margin:0;color:var(--muted);font-size:13px;
text-transform:uppercase;letter-spacing:.06em}h1{font-size:26px;margin:4px 0 12px;overflow-wrap:anywhere}h2{font-size:20px;margin:32px 0 2px}
dl{display:grid;grid-template-columns:max-content 1fr;gap:2px 16px;margin:0 0 12px;font-size:14px}dt{color:var(--muted)}dd{margin:0;overflow-wrap:anywhere}
.notice{background:var(--heldbg);border-radius:8px;padding:10px 12px;font-size:14px}.redaction{font-size:14px;color:var(--muted)}
nav ul{margin:8px 0 0;padding-left:18px;font-size:14px}.umeta{color:var(--muted);margin:0 0 12px;font-size:13px}
details.turn{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:10px 0;padding:0 14px}
details.turn>summary{display:flex;gap:10px;align-items:baseline;padding:10px 0;cursor:pointer;list-style:none}
details.turn>summary::-webkit-details-marker{display:none}details.turn[open]>summary .first{visibility:hidden}.num{font:12px ui-monospace,Menlo,monospace;color:var(--muted);text-decoration:none;min-width:2.5em}
.who-s{font-weight:600;font-size:13px;white-space:nowrap}.first{flex:1;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.meta,.ts{font-size:12px;color:var(--muted);white-space:nowrap}.prompt{border-radius:8px;padding:10px 12px;margin:0 0 10px}
.prompt.developer{background:var(--dev);border-left:3px solid var(--accent)}.prompt.teammate{background:var(--mate)}
.prompt.agent,.prompt.compaction{background:var(--agent)}.who{font-size:12px;font-weight:600;color:var(--muted);margin-bottom:4px}
.prose{white-space:pre-wrap;overflow-wrap:anywhere}.assistant{margin:8px 0}.h{display:block;margin-top:6px}
code{font:13px ui-monospace,Menlo,monospace;background:var(--code);padding:1px 4px;border-radius:4px}
pre{font:12.5px/1.45 ui-monospace,Menlo,monospace;background:var(--code);padding:10px;border-radius:6px;overflow:auto;max-height:480px;
white-space:pre-wrap;overflow-wrap:anywhere;margin:4px 0 8px}pre.withheld{background:var(--heldbg);color:var(--held)}
details.tool{border-top:1px dashed var(--line)}details.tool>summary{display:flex;gap:8px;align-items:baseline;padding:6px 0;cursor:pointer;font-size:13px}
.tname{font:600 12.5px ui-monospace,Menlo,monospace}.targ{flex:1;font:12.5px ui-monospace,Menlo,monospace;color:var(--muted);overflow:hidden;
text-overflow:ellipsis;white-space:nowrap;min-width:0}.badge{font-size:11px;border-radius:999px;padding:0 7px;border:1px solid}
.badge.err{color:var(--err)}.badge.held{color:var(--held)}.label{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
details.subagent{margin:6px 0 10px 12px;border-left:3px solid var(--line);padding-left:12px}details.subagent>summary{cursor:pointer;font-weight:600;font-size:14px;padding:4px 0}
.note{color:var(--muted);font-style:italic;font-size:14px}.parts{font-size:14px}
@media (max-width:640px){.meta,.ts{display:none}dl{grid-template-columns:1fr}}
"""


def _split_turn(turn: Turn, measure: Page, budget: int) -> list[Turn]:
    """A turn too large for one part, as consecutive copies holding slices of its items (the prompt stays on the first)."""
    pieces: list[list[Item]] = [[]]
    size = len(measure.turn(replace(turn, items=[]), 0, True).encode())
    for item in turn.items:
        length = len(measure.item(item, 0).encode())
        if pieces[-1] and size + length > budget:
            pieces.append([])
            size = 0
        pieces[-1].append(item)
        size += length
    return [replace(turn, items=items, text=turn.text if index == 0 else "", kind=turn.kind if index == 0 else "agent",
                    sender=turn.sender if index == 0 else f"turn {turn.number}, continued") for index, items in enumerate(pieces)]


def _split(unit: Unit, page: Page) -> list[Unit]:
    """One unit, or consecutive slices of its turns (a single huge turn split by its items) that each fit in a part."""
    measure = Page(context=page.context, redactor=Redactor(known_secrets=page.redactor.known_secrets), expires="", generated="")
    budget = MAX_PART_BYTES - PAGE_OVERHEAD_BYTES
    if len(measure.unit(unit).encode()) <= budget:
        return [unit]
    slices: list[list[Turn]] = [[]]
    size = 0
    for whole in unit.turns:
        for turn in ([whole] if len(measure.turn(whole, 0, True).encode()) <= budget else _split_turn(whole, measure, budget)):
            length = len(measure.turn(turn, 0, True).encode())
            if slices[-1] and size + length > budget:
                slices.append([])
                size = 0
            slices[-1].append(turn)
            size += length
    return [replace(unit, id=f"{unit.id}-{index + 1}", turns=turns, title=f"{unit.title} ({index + 1} of {len(slices)})",
                    omitted_turns=unit.omitted_turns if index == 0 else 0) for index, turns in enumerate(slices)]


def build_pages(context: RepoContext, units: list[Unit], redactor: Redactor, expires: str, generated: str,
                names: list[str] | None = None) -> tuple[list[str], Page]:
    """HTML for each part (one unless the page passes the size cap) and the Page holding redaction counts."""
    number_turns(units)
    page = Page(context=context, redactor=redactor, expires=expires, generated=generated)
    # Titles and senders come from session metadata (subagent descriptions, teammate names): redact them like any text.
    for top in units:
        for unit in _walk(top):
            unit.title = page.line(unit.title, 200)
            unit.id = page.line(unit.id, 120)
            for turn in unit.turns:
                turn.sender = page.line(turn.sender, 80)
    # Teammates become top-level sections so a part can break between them, and one long session splits by turns.
    flat = [piece for top in units for unit in (replace(top, teammates=[]), *top.teammates) for piece in _split(unit, page)]
    sections = [(unit, page.unit(unit)) for unit in flat]
    parts: list[list[tuple[Unit, str]]] = [[]]
    size = 0
    for unit, section in sections:
        length = len(section.encode())
        if parts[-1] and size + length > MAX_PART_BYTES - PAGE_OVERHEAD_BYTES:
            parts.append([])
            size = 0
        parts[-1].append((unit, section))
        size += length
    links = names or [f"part-{index + 1}.html" for index in range(len(parts))]
    summary = page.redaction_summary()
    # What the page covers, for tools: the repo, branch, base..head, and the commits in between.
    coverage = "".join(f"<meta name=\"agent-session-{name}\" content=\"{html.escape(value)}\">" for name, value in (
        ("repo", context.repo_slug), ("branch", context.branch), ("base", context.base), ("head", context.head),
        ("commits", " ".join(context.commits))) if value)
    pages = []
    for index, part in enumerate(parts):
        header = page.header([unit for unit, _ in part], (index + 1, len(parts)), links).replace("<!--REDACTION-->", summary)
        title = html.escape(f"Agent sessions · {context.repo_name} · {context.branch}")
        pages.append(f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                     f"<meta name=\"generator\" content=\"{GENERATOR}\"><meta name=\"agent-session-expires\" content=\"{html.escape(expires)}\">"
                     f"{coverage}"
                     f"<meta name=\"referrer\" content=\"no-referrer\"><title>{title}</title><style>{STYLE}</style></head>"
                     f"<body><main>{header}{''.join(section for _, section in part)}</main></body></html>")
    return pages, page
