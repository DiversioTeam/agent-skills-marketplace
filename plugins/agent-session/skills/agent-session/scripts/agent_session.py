#!/usr/bin/env python3
"""Find, render, redact, and publish the agent sessions behind a pull request.

    agent_session.py share [--pr N] [--yes]    render, publish, link in the PR body, delete superseded uploads
    agent_session.py find                      list the sessions that belong to this branch or PR
    agent_session.py render [--open]           write the redacted preview page(s) locally
    agent_session.py publish                   upload the reviewed preview to Internal Share
    agent_session.py declare-none REASON       no agent worked on this branch: record it and say so in the PR
    agent_session.py update-body FILE --link URL ...   add or replace the PR body's "Agent sessions" section
    agent_session.py check-body FILE|-         exit 1 unless a body has a session link or a "No agent session:" line

Standard library only, so it runs the same under Claude Code, Pi, and Codex.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import claude_code  # noqa: E402
import pr_body  # noqa: E402
import publish as publisher  # noqa: E402
from redaction import Redactor, collect_known_secrets  # noqa: E402
from render_html import build_pages, number_turns  # noqa: E402
from repo_context import RepoContext  # noqa: E402
import store  # noqa: E402
from session_model import Item, Turn, Unit  # noqa: E402

DEFAULT_RETENTION_DAYS = 365
MANIFEST = "manifest.json"


def _context(args: argparse.Namespace) -> RepoContext:
    return RepoContext.detect(Path(args.repo).resolve(), branch=args.branch, pr=args.pr)


def _out_dir(args: argparse.Namespace, context: RepoContext) -> Path:
    if getattr(args, "out", None):
        return Path(args.out).expanduser().resolve()
    slug = f"{context.repo_name}-{context.branch}".replace("/", "-")
    return Path.home() / ".agent" / "sessions" / slug


def _select_turns(unit: Unit, context: RepoContext, whole: bool) -> None:
    """Keep the turns that belong to this work: on the branch, mentioning it or the PR, or starting a subagent that does."""
    if whole:
        return
    def belongs(turn: Turn) -> bool:
        if turn.evidence or (context.branch and turn.branch == context.branch):
            return True
        return any(item.tool and item.tool.subagent and item.tool.subagent.evidence for item in turn.items)
    kept = [turn for turn in unit.turns if belongs(turn)]
    unit.omitted_turns = len(unit.turns) - len(kept)
    unit.turns = kept
    if kept and unit.omitted_turns:
        unit.started = kept[0].timestamp
        last = kept[-1]
        unit.ended = max([last.timestamp, *(item.timestamp for item in last.items if item.timestamp)])


def load_units(context: RepoContext, args: argparse.Namespace) -> list[Unit]:
    root = Path(args.projects_root).expanduser() if args.projects_root else None
    paths = claude_code.find_sessions(context, root)
    if args.session:
        wanted = set(args.session)
        all_paths = [path for project in (root or claude_code.projects_root()).iterdir() if project.is_dir()
                     for path in project.glob("*.jsonl") if path.stem in wanted]
        paths = sorted({*paths, *all_paths}, key=lambda path: path.stat().st_mtime)
    excluded = set(args.exclude or [])
    whole = set(args.whole or []) | set(args.session or [])
    units = []
    for path in paths:
        if path.stem in excluded:
            continue
        unit = claude_code.load_session(path, context)
        _select_turns(unit, context, unit.id in whole)
        unit.teammates = [mate for mate in unit.teammates
                          if mate.id not in excluded and (mate.evidence or mate.id in whole or unit.id in whole)]
        if unit.turns or unit.teammates:
            units.append(unit)
    return units


def _apply_turn_choices(units: list[Unit], drop: set[int], include_output: set[int]) -> None:
    number_turns(units)
    stack = list(units)
    while stack:
        unit = stack.pop()
        stack.extend(unit.teammates)
        for turn in unit.turns:
            for item in turn.items:
                if item.tool and item.tool.subagent:
                    stack.append(item.tool.subagent)
                if item.tool and turn.number in include_output and item.tool.withheld == "prod or staging data access":
                    item.tool.withheld = None
            if turn.number in drop:
                turn.text = ""
                turn.items = [Item(kind="note", text=f"Turn {turn.number} was removed by the developer before publishing.")]


def cmd_find(args: argparse.Namespace) -> int:
    context = _context(args)
    units = load_units(context, args)
    rows = []
    for unit in units:
        rows.append({"session": unit.id, "harness": unit.harness, "started": unit.started, "ended": unit.ended,
                     "turns_included": len(unit.turns), "turns_omitted": unit.omitted_turns, "evidence": unit.evidence,
                     "teammates": [{"id": mate.id, "title": mate.title, "evidence": mate.evidence} for mate in unit.teammates]})
    if args.json:
        print(json.dumps({"repo": context.repo_slug, "branch": context.branch, "pr": context.pr, "sessions": rows}, indent=2))
        return 0
    print(f"{context.repo_slug or context.repo_name} · {context.branch}{f' · PR #{context.pr}' if context.pr else ''}")
    if not rows:
        print("No agent sessions found for this branch. If no agent worked on it, declare that in the PR body:\n"
              "  No agent session: <reason>")
        return 0
    for row in rows:
        print(f"- {row['session']} ({row['harness']}) {row['started'][:16]} to {row['ended'][11:16]}: "
              f"{row['turns_included']} turns included, {row['turns_omitted']} omitted; {', '.join(row['evidence']) or 'no direct evidence'}")
        for mate in row["teammates"]:
            print(f"    · {mate['title']} ({mate['id']}): {', '.join(mate['evidence']) or 'included with its session'}")
    return 0


def _render(args: argparse.Namespace, context: RepoContext) -> tuple[Path, dict] | None:
    """Write the preview page(s) and manifest; print the summary. None when no session was found."""
    units = load_units(context, args)
    if not units:
        print("No agent sessions found for this branch. Add one with --session ID, or run declare-none 'reason' if no agent worked on it.")
        return None
    _apply_turn_choices(units, set(args.drop_turn or []), set(args.include_output or []))
    roots = [context.root, *context.worktrees]
    redactor = Redactor(known_secrets=collect_known_secrets(roots))
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(days=args.retention_days)).strftime("%Y-%m-%d")
    # Render once to learn the part count, then name the parts so they can link to each other.
    pages, _ = build_pages(context, units, Redactor(known_secrets=redactor.known_secrets), expires, now.strftime("%Y-%m-%d %H:%M UTC"))
    names = publisher.build_names(context.repo_name, context.branch, len(pages), context.head, now)
    pages, page = build_pages(context, units, redactor, expires, now.strftime("%Y-%m-%d %H:%M UTC"), names)
    out = _out_dir(args, context)
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("session-*.html"):
        stale.unlink()
    files = []
    for name, html_text in zip(names, pages):
        (out / name).write_text(html_text, encoding="utf-8")
        files.append({"name": name, "sha256": hashlib.sha256(html_text.encode()).hexdigest(), "bytes": len(html_text.encode())})
    counts = {kind: count for kind, count in redactor.counts.items() if count}
    manifest = {"repo": context.repo_slug, "branch": context.branch, "pr": context.pr, "expires": expires, "files": files,
                "head": context.head, "base": context.base, "commits": context.commits,
                "sessions": [unit.id for unit in units], "redactions": counts, "withheld": dict(page.withheld),
                "clipped": page.counts["clipped"], "turns": page.counts["turns"]}
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Preview: {out / names[0]}" + (f" (+{len(names) - 1} more parts)" if len(names) > 1 else ""))
    print(f"Covers: {context.base[:12] or 'start'}..{context.head[:12]} ({len(context.commits)} commits); "
          f"sessions: {len(units)}; turns: {page.counts['turns']}; tool calls: {page.counts['tool_calls']}")
    summary = [f"{count} {kind.replace('_', ' ')}" for kind, count in sorted(counts.items())]
    summary += [f"{count} outputs withheld ({reason})" for reason, count in sorted(page.withheld.items())]
    print("Redacted: " + (", ".join(summary) if summary else "nothing matched"))
    if getattr(args, "open", False):
        webbrowser.open((out / names[0]).as_uri())
    return out, manifest


def cmd_render(args: argparse.Namespace) -> int:
    rendered = _render(args, _context(args))
    if rendered:
        print("Review the page before publishing: it includes your own prompts word for word. "
              "Drop a turn with --drop-turn N; include a withheld prod/staging output with --include-output N.")
    return 0 if rendered else 1


def _labels(links: list[str]) -> list[str]:
    return ["Agent session transcript" if len(links) == 1 else f"Agent session transcript, part {index + 1}" for index in range(len(links))]


def _find_pr(context: RepoContext) -> int | None:
    """The open PR for this branch, through gh; None when there is none or gh cannot tell."""
    if not context.repo_slug or not context.branch:
        return None
    completed = subprocess.run(["gh", "pr", "view", context.branch, "-R", context.repo_slug, "--json", "number,state", "-q",
                                'select(.state == "OPEN") | .number'], capture_output=True, text=True, check=False, timeout=60)
    value = completed.stdout.strip()
    return int(value) if completed.returncode == 0 and value.isdigit() else None


def _update_pr_body(context: RepoContext, pr: int, new_section: str) -> bool:
    view = subprocess.run(["gh", "pr", "view", str(pr), "-R", context.repo_slug, "--json", "body", "-q", ".body"],
                          capture_output=True, text=True, check=False, timeout=60)
    if view.returncode != 0:
        print(f"Could not read PR #{pr}; add this section to its body yourself:\n\n{new_section}")
        return False
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write(pr_body.upsert(view.stdout, new_section))
    try:
        edit = subprocess.run(["gh", "pr", "edit", str(pr), "-R", context.repo_slug, "--body-file", handle.name],
                              capture_output=True, text=True, check=False, timeout=60)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    if edit.returncode != 0:
        print(f"Could not update PR #{pr}; add this section to its body yourself:\n\n{new_section}")
        return False
    print(f"Updated the Agent sessions section of PR #{pr}.")
    return True


def _publish(context: RepoContext, out: Path, manifest: dict) -> int:
    """Upload a rendered preview, record it, link it in the PR, and delete the uploads it supersedes."""
    previous = store.latest(context.repo_slug, context.branch)
    links = []
    try:
        for entry in manifest["files"]:
            path = out / entry["name"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                print(f"{path.name} changed after render; render again before publishing.")
                return 1
            links.append(publisher.upload(path, entry["name"]))
    except publisher.PublishError as error:
        print(error)
        return 1
    names = [entry["name"] for entry in manifest["files"]]
    manifest["links"] = links
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    pr = context.pr or _find_pr(context)
    store.record({"repo": context.repo_slug, "branch": context.branch, "head": manifest["head"], "base": manifest["base"],
                  "commits": manifest["commits"], "names": names, "links": links, "pr": pr,
                  "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    for link in links:
        print(f"Published: {link}")
    section = pr_body.section(list(zip(_labels(links), links)))
    if pr:
        _update_pr_body(context, pr, section)
    else:
        print("\nNo open PR yet. Put this section in the PR body (or run share again after opening it):\n\n" + section)
    for name in (previous or {}).get("names") or []:
        if name not in names:
            try:
                gone = publisher.delete(str(name))
            except publisher.PublishError:
                gone = False
            print(f"{'Deleted' if gone else 'Could not delete'} the superseded {name}.")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    context = _context(args)
    out = _out_dir(args, context)
    try:
        manifest = json.loads((out / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(f"No rendered preview in {out}. Run render first.")
        return 1
    if manifest.get("head") != context.head:
        print(f"The preview covers {str(manifest.get('head'))[:12]} but HEAD is {context.head[:12]}; run share (or render) again.")
        return 1
    return _publish(context, out, manifest)


def cmd_share(args: argparse.Namespace) -> int:
    """Render, publish, and link in one step. The first publish on a branch waits for the developer's yes."""
    context = _context(args)
    context.pr = context.pr or _find_pr(context)
    rendered = _render(args, context)
    if not rendered:
        return 1
    previous = store.latest(context.repo_slug, context.branch)
    approved = previous is not None and not previous.get("none")
    if not args.yes and not approved:
        print("First publish for this branch: show the developer the preview and redaction summary (their prompts appear "
              "word for word, visible to Diversio staff). With their yes, run the same command with --yes.")
        return 3
    return _publish(context, *rendered)


def cmd_declare_none(args: argparse.Namespace) -> int:
    """Record that no agent worked on this branch, and say so in the PR body."""
    context = _context(args)
    reason = args.reason.strip()
    if len(reason) < 3:
        print("Give a reason, for example: declare-none 'hand-edited a config value'.")
        return 1
    pr = context.pr or _find_pr(context)
    store.record({"repo": context.repo_slug, "branch": context.branch, "head": context.head, "none": reason, "pr": pr,
                  "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    section = f"{pr_body.SECTION_HEADING}\n\nNo agent session: {reason}\n"
    if pr:
        _update_pr_body(context, pr, section)
    else:
        print("Recorded. Put this in the PR body when you open it:\n\n" + section)
    return 0


def cmd_update_body(args: argparse.Namespace) -> int:
    path = Path(args.body_file)
    body = path.read_text(encoding="utf-8") if path.exists() else ""
    links = args.link or []
    labels = _labels(links)
    if not links and not args.none:
        print("Pass --link URL (repeatable) or --none 'reason'.")
        return 1
    new_section = pr_body.section(list(zip(labels, links))) if links else f"{pr_body.SECTION_HEADING}\n\nNo agent session: {args.none.strip()}\n"
    path.write_text(pr_body.upsert(body, new_section), encoding="utf-8")
    return 0


def cmd_check_body(args: argparse.Namespace) -> int:
    body = sys.stdin.read() if args.body_file == "-" else Path(args.body_file).read_text(encoding="utf-8")
    if pr_body.has_transcript(body):
        return 0
    print("The PR body has no agent session link. Run the agent-session skill, or add 'No agent session: <reason>'.")
    return 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = root.add_subparsers(dest="command", required=True)

    def selection(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--repo", default=".", help="Repository path (default: current directory).")
        sub.add_argument("--branch", help="Branch (default: the checked-out branch).")
        sub.add_argument("--pr", type=int, help="PR number, when one exists.")
        sub.add_argument("--session", action="append", help="Also include this session id, whole.")
        sub.add_argument("--exclude", action="append", help="Leave out this session or teammate id.")
        sub.add_argument("--whole", action="append", help="Include every turn of this session, not only the matching ones.")
        sub.add_argument("--projects-root", help="Claude Code projects folder (default: ~/.claude/projects).")
        sub.add_argument("--out", help="Where previews go (default: ~/.agent/sessions/<repo>-<branch>).")

    find = commands.add_parser("find", help="List the sessions behind this branch or PR.")
    selection(find)
    find.add_argument("--json", action="store_true")
    find.set_defaults(run=cmd_find)

    def rendering(sub: argparse.ArgumentParser) -> None:
        selection(sub)
        sub.add_argument("--drop-turn", type=int, action="append", help="Remove this turn number (repeatable).")
        sub.add_argument("--include-output", type=int, action="append",
                         help="Publish the withheld prod or staging output in this turn (repeatable). Never applies to credentials.")
        sub.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
        sub.add_argument("--open", action="store_true", help="Open the preview in the browser.")

    share = commands.add_parser("share", help="Render, publish, link in the PR, and delete superseded uploads (the usual command).")
    rendering(share)
    share.add_argument("--yes", action="store_true", help="The developer reviewed the preview and agreed to publish.")
    share.set_defaults(run=cmd_share)

    render = commands.add_parser("render", help="Write the redacted preview page(s).")
    rendering(render)
    render.set_defaults(run=cmd_render)

    none = commands.add_parser("declare-none", help="Record that no agent worked on this branch and say so in the PR body.")
    none.add_argument("reason")
    none.add_argument("--repo", default=".")
    none.add_argument("--branch")
    none.add_argument("--pr", type=int)
    none.set_defaults(run=cmd_declare_none)

    publish = commands.add_parser("publish", help="Upload the reviewed preview to Internal Share.")
    publish.add_argument("--repo", default=".")
    publish.add_argument("--branch")
    publish.add_argument("--pr", type=int)
    publish.add_argument("--out")
    publish.set_defaults(run=cmd_publish)

    update = commands.add_parser("update-body", help="Add or replace the PR body's Agent sessions section.")
    update.add_argument("body_file")
    update.add_argument("--link", action="append")
    update.add_argument("--none", help="Declare that no agent session was involved, with the reason.")
    update.set_defaults(run=cmd_update_body)

    check = commands.add_parser("check-body", help="Exit 1 unless the body has a session link or a declaration.")
    check.add_argument("body_file")
    check.set_defaults(run=cmd_check_body)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
