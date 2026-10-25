import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).parents[1] / "plugins" / "agent-session" / "skills" / "agent-session" / "scripts"
sys.path.insert(0, str(SCRIPTS))

agent_session = importlib.import_module("agent_session")
claude_code = importlib.import_module("claude_code")
check_pr_hook = importlib.import_module("check_pr_hook")
pr_body = importlib.import_module("pr_body")
publish = importlib.import_module("publish")
redaction = importlib.import_module("redaction")
render_html = importlib.import_module("render_html")
repo_context = importlib.import_module("repo_context")
store = importlib.import_module("store")
check = importlib.import_module("check")
slicing = importlib.import_module("slicing")

# Synthetic secrets, assembled at runtime so no literal token shape is committed.
GITHUB_TOKEN = "ghp_" + "Zx9Q" * 9
SLACK_TOKEN = "xoxb-" + "1234567890-" + "abcdefghijKLMNOP"
AWS_KEY_ID = "AKIA" + "QZ7X" * 4
OPENAI_KEY = "sk-" + "proj" + "A1b2C3d4" * 3
JWT = "eyJ" + "hbGciOiJIUzI1NiJ9" + "." + "eyJzdWIiOiIxIn0" + "." + "c2lnbmF0dXJl"
ENV_SECRET = "synthetic-" + "env-value-" + "7f3a9c"
CUSTOMER_EMAIL = "pat.customer" + "@" + "acme-example.io"
STAFF_EMAIL = "dev" + "@" + "diversio.com"
HEAD = "0123456789abcdef0123456789abcdef01234567"


class RedactorTests(unittest.TestCase):
    def setUp(self):
        self.redactor = redaction.Redactor(known_secrets=(ENV_SECRET,))

    def test_secret_shapes_are_replaced_and_counted(self):
        text = (f"token {GITHUB_TOKEN} slack {SLACK_TOKEN} aws {AWS_KEY_ID} key {OPENAI_KEY} jwt {JWT}\n"
                f"Authorization: Bearer {'q' * 24}\nCookie: sessionid=abc123def456\n"
                f"https://app.example.com/callback?code=Zq81xYw2&state=s7d9\npostgres://admin:hunter2pass@db.internal/app\n"
                f"API_TOKEN={'Ab3' * 6}\nvalue {ENV_SECRET}")
        result = self.redactor.text(text)
        for secret in (GITHUB_TOKEN, SLACK_TOKEN, AWS_KEY_ID, OPENAI_KEY, JWT, "q" * 24, "abc123def456", "Zq81xYw2", "hunter2pass", "Ab3" * 6, ENV_SECRET):
            self.assertNotIn(secret, result)
        self.assertIn("API_TOKEN=[redacted]", result)
        self.assertIn("postgres://admin:[redacted]@db.internal", result)
        self.assertGreaterEqual(self.redactor.counts["known_secret"], 1)
        self.assertGreaterEqual(self.redactor.counts["github_token"], 1)

    def test_customer_emails_and_phones_go_staff_emails_stay(self):
        result = self.redactor.text(f"{CUSTOMER_EMAIL} and {STAFF_EMAIL}, call 416-555-0199")
        self.assertNotIn(CUSTOMER_EMAIL, result)
        self.assertIn(STAFF_EMAIL, result)
        self.assertIn("[phone]", result)

    def test_code_and_shas_survive(self):
        text = "password_field = models.CharField(max_length=128)\ncommit 3f08af3826512dc9e1b2a3c4d5e6f708192a3b4c"
        self.assertEqual(self.redactor.text(text), text)

    def test_personal_rows_and_withheld_commands(self):
        rows = json.dumps([{"email": "a", "first_name": "b", "last_name": "c"}, {"email": "d", "first_name": "e", "last_name": "f"}])
        self.assertTrue(redaction.looks_like_personal_rows(rows))
        self.assertFalse(redaction.looks_like_personal_rows("def send_email(user): return user.email"))
        self.assertEqual(redaction.withheld_reason("Read", {"file_path": "/repo/.env.local"}), "credential file")
        self.assertIsNone(redaction.withheld_reason("Read", {"file_path": "/repo/.env.example"}))
        self.assertEqual(redaction.withheld_reason("Read", {"file_path": "/repo/config/secrets-prod.json"}), "credential file")
        self.assertEqual(redaction.withheld_reason("Read", {"file_path": "/repo/credentials.local"}), "credential file")
        self.assertIsNone(redaction.withheld_reason("Read", {"file_path": "/repo/app/secrets_manager.py"}))
        self.assertEqual(redaction.withheld_reason("Bash", {"command": "printenv | sort"}), "command prints credentials")
        self.assertEqual(redaction.withheld_reason("Bash", {"command": "op read op://Vault/item/field"}), "command prints credentials")
        self.assertEqual(redaction.withheld_reason("Bash", {"command": "psql -h db.prod.internal -c 'select 1'"}), "prod or staging data access")
        self.assertEqual(redaction.withheld_reason("Bash", {"command": "ssh staging 'python manage.py shell'"}), "prod or staging data access")
        self.assertIsNone(redaction.withheld_reason("Bash", {"command": "pytest tests/ -k staging_banner"}))

    def test_known_secrets_come_from_env_files_and_secret_named_variables(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, ".env").write_text(f"DJANGO_SECRET_KEY='{ENV_SECRET}'\nDEBUG=true\n", encoding="utf-8")
            Path(directory, ".env.example").write_text("EXAMPLE=placeholder-value\n", encoding="utf-8")
            values = redaction.collect_known_secrets([Path(directory)], {"MY_API_TOKEN": "tok-" + "9" * 10, "HOME": "/Users/someone"})
        self.assertIn(ENV_SECRET, values)
        self.assertIn("tok-" + "9" * 10, values)
        self.assertNotIn("placeholder-value", values)
        self.assertNotIn("/Users/someone", values)


def _record(kind, content, timestamp, branch="feature/demo-transcripts", **extra):
    message = {"role": "user", "content": content} if kind == "user" else {
        "id": extra.pop("message_id", f"msg_{timestamp}"), "model": "claude-opus-5-5", "role": "assistant", "content": content,
        "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 20}}
    return {"type": kind, "timestamp": timestamp, "gitBranch": branch, "cwd": "/tmp/demo-repo", "sessionId": "s1", "message": message, **extra}


def build_store(root: Path, cwd: str = "") -> Path:
    project = root / "-tmp-demo-repo"
    session = project / "11111111-2222-3333-4444-555555555555"
    (session / "subagents").mkdir(parents=True)
    records = [
        _record("user", "Earlier unrelated work on main", "2026-10-23T09:00:00Z", branch="main", origin={"kind": "human"}),
        _record("assistant", [{"type": "text", "text": "Done with that."}], "2026-10-23T09:00:05Z", branch="main"),
        _record("user", f"<system-reminder>ignore me</system-reminder>Add the transcript feature. My key is {OPENAI_KEY}",
                "2026-10-23T10:00:00Z", origin={"kind": "human"}),
        _record("assistant", [{"type": "thinking", "thinking": "private"}], "2026-10-23T10:00:01Z", message_id="m1"),
        _record("assistant", [{"type": "text", "text": "Reading the config and the **database**. See `src/app.py`."}], "2026-10-23T10:00:02Z", message_id="m1"),
        _record("assistant", [{"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/tmp/demo-repo/.env"}}], "2026-10-23T10:00:03Z", message_id="m1"),
        _record("user", [{"type": "tool_result", "tool_use_id": "t1", "content": f"SECRET={ENV_SECRET}"}], "2026-10-23T10:00:04Z"),
        _record("assistant", [{"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "psql -h db.prod.internal -c 'select * from users'"}}], "2026-10-23T10:00:05Z"),
        _record("user", [{"type": "tool_result", "tool_use_id": "t2", "content": f"id | email\n1 | {CUSTOMER_EMAIL}"}], "2026-10-23T10:00:06Z"),
        _record("assistant", [{"type": "tool_use", "id": "t3", "name": "Bash", "input": {"command": "gh auth status"}}], "2026-10-23T10:00:07Z"),
        _record("user", [{"type": "tool_result", "tool_use_id": "t3", "content": f"Logged in, token {GITHUB_TOKEN}, owner {CUSTOMER_EMAIL}"}], "2026-10-23T10:00:08Z"),
        _record("assistant", [{"type": "tool_use", "id": "t4", "name": "Agent", "input": {"description": "Explore the store", "prompt": "Look around"}}], "2026-10-23T10:00:09Z"),
        _record("user", [{"type": "tool_result", "tool_use_id": "t4", "content": "Found it."}], "2026-10-23T10:01:00Z"),
        _record("user", "<script>alert(1)</script> please render this safely", "2026-10-23T10:02:00Z", origin={"kind": "human"}),
        _record("assistant", [{"type": "text", "text": "Escaped. PR: https://github.com/DiversioTeam/demo/pull/7"}], "2026-10-23T10:02:01Z"),
        {"type": "pr-link", "prNumber": 7, "prRepository": "DiversioTeam/demo", "timestamp": "2026-10-23T10:03:00Z"},
    ]
    main = project / f"{session.name}.jsonl"
    main.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    sub = session / "subagents" / "agent-a1.jsonl"
    sub.write_text("\n".join(json.dumps(record) for record in [
        _record("user", "Look around", "2026-10-23T10:00:10Z"),
        _record("assistant", [{"type": "text", "text": f"Sub found {SLACK_TOKEN}"}], "2026-10-23T10:00:20Z"),
    ]) + "\n", encoding="utf-8")
    (session / "subagents" / "agent-a1.meta.json").write_text(json.dumps({"toolUseId": "t4", "description": "Explore the store", "agentType": "Explore"}))
    mate = session / "subagents" / "agent-amate-1.jsonl"
    mate.write_text("\n".join(json.dumps(record) for record in [
        _record("user", '<teammate-message teammate_id="team-lead">Build the renderer for feature/demo-transcripts</teammate-message>', "2026-10-23T10:05:00Z"),
        _record("assistant", [{"type": "text", "text": "On it."}], "2026-10-23T10:05:10Z"),
    ]) + "\n", encoding="utf-8")
    (session / "subagents" / "agent-amate-1.meta.json").write_text(json.dumps({"name": "renderer", "taskKind": "in_process_teammate"}))
    other = project / "99999999-0000-0000-0000-000000000000.jsonl"
    other.write_text(json.dumps(_record("user", "Unrelated session", "2026-10-23T08:00:00Z", branch="other", origin={"kind": "human"})) + "\n")
    if cwd:  # the sessions ran in this checkout instead
        for path in project.rglob("*.jsonl"):
            path.write_text(path.read_text(encoding="utf-8").replace('"cwd": "/tmp/demo-repo"', json.dumps({"cwd": cwd})[1:-1]), encoding="utf-8")
    return main


def demo_context() -> "repo_context.RepoContext":
    return repo_context.RepoContext(root=Path("/tmp/demo-repo"), branch="feature/demo-transcripts", repo_slug="DiversioTeam/demo",
                                    pr=7, worktrees=[Path("/tmp/demo-repo")], since=0, head=HEAD, base="f" * 40, commits=[HEAD])


class ClaudeCodeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.main = build_store(self.root)

    def tearDown(self):
        self.directory.cleanup()

    def test_finds_only_sessions_for_the_branch(self):
        found = claude_code.find_sessions(demo_context(), self.root)
        self.assertEqual([path.name for path in found], [self.main.name])

    def test_parses_turns_tools_subagents_teammates_and_tokens(self):
        unit = claude_code.load_session(self.main, demo_context())
        self.assertEqual([turn.kind for turn in unit.turns], ["developer", "developer", "developer"])
        self.assertEqual(unit.models, ["claude-opus-5-5"])
        self.assertIn("linked to PR #7", unit.evidence)
        tools = [item.tool for item in unit.turns[1].items if item.tool]
        self.assertEqual([tool.withheld for tool in tools], ["credential file", "prod or staging data access", None, None])
        self.assertEqual(tools[3].subagent.title, "Subagent: Explore the store")
        self.assertEqual([mate.title for mate in unit.teammates], ["Teammate: renderer"])
        self.assertEqual(unit.teammates[0].turns[0].kind, "teammate")
        # m1 spans three records but is counted once.
        self.assertEqual(unit.tokens.output, 5 * 6)

    def test_rendered_page_is_redacted_escaped_and_script_free(self):
        unit = claude_code.load_session(self.main, demo_context())
        agent_session._select_turns(unit, demo_context(), whole=False)
        self.assertEqual(unit.omitted_turns, 1)
        redactor = redaction.Redactor(known_secrets=(ENV_SECRET,))
        pages, page = render_html.build_pages(demo_context(), [unit], redactor, "2027-10-23", "2026-10-23 12:00 UTC")
        self.assertEqual(len(pages), 1)
        html = pages[0]
        for secret in (OPENAI_KEY, ENV_SECRET, GITHUB_TOKEN, SLACK_TOKEN, CUSTOMER_EMAIL, "private"):
            self.assertNotIn(secret, html)
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("ignore me", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("Output withheld: credential file.", html)
        self.assertIn("Output withheld: prod or staging data access.", html)
        self.assertIn("Subagent: Explore the store", html)
        self.assertIn("Teammate: renderer", html)
        self.assertIn("1 earlier or later turns", html)
        self.assertIn("<strong>database</strong>", html)
        self.assertNotRegex(html, r"<(?:link|img|iframe|object|embed)\b|\bon[a-z]+=|src=")
        self.assertEqual(dict(page.withheld), {"credential file": 1, "prod or staging data access": 1})
        self.assertIn(f'<meta name="agent-session-head" content="{HEAD}">', html)
        self.assertIn(f"ffffffffffff..{HEAD[:12]} (1 commit)", html)

    def test_drop_turn_and_include_output(self):
        unit = claude_code.load_session(self.main, demo_context())
        agent_session._select_turns(unit, demo_context(), whole=False)
        agent_session._apply_turn_choices([unit], drop={3}, include_output={1})  # 1 main, 2 its subagent, 3 the next main turn
        tools = [item.tool for item in unit.turns[0].items if item.tool]
        self.assertEqual(tools[0].withheld, "credential file")
        self.assertIsNone(tools[1].withheld)
        dropped = next(turn for turn in unit.turns if turn.number == 3)
        self.assertEqual(dropped.text, "")
        self.assertIn("removed by the developer", dropped.items[0].text)

    def test_large_pages_split_into_linked_parts_even_within_one_session(self):
        unit = claude_code.load_session(self.main, demo_context())
        original = render_html.MAX_PART_BYTES
        render_html.MAX_PART_BYTES = 1
        try:
            # One session of three turns plus its teammate: each turn and the teammate land in their own part.
            count = len(render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")[0])
            unit = claude_code.load_session(self.main, demo_context())
            names = publish.build_names("demo", "feature/demo-transcripts", count, HEAD)
            pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now", names)
        finally:
            render_html.MAX_PART_BYTES = original
        self.assertGreaterEqual(len(pages), 4)
        self.assertIn(f'href="{names[-1]}"', pages[0])
        self.assertIn("Session 11111111 (1 of", pages[0])
        self.assertIn("Teammate: renderer", pages[-1])

    def test_titles_and_senders_are_redacted(self):
        unit = claude_code.load_session(self.main, demo_context())
        unit.teammates[0].title = f"Teammate: {CUSTOMER_EMAIL}"
        unit.teammates[0].turns[0].sender = GITHUB_TOKEN
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertNotIn(CUSTOMER_EMAIL, pages[0])
        self.assertNotIn(GITHUB_TOKEN, pages[0])

    def test_pr_links_alone_find_a_session_and_numbers_are_whole(self):
        project = self.root / "-elsewhere"
        project.mkdir()
        linked = project / "aaaaaaaa-0000-0000-0000-000000000000.jsonl"
        linked.write_text("\n".join(json.dumps(record) for record in [
            _record("user", "Unrelated words", "2026-10-23T11:00:00Z", branch="main", origin={"kind": "human"}),
            {"type": "pr-link", "sessionId": "x", "prNumber": 7, "prRepository": "DiversioTeam/demo", "timestamp": "2026-10-23T11:01:00Z"},
        ]) + "\n", encoding="utf-8")
        other = project / "bbbbbbbb-0000-0000-0000-000000000000.jsonl"
        other.write_text(json.dumps(_record("user", "see https://github.com/DiversioTeam/demo/pull/74 and feature/demo-transcripts-2",
                                            "2026-10-23T11:00:00Z", branch="main", origin={"kind": "human"})) + "\n", encoding="utf-8")
        found = {path.name for path in claude_code.find_sessions(demo_context(), self.root)}
        self.assertIn(linked.name, found)
        self.assertNotIn(other.name, found)
        # Selected end to end: no turn matches the branch, but the session opened the PR, so it is kept whole.
        unit = claude_code.load_session(linked, demo_context())
        agent_session._select_turns(unit, demo_context(), whole=False)
        self.assertEqual([turn.text for turn in unit.turns], ["Unrelated words"])


def build_lead_store(root: Path) -> Path:
    """A lead session on main running three features through three teammates and a subagent. Feature B is this PR."""
    project = root / "-tmp-lead"
    session = project / "22222222-0000-0000-0000-000000000000"
    (session / "subagents").mkdir(parents=True)
    rec = lambda kind, content, ts, **extra: _record(kind, content, ts, branch="main", **extra)
    tool = lambda call_id, name, tool_input, ts: rec("assistant", [{"type": "tool_use", "id": call_id, "name": name, "input": tool_input}], ts)
    result = lambda call_id, text, ts: rec("user", [{"type": "tool_result", "tool_use_id": call_id, "content": text}], ts)
    records = [
        rec("user", "Build feature A: the Fleet panel.", "2026-10-23T09:00:00Z", origin={"kind": "human"}),
        rec("assistant", [{"type": "text", "text": "Starting Fleet work with a teammate."}], "2026-10-23T09:00:01Z"),
        tool("a1", "Agent", {"name": "alpha", "description": "Fleet panel", "prompt": "Build the Fleet panel secret-alpha-plan", "subagent_type": "general-purpose"}, "2026-10-23T09:00:02Z"),
        result("a1", "spawned alpha", "2026-10-23T09:00:03Z"),
        rec("user", "Also build feature B: transcripts. And C: the video.", "2026-10-23T09:10:00Z", origin={"kind": "human"}),
        rec("assistant", [{"type": "text", "text": "Spawning the transcripts teammate now."}], "2026-10-23T09:10:01Z"),
        tool("b1", "Agent", {"name": "beta", "description": "PR transcripts", "prompt": "Design and build PR transcripts", "subagent_type": "general-purpose"}, "2026-10-23T09:10:02Z"),
        result("b1", "spawned beta", "2026-10-23T09:10:03Z"),
        rec("assistant", [{"type": "text", "text": "And the video teammate."}], "2026-10-23T09:10:04Z"),
        tool("g1", "Agent", {"name": "gamma", "description": "Explainer video", "prompt": "Make the video secret-gamma-plan", "subagent_type": "general-purpose"}, "2026-10-23T09:10:05Z"),
        result("g1", "spawned gamma", "2026-10-23T09:10:06Z"),
        rec("user", '<teammate-message teammate_id="alpha">Fleet panel is done secret-alpha-report</teammate-message>', "2026-10-23T09:20:00Z"),
        rec("assistant", [{"type": "text", "text": "Great, merging plan for Fleet."}], "2026-10-23T09:20:01Z"),
        rec("user", '<teammate-message teammate_id="beta">Design ready for review</teammate-message>', "2026-10-23T09:30:00Z"),
        rec("assistant", [{"type": "text", "text": "Approving the design."}], "2026-10-23T09:30:01Z"),
        tool("s1", "SendMessage", {"to": "beta", "message": "Go, with conservative defaults", "summary": "go"}, "2026-10-23T09:30:02Z"),
        result("s1", "queued", "2026-10-23T09:30:03Z"),
        rec("assistant", [{"type": "text", "text": "Also nudging gamma."}], "2026-10-23T09:30:04Z"),
        tool("s2", "SendMessage", {"to": "gamma", "message": "Use the new logo secret-gamma-note"}, "2026-10-23T09:30:05Z"),
        result("s2", "queued", "2026-10-23T09:30:06Z"),
        rec("user", "How is the video going?", "2026-10-23T09:40:00Z", origin={"kind": "human"}),
        rec("assistant", [{"type": "text", "text": "Video is rendering."}], "2026-10-23T09:40:01Z"),
    ]
    main = project / f"{session.name}.jsonl"
    main.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    for name, lines in (("alpha", ["Working on Fleet on feature/fleet-panel"]), ("beta", ["Working on feature/demo-transcripts", "Opened PR"]),
                        ("gamma", ["Rendering the video"])):
        path = session / "subagents" / f"agent-a{name}-1.jsonl"
        path.write_text("\n".join(json.dumps(rec("assistant", [{"type": "text", "text": line}], f"2026-10-23T09:1{index}:00Z"))
                                  for index, line in enumerate(lines)) + "\n", encoding="utf-8")
        (session / "subagents" / f"agent-a{name}-1.meta.json").write_text(json.dumps({"name": name, "taskKind": "in_process_teammate"}))
    return main


class SlicingTests(unittest.TestCase):
    def test_a_multi_feature_lead_session_shows_only_this_prs_work(self):
        with tempfile.TemporaryDirectory() as directory:
            main = build_lead_store(Path(directory))
            self.assertEqual(claude_code.find_sessions(demo_context(), Path(directory)), [main])
            unit = claude_code.load_session(main, demo_context())
        slicing.slice_to_work(unit, demo_context(), whole=False)
        self.assertEqual([mate.worker_key for mate in unit.teammates], ["beta"])
        self.assertTrue(unit.title.endswith("only the parts about this work"))
        prompts = [turn.text for turn in unit.turns]
        self.assertEqual(prompts, ["Also build feature B: transcripts. And C: the video.", "Design ready for review"])
        calls = [(item.tool.name, item.tool.links_to) for turn in unit.turns for item in turn.items if item.tool]
        self.assertEqual(calls, [("Agent", "beta"), ("SendMessage", "beta")])
        texts = [item.text for turn in unit.turns for item in turn.items if item.kind == "assistant"]
        self.assertEqual(texts, ["Spawning the transcripts teammate now.", "Approving the design."])
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        html = pages[0]
        for present in ("Design and build PR transcripts", "Go, with conservative defaults", "Teammate: beta", "Working on feature/demo-transcripts"):
            self.assertIn(present, html)
        for absent in ("secret-alpha", "secret-gamma", "Fleet panel", "Explainer video", "Rendering the video", "How is the video going"):
            self.assertNotIn(absent, html)
        self.assertIn("turns in this session were about other work", html)


class CourageBotFindingsTests(unittest.TestCase):
    """Regressions for the redaction gaps courage-bot reproduced on #116."""

    def render(self, records, known=()):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "s.jsonl"
            path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
            unit = claude_code.parse_unit(path, "session", "Session", demo_context())
            pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(known_secrets=tuple(known)), "2027-10-23", "now")
            return unit, pages[0]

    def tool(self, call_id, name, tool_input, output, timestamp):
        return [_record("assistant", [{"type": "tool_use", "id": call_id, "name": name, "input": tool_input}], timestamp),
                _record("user", [{"type": "tool_result", "tool_use_id": call_id, "content": output}], timestamp)]

    def test_known_secrets_with_json_escapes_are_redacted_in_structured_inputs(self):
        secret = "syn\\the\"tic\nvalue-" + "42ab"
        _, html = self.render([_record("user", "write it", "2026-10-23T10:00:00Z", origin={"kind": "human"}),
                               *self.tool("w1", "Write", {"file_path": "/repo/app.cfg", "content": f"token = {secret}"}, "ok", "2026-10-23T10:00:01Z")],
                              known=[secret])
        escaped = json.dumps(secret)[1:-1]
        self.assertNotIn(escaped, html)
        self.assertNotIn(render_html.html.escape(escaped), html)

    def test_shell_reads_of_credential_paths_are_withheld(self):
        auth = "dXNlcjpw" + "YXNzd29yZA=="
        unit, html = self.render([_record("user", "check docker", "2026-10-23T10:00:00Z", origin={"kind": "human"}),
                                  *self.tool("b1", "Bash", {"command": "cat ~/.docker/config.json"}, f'{{"auths": {{"r": {{"auth": "{auth}"}}}}}}', "2026-10-23T10:00:01Z")])
        self.assertNotIn(auth, html)
        self.assertIn("Output withheld: credential file.", html)

    def test_background_output_inherits_the_starting_calls_withholding(self):
        sentinel = "private-" + "note-" + "77"
        started = "Command running in background with ID: bg12345. Output is being written to: /tmp/tasks/bg12345.output"
        records = [_record("user", "check prod", "2026-10-23T10:00:00Z", origin={"kind": "human"}),
                   *self.tool("b1", "Bash", {"command": "ssh production 'tail app.log'", "run_in_background": True}, started, "2026-10-23T10:00:01Z"),
                   *self.tool("o1", "TaskOutput", {"task_id": "bg12345"}, sentinel, "2026-10-23T10:00:02Z"),
                   *self.tool("r1", "Read", {"file_path": "/tmp/tasks/bg12345.output"}, sentinel, "2026-10-23T10:00:03Z"),
                   *self.tool("o2", "TaskOutput", {"task_id": "never-seen"}, sentinel, "2026-10-23T10:00:04Z"),
                   *self.tool("b2", "Bash", {"command": "pytest", "run_in_background": True}, started.replace("bg12345", "bg99999"), "2026-10-23T10:00:05Z"),
                   *self.tool("o3", "TaskOutput", {"task_id": "bg99999"}, "4 passed", "2026-10-23T10:00:06Z")]
        unit, html = self.render(records)
        reasons = {item.tool.id: item.tool.withheld for item in unit.turns[0].items if item.tool}
        self.assertEqual(reasons, {"b1": "prod or staging data access", "o1": "prod or staging data access", "r1": "prod or staging data access",
                                   "o2": "background output of unknown origin", "b2": None, "o3": None})
        self.assertNotIn(sentinel, html)
        self.assertIn("4 passed", html)


class CheckTests(unittest.TestCase):
    """`agent-session check`, the local-ci step. Its output is a contract for coding agents; change it deliberately."""

    LINK = "https://internal-share.diversio.com/session-courage-feature-x-20261023-h0123456789ab-a1b2c3.html"
    OLD = "https://internal-share.diversio.com/session-courage-feature-x-20261022-hfedcba987654-d4e5f6.html"

    def input(self, **changes):
        values = dict(repo_root="/work/courage", repo_slug="DiversioTeam/courage", branch="feature/x", head=HEAD)
        values.update(changes)
        return check.Input(**values)

    def test_failure_output_is_pinned(self):
        result = check.decide(self.input(pr=(79, f"## Agent sessions\n\n- [Agent session transcript]({self.OLD})\n")))
        self.assertFalse(result.ok)
        self.assertEqual(result.message, "\n".join([
            "agent-session: stale (transcript covers fedcba987654, HEAD is 0123456789ab) for DiversioTeam/courage branch feature/x PR #79",
            "fix: agent-session share --repo /work/courage --pr 79",
            "next: share renders a redacted preview, publishes it to internal-share, and puts its link in the PR body's \"## Agent sessions\" "
            "section; on a branch's first publish it stops (exit 3) for the developer's review, then rerun with --yes. Run local-ci again afterwards.",
            "no agent worked on this branch: agent-session declare-none '<reason>' --repo /work/courage --pr 79 (writes \"No agent session: <reason>\")",
        ]))

    def test_unverified_and_quoting(self):
        result = check.decide(self.input(pr_lookup_error="gh could not read the PR (check gh auth status)"))
        self.assertEqual(result.message, "agent-session: unverified (gh could not read the PR (check gh auth status)) for DiversioTeam/courage branch feature/x\n"
                                         "fix: gh auth login, then run local-ci again\n"
                                         "next: with the PR readable, the check compares the PR body's agent session link with HEAD")
        quoted = check.decide(self.input(repo_root="/work/$(touch marker)/it's"))
        self.assertIn("--repo '/work/$(touch marker)/it'\"'\"'s'", quoted.message)

    def test_release_flows_bots_and_cloud_sessions_are_skipped(self):
        cases = [
            (dict(branch="main"), "HEAD is on the integration branch main"),
            (dict(branch="dev"), "HEAD is on the integration branch dev"),
            (dict(branch="release/2026.10.24"), "HEAD is on the integration branch release/2026.10.24"),
            (dict(branch="", merged_into="master"), "HEAD is already on the integration branch master"),
            (dict(branch="promote/2026.10.24", pr=(9, ""), pr_base="release"), "a promotion or release PR (promote/2026.10.24 into release)"),
            (dict(branch="releases/2026.10.24", pr=(9, ""), pr_base="master"), "a promotion or release PR (releases/2026.10.24 into master)"),
            (dict(pr=(9, ""), pr_base="dev", pr_author="dependabot[bot]", pr_author_is_bot=True), "a bot's PR (dependabot[bot])"),
            (dict(remote=True), "a cloud session; transcripts are published from a developer's machine"),
        ]
        for changes, reason in cases:
            with self.subTest(changes=changes):
                result = check.decide(self.input(**changes))
                self.assertTrue(result.ok)
                self.assertEqual(result.kind, "skipped")
                self.assertTrue(result.message.startswith(f"agent-session: skipped ({reason}) for DiversioTeam/courage branch "), result.message)
        # Feature work is still checked: a human's feature PR into master, a promote/ branch with no PR, a detached HEAD
        # that no integration branch contains, and a bot-looking branch name from a person.
        for changes in (dict(pr=(9, ""), pr_base="master"), dict(branch="promote/2026.10.24"), dict(branch=""),
                        dict(branch="dependabot/pip/x", pr=(9, ""), pr_base="dev", pr_author="someone")):
            with self.subTest(changes=changes):
                self.assertEqual(check.decide(self.input(**changes)).ok, False)

    def test_check_command_skips_without_asking_github(self):
        import contextlib, io, subprocess
        from unittest import mock
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            git = lambda *args: subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
            git("init", "-q", "-b", "main")
            git("-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-q", "--allow-empty", "-m", "init")
            git("update-ref", "refs/remotes/origin/master", "HEAD")
            git("checkout", "-q", "--detach")
            no_github = mock.patch.object(check, "open_pr", side_effect=AssertionError("asked GitHub"))
            with no_github, contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(agent_session.main(["check", "--repo", str(repo)]), 0)
            self.assertTrue(out.getvalue().startswith("agent-session: skipped (HEAD is already on the integration branch master)"), out.getvalue())
            git("checkout", "-q", "-b", "feature/x")
            with no_github, mock.patch.dict("os.environ", {"CLAUDE_CODE_REMOTE": "true"}), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(agent_session.main(["check", "--repo", str(repo)]), 0)
            self.assertIn("skipped (a cloud session", out.getvalue())
            bot = {"number": 5, "body": "", "base": {"ref": "main"}, "user": {"login": "dependabot[bot]", "type": "Bot"}}
            with mock.patch.object(check, "open_pr", return_value=(bot, "")), mock.patch.dict("os.environ", {"CLAUDE_CODE_REMOTE": ""}), \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(agent_session.main(["check", "--repo", str(repo)]), 0)
            self.assertIn("skipped (a bot's PR (dependabot[bot]))", out.getvalue())
            person = {**bot, "user": {"login": "someone", "type": "User"}}
            with mock.patch.object(check, "open_pr", return_value=(person, "")), mock.patch.dict("os.environ", {"CLAUDE_CODE_REMOTE": ""}), \
                    mock.patch.dict("os.environ", {"AGENT_SESSION_HOME": directory}), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(agent_session.main(["check", "--repo", str(repo)]), 1)
            self.assertTrue(out.getvalue().startswith("agent-session: missing"), out.getvalue())

    def test_decisions(self):
        current = {"head": HEAD, "links": [self.LINK]}
        cases = [
            (dict(pr=(1, "x\n" + self.LINK)), True, "ok"),
            (dict(pr=(1, self.OLD + "\n" + self.LINK)), True, "ok"),
            (dict(pr=(1, "## Agent sessions\n\nNo agent session: hand-edited config")), True, "declared"),
            (dict(pr=(1, "No agent session:")), False, "missing"),
            (dict(pr=(1, self.OLD)), False, "stale"),
            (dict(pr=(1, self.OLD), published=current), False, "unlinked"),
            (dict(pr=(1, "https://internal-share.diversio.com/report.html")), False, "missing"),
            (dict(published=current), True, "ok"),
            (dict(published={"head": "f" * 40, "links": [self.OLD]}), False, "stale"),
            (dict(published={"head": "f" * 40, "none": "manual fix"}), True, "declared"),
            (dict(), False, "missing"),
            (dict(branch="", published=current), False, "missing"),
            (dict(pr_lookup_error="x", published=current), False, "unverified"),
        ]
        for changes, ok, kind in cases:
            result = check.decide(self.input(**changes))
            self.assertEqual((result.ok, result.kind), (ok, kind), changes)

    def test_shim_installs_idempotently(self):
        import contextlib, io, subprocess
        with tempfile.TemporaryDirectory() as directory:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                agent_session.main(["install-shim", "--bin-dir", directory])
                agent_session.main(["install-shim", "--bin-dir", directory, "--quiet"])
            shim = Path(directory, "agent-session")
            self.assertTrue(os.access(shim, os.X_OK))
            self.assertEqual(out.getvalue().count("Installed"), 1)
            completed = subprocess.run([str(shim), "--help"], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0)
            self.assertIn("share", completed.stdout)


class LittlePersonFindingsTests(unittest.TestCase):
    """Regressions for little-person's #116 findings."""

    def write(self, directory, name, records):
        path = Path(directory) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
        return path

    def test_a_turn_that_names_the_pr_keeps_its_ordinary_work(self):
        with tempfile.TemporaryDirectory() as directory:
            main = self.write(directory, "-p/33333333-0000-0000-0000-000000000000.jsonl", [
                _record("user", "Please review https://github.com/DiversioTeam/demo/pull/7", "2026-10-23T10:00:00Z", branch="main", origin={"kind": "human"}),
                _record("assistant", [{"type": "text", "text": "Looking at the diff."}], "2026-10-23T10:00:01Z", branch="main"),
                _record("assistant", [{"type": "tool_use", "id": "d1", "name": "Bash", "input": {"command": "git diff"}}], "2026-10-23T10:00:02Z", branch="main"),
                _record("user", [{"type": "tool_result", "tool_use_id": "d1", "content": "diff --git a/app.py"}], "2026-10-23T10:00:03Z", branch="main"),
            ])
            unit = claude_code.load_session(main, demo_context())
        slicing.slice_to_work(unit, demo_context(), whole=False)
        self.assertEqual([item.kind for item in unit.turns[0].items], ["assistant", "tool"])
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("diff --git a/app.py", pages[0])

    def test_nested_subagents_attach_through_their_parent_subagent(self):
        with tempfile.TemporaryDirectory() as directory:
            main = self.write(directory, "-p/44444444-0000-0000-0000-000000000000.jsonl", [
                _record("user", "Work on it", "2026-10-23T10:00:00Z", origin={"kind": "human"}),
                _record("assistant", [{"type": "tool_use", "id": "p1", "name": "Agent", "input": {"description": "parent", "prompt": "go"}}], "2026-10-23T10:00:01Z"),
            ])
            folder = Path(directory) / "-p" / "44444444-0000-0000-0000-000000000000" / "subagents"
            self.write(folder, "agent-parent.jsonl", [
                _record("user", "go", "2026-10-23T10:00:02Z"),
                _record("assistant", [{"type": "tool_use", "id": "c1", "name": "Agent", "input": {"description": "child", "prompt": "dig"}}], "2026-10-23T10:00:03Z"),
            ])
            (folder / "agent-parent.meta.json").write_text(json.dumps({"toolUseId": "p1", "description": "parent"}))
            self.write(folder, "agent-child.jsonl", [
                _record("user", "dig", "2026-10-23T10:00:04Z", branch="main"),
                _record("assistant", [{"type": "text", "text": "Grandchild finding"}], "2026-10-23T10:00:05Z", branch="main"),
            ])
            (folder / "agent-child.meta.json").write_text(json.dumps({"toolUseId": "c1", "description": "child"}))
            unit = claude_code.load_session(main, demo_context())
        slicing.slice_to_work(unit, demo_context(), whole=False)
        self.assertEqual(unit.teammates, [])
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("Subagent: child", pages[0])
        self.assertIn("Grandchild finding", pages[0])

    def test_one_huge_turn_splits_into_parts_that_fit(self):
        records = [_record("user", "Run everything", "2026-10-23T10:00:00Z", origin={"kind": "human"})]
        for index in range(400):
            records.append(_record("assistant", [{"type": "tool_use", "id": f"t{index}", "name": "Bash", "input": {"command": f"echo {index}"}}], "2026-10-23T10:00:01Z"))
            records.append(_record("user", [{"type": "tool_result", "tool_use_id": f"t{index}", "content": "x" * 3000}], "2026-10-23T10:00:02Z"))
        with tempfile.TemporaryDirectory() as directory:
            unit = claude_code.load_session(self.write(directory, "-p/55555555-0000-0000-0000-000000000000.jsonl", records), demo_context())
        original = render_html.MAX_PART_BYTES
        render_html.MAX_PART_BYTES = 400_000
        try:
            pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        finally:
            render_html.MAX_PART_BYTES = original
        self.assertGreater(len(pages), 2)
        self.assertTrue(all(len(page.encode()) <= 400_000 for page in pages), [len(page.encode()) for page in pages])
        self.assertIn("continued", pages[1])

    def test_a_grandchild_on_the_branch_keeps_the_path_to_it(self):
        import argparse
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as empty:
            main = self.write(directory, "-p/77777777-0000-0000-0000-000000000000.jsonl", [
                _record("user", "Coordinate the work", "2026-10-23T10:00:00Z", branch="main", origin={"kind": "human"}),
                _record("assistant", [{"type": "tool_use", "id": "p1", "name": "Agent", "input": {"description": "parent", "prompt": "go"}}], "2026-10-23T10:00:01Z", branch="main"),
                _record("user", "private-" + "lead-" + "other", "2026-10-23T10:10:00Z", branch="main", origin={"kind": "human"}),
                _record("assistant", [{"type": "tool_use", "id": "u1", "name": "Agent", "input": {"description": "unrelated", "prompt": "elsewhere"}}], "2026-10-23T10:10:01Z", branch="main"),
            ])
            folder = Path(directory) / "-p" / "77777777-0000-0000-0000-000000000000" / "subagents"
            self.write(folder, "agent-parent.jsonl", [
                _record("user", "go", "2026-10-23T10:00:02Z", branch="main"),
                _record("assistant", [{"type": "tool_use", "id": "c1", "name": "Agent", "input": {"description": "child", "prompt": "dig"}}], "2026-10-23T10:00:03Z", branch="main"),
                _record("user", "private-" + "parent-" + "other", "2026-10-23T10:00:30Z", branch="main"),
                _record("assistant", [{"type": "text", "text": "private-" + "parent-" + "reply"}], "2026-10-23T10:00:31Z", branch="main"),
            ])
            (folder / "agent-parent.meta.json").write_text(json.dumps({"toolUseId": "p1", "description": "parent"}))
            self.write(folder, "agent-child.jsonl", [
                _record("user", "dig", "2026-10-23T10:00:04Z"),
                _record("assistant", [{"type": "text", "text": "Grandchild did the PR work"}], "2026-10-23T10:00:05Z"),
            ])
            (folder / "agent-child.meta.json").write_text(json.dumps({"toolUseId": "c1", "description": "child"}))
            self.write(folder, "agent-unrelated.jsonl", [
                _record("user", "elsewhere", "2026-10-23T10:10:02Z", branch="main"),
                _record("assistant", [{"type": "text", "text": "private-" + "sibling-" + "work"}], "2026-10-23T10:10:03Z", branch="main"),
            ])
            (folder / "agent-unrelated.meta.json").write_text(json.dumps({"toolUseId": "u1", "description": "unrelated"}))
            args = argparse.Namespace(projects_root=directory, pi_root=empty, codex_root=empty, session=None, exclude=None, whole=None)
            units = agent_session.load_units(demo_context(), args)
        self.assertEqual([unit.id for unit in units], [main.stem])
        pages, _ = render_html.build_pages(demo_context(), units, redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("Grandchild did the PR work", pages[0])
        self.assertIn("Coordinate the work", pages[0])
        for sentinel in ("lead-other", "parent-other", "parent-reply", "sibling-work"):
            self.assertNotIn("private-" + sentinel, pages[0])

    def test_a_huge_subagent_moves_to_its_own_sections_that_fit(self):
        calls = []
        for index in range(400):
            calls.append(_record("assistant", [{"type": "tool_use", "id": f"k{index}", "name": "Bash", "input": {"command": f"echo {index}"}}], "2026-10-23T10:00:03Z"))
            calls.append(_record("user", [{"type": "tool_result", "tool_use_id": f"k{index}", "content": "y" * 3000}], "2026-10-23T10:00:04Z"))
        with tempfile.TemporaryDirectory() as directory:
            main = self.write(directory, "-p/66666666-0000-0000-0000-000000000000.jsonl", [
                _record("user", "Work on it", "2026-10-23T10:00:00Z", origin={"kind": "human"}),
                _record("assistant", [{"type": "tool_use", "id": "p1", "name": "Agent", "input": {"description": "big child", "prompt": "go"}}], "2026-10-23T10:00:01Z"),
            ])
            folder = Path(directory) / "-p" / "66666666-0000-0000-0000-000000000000" / "subagents"
            self.write(folder, "agent-big.jsonl", [_record("user", "go", "2026-10-23T10:00:02Z"), *calls,
                                                   _record("assistant", [{"type": "text", "text": "Child finished"}], "2026-10-23T10:00:05Z")])
            (folder / "agent-big.meta.json").write_text(json.dumps({"toolUseId": "p1", "description": "big child"}))
            unit = claude_code.load_session(main, demo_context())
        original = render_html.MAX_PART_BYTES
        render_html.MAX_PART_BYTES = 400_000
        try:
            pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
            again, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        finally:
            render_html.MAX_PART_BYTES = original
        self.assertGreater(len(pages), 2)
        self.assertEqual(len(again), len(pages))  # the units are not changed by rendering
        self.assertTrue(all(len(page.encode()) <= 400_000 for page in pages), [len(page.encode()) for page in pages])
        self.assertIn("too long to show inline", pages[0])
        self.assertIn("Child finished", pages[-1])

    def test_bare_credential_operands_are_withheld(self):
        for command in ("cat secrets", "cat secrets-prod", "less service-account", "cat cookies", "head credentials"):
            self.assertEqual(redaction.withheld_reason("Bash", {"command": command}), "credential file", command)
        for command in ("git status", "pytest tests/test_secret_rotation.py -q", "cat README.md"):
            self.assertIsNone(redaction.withheld_reason("Bash", {"command": command}), command)


class PrBodyAndHookTests(unittest.TestCase):
    LINK = "https://internal-share.diversio.com/session-demo-feature-demo-20261023-a1b2c3.html"

    def test_automatic_pr_lookup_reads_githubs_pull_object(self):
        from unittest import mock
        context = repo_context.RepoContext(root=Path("/tmp"), branch="feature/x", repo_slug="DiversioTeam/demo")
        pull = {"number": 7, "body": "", "base": {"ref": "main"}, "user": {"login": "someone", "type": "User"}}
        with mock.patch.object(check, "open_pr", return_value=(pull, "")):
            self.assertEqual(agent_session._find_pr(context), 7)
        with mock.patch.object(check, "open_pr", return_value=(None, "")):
            self.assertIsNone(agent_session._find_pr(context))

    def test_pr_edit_timeouts_are_a_failed_link(self):
        import contextlib, io, subprocess
        from unittest import mock
        context = repo_context.RepoContext(root=Path("/tmp"), branch="feature/x", repo_slug="DiversioTeam/demo")
        with mock.patch.object(agent_session.subprocess, "run", side_effect=subprocess.TimeoutExpired("gh", 60)), \
                contextlib.redirect_stdout(io.StringIO()) as said:
            self.assertFalse(agent_session._update_pr_body(context, 7, "## Agent sessions"))
        self.assertIn("gh did not answer", said.getvalue())

    def test_publisher_timeouts_are_failures_not_crashes(self):
        import subprocess
        from unittest import mock
        with mock.patch.object(publish, "_cloudflared", return_value="cloudflared"), \
                mock.patch.object(publish.subprocess, "run", side_effect=subprocess.TimeoutExpired("cloudflared", 60)):
            self.assertFalse(publish.delete("session-x.html"))
        with mock.patch.object(publish.shutil, "which", return_value="/usr/local/bin/cloudflared"), \
                mock.patch.object(publish.subprocess, "run", side_effect=subprocess.TimeoutExpired("cloudflared", 600)):
            with self.assertRaises(publish.PublishError):
                publish._cloudflared()

    def test_names_are_flat_and_bounded(self):
        names = publish.build_names("courage", "feature/" + "x" * 300, 2, HEAD)
        for name in names:
            self.assertTrue(name.startswith("session-courage-feature-"))
            self.assertIn(f"-h{HEAD[:12]}-", name)
            self.assertNotIn("/", name)
            self.assertLessEqual(len(name), 180)
            self.assertTrue(name.endswith(".html"))

    def test_body_detection_and_upsert(self):
        self.assertTrue(pr_body.has_transcript(f"text\n{self.LINK}"))
        self.assertTrue(pr_body.has_transcript("No agent session: typo fix in the README by hand"))
        self.assertFalse(pr_body.has_transcript("No agent session:"))
        self.assertFalse(pr_body.has_transcript("https://internal-share.diversio.com/report.html"))
        body = "## Summary\n\nThings.\n\n## Agent sessions\n\n- old\n\n## Testing\n\nRan it.\n"
        updated = pr_body.upsert(body, pr_body.section([("Agent session transcript", self.LINK)]))
        self.assertIn(self.LINK, updated)
        self.assertNotIn("- old", updated)
        self.assertIn("## Testing", updated)
        self.assertEqual(updated.count("## Agent sessions"), 1)

    def test_hook_blocks_pr_bodies_without_a_transcript(self):
        cwd = Path("/nonexistent")
        repo = "--repo DiversioTeam/demo"
        self.assertIsNotNone(check_pr_hook.decide(f"gh pr create {repo} --title T --body 'Summary only'", cwd))
        self.assertIsNotNone(check_pr_hook.decide(f"gh pr create {repo} --fill", cwd))
        self.assertIsNone(check_pr_hook.decide(f"gh pr create {repo} --title T --body 'See {self.LINK}'", cwd))
        self.assertIsNone(check_pr_hook.decide(f"gh pr create {repo} --body \"$(cat <<'EOF'\nNo agent session: manual hotfix\nEOF\n)\"", cwd))
        self.assertIsNone(check_pr_hook.decide(f"gh pr create {repo} --title T --body 'No agent session: manual hotfix'", cwd))
        self.assertIsNone(check_pr_hook.decide(f"gh pr create {repo} --title T --body='No agent session: manual hotfix'", cwd))
        self.assertIsNotNone(check_pr_hook.decide(f"gh pr create {repo} --title 'No agent session: sneaky title' --body x", cwd))
        self.assertIsNone(check_pr_hook.decide(f"gh pr edit 7 {repo} --add-label bug", cwd))
        self.assertIsNotNone(check_pr_hook.decide(f"gh pr edit 7 {repo} --body 'rewritten'", cwd))
        self.assertIsNone(check_pr_hook.decide("gh pr create --repo someone/else --body 'x'", cwd))
        self.assertIsNone(check_pr_hook.decide("git status", cwd))
        self.assertIsNotNone(check_pr_hook.decide("gh api repos/DiversioTeam/demo/pulls -X POST -f title=T -f body=hello", cwd))

    def test_hook_reads_body_files(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "body.md").write_text(f"## Agent sessions\n\n- {self.LINK}\n", encoding="utf-8")
            self.assertIsNone(check_pr_hook.decide("gh pr create --repo DiversioTeam/demo --body-file body.md", Path(directory)))
            Path(directory, "empty.md").write_text("Summary\n", encoding="utf-8")
            self.assertIsNotNone(check_pr_hook.decide("gh pr create --repo DiversioTeam/demo -F empty.md", Path(directory)))


if __name__ == "__main__":
    unittest.main()


class PublishTests(unittest.TestCase):
    """Real upload response parsing with synthetic storage; no Cloudflare or GitHub calls."""

    def setUp(self):
        import hashlib
        from unittest import mock
        self.mock = mock
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.out = Path(self.directory.name)
        self.context = repo_context.RepoContext(root=self.out, branch="feature/x", repo_slug="DiversioTeam/demo", pr=7)
        self.names = ["session-first.html", "session-second.html", "session-third.html"]
        files = []
        for name in self.names:
            content = f"<html>{name}</html>".encode()
            (self.out / name).write_bytes(content)
            files.append({"name": name, "sha256": hashlib.sha256(content).hexdigest()})
        self.manifest = {"files": files, "head": HEAD, "base": "", "commits": []}
        self.remote, self.attempts, self.deleted = {}, [], []
        self.failure = None
        self.delete_succeeds = True
        patches = [
            mock.patch.dict(os.environ, {"AGENT_SESSION_HOME": str(self.out / "state")}),
            mock.patch.object(publish, "_cloudflared", return_value="cloudflared"),
            mock.patch.object(publish.subprocess, "run", side_effect=self.upload_response),
            mock.patch.object(publish, "delete", side_effect=self.delete),
            mock.patch.object(agent_session, "_update_pr_body", return_value=True),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def upload_response(self, command, **kwargs):
        import subprocess
        staged = Path(command[command.index("--form") + 1].removeprefix("file=@").split(";", 1)[0])
        name = staged.name
        self.attempts.append(name)
        if name in self.remote:
            return subprocess.CompletedProcess(command, 0, "HTTP/1.1 100 Continue\r\n\r\nHTTP/2 409\r\n\r\n", "")
        self.remote[name] = staged.read_bytes()
        if name == self.names[1] and self.failure:
            if isinstance(self.failure, Exception):
                raise self.failure
            return self.failure
        return subprocess.CompletedProcess(command, 0, f"HTTP/2 303\r\nlocation: /{name}\r\n\r\n", "")

    def delete(self, name):
        self.deleted.append(name)
        if self.delete_succeeds:
            self.remote.pop(name, None)
        return self.delete_succeeds

    def run_publish(self):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            return agent_session._publish(self.context, self.out, self.manifest)

    def test_repeated_same_manifest_publish_preserves_linked_pages_and_journal(self):
        self.assertEqual(self.run_publish(), 0)
        remote = dict(self.remote)
        journal = store.path().read_bytes()
        manifest = (self.out / agent_session.MANIFEST).read_bytes()
        for _ in range(2):
            self.assertEqual(self.run_publish(), 1)
            self.assertEqual(self.deleted, [])
            self.assertEqual(self.remote, remote)
            self.assertEqual(store.path().read_bytes(), journal)
            self.assertEqual((self.out / agent_session.MANIFEST).read_bytes(), manifest)
        self.assertEqual(self.attempts, [*self.names, self.names[0], self.names[0]])
        agent_session._update_pr_body.assert_called_once()

    def test_multipart_conflict_cleans_only_created_parts_and_never_owes_conflicting_page(self):
        store.record({"repo": self.context.repo_slug, "branch": self.context.branch, "linked": True,
                      "names": [self.names[1]], "links": [publish.link_for(self.names[1])]})
        previous = store.latest(self.context.repo_slug, self.context.branch)
        for succeeds in (True, False):
            with self.subTest(delete_succeeds=succeeds):
                self.remote = {self.names[1]: b"previously linked page"}
                self.delete_succeeds = succeeds
                self.deleted.clear()
                self.assertEqual(self.run_publish(), 1)
                self.assertEqual(self.deleted, [self.names[0]])
                self.assertEqual(self.remote[self.names[1]], b"previously linked page")
                self.assertNotIn(self.names[2], self.attempts)
                self.assertEqual(store.latest(self.context.repo_slug, self.context.branch), previous)
                self.assertEqual(store.cleanup_debt(self.context.repo_slug, self.context.branch),
                                 [] if succeeds else [self.names[0]])
        agent_session._update_pr_body.assert_not_called()

    def test_lost_upload_response_still_cleans_created_and_uncertain_parts(self):
        import subprocess
        for failure in (subprocess.TimeoutExpired("cloudflared", 180),
                        subprocess.CompletedProcess([], 1, "", "connection lost"),
                        subprocess.CompletedProcess([], 0, "HTTP/2 303\r\n", ""),
                        subprocess.CompletedProcess([], 0, "HTTP/2 4099\r\n", "")):
            with self.subTest(failure=failure):
                self.failure = failure
                self.deleted.clear()
                self.assertEqual(self.run_publish(), 1)
                self.assertEqual(self.deleted, self.names[:2])
                self.assertEqual(self.remote, {})
                self.assertFalse(store.path().exists())
        agent_session._update_pr_body.assert_not_called()

    def test_upload_uses_final_http_status_to_identify_conflict(self):
        import subprocess
        for headers, stderr, returncode, rejected in (
                ("HTTP/2 409\r\n", "", 0, True),
                ("", "HTTP/2 409\r\n", 22, True),
                ("HTTP/2 303\r\nlocation: /old.html\r\n\r\nHTTP/2 409\r\n", "", 0, True),
                ("HTTP/2 409\r\n\r\nHTTP/2 500\r\n", "", 0, False),
                ("HTTP/2 4099\r\n", "", 0, False),
                ("", "", 0, False)):
            with self.subTest(headers=headers, stderr=stderr), self.mock.patch.object(
                    publish.subprocess, "run", return_value=subprocess.CompletedProcess([], returncode, headers, stderr)):
                with self.assertRaises(publish.PublishError) as caught:
                    publish.upload(self.out / self.names[0], self.names[0])
                self.assertEqual(isinstance(caught.exception, publish.UploadRejected), rejected)

    def test_pre_upload_rejections_never_delete_the_attempted_name(self):
        self.manifest["files"] = self.manifest["files"][:1]
        self.remote[self.names[0]] = b"existing page"
        with self.mock.patch.object(publish, "MAX_UPLOAD_BYTES", 1):
            self.assertEqual(self.run_publish(), 1)
        with self.mock.patch.object(publish, "_cloudflared", side_effect=publish.PublishError("login failed")):
            self.assertEqual(self.run_publish(), 1)
        self.assertEqual(self.attempts, [])
        self.assertEqual(self.deleted, [])
        self.assertEqual(self.remote[self.names[0]], b"existing page")
        self.assertFalse(store.path().exists())


class ShareTests(unittest.TestCase):
    """share: one command that renders, publishes, records coverage, links the PR, and deletes what it supersedes."""

    def setUp(self):
        import subprocess
        from unittest import mock
        self.mock = mock
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        git = lambda *args: subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)
        git("init", "-q", "-b", "main")
        git("-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-q", "--allow-empty", "-m", "init")
        git("checkout", "-q", "-b", "feature/demo-transcripts")
        git("remote", "add", "origin", "https://github.com/DiversioTeam/demo.git")
        build_store(root / "store", str(self.repo.resolve()))
        self.args = ["--repo", str(self.repo), "--projects-root", str(root / "store"), "--out", str(root / "out")]
        self.env = mock.patch.dict("os.environ", {"AGENT_SESSION_HOME": str(root / "state")})
        self.env.start()
        self.uploads, self.deleted, self.bodies = [], [], []
        patches = [
            mock.patch.object(publish, "upload", side_effect=lambda path, name: self.uploads.append(name) or publish.link_for(name)),
            mock.patch.object(publish, "delete", side_effect=lambda name: self.deleted.append(name) or True),
            mock.patch.object(agent_session, "_find_pr", return_value=7),
            mock.patch.object(agent_session, "_update_pr_body", side_effect=lambda context, pr, section: self.bodies.append((pr, section)) or True),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_first_publish_waits_for_yes_then_republish_is_one_command(self):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args]), 3)
            self.assertEqual(self.uploads, [])
            self.assertEqual(agent_session.main(["share", *self.args, "--yes"]), 0)
        first = list(self.uploads)
        record = store.latest("DiversioTeam/demo", "feature/demo-transcripts")
        self.assertEqual(record["names"], first)
        self.assertEqual(len(record["head"]), 40)
        self.assertIn(f"-h{record['head'][:12]}-", first[0])
        self.assertEqual(self.bodies[0][0], 7)
        self.assertIn(publish.link_for(first[0]), self.bodies[0][1])
        # A later republish needs no --yes and deletes the upload it replaces.
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args]), 0)
        self.assertEqual(self.deleted, first)
        self.assertNotEqual(self.uploads[-1], first[0])

    def test_republish_keeps_dropped_turns_and_a_failed_link_keeps_the_old_page(self):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args, "--yes", "--drop-turn", "1"]), 0)
        first = list(self.uploads)
        preview = Path(self.directory.name) / "out" / first[0]
        self.assertNotIn("Add the transcript feature", preview.read_text(encoding="utf-8"))
        self.assertEqual(len(store.latest("DiversioTeam/demo", "feature/demo-transcripts")["choices"]["drop"]), 1)
        # A plain republish remembers the drop.
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args]), 0)
        second = self.uploads[-1]
        self.assertNotIn("Add the transcript feature", (Path(self.directory.name) / "out" / second).read_text(encoding="utf-8"))
        # When the PR body cannot be updated, the page it still links is kept and share fails.
        with self.mock.patch.object(agent_session, "_update_pr_body", return_value=False), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args]), 1)
        self.assertNotIn(second, self.deleted)
        # --reset-choices brings the turn back.
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args, "--reset-choices"]), 0)
        self.assertIn("Add the transcript feature", (Path(self.directory.name) / "out" / self.uploads[-1]).read_text(encoding="utf-8"))

    def test_a_failed_pr_lookup_publishes_and_deletes_nothing(self):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args, "--yes"]), 0)
        uploads = list(self.uploads)
        with self.mock.patch.object(agent_session, "_find_pr", side_effect=agent_session.PrLookupError("gh could not read the PR")), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(agent_session.main(["share", *self.args]), 1)
        self.assertIn("nothing was published", out.getvalue())
        self.assertEqual(self.uploads, uploads)
        self.assertEqual(self.deleted, [])

    def test_a_failed_link_keeps_cleanup_history_until_a_retry_links(self):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            agent_session.main(["share", *self.args, "--yes"])
        first = self.uploads[-1]
        with self.mock.patch.object(agent_session, "_update_pr_body", return_value=False), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args]), 1)
        second = self.uploads[-1]
        self.assertEqual(self.deleted, [])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args]), 0)
        self.assertEqual(sorted(self.deleted), sorted([first, second]))

    def test_drop_numbers_name_the_turns_the_last_preview_showed(self):
        import contextlib, io
        # Turn 1 holds a subagent (turn 2); dropping it renumbers the next prompt as turn 2 in the preview.
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args, "--yes", "--drop-turn", "1"]), 0)
        preview = (Path(self.directory.name) / "out" / self.uploads[-1]).read_text(encoding="utf-8")
        self.assertRegex(preview, r'href="#turn-2">2</a><span class="who-s developer">Developer</span><span class="first">&lt;script')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args, "--drop-turn", "2"]), 0)
        page = (Path(self.directory.name) / "out" / self.uploads[-1]).read_text(encoding="utf-8")
        self.assertNotIn("please render this safely", page)
        self.assertNotIn("Add the transcript feature", page)
        self.assertIn("Build the renderer", page)
        self.assertEqual(len(store.latest("DiversioTeam/demo", "feature/demo-transcripts")["choices"]["drop"]), 2)

    def test_a_failed_upload_removes_the_parts_it_already_uploaded(self):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args, "--yes"]), 0)
        linked = list(self.uploads)
        attempts = []

        def flaky(path, name):
            attempts.append(name)
            if len(attempts) == 2:
                raise publish.PublishError("upload failed")
            self.uploads.append(name)
            return publish.link_for(name)

        original = render_html.MAX_PART_BYTES
        render_html.MAX_PART_BYTES = 1
        try:
            with self.mock.patch.object(publish, "upload", side_effect=flaky), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(agent_session.main(["share", *self.args]), 1)
            # Removed at once, with the part whose upload failed (it may have landed); the linked page stays.
            self.assertEqual(self.deleted, attempts[:2])
            # A part that cannot be removed now is remembered and removed by the next successful share.
            attempts.clear()
            with self.mock.patch.object(publish, "upload", side_effect=flaky), \
                    self.mock.patch.object(publish, "delete", return_value=False), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(agent_session.main(["share", *self.args]), 1)
            stuck = attempts[:2]
        finally:
            render_html.MAX_PART_BYTES = original
        self.assertNotIn(linked[0], self.deleted)
        # The stuck part outlives a replacement that links while deletion still fails ...
        with self.mock.patch.object(publish, "delete", return_value=False), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args]), 0)
        self.assertEqual(store.cleanup_debt("DiversioTeam/demo", "feature/demo-transcripts"), sorted([*stuck, linked[0]]))
        self.assertTrue(store.latest("DiversioTeam/demo", "feature/demo-transcripts")["linked"])
        # ... and the next share deletes it.
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args]), 0)
        self.assertTrue(set(stuck) <= set(self.deleted))
        self.assertIn(linked[0], self.deleted)
        self.assertEqual(store.cleanup_debt("DiversioTeam/demo", "feature/demo-transcripts"), [])

    def test_a_same_named_branch_in_another_repository_stays_out(self):
        import contextlib, io
        other = Path(self.directory.name) / "store" / "-work-other"
        other.mkdir(parents=True)
        record = lambda kind, content, timestamp: {**_record(kind, content, timestamp), "cwd": "/work/other"}
        (other / "88888888-0000-0000-0000-000000000000.jsonl").write_text("\n".join(json.dumps(item) for item in [
            record("user", "private-" + "other-" + "repo prompt", "2026-10-23T12:00:00Z"),
            record("assistant", [{"type": "text", "text": "Done"}], "2026-10-23T12:00:01Z")]) + "\n")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args, "--yes"]), 0)
            self.assertEqual(agent_session.main(["share", *self.args]), 0)
        out = Path(self.directory.name) / "out"
        for name in self.uploads:
            if (out / name).exists():
                self.assertNotIn("private-other-repo", (out / name).read_text(encoding="utf-8"))
        self.assertIn("Add the transcript feature", (out / self.uploads[-1]).read_text(encoding="utf-8"))
        # Naming the session still brings it in.
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args, "--session", "88888888-0000-0000-0000-000000000000"]), 0)
        self.assertIn("private-other-repo", (out / self.uploads[-1]).read_text(encoding="utf-8"))

    def test_drop_numbers_follow_unpublished_previews_too(self):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            # Preview only (a first publish waits for --yes): turn 1 and its subagent go, the next prompt shows as 2.
            self.assertEqual(agent_session.main(["share", *self.args, "--drop-turn", "1"]), 3)
            self.assertEqual(agent_session.main(["share", *self.args, "--yes", "--drop-turn", "2"]), 0)
        page = (Path(self.directory.name) / "out" / self.uploads[-1]).read_text(encoding="utf-8")
        self.assertNotIn("Add the transcript feature", page)
        self.assertNotIn("please render this safely", page)
        self.assertIn("Build the renderer", page)

    def test_workers_are_judged_by_their_own_repository(self):
        import argparse
        root = Path(self.directory.name)
        here = str(self.repo.resolve())
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as empty:
            def write(path, records):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
            at = lambda cwd, branch, kind, content, timestamp, **extra: {**_record(kind, content, timestamp, branch=branch, **extra), "cwd": cwd}
            # A lead in this repository with a teammate working in another repository on a same-named branch.
            lead = Path(directory) / "-here" / "aaaaaaaa-0000-0000-0000-000000000000.jsonl"
            write(lead, [at(here, "feature/demo-transcripts", "user", "Lead work here", "2026-10-23T10:00:00Z", origin={"kind": "human"})])
            folder = lead.with_suffix("") / "subagents"
            write(folder / "agent-amate-x.jsonl", [at("/work/other-repository", "feature/demo-transcripts", "user",
                                                      '<teammate-message teammate_id="team-lead">private-' + 'other-' + 'teammate</teammate-message>', "2026-10-23T10:01:00Z")])
            (folder / "agent-amate-x.meta.json").write_text(json.dumps({"name": "elsewhere", "taskKind": "in_process_teammate"}))
            # A lead elsewhere on main, with no PR marker, whose worker ran here on the PR branch.
            outside = Path(directory) / "-elsewhere" / "bbbbbbbb-0000-0000-0000-000000000000.jsonl"
            write(outside, [at("/work/coordinator", "main", "user", "Coordinate", "2026-10-23T11:00:00Z", origin={"kind": "human"}),
                            at("/work/coordinator", "main", "assistant", [{"type": "tool_use", "id": "w1", "name": "Agent", "input": {"description": "worker", "prompt": "go"}}], "2026-10-23T11:00:01Z")])
            sub = outside.with_suffix("") / "subagents"
            write(sub / "agent-worker.jsonl", [at(here, "feature/demo-transcripts", "user", "go", "2026-10-23T11:00:02Z"),
                                               at(here, "feature/demo-transcripts", "assistant", [{"type": "text", "text": "Worker did it here"}], "2026-10-23T11:00:03Z")])
            (sub / "agent-worker.meta.json").write_text(json.dumps({"toolUseId": "w1", "description": "worker"}))
            context = agent_session._context(agent_session.parser().parse_args(["find", "--repo", str(self.repo)]))
            args = argparse.Namespace(projects_root=directory, pi_root=empty, codex_root=empty, session=None, exclude=None, whole=None)
            units = agent_session.load_units(context, args)
            pages, _ = render_html.build_pages(context, units, redaction.Redactor(), "2027-10-23", "now")
        page = "".join(pages)
        self.assertIn("Lead work here", page)
        self.assertNotIn("private-other-teammate", page)
        self.assertIn("Worker did it here", page)
        self.assertIn("Coordinate", page)

    def test_drop_numbers_survive_the_session_growing_after_the_preview(self):
        import contextlib, io, re
        out = Path(self.directory.name) / "out"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args]), 3)
        preview = next(out.glob("session-*.html")).read_text(encoding="utf-8")
        shown = int(re.search(r'href="#turn-(\d+)">\d+</a><span class="who-s teammate">[^<]*</span><span class="first">Build the renderer', preview).group(1))
        main = next((Path(self.directory.name) / "store").glob("*/11111111-*.jsonl"))
        with main.open("a") as handle:
            handle.write(json.dumps({**_record("user", "Looks good, publish it", "2026-10-23T10:02:30Z", origin={"kind": "human"}),
                                     "cwd": str(self.repo.resolve())}) + "\n")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args, "--yes", "--drop-turn", str(shown)]), 0)
        page = (out / self.uploads[-1]).read_text(encoding="utf-8")
        self.assertNotIn("Build the renderer", page)
        self.assertIn("Looks good, publish it", page)
        with contextlib.redirect_stdout(io.StringIO()) as said:
            self.assertEqual(agent_session.main(["share", *self.args, "--drop-turn", "99"]), 1)
        self.assertIn("Turn 99 is not in the last preview", said.getvalue())

    def test_an_interrupted_pr_edit_leaves_its_upload_for_cleanup(self):
        import contextlib, io, subprocess
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args, "--yes"]), 0)
        with self.mock.patch.object(agent_session, "_update_pr_body", side_effect=subprocess.TimeoutExpired("gh", 60)), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(subprocess.TimeoutExpired):
            agent_session.main(["share", *self.args])
        orphan = self.uploads[-1]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["share", *self.args]), 0)
        self.assertIn(orphan, self.deleted)

    def test_declare_none_records_and_links(self):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["declare-none", "hand-edited a config value", "--repo", str(self.repo)]), 0)
        self.assertEqual(store.latest("DiversioTeam/demo", "feature/demo-transcripts")["none"], "hand-edited a config value")
        self.assertIn("No agent session: hand-edited a config value", self.bodies[0][1])
