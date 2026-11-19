#!/usr/bin/env python3
"""Check an HTML explainer against the Diversio readable-page standard before it is shared.

The same rules, with the same names, as Courage's internal-share page gate
(DiversioTeam/courage src/readable-pages.ts and docs/standards/readable-output.md),
so a page that passes here also passes there. Standard library only.

Usage: python3 check_page.py PAGE.html [--kind slides]   (exit 0 when it passes, 1 with a list of fixes)
"""

from __future__ import annotations

import re
import sys
import urllib.parse
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

LEAD_WORDS = 80
PARAGRAPH_WORDS = 110
SECTION_WORDS = 350
NAV_SECTIONS = 5
NAV_WORDS = 1200
MAX_SHORT_IDS = 3
NUMERIC_CELLS = 12

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
HIDDEN = {"script", "style", "template", "noscript", "head"}
EVIDENCE = {"pre", "details", "svg", "nav"}
BLOCK = {"p", "li", "div", "section", "td", "th", "tr", "h1", "h2", "h3", "h4", "br", "ul", "ol", "table", "main", "body",
         "header", "footer", "blockquote", "dd", "dt"}
CONTENT = {"p", "ul", "ol", "table", "pre", "img", "svg", "figure", "blockquote", "details", "dl", "canvas", "video", "picture"}

GENERIC_TITLES = re.compile(r"^(report title|untitled|document|page|report|cli log|new page|index)$", re.I)
PLACEHOLDERS = [re.compile(r"\blorem ipsum\b", re.I), re.compile(r"one or two sentences a busy reader can stop after", re.I),
                re.compile(r"^\s*(todo|tbd|placeholder)\b", re.I | re.M), re.compile(r"\[(todo|tbd|placeholder)\]", re.I)]
SUMMARY_HEADING = re.compile(r"^(summary|bottom line|tl;?dr|in short|the answer|answer|overview|what (this|you need to know))\b", re.I)
ACTION = re.compile(
    r"\b(next( steps?)?:|next,|next step|please|you (need|should|can|could|may|only need)|needs? (your|a|an|someone|one)|decide|"
    r"decision (needed|for you)|approve|approval|reply|choose|pick one|confirm|ready (for|to)|(for|needs) (your )?review|"
    r"waiting (for|on)|nothing (for you|to do|else|is needed|needed)|no action|action needed|to do:|sign off|retest)(?![a-z])", re.I)
LONG_IDS = [
    (re.compile(r"\b[0-9a-f]{40}\b"), "a full commit hash"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "a UUID"),
    (re.compile(r"(?:/private/(?:var|tmp)/|/var/lib/|/opt/courage/|/Users/[\w.-]+/|/home/[\w.-]+/|(?<![\w.])/workspaces?/|(?<![\w.])/tmp/)[^\s)<]*"),
     "a machine path"),
    (re.compile(r"(?<![\w,.$])\d{10,}(?![\w,])"), "a long numeric id"),
]
SHORT_IDS = [
    re.compile(r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,39}\b"),
    re.compile(r"\b\d{8}T\d{6}Z-[0-9a-f]{6,}\b"),
    re.compile(r"\b(?:[CUGD]0[A-Z0-9]{7,}|S0[A-Z0-9]{8,})\b"),
    re.compile(r"(?<![\w,.$])\d{9}(?![\w,])"),
]
NUMBER_CELL = re.compile(r"^\s*[-+−]?[$€£]?\s*\d[\d,]*(\.\d+)?\s*(%|ms|s|m|h|k|mb|gb|x)?\s*$", re.I)
VISUAL_CLASS = re.compile(r"\b(stats?|bar|bars|chart|spark\w*|meter|timeline|diff|before-after|tile)\b")
LOADING_RELS = re.compile(r"\b(stylesheet|preload|modulepreload|icon|apple-touch-icon|manifest)\b", re.I)
MEDIA_SRC = {"img", "iframe", "embed", "video", "audio", "source", "track", "input", "frame"}


# Identity equality: two identical sections are still two nodes (nodes.index must find the one it was given).
@dataclass(eq=False)
class Node:
    name: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node | str"] = field(default_factory=list)
    parent: "Node | None" = None

    def cls(self, pattern: re.Pattern[str]) -> bool:
        return bool(pattern.search(self.attrs.get("class", "")))


class TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#document")
        self.current = self.root
        self.doctype = False

    def handle_decl(self, decl: str) -> None:
        if decl.lower().startswith("doctype html"):
            self.doctype = True

    # Optional end tags, the way browsers read them: a new cell closes the open cell, a new row the open row, a new list
    # item the open item, and a block element an open paragraph.
    IMPLIED = {
        "td": ({"td", "th"}, {"tr", "table"}), "th": ({"td", "th"}, {"tr", "table"}),
        "tr": ({"td", "th", "tr"}, {"table", "tbody", "thead", "tfoot"}),
        "tbody": ({"td", "th", "tr", "tbody", "thead", "tfoot"}, {"table"}), "thead": ({"td", "th", "tr", "tbody", "thead", "tfoot"}, {"table"}),
        "tfoot": ({"td", "th", "tr", "tbody", "thead", "tfoot"}, {"table"}),
        "li": ({"li"}, {"ul", "ol"}), "dt": ({"dt", "dd"}, {"dl"}), "dd": ({"dt", "dd"}, {"dl"}), "option": ({"option"}, {"select"}),
    }
    BLOCKS = {"p", "div", "ul", "ol", "dl", "table", "section", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote", "figure", "details", "header",
              "footer", "nav", "main", "form", "hr"}

    def _close_implied(self, tag: str) -> None:
        if tag in self.BLOCKS and self.current.name == "p" and self.current.parent is not None:
            self.current = self.current.parent
        if tag not in self.IMPLIED:
            return
        closes, stops = self.IMPLIED[tag]
        node: Node | None = self.current
        # Walk up to the enclosing container; an open element of the same family closes, with anything inside it.
        while node is not None and node.parent is not None and node.name not in stops:
            if node.name in closes:
                self.current = node.parent
            node = node.parent

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._close_implied(tag)
        node = Node(tag, {name: value or "" for name, value in attrs}, parent=self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.current.children.append(Node(tag, {name: value or "" for name, value in attrs}, parent=self.current))

    def handle_endtag(self, tag: str) -> None:
        node: Node | None = self.current
        while node is not None and node.name != tag:
            node = node.parent
        if node is not None and node.parent is not None:
            self.current = node.parent

    def handle_data(self, data: str) -> None:
        self.current.children.append(data)


def walk(node: Node):
    yield node
    for child in node.children:
        if isinstance(child, Node):
            yield from walk(child)


def text_of(node: Node, skip: set[str] = HIDDEN) -> str:
    if node.name in skip:
        return ""
    parts = [child if isinstance(child, str) else text_of(child, skip) for child in node.children]
    return (" " if node.name in BLOCK else "").join(parts)


# Elements that start a new line for the reader, so text in one never runs on into the next.
LINE_BLOCKS = BLOCK | {"pre", "figure", "figcaption", "dl", "details", "summary", "article", "aside", "nav", "h5", "h6", "address"}


def visible_lines(node: Node) -> str:
    """The text a reader sees, with a line break at every block edge; hidden elements (template, hidden attribute) are left out."""
    if node.name in HIDDEN or "hidden" in node.attrs:
        return ""
    parts = [child if isinstance(child, str) else visible_lines(child) for child in node.children]
    # Inline children run together (<strong> inside a sentence stays in the sentence); only a block starts a new line.
    text = "".join(parts)
    return f"\n{text}\n" if node.name in LINE_BLOCKS else text


def hidden_nodes(root: Node) -> set[int]:
    """Ids of every node a reader never sees: script, style, template and the like, and anything under a hidden attribute."""
    found: set[int] = set()

    def visit(node: Node, hidden: bool) -> None:
        hidden = hidden or node.name in HIDDEN or "hidden" in node.attrs
        if hidden:
            found.add(id(node))
        for child in node.children:
            if isinstance(child, Node):
                visit(child, hidden)

    visit(root, False)
    return found


def strip_comments(css: str) -> str:
    """CSS without /* comments */; quoted strings are kept as they are, so a "/*" inside one is not a comment."""
    output, index, quote = [], 0, ""
    while index < len(css):
        character = css[index]
        if quote:
            output.append(character)
            if character == "\\" and index + 1 < len(css):
                output.append(css[index + 1])
                index += 1
            elif character == quote:
                quote = ""
        elif character in "\"'":
            quote = character
            output.append(character)
        elif css.startswith("/*", index):
            end = css.find("*/", index + 2)
            index = len(css) if end < 0 else end + 2
            output.append(" ")
            continue
        else:
            output.append(character)
        index += 1
    return "".join(output)


def srcset_urls(value: str) -> list[str]:
    """Every URL in a srcset, read the way browsers do: a URL runs to the next space (so a data: URI keeps its comma), and
    a comma ends a candidate even with no space after it ("a.gif 1x,b.png 2x")."""
    urls, index = [], 0
    while index < len(value):
        while index < len(value) and (value[index].isspace() or value[index] == ","):
            index += 1
        start = index
        while index < len(value) and not value[index].isspace():
            index += 1
        url = value[start:index]
        if url.endswith(","):
            url = url.rstrip(",")
        else:
            depth = 0
            while index < len(value):
                character = value[index]
                index += 1
                if character == "(":
                    depth += 1
                elif character == ")":
                    depth = max(0, depth - 1)
                elif character == "," and not depth:
                    break
        if url:
            urls.append(url)
    return urls


def inside(node: Node, test) -> bool:
    at = node.parent
    while at is not None:
        if test(at):
            return True
        at = at.parent
    return False


def words(text: str) -> int:
    return sum(1 for word in text.split() if re.search(r"\w", word))


def is_visual(node: Node) -> bool:
    return (node.name in {"svg", "img", "canvas", "meter", "progress", "picture", "video"} or node.cls(VISUAL_CLASS)
            or bool(re.search(r"--bar\s*:", node.attrs.get("style", ""))))


def strip_media(css: str) -> str:
    output, index = [], 0
    while True:
        at = css.find("@media", index)
        if at < 0:
            output.append(css[index:])
            break
        output.append(css[index:at])
        opened = css.find("{", at)
        if opened < 0:
            break
        depth, cursor = 1, opened + 1
        while cursor < len(css) and depth:
            depth += {"{": 1, "}": -1}.get(css[cursor], 0)
            cursor += 1
        index = cursor
    return "".join(output)


def media_blocks(css: str, pattern: re.Pattern[str]) -> str:
    output = []
    for match in re.finditer(r"@media[^{]*\{", css):
        if not pattern.search(match.group(0)):
            continue
        depth, cursor = 1, match.end()
        while cursor < len(css) and depth:
            depth += {"{": 1, "}": -1}.get(css[cursor], 0)
            cursor += 1
        output.append(css[match.end():cursor - 1])
    return "\n".join(output)


def tokens(css: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for block in re.finditer(r"(?:^|[}\s]):root[^{]*\{([^{}]*)\}", css):
        for match in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+)", block.group(1)):
            found[match.group(1)] = match.group(2).strip()
    return found


def contrast_ratio(foreground: str, background: str) -> float | None:
    def parse(value: str):
        match = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", value.strip(), re.I)
        if not match:
            return None
        digits = match.group(1)
        digits = "".join(c * 2 for c in digits) if len(digits) == 3 else digits
        return [int(digits[i:i + 2], 16) for i in (0, 2, 4)]

    def luminance(rgb):
        channels = [(v / 255) / 12.92 if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4 for v in rgb]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    a, b = parse(foreground), parse(background)
    if a is None or b is None:
        return None
    light, dark = sorted([luminance(a), luminance(b)], reverse=True)
    return (light + 0.05) / (dark + 0.05)


PAIRS = [("--text", "--bg"), ("--text", "--surface"), ("--muted", "--bg"), ("--muted", "--surface"), ("--accent", "--bg"),
         ("--accent", "--surface"), ("--accent", "--accent-soft"), ("--ok", "--ok-soft"), ("--warn", "--warn-soft"),
         ("--bad", "--bad-soft"), ("--info", "--info-soft"), ("--text", "--code-bg"), ("--fg", "--bg"), ("--fg", "--card"),
         ("--muted", "--card")]


def balanced(text: str, start: int) -> str:
    """The text up to the parenthesis that closes one already open at `start`, skipping nested parentheses and strings."""
    depth, quote = 1, ""
    for index in range(start, len(text)):
        character = text[index]
        if quote:
            if character == quote:
                quote = ""
        elif character in "\"'":
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return text[start:index]
    return text[start:]


def css_urls(css: str) -> list[str]:
    """Every file a stylesheet loads: url(...), @import, and image-set(...) candidates (bare strings count too)."""
    found = [match.group(2) for match in re.finditer(r"url\(\s*(['\"]?)([^'\")]*)\1\s*\)", css, re.I)]
    found += [match.group(2) for match in re.finditer(r"@import\s+(['\"])([^'\"]+)\1", css, re.I)]
    for match in re.finditer(r"image-set\(", css, re.I):
        inner = re.sub(r"\btype\(\s*(['\"])[^'\"]*\1\s*\)", "", balanced(css, match.end()), flags=re.I)
        found += [string.group(2) for string in re.finditer(r"(['\"])([^'\"]+)\1", inner)]
    return found


def parse_tree(html: str) -> TreeBuilder:
    builder = TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder


def external_loads(nodes: list[Node], css: str) -> list[str]:
    def external(url: str) -> bool:
        value = url.strip()
        return bool(value) and not re.match(r"^(data:|#|about:blank$)", value, re.I)

    found = []
    for node in nodes:
        attrs = node.attrs
        if node.name == "script" and external(attrs.get("src", "")):
            found.append(f"script {attrs['src']}")
        if node.name == "script":
            for match in re.finditer(r"\bimport\s*(?:[\w*{}\s,$]+\s+from\s*)?\(?\s*(['\"])([^'\"]+)\1", text_of(node, set())):
                if external(match.group(2)):
                    found.append(f"script import {match.group(2)}")
        if node.name == "link" and LOADING_RELS.search(attrs.get("rel", "")) and external(attrs.get("href", "")):
            found.append(f"{attrs.get('rel')} {attrs['href']}")
        if node.name in MEDIA_SRC and external(attrs.get("src", "")):
            found.append(f"{node.name} {attrs['src']}")
        for candidate in srcset_urls(attrs.get("srcset", "")):
            if external(candidate):
                found.append(f"image {candidate}")
        if node.name in {"image", "use", "feimage"}:
            href = attrs.get("href") or attrs.get("xlink:href") or ""
            if external(href):
                found.append(f"SVG image {href}")
        if node.name == "video" and external(attrs.get("poster", "")):
            found.append(f"video poster {attrs['poster']}")
        if node.name == "object" and external(attrs.get("data", "")):
            found.append(f"object {attrs['data']}")
        for url in css_urls(strip_comments(attrs.get("style", ""))):
            if external(url):
                found.append(f"inline style url {url}")
        # An inline frame's document is part of the page: its images and styles load from elsewhere just the same.
        if node.name == "iframe" and attrs.get("srcdoc"):
            inner = list(walk(parse_tree(attrs["srcdoc"]).root))
            inner_css = strip_comments("\n".join(text_of(item, set()) for item in inner if item.name == "style"))
            found += [f"iframe srcdoc: {item}" for item in external_loads(inner, inner_css)]
    for url in css_urls(css):
        if external(url):
            found.append(f"CSS url {url}")
    return list(dict.fromkeys(found))


def section_nodes(nodes: list[Node], heading: Node) -> list[Node]:
    level = int(heading.name[1])
    result = []
    for node in nodes[nodes.index(heading) + 1:]:
        if inside(node, lambda ancestor: ancestor is heading):
            continue
        if re.fullmatch(r"h[1-6]", node.name) and int(node.name[1]) <= level or node.name == "footer":
            break
        result.append(node)
    return result


def check_page(html: str, kind: str = "report") -> list[tuple[str, str]]:
    rules = {
        "report": {"self_contained", "basics", "dark_mode", "answer_first", "next_step", "ids", "navigation", "wall_of_text",
                   "visuals", "type", "contrast", "empty"},
        "log": {"self_contained", "basics", "dark_mode", "answer_first", "type", "contrast"},
        "transcript": {"self_contained", "basics", "dark_mode", "contrast"},
        # A slide deck is a sequence of screens, not a scrolling report: no summary box, nav or table stacking, but it must
        # be self-contained, readable and themed (a light or a dark palette under prefers-color-scheme), with no Mermaid.
        "slides": {"self_contained", "basics", "dark_mode", "visuals", "type", "contrast"},
    }[kind]
    problems: list[tuple[str, str]] = []

    def add(rule: str, message: str) -> None:
        if rule in rules:
            problems.append((rule, message))

    builder = parse_tree(html)
    nodes = list(walk(builder.root))
    by_name = lambda name: [node for node in nodes if node.name == name]  # noqa: E731
    css = strip_comments("\n".join(text_of(node, set()) for node in by_name("style")))

    loads = external_loads(nodes, css)
    if loads:
        add("self_contained", f"It loads files from elsewhere ({'; '.join(loads[:3])}). Inline the CSS and scripts, use the system "
            "font stack and embed images as data: URIs.")

    missing = []
    if not builder.doctype:
        missing.append("<!doctype html>")
    if not any(node.attrs.get("lang") for node in by_name("html")):
        missing.append('<html lang="en">')
    if not any(node.attrs.get("name") == "viewport" for node in by_name("meta")):
        missing.append("a viewport meta tag")
    title = " ".join(text_of(node, set()) for node in by_name("title")).strip()
    if not title:
        missing.append("a <title>")
    elif GENERIC_TITLES.match(title):
        missing.append(f'a real title (not "{title}")')
    if missing:
        add("basics", f"Add {', '.join(missing)}.")

    if not re.search(r"prefers-color-scheme\s*:\s*" + ("(dark|light)" if kind == "slides" else "dark"), css, re.I):
        add("dark_mode", "Add a dark palette under @media (prefers-color-scheme: dark), using colour tokens on :root.")

    body = (by_name("body") or [builder.root])[0]
    main = (by_name("main") or [body])[0]
    in_main = lambda node: inside(node, lambda ancestor: ancestor is main)  # noqa: E731
    chrome = lambda node: inside(node, lambda a: a.name in {"header", "footer", "nav"} or a.cls(re.compile(r"\b(report-head|meta|eyebrow)\b")))  # noqa: E731
    sections = [node for node in nodes if node.name == "h2" and in_main(node)]
    first_h2 = sections[0] if sections else None

    stop = nodes.index(first_h2) if first_h2 else len(nodes)
    # A summary the reader cannot see (hidden, or in a template) does not answer anything.
    unseen = hidden_nodes(builder.root)
    summary = next((node for node in nodes if node.cls(re.compile(r"\bsummary\b")) and node.name != "details" and not chrome(node)
                    and id(node) not in unseen), None)
    if summary is not None and nodes.index(summary) < stop:
        lead = text_of(summary)
    else:
        before = [node for node in nodes[:stop] if node.name in {"p", "ul", "ol"} and not chrome(node) and in_main(node)
                  and id(node) not in unseen
                  and not inside(node, lambda a: a.name in {"p", "ul", "ol", "details"})]
        lead = " ".join(text_of(node) for node in before)
        if not lead.strip() and first_h2 is not None and SUMMARY_HEADING.match(text_of(first_h2).strip()):
            lead = " ".join(text_of(node) for node in section_nodes(nodes, first_h2) if node.name in {"p", "li"} and id(node) not in unseen)
    count = words(lead)
    if not count:
        add("answer_first", "Start with the answer: one or two plain sentences before the first section (a .summary box) saying "
            "what was found or decided.")
    elif count > LEAD_WORDS:
        add("answer_first", f"The opening summary is {count} words. Cut it to two sentences (at most {LEAD_WORDS} words) and move "
            "the rest into sections.")
    if count and not ACTION.search(lead):
        add("next_step", "Say in the opening summary what the reader should do next, or that nothing is needed from them.")

    prose = text_of(main, HIDDEN | EVIDENCE)
    long_found, kinds = [], []
    for pattern, label in LONG_IDS:
        found = list(dict.fromkeys(match.group(0) for match in pattern.finditer(prose)))
        long_found += found
        if found:
            kinds.append(f"{f'{len(found)} × ' if len(found) > 1 else ''}{label} ({found[0][:48]})")
    if kinds:
        add("ids", f"Remove {', '.join(kinds)} from the text, or move them into a folded <details class=\"evidence\"> section.")
    short = list(dict.fromkeys(match.group(0) for pattern in SHORT_IDS for match in pattern.finditer(prose)
                               if not any(match.group(0) in item for item in long_found)))
    if len(short) > MAX_SHORT_IDS:
        add("ids", f"The text has {len(short)} ids or hashes ({', '.join(short[:5])}). Name things in words; keep ids people need "
            "in one Evidence section (<details>).")

    total = words(text_of(main))
    nav_links = [node for node in nodes if node.name == "a" and node.attrs.get("href", "").startswith("#")
                 and inside(node, lambda a: a.name == "nav" or a.cls(re.compile(r"\btoc\b")))]
    linked = {urllib.parse.unquote(link.attrs["href"][1:]) for link in nav_links}
    if (len(sections) >= NAV_SECTIONS or total > NAV_WORDS) and len(nav_links) < 3:
        add("navigation", f"The page has {len(sections)} sections and {total} words. Add a section nav (<nav class=\"toc\"> with "
            "links to each section's id) near the top.")
    elif len(sections) >= NAV_SECTIONS or total > NAV_WORDS:
        # The nav covers every section, not any three of them.
        def targets(heading: Node) -> set[str]:
            # A link can land on the heading or on the section that wraps it, when that section holds only this heading.
            found = {heading.attrs["id"]} if heading.attrs.get("id") else set()
            wrapper = heading.parent
            while wrapper is not None and wrapper.name not in {"section", "article", "main", "body"}:
                wrapper = wrapper.parent
            if wrapper is not None and wrapper.name in {"section", "article"} and wrapper.attrs.get("id") \
                    and sum(1 for node in walk(wrapper) if isinstance(node, Node) and node.name == "h2") == 1:
                found.add(wrapper.attrs["id"])
            return found

        unlisted = [text_of(heading).strip()[:40] for heading in sections if not targets(heading) & linked]
        if unlisted:
            add("navigation", f"The section nav leaves out {', '.join(repr(item) for item in unlisted[:4])}. Give every section an id and a link.")
    id_counts: dict[str, int] = {}
    for node in nodes:
        if node.attrs.get("id"):
            id_counts[node.attrs["id"]] = id_counts.get(node.attrs["id"], 0) + 1
    # Fragments are percent-decoded, as browsers do ("#caf%C3%A9s" lands on id="cafés").
    broken = list(dict.fromkeys(link.attrs["href"][1:] for link in nav_links
                                if link.attrs["href"][1:] and id_counts.get(urllib.parse.unquote(link.attrs["href"][1:])) != 1))
    if broken:
        add("navigation", f"Section links must each point at one section: {', '.join('#' + item for item in broken[:4])} "
            f"{'are' if len(broken) > 1 else 'is'} missing or used twice. Give every section a unique id.")

    long_blocks = [words(text_of(node)) for node in nodes if node.name in {"p", "li", "blockquote"}
                   and not inside(node, lambda a: a.name in {"details", "pre", "li", "blockquote"})]
    long_blocks = [value for value in long_blocks if value > PARAGRAPH_WORDS]
    if long_blocks:
        add("wall_of_text", f"{len(long_blocks)} paragraph(s) over {PARAGRAPH_WORDS} words (longest {max(long_blocks)}). Split them, "
            "or turn them into a list, table or visual.")
    for heading in sections:
        own = section_nodes(nodes, heading)
        plain = sum(words(text_of(node)) for node in own if node.name == "p"
                    and not inside(node, lambda a: a.name in {"li", "details", "blockquote", "td"}))
        structured = any(node.name in {"ul", "ol", "table", "pre", "figure", "dl"} or is_visual(node)
                         or node.cls(re.compile(r"\bcallout\b")) for node in own)
        if plain > SECTION_WORDS and not structured:
            add("wall_of_text", f'"{text_of(heading).strip()[:60]}" is {plain} words of plain paragraphs. Break it up with a list, '
                "table or visual.")

    if (re.search(r"class\s*=\s*[\"'][^\"']*\bmermaid\b", html, re.I) or re.search(r"<script[^>]*mermaid", html, re.I)
            or re.search(r"cdn\.jsdelivr\.net/npm/mermaid", html)
            # Diagram source shown as text, in any visible block (a blockquote too), but not in a template or hidden element.
            # Courage's gate reads the same visible lines.
            or re.search(r"```mermaid|^\s*(graph|flowchart) (TD|LR|TB|RL)\b|^\s*sequenceDiagram\b", visible_lines(main), re.M)):
        add("visuals", "Replace the Mermaid diagram with an inline SVG drawing (or render it to SVG and remove the Mermaid source).")
    numbers = sum(1 for node in nodes if node.name == "td" and NUMBER_CELL.match(text_of(node)))
    if numbers >= NUMERIC_CELLS and not any(is_visual(node) for node in nodes):
        add("visuals", f"The page shows {numbers} numbers only in tables. Show the ones that matter as stat tiles, bars or a small "
            "chart.")

    flat = strip_media(css)
    # Sizes set inside media rules (a phone breakpoint, say) are what some readers get, so they count too.
    sized = flat + "\n" + media_blocks(css, re.compile(r"."))
    # Inline styles count as well, with the element that owns them standing in for the selector.
    inline = [(f"{node.name} ", strip_comments(node.attrs["style"])) for node in nodes if node.attrs.get("style")]
    font_size = r"font(?:-size)?\s*:\s*[^;{}]*?(\d+(?:\.\d+)?)px"
    tiny = [float(m.group(1)) for text in [sized, *(style for _, style in inline)] for m in re.finditer(font_size, text, re.I)
            if float(m.group(1)) < 12]
    # SVG text sized by its font-size attribute ("11" or "11px"), on the text itself or a group around it.
    tiny += [float(m.group(1)) for node in nodes if "font-size" in node.attrs
             for m in [re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(px)?\s*", node.attrs["font-size"])] if m and float(m.group(1)) < 12]
    if tiny:
        add("type", f"Text as small as {min(tiny):g}px is hard to read. Keep everything at 12px or more.")
    body_sizes = []
    for selector, declarations in [(m.group(1), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", sized)] + inline:
        if re.search(r"(^|[\s,])(body|html|main|p)(?=$|[\s,:.{])", selector):
            size = re.search(font_size, declarations, re.I)
            if size and float(size.group(1)) < 15:
                body_sizes.append(size.group(1))
    for size in dict.fromkeys(body_sizes):
        add("type", f"Body text is {size}px. Use at least 15px.")
    wide = [int(m.group(2)) for m in re.finditer(r"(?<![-\w])(min-)?width\s*:\s*(\d+)px", flat, re.I) if int(m.group(2)) > 480]
    for node in nodes:
        wide += [int(m.group(2)) for m in re.finditer(r"(?<![-\w])(min-)?width\s*:\s*(\d+)px", node.attrs.get("style", ""), re.I)
                 if int(m.group(2)) > 480]
    if wide:
        add("type", f"A fixed width of {max(wide)}px overflows a phone. Use max-width, percentages or a grid that wraps.")
    bare = [table for table in by_name("table") if not inside(table, lambda a: a.cls(re.compile(r"\b(table-wrap|scroll|wrap)\b"))
                                                             or "overflow" in a.attrs.get("style", ""))]
    if bare:
        add("type", f"{len(bare)} table(s) not in a scroll wrapper. Put each in <div class=\"table-wrap\"> with overflow-x: auto.")
    # Four or more columns run off a phone; they must stack into one card per row there (class="stack" and a data-label
    # with the column name on every cell after the first).
    def columns(table: Node) -> int:
        rows = [node for node in walk(table) if node.name == "tr"]
        return max([sum(1 for cell in row.children if isinstance(cell, Node) and cell.name in {"td", "th"}) for row in rows] or [0])

    # The class does nothing without the narrow-screen rule that turns rows into cards.
    phone_css = media_blocks(css, re.compile(r"max-width\s*:\s*\d+px", re.I))
    has_card_rule = bool(re.search(r"\.stack\b[^{]*\{[^}]*display\s*:\s*block", phone_css))

    def stacks(table: Node) -> bool:
        if not table.cls(re.compile(r"\bstack\b")) or not has_card_rule:
            return False
        for row in (node for node in walk(table) if node.name == "tr"):
            cells = [cell for cell in row.children if isinstance(cell, Node) and cell.name == "td"]
            if any("data-label" not in cell.attrs for cell in cells[1:]):
                return False
        return True

    unstacked = [table for table in by_name("table") if columns(table) >= 4 and not stacks(table)] if kind != "slides" else []
    if unstacked:
        add("type", f"{len(unstacked)} table(s) with four or more columns run off a phone screen. Add class=\"stack\" and a "
            "data-label with the column name to every cell after the first (see templates/data-table.html), or cut to three columns.")

    # Each theme is the base palette plus its own overrides: a dark-first deck keeps its light palette under
    # prefers-color-scheme: light, so that block is checked too, not only the base colours.
    light_css = media_blocks(css, re.compile(r"prefers-color-scheme\s*:\s*light", re.I))
    dark_css = media_blocks(css, re.compile(r"prefers-color-scheme\s*:\s*dark", re.I))
    base = tokens(flat)
    light = {**base, **tokens(light_css)}
    dark = {**base, **tokens(dark_css)}
    failures = []
    for theme, palette in (("light", light), ("dark", dark)):
        for foreground, background in PAIRS:
            # Code blocks that set their own --code-text are read in that colour, not --text.
            if (foreground, background) == ("--text", "--code-bg") and "--code-text" in palette:
                foreground = "--code-text"
            ratio = contrast_ratio(palette.get(foreground, ""), palette.get(background, ""))
            if ratio is not None and ratio < 4.5:
                failures.append(f"In the {theme} theme {foreground} on {background} is {ratio:.1f}:1; text needs 4.5:1.")
    # Literal colour pairs in plain rules, in light- and dark-mode rules and in inline styles.
    for selector, declarations in [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", flat)] + \
            [(f"{m.group(1).strip()} (light mode)", m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", light_css)] + \
            [(f"{m.group(1).strip()} (dark mode)", m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", dark_css)] + \
            [(f"<{node.name} style>", strip_comments(node.attrs["style"])) for node in nodes if node.attrs.get("style")]:
        color = re.search(r"(?:^|;|\s)color\s*:\s*(#[0-9a-f]{3,6})\b", declarations, re.I)
        background = re.search(r"background(?:-color)?\s*:\s*(#[0-9a-f]{3,6})\b", declarations, re.I)
        ratio = contrast_ratio(color.group(1), background.group(1)) if color and background else None
        if ratio is not None and ratio < 4.5:
            failures.append(f"{selector[:40]} sets {color.group(1)} on {background.group(1)} ({ratio:.1f}:1); text needs 4.5:1.")
    for failure in list(dict.fromkeys(failures))[:5]:
        add("contrast", failure)

    visible = text_of(main)
    for pattern in PLACEHOLDERS:
        match = pattern.search(visible)
        if match:
            add("empty", f'Replace the placeholder text ("{match.group(0).strip()}").')
            break
    empty = []
    for heading in [node for node in nodes if re.fullmatch(r"h[2-4]", node.name) and in_main(node)]:
        own = section_nodes(nodes, heading)
        if not any((node.name in CONTENT or is_visual(node) or node.name == "div")
                   and (text_of(node).strip() or any(is_visual(inner) for inner in walk(node))) for node in own):
            empty.append(f'"{text_of(heading).strip()[:50]}"')
    if empty:
        add("empty", f"Fill in or remove the empty section(s) {', '.join(empty[:4])}.")
    hollow = [table for table in by_name("table") if not any(node.name == "td" and text_of(node).strip() for node in walk(table))]
    if hollow:
        add("empty", "Remove the empty table, or say in a sentence that there is nothing to list.")
    return problems


def main(argv: list[str]) -> int:
    kind = "report"
    if len(argv) == 4 and argv[2] == "--kind" and argv[3] in {"report", "slides"}:
        kind = argv[3]
    elif len(argv) != 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    problems = check_page(Path(argv[1]).read_text(encoding="utf-8"), kind)
    if not problems:
        print("Page meets the readable-page standard.")
        return 0
    print("Page does not meet the readable-page standard yet. Fix these:")
    for _rule, message in problems:
        print(f"- {message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
