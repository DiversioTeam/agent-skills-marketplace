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
codex_sessions = importlib.import_module("codex_sessions")
pi_sessions = importlib.import_module("pi_sessions")
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
def build_pi_store(root: Path, cwd: str) -> Path:
    folder = root / ("--" + cwd.strip("/").replace("/", "-") + "--")
    folder.mkdir(parents=True)
    usage = {"input": 100, "output": 20, "cacheRead": 50, "cacheWrite": 0, "totalTokens": 170}

    def message(entry_id, parent, role, content, **extra):
        return {"type": "message", "id": entry_id, "parentId": parent, "timestamp": f"2026-10-23T10:00:{entry_id[-2:]}Z",
                "message": {"role": role, "content": content, **extra}}
    entries = [
        {"type": "session", "version": 3, "id": "01pi-session", "timestamp": "2026-10-23T10:00:00Z", "cwd": cwd},
        {"type": "model_change", "id": "aa000001", "parentId": None, "timestamp": "2026-10-23T10:00:01Z", "provider": "openai-codex", "modelId": "gpt-5.5"},
        message("aa000002", "aa000001", "user", [{"type": "text", "text": '<skill name="review" location="/x/SKILL.md">\nlong skill body\n</skill>\nReview the branch'}]),
        message("aa000003", "aa000002", "assistant", [{"type": "thinking", "thinking": "", "thinkingSignature": "x"},
                                                    {"type": "toolCall", "id": "c1", "name": "bash", "arguments": {"command": "psql -h db.prod.internal -c 'select 1'"}}],
                model="gpt-5.5", usage=usage),
        message("aa000004", "aa000003", "toolResult", [{"type": "text", "text": f"secret row {CUSTOMER_EMAIL}"}], toolCallId="c1", toolName="bash", isError=False,
                details={"truncation": {"truncated": True}, "fullOutputPath": "/tmp/pi-bash-abc123.log"}),
        message("aa000005", "aa000004", "assistant", [{"type": "text", "text": f"Abandoned idea with {GITHUB_TOKEN}"}], model="gpt-5.5", usage=usage),
        {"type": "branch_summary", "id": "aa000006", "parentId": "aa000004", "timestamp": "2026-10-23T10:00:06Z", "fromId": "aa000005", "summary": "x"},
        message("aa000007", "aa000006", "user", [{"type": "text", "text": "Try the other approach"}]),
        message("aa000008", "aa000007", "assistant", [{"type": "toolCall", "id": "c2", "name": "read", "arguments": {"path": "README.md"}},
                                                    {"type": "toolCall", "id": "c3", "name": "read", "arguments": {"path": "/tmp/pi-bash-abc123.log"}}], model="gpt-5.5", usage=usage),
        message("aa000009", "aa000008", "toolResult", [{"type": "text", "text": "# Demo"}], toolCallId="c2", toolName="read", isError=False),
        message("aa000011", "aa000009", "toolResult", [{"type": "text", "text": "private-" + "overflow-" + "row"}], toolCallId="c3", toolName="read", isError=False),
        message("aa000010", "aa000011", "assistant", [{"type": "text", "text": "Done on the other approach."}], model="gpt-5.5", usage=usage),
    ]
    path = folder / "2026-10-23T10-00-00-000Z_01pi-session.jsonl"
    path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8")
    return path


class PiTests(unittest.TestCase):
    def test_pi_sessions_follow_the_active_branch_and_render_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            cwd = "/work/demo-feature"
            path = build_pi_store(Path(directory), cwd)
            context = demo_context()
            context.worktree_branches = {cwd: "feature/demo-transcripts"}
            self.assertEqual(pi_sessions.find_sessions(context, Path(directory)), [path])
            nested = demo_context()
            nested.worktree_branches = {"/work": "feature/demo-transcripts"}
            self.assertEqual(pi_sessions.find_sessions(nested, Path(directory)), [path])
            sibling = demo_context()
            sibling.worktree_branches = {"/work/demo": "feature/demo-transcripts"}
            self.assertEqual(pi_sessions.find_sessions(sibling, Path(directory)), [])
            elsewhere = demo_context()
            elsewhere.worktree_branches = {cwd: "other"}
            self.assertEqual(pi_sessions.find_sessions(elsewhere, Path(directory)), [])
            # A worktree nested inside one on the branch is owned by its own (other) branch.
            inner = demo_context()
            inner.worktree_branches = {"/work": "feature/demo-transcripts", cwd: "feature/other"}
            self.assertEqual(pi_sessions.find_sessions(inner, Path(directory)), [])
            self.assertFalse(inner.in_worktree_on_branch(cwd + "/backend"))
            self.assertTrue(inner.in_worktree_on_branch("/work/elsewhere"))
            unit = pi_sessions.parse_session(path, context)
        self.assertEqual(unit.harness, "Pi")
        self.assertEqual(unit.models, ["gpt-5.5"])
        self.assertEqual([turn.text for turn in unit.turns], ["/skill:review Review the branch", "Try the other approach"])
        self.assertEqual(unit.tokens.output, 60)
        self.assertEqual([item.tool.withheld for turn in unit.turns for item in turn.items if item.tool],
                         ["prod or staging data access", None, "prod or staging data access"])
        self.assertEqual(unit.notes, ["1 entry on abandoned branches of the session tree is not shown."])
        pages, _ = render_html.build_pages(context, [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertNotIn(GITHUB_TOKEN, pages[0])
        self.assertNotIn(CUSTOMER_EMAIL, pages[0])
        self.assertNotIn("long skill body", pages[0])
        self.assertNotIn("private-overflow-row", pages[0])
        self.assertIn("Done on the other approach.", pages[0])
        self.assertIn("Agents</dt><dd>Pi", pages[0])


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
class PiSlicingTests(unittest.TestCase):
    def test_pi_lead_keeps_only_the_subagent_for_this_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "--elsewhere--"
            artifacts = folder / "subagent-artifacts"
            artifacts.mkdir(parents=True)
            message = lambda entry_id, parent, role, content, **extra: {"type": "message", "id": entry_id, "parentId": parent,
                                                                       "timestamp": "2026-10-23T10:00:00Z", "message": {"role": role, "content": content, **extra}}
            entries = [
                {"type": "session", "version": 3, "id": "lead-1", "timestamp": "2026-10-23T10:00:00Z", "cwd": "/elsewhere"},
                message("e1", None, "user", "Do the transcripts work and the unrelated cleanup"),
                message("e2", "e1", "assistant", [{"type": "toolCall", "id": "c1", "name": "subagent", "arguments": {"agent": "delegate", "task": "transcripts"}}]),
                message("e3", "e2", "toolResult", [{"type": "text", "text": "run run-good finished"}], toolCallId="c1", toolName="subagent"),
                message("e4", "e3", "assistant", [{"type": "toolCall", "id": "c2", "name": "subagent", "arguments": {"agent": "delegate", "task": "cleanup secret-cleanup"}}]),
                message("e5", "e4", "toolResult", [{"type": "text", "text": "run run-other finished"}], toolCallId="c2", toolName="subagent"),
                message("e6", "e5", "user", "Unrelated question about lunch"),
            ]
            lead = folder / "2026-10-23T10-00-00-000Z_lead-1.jsonl"
            lead.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8")
            for run_id, text in (("run-good", "Working on feature/demo-transcripts"), ("run-other", "Cleaning up secret-cleanup")):
                transcript = artifacts / f"{run_id}_delegate_transcript.jsonl"
                transcript.write_text(json.dumps({"recordType": "message", "cwd": "/tmp/demo-repo", "timestamp": "2026-10-23T10:01:00Z",
                                                  "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}) + "\n")
                (artifacts / f"{run_id}_delegate_meta.json").write_text(json.dumps({"runId": run_id, "parentSessionId": "lead-1", "agent": "delegate",
                                                                                    "transcriptPath": str(transcript)}))
            self.assertEqual(pi_sessions.find_sessions(demo_context(), Path(directory)), [lead])
            unit = pi_sessions.load_session(lead, demo_context())
        slicing.slice_to_work(unit, demo_context(), whole=False)
        self.assertEqual([turn.text for turn in unit.turns], ["Do the transcripts work and the unrelated cleanup"])
        calls = [item.tool for turn in unit.turns for item in turn.items if item.tool]
        self.assertEqual([call.links_to for call in calls], ["run-good"])
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("Working on feature/demo-transcripts", pages[0])
        self.assertNotIn("secret-cleanup", pages[0])
        self.assertNotIn("lunch", pages[0])
def _codex(record_type, payload, ordinal, timestamp="2026-10-23T11:00:00Z"):
    return {"timestamp": timestamp, "ordinal": ordinal, "type": record_type, "payload": payload}


def build_codex_store(root: Path) -> Path:
    day = root / "2026" / "10" / "23"
    day.mkdir(parents=True)
    git = {"branch": "feature/demo-transcripts", "commit_hash": HEAD, "repository_url": "git@github.com:DiversioTeam/demo.git"}
    main = [
        _codex("session_meta", {"id": "thread-main", "cwd": "/work/demo", "git": git, "source": "cli"}, 0),
        _codex("turn_context", {"model": "gpt-5.6-sol"}, 1),
        _codex("response_item", {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "system rules"}]}, 2),
        _codex("response_item", {"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "<environment_context>\n<cwd>/work/demo</cwd>\n</environment_context>"},
            {"type": "input_text", "text": "Fix the flaky test"}]}, 3),
        _codex("response_item", {"type": "reasoning", "encrypted_content": "gAAAA-private"}, 4),
        _codex("response_item", {"type": "function_call", "name": "exec_command", "call_id": "c1",
                                 "arguments": json.dumps({"cmd": "psql -h db.staging.internal -c 'select * from users'"})}, 5),
        _codex("response_item", {"type": "function_call_output", "call_id": "c1", "output": f"row {CUSTOMER_EMAIL}"}, 6),
        _codex("response_item", {"type": "custom_tool_call", "name": "apply_patch", "call_id": "c2", "input": "*** Begin Patch\n*** Update File: /work/demo/.env\n+TOKEN=x\n*** End Patch"}, 7),
        _codex("response_item", {"type": "custom_tool_call_output", "call_id": "c2", "output": json.dumps({"output": "Success."})}, 8),
        _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "c4",
                                 "input": 'const r = await tools.exec_command({cmd:"ssh production \\"tail app.log\\"","workdir":"/work/demo"}); text(r.output);'}, 8),
        _codex("response_item", {"type": "custom_tool_call_output", "call_id": "c4", "output": "private-" + "prod-" + "log"}, 8),
        _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "c5",
                                 "input": 'const r = await tools.exec_command({cmd:"git status --short"}); text(r.output);'}, 8),
        _codex("response_item", {"type": "custom_tool_call_output", "call_id": "c5", "output": "M app.py"}, 8),
        _codex("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "<task>Also tidy the fixture</task>"}]}, 9),
        _codex("response_item", {"type": "function_call", "name": "exec_command", "call_id": "c3", "arguments": json.dumps({"cmd": "pytest -q"})}, 9),
        _codex("response_item", {"type": "function_call_output", "call_id": "c3", "output": json.dumps({"output": "3 passed"})}, 10),
        _codex("response_item", {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": f"Fixed. Token was {GITHUB_TOKEN}"}]}, 11),
        _codex("event_msg", {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 1000, "cached_input_tokens": 400, "output_tokens": 50}}}, 12),
    ]
    sub = [
        _codex("session_meta", {"id": "thread-sub", "parent_thread_id": "thread-main", "agent_nickname": "Curie", "agent_role": "explorer",
                                "subagent_history_start_ordinal": 2, "cwd": "/work/demo", "git": git}, 0),
        _codex("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "copied parent history"}]}, 1),
        _codex("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Find the flaky test"}]}, 2),
        _codex("response_item", {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "It is test_retry."}]}, 3),
    ]
    other = [_codex("session_meta", {"id": "thread-other", "cwd": "/elsewhere", "git": {**git, "branch": "main"}}, 0)]
    for name, records in (("rollout-2026-10-23T11-00-00-thread-main", main), ("rollout-2026-10-23T11-05-00-thread-sub", sub),
                          ("rollout-2026-10-23T11-06-00-thread-other", other)):
        (day / f"{name}.jsonl").write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return day / "rollout-2026-10-23T11-00-00-thread-main.jsonl"


class CodexTests(unittest.TestCase):
    def test_codex_rollouts_by_git_branch_with_subagents(self):
        with tempfile.TemporaryDirectory() as directory:
            main = build_codex_store(Path(directory))
            self.assertEqual(codex_sessions.find_sessions(demo_context(), Path(directory)), [main])
            unit = codex_sessions.load_session(main, demo_context(), Path(directory))
        self.assertEqual(unit.harness, "Codex")
        self.assertEqual(unit.models, ["gpt-5.6-sol"])
        self.assertEqual([turn.text for turn in unit.turns], ["Fix the flaky test", "<task>Also tidy the fixture</task>"])
        self.assertEqual((unit.tokens.input, unit.tokens.cache_read, unit.tokens.output), (600, 400, 50))
        tools = [item.tool for turn in unit.turns for item in turn.items if item.tool]
        self.assertEqual([(tool.name, tool.withheld) for tool in tools],
                         [("exec_command", "prod or staging data access"), ("apply_patch", "credential file"),
                          ("exec", "prod or staging data access"), ("exec", None), ("exec_command", None)])
        self.assertEqual(tools[4].output, "3 passed")
        self.assertEqual([mate.title for mate in unit.teammates], ["Codex subagent: Curie (explorer)"])
        self.assertEqual([turn.text for turn in unit.teammates[0].turns], ["Find the flaky test"])
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        for leaked in (GITHUB_TOKEN, CUSTOMER_EMAIL, "gAAAA-private", "TOKEN=x", "environment_context", "copied parent history", "private-prod-log"):
            self.assertNotIn(leaked, pages[0])
        self.assertIn("3 passed", pages[0])

    def test_hook_reads_codex_commands_and_install_is_idempotent(self):
        import contextlib, io, subprocess
        hook = Path(check_pr_hook.__file__)
        for tool_input in ({"cmd": "gh pr create --repo DiversioTeam/demo --body x"}, {"command": ["gh", "pr", "create", "--repo", "DiversioTeam/demo", "--body", "x"]}):
            completed = subprocess.run([sys.executable, str(hook)], input=json.dumps({"tool_input": tool_input, "cwd": "/tmp"}), capture_output=True, text=True)
            self.assertEqual(completed.returncode, 2, tool_input)
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "hooks.json").write_text(json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]}}))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(agent_session.main(["install-codex-hook", "--codex-home", directory, "--bin-dir", f"{directory}/bin"]), 0)
                self.assertEqual(agent_session.main(["install-codex-hook", "--codex-home", directory, "--bin-dir", f"{directory}/bin"]), 0)
            config = json.loads(Path(directory, "hooks.json").read_text())
            self.assertTrue(os.access(Path(directory, "bin", "agent-session"), os.X_OK), "a fresh install gets the command")
            self.assertEqual(len(config["hooks"]["SessionStart"]), 1)
        self.assertEqual(len(config["hooks"]["PreToolUse"]), 1)
        self.assertIn("check_pr_hook.py", config["hooks"]["PreToolUse"][0]["hooks"][0]["command"])
        self.assertIn("Stop", config["hooks"])


class PiChildFindingsTests(unittest.TestCase):
    """Regressions for little-person's #117 findings on pi-subagents children."""

    def store(self, directory, lead_cwd, children, tasks=("a", "b"), result="run run-par finished; run run-unrelated finished", details=None):
        folder = Path(directory) / "--lead--"
        artifacts = folder / "subagent-artifacts"
        artifacts.mkdir(parents=True)
        message = lambda entry_id, parent, role, content, **extra: {"type": "message", "id": entry_id, "parentId": parent,
                                                                   "timestamp": "2026-10-23T10:00:00Z", "message": {"role": role, "content": content, **extra}}
        entries = [{"type": "session", "version": 3, "id": "lead-2", "timestamp": "2026-10-23T10:00:00Z", "cwd": lead_cwd},
                   message("e1", None, "user", "Run the workers"),
                   message("e2", "e1", "assistant", [{"type": "toolCall", "id": "c1", "name": "subagent", "arguments": {"tasks": list(tasks)}}]),
                   message("e3", "e2", "toolResult", [{"type": "text", "text": result}], toolCallId="c1", toolName="subagent",
                           **({"details": details} if details else {}))]
        lead = folder / "2026-10-23T10-00-00-000Z_lead-2.jsonl"
        lead.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")
        for name, run_id, cwd, messages in children:
            transcript = artifacts / f"{name}_transcript.jsonl"
            transcript.write_text("\n".join(json.dumps({"recordType": "message", "cwd": cwd, "timestamp": "2026-10-23T10:01:00Z", "message": item})
                                            for item in messages) + "\n")
            index = int(name.rsplit("_", 1)[1]) if name.rsplit("_", 1)[1].isdigit() else None
            (artifacts / f"{name}_meta.json").write_text(json.dumps({"runId": run_id, "parentSessionId": "lead-2", "agent": name.split("_")[1],
                                                                     "transcriptPath": str(transcript), **({"index": index} if index is not None else {})}))
        return lead

    def test_a_read_naming_a_known_and_an_unknown_overflow_file_is_withheld(self):
        sentinel = "private-" + "overflow-" + "mixed"
        child = [
            {"role": "user", "content": [{"type": "text", "text": "Check prod for feature/demo-transcripts"}]},
            {"role": "assistant", "content": [{"type": "toolCall", "id": "k1", "name": "bash", "arguments": {"command": "ls -R"}}]},
            {"role": "toolResult", "toolCallId": "k1", "toolName": "bash", "content": [{"type": "text", "text": "a\n[Output truncated. Full output: /tmp/pi-bash-safe.log]"}]},
            {"role": "assistant", "content": [{"type": "toolCall", "id": "k2", "name": "bash", "arguments": {"command": "psql -h db.prod.internal -c 'select 1'"}}]},
            {"role": "toolResult", "toolCallId": "k2", "toolName": "bash", "content": [{"type": "text", "text": "row\n" * 10000}]},
            {"role": "assistant", "content": [{"type": "toolCall", "id": "k3", "name": "bash", "arguments": {"command": "tail /tmp/pi-bash-safe.log /tmp/pi-bash-9f3a.log"}}]},
            {"role": "toolResult", "toolCallId": "k3", "toolName": "bash", "content": [{"type": "text", "text": sentinel}]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            lead = self.store(directory, "/tmp/demo-repo", [("run-par_delegate", "run-par", "/tmp/demo-repo", child)])
            unit = pi_sessions.load_session(lead, demo_context())
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertNotIn(sentinel, pages[0])

    def test_a_task_naming_the_work_keeps_only_its_child_and_its_task(self):
        say = lambda text: [{"role": "assistant", "content": [{"type": "text", "text": text}]}]
        tasks = [{"agent": "worker", "task": "Implement feature/demo-transcripts"}, {"agent": "worker", "task": "private-" + "task-" + "sibling"}]
        with tempfile.TemporaryDirectory() as directory:
            lead = self.store(directory, "/tmp/demo-repo", [
                ("run-par_worker_0", "run-par", "/tmp/demo-repo", say("Did the work")),
                ("run-par_worker_1", "run-par", "/tmp/demo-repo", say("private-" + "note-" + "sibling")),
            ], tasks=tasks, result="run run-par: worker 0 did the work; worker 1 found private-" + "result-" + "sibling")
            unit = pi_sessions.load_session(lead, demo_context())
        slicing.slice_to_work(unit, demo_context(), whole=False)
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("Did the work", pages[0])
        self.assertIn("Implement feature/demo-transcripts", pages[0])
        for sentinel in ("note-sibling", "task-sibling", "result-sibling"):
            self.assertNotIn("private-" + sentinel, pages[0])

    def test_a_filtered_siblings_task_prompt_does_not_render(self):
        say = lambda text: [{"role": "assistant", "content": [{"type": "text", "text": text}]}]
        tasks = [{"agent": "worker", "task": "Build the renderer"}, {"agent": "worker", "task": "private-" + "task-" + "other"}]
        with tempfile.TemporaryDirectory() as directory:
            lead = self.store(directory, "/tmp/demo-repo", [
                ("run-par_worker_0", "run-par", "/tmp/demo-repo", say("Did feature/demo-transcripts")),
                ("run-par_worker_1", "run-par", "/tmp/demo-repo", say("Other work")),
            ], tasks=tasks)
            unit = pi_sessions.load_session(lead, demo_context())
        slicing.slice_to_work(unit, demo_context(), whole=False)
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("Build the renderer", pages[0])
        self.assertNotIn("private-task-other", pages[0])
        self.assertNotIn("Other work", pages[0])

    def test_pi_edits_of_credential_files_hide_their_text(self):
        child = [
            {"role": "user", "content": [{"type": "text", "text": "Rotate the key for feature/demo-transcripts"}]},
            {"role": "assistant", "content": [{"type": "toolCall", "id": "k1", "name": "edit", "arguments": {
                "path": "/work/demo/.env", "oldText": "API_KEY=private-" + "old-" + "cred", "newText": "API_KEY=private-" + "new-" + "cred"}}]},
            {"role": "toolResult", "toolCallId": "k1", "toolName": "edit", "content": [{"type": "text", "text": "Edited"}]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            lead = self.store(directory, "/tmp/demo-repo", [("run-par_delegate", "run-par", "/tmp/demo-repo", child)])
            unit = pi_sessions.load_session(lead, demo_context())
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("/work/demo/.env", pages[0])
        self.assertNotIn("private-old-cred", pages[0])
        self.assertNotIn("private-new-cred", pages[0])

    def test_a_turn_naming_the_work_drops_its_spawns_for_other_work(self):
        say = lambda text: [{"role": "assistant", "content": [{"type": "text", "text": text}]}]
        with tempfile.TemporaryDirectory() as directory:
            lead = self.store(directory, "/tmp/demo-repo", [
                ("run-a_worker_0", "run-a", "/tmp/demo-repo", say("Did the work")),
                ("run-b_worker_0", "run-b", "/tmp/demo-repo", say("private-" + "other-" + "child")),
            ])
            message = lambda entry_id, parent, role, content, **extra: {"type": "message", "id": entry_id, "parentId": parent,
                                                                       "timestamp": "2026-10-23T10:00:00Z", "message": {"role": role, "content": content, **extra}}
            entries = [{"type": "session", "version": 3, "id": "lead-2", "timestamp": "2026-10-23T10:00:00Z", "cwd": "/tmp/demo-repo"},
                       message("e1", None, "user", "Run both"),
                       message("e2", "e1", "assistant", [
                           {"type": "toolCall", "id": "c1", "name": "subagent", "arguments": {"tasks": [{"agent": "worker", "task": "Implement feature/demo-transcripts"}]}},
                           {"type": "toolCall", "id": "c2", "name": "subagent", "arguments": {"tasks": [{"agent": "worker", "task": "private-" + "other-" + "task"}]}}]),
                       message("e3", "e2", "toolResult", [{"type": "text", "text": "done"}], toolCallId="c1", toolName="subagent", details={"runId": "run-a"}),
                       message("e4", "e3", "toolResult", [{"type": "text", "text": "private-" + "other-" + "result"}], toolCallId="c2", toolName="subagent", details={"runId": "run-b"})]
            lead.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")
            unit = pi_sessions.load_session(lead, demo_context())
        slicing.slice_to_work(unit, demo_context(), whole=False)
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("Did the work", pages[0])
        self.assertIn("Implement feature/demo-transcripts", pages[0])
        for sentinel in ("other-child", "other-task", "other-result"):
            self.assertNotIn("private-" + sentinel, pages[0])

    def test_children_spawned_on_an_abandoned_branch_are_not_shown(self):
        say = lambda text: [{"role": "assistant", "content": [{"type": "text", "text": text}]}]
        with tempfile.TemporaryDirectory() as directory:
            lead = self.store(directory, "/tmp/demo-repo", [("run-par_delegate", "run-par", "/tmp/demo-repo", say("private-" + "abandoned-" + "child on feature/demo-transcripts"))],
                              result="Done.", details={"runId": "run-par"})
            # The developer went back to e1 and continued differently: e2 and e3 (the spawn and its result) are abandoned.
            with lead.open("a") as handle:
                handle.write(json.dumps({"type": "message", "id": "e4", "parentId": "e1", "timestamp": "2026-10-23T10:05:00Z",
                                         "message": {"role": "user", "content": "Continue on feature/demo-transcripts another way"}}) + "\n")
                # An active listing names the abandoned run without having started it.
                for entry_id, parent, message in (
                        ("e5", "e4", {"role": "assistant", "content": [{"type": "toolCall", "id": "l1", "name": "bash", "arguments": {"command": "ls subagent-artifacts"}}]}),
                        ("e6", "e5", {"role": "toolResult", "toolCallId": "l1", "toolName": "bash",
                                      "content": [{"type": "text", "text": "run-par_delegate_meta.json\nrun-par_delegate_transcript.jsonl"}]}),
                        ("e7", "e6", {"role": "assistant", "content": [{"type": "toolCall", "id": "s1", "name": "subagent", "arguments": {"action": "status", "runId": "run-par"}}]}),
                        # An active spawn whose task names the abandoned run, but whose result says it started its own.
                        ("e8", "e7", {"role": "assistant", "content": [{"type": "toolCall", "id": "c2", "name": "subagent",
                                                                        "arguments": {"agent": "delegate", "task": "Do the artifact files for run-par exist?"}}]}),
                        ("e9", "e8", {"role": "toolResult", "toolCallId": "c2", "toolName": "subagent", "content": [{"type": "text", "text": "Artifacts exist."}],
                                      "details": {"runId": "run-new"}})):
                    handle.write(json.dumps({"type": "message", "id": entry_id, "parentId": parent, "timestamp": "2026-10-23T10:06:00Z", "message": message}) + "\n")
            unit = pi_sessions.load_session(lead, demo_context())
        self.assertEqual(unit.teammates, [])
        slicing.slice_to_work(unit, demo_context(), whole=False)
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("Continue on feature/demo-transcripts another way", "".join(pages))
        self.assertIn("Artifacts exist.", "".join(pages))
        for page in pages:
            self.assertNotIn("private-abandoned-child", page)

    def test_a_selected_foreign_session_keeps_only_its_pr_turns(self):
        import argparse
        pr_url = "https://github.com/DiversioTeam/demo/pull/7"

        def pi_store(folder, cwd):
            path = Path(folder) / "--s--" / "2026-10-23T10-00-00-000Z_s.jsonl"
            path.parent.mkdir(parents=True)
            message = lambda entry_id, parent, role, content: {"type": "message", "id": entry_id, "parentId": parent,
                                                               "timestamp": "2026-10-23T10:00:00Z", "message": {"role": role, "content": content}}
            entries = [{"type": "session", "version": 3, "id": "s", "timestamp": "2026-10-23T10:00:00Z", "cwd": cwd},
                       message("e1", None, "user", f"Review {pr_url}"),
                       message("e2", "e1", "user", "private-" + "later-" + "prompt about other work"),
                       message("e3", "e2", "assistant", [{"type": "text", "text": "private-" + "later-" + "reply on feature/demo-transcripts"}])]
            path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")

        def claude_store(folder, cwd):
            path = Path(folder) / "-s" / "cccccccc-0000-0000-0000-000000000000.jsonl"
            path.parent.mkdir(parents=True)
            records = [_record("user", f"Review {pr_url}", "2026-10-23T10:00:00Z", branch="main", origin={"kind": "human"}),
                       _record("user", "private-" + "later-" + "prompt about other work", "2026-10-23T10:01:00Z", branch="main", origin={"kind": "human"}),
                       _record("assistant", [{"type": "text", "text": "private-" + "later-" + "reply on feature/demo-transcripts"}], "2026-10-23T10:01:05Z", branch="main")]
            path.write_text("\n".join(json.dumps({**record, "cwd": cwd}) for record in records) + "\n")

        for harness, store in (("pi", pi_store), ("claude", claude_store)):
            for cwd, here in (("/work/other-repository", False), ("/tmp/demo-repo", True)):
                with self.subTest(harness=harness, cwd=cwd), tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as empty:
                    store(directory, cwd)
                    roots = {"projects_root": directory if harness == "claude" else empty, "pi_root": directory if harness == "pi" else empty}
                    units = agent_session.load_units(demo_context(), argparse.Namespace(**roots, session=None, exclude=None, whole=None))
                    page = "".join(render_html.build_pages(demo_context(), units, redaction.Redactor(), "2027-10-23", "now")[0])
                    self.assertIn("Review " + pr_url, page)
                    # In this repository the branch ties the later turn to the work; elsewhere it does not.
                    for sentinel in ("private-later-prompt", "private-later-reply"):
                        (self.assertIn if here else self.assertNotIn)(sentinel, page)

    def test_sessions_in_another_repository_need_the_pr_not_just_a_shared_branch_name(self):
        import argparse
        pr_url = "https://github.com/DiversioTeam/demo/pull/7"
        say = lambda text: [{"role": "assistant", "content": [{"type": "text", "text": text}]}]

        def native(folder, session_id, cwd, text):
            path = Path(folder) / f"--{session_id}--" / f"2026-10-23T10-00-00-000Z_{session_id}.jsonl"
            path.parent.mkdir(parents=True)
            entries = [{"type": "session", "version": 3, "id": session_id, "timestamp": "2026-10-23T10:00:00Z", "cwd": cwd},
                       {"type": "message", "id": "e1", "parentId": None, "timestamp": "2026-10-23T10:00:00Z", "message": {"role": "user", "content": text}}]
            path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n")
            return path

        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as empty:
            foreign = native(directory, "foreign", "/work/other-repository", "Work on feature/demo-transcripts: private-" + "foreign-" + "native")
            linked = native(directory, "linked", "/work/other-repository", f"Review {pr_url}")
            here = native(directory, "here", "/tmp/demo-repo/backend", "Work on feature/demo-transcripts here")
            # A lead elsewhere whose only child also ran elsewhere and names just the branch.
            lead = self.store(directory, "/work/coordinator", [("run-far_delegate", "run-far", "/work/other-repository",
                                                                say("private-" + "foreign-" + "child on feature/demo-transcripts"))],
                              result="Done.", details={"runId": "run-far"})
            self.assertEqual(sorted(path.name for path in pi_sessions.find_sessions(demo_context(), Path(directory))), sorted([linked.name, here.name]))
            self.assertEqual(pi_sessions.parse_session(foreign, demo_context()).evidence, [])
            args = argparse.Namespace(projects_root=empty, pi_root=directory, session=None, exclude=None, whole=None)
            units = agent_session.load_units(demo_context(), args)
        page = "".join(render_html.build_pages(demo_context(), units, redaction.Redactor(), "2027-10-23", "now")[0])
        self.assertIn("Work on feature/demo-transcripts here", page)
        self.assertIn("Review " + pr_url, page)
        self.assertNotIn("private-foreign-native", page)
        self.assertNotIn("private-foreign-child", page)

    def test_structured_run_ids_attach_children_to_their_spawning_call(self):
        say = lambda text: [{"role": "assistant", "content": [{"type": "text", "text": text}]}]
        with tempfile.TemporaryDirectory() as directory:
            lead = self.store(directory, "/tmp/demo-repo", [("run-par_delegate", "run-par", "/tmp/demo-repo", say("Did feature/demo-transcripts"))],
                              tasks=[{"agent": "delegate", "task": "spawn-" + "task-" + "marker"}], result="All done.",
                              details={"mode": "single", "runId": "run-par"})
            unit = pi_sessions.load_session(lead, demo_context())
        slicing.slice_to_work(unit, demo_context(), whole=False)
        self.assertEqual(unit.teammates, [])
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("spawn-task-marker", pages[0])
        self.assertIn("Did feature/demo-transcripts", pages[0])

    def test_exclude_removes_a_reported_pi_teammate(self):
        import argparse
        say = lambda text: [{"role": "assistant", "content": [{"type": "text", "text": text}]}]
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as empty:
            self.store(directory, "/tmp/demo-repo", [
                ("run-x_worker_0", "run-x", "/tmp/demo-repo", say("private-" + "excluded-" + "worker on feature/demo-transcripts")),
                ("run-x_worker_1", "run-x", "/tmp/demo-repo", say("Kept worker on feature/demo-transcripts")),
            ], result="done")
            args = argparse.Namespace(projects_root=empty, pi_root=directory, codex_root=empty, session=None, exclude=["run-x_worker_0"], whole=None)
            units = agent_session.load_units(demo_context(), args)
        pages, _ = render_html.build_pages(demo_context(), units, redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("Kept worker", pages[0])
        self.assertNotIn("private-excluded-worker", pages[0])

    def test_child_overflow_reads_inherit_withholding_without_details(self):
        sentinel = "private-" + "overflow-" + "child"
        child = [
            {"role": "user", "content": [{"type": "text", "text": "Check prod for feature/demo-transcripts"}]},
            {"role": "assistant", "content": [{"type": "toolCall", "id": "k1", "name": "bash", "arguments": {"command": "psql -h db.prod.internal -c 'select 1'"}}]},
            {"role": "toolResult", "toolCallId": "k1", "toolName": "bash", "content": [{"type": "text", "text": "row 1\n[Output truncated. Full output: /tmp/pi-bash-private.log]"}]},
            {"role": "assistant", "content": [{"type": "toolCall", "id": "k2", "name": "read", "arguments": {"path": "/tmp/pi-bash-private.log"}},
                                              {"type": "toolCall", "id": "k3", "name": "bash", "arguments": {"command": "tail /tmp/pi-bash-private.log"}}]},
            {"role": "toolResult", "toolCallId": "k2", "toolName": "read", "content": [{"type": "text", "text": sentinel}]},
            {"role": "toolResult", "toolCallId": "k3", "toolName": "bash", "content": [{"type": "text", "text": sentinel + "-2"}]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            lead = self.store(directory, "/tmp/demo-repo", [("run-par_delegate", "run-par", "/tmp/demo-repo", child)])
            unit = pi_sessions.load_session(lead, demo_context())
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertNotIn(sentinel, pages[0])

    def test_parallel_children_of_one_call_all_render_and_unrelated_ones_are_filtered(self):
        say = lambda text: [{"role": "assistant", "content": [{"type": "text", "text": text}]}]
        with tempfile.TemporaryDirectory() as directory:
            lead = self.store(directory, "/tmp/demo-repo", [
                ("run-par_worker_0", "run-par", "/tmp/demo-repo", say("First half of feature/demo-transcripts")),
                ("run-par_worker_1", "run-par", "/tmp/demo-repo", say("Second half of feature/demo-transcripts")),
                ("run-unrelated_cleaner", "run-unrelated", "/tmp/demo-repo", say("secret-unrelated cleanup")),
            ])
            unit = pi_sessions.load_session(lead, demo_context())
        slicing.slice_to_work(unit, demo_context(), whole=False)
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("First half", pages[0])
        self.assertIn("Second half", pages[0])
        self.assertNotIn("secret-unrelated", pages[0])

    def test_siblings_sharing_a_run_id_are_selected_one_by_one(self):
        say = lambda text: [{"role": "assistant", "content": [{"type": "text", "text": text}]}]
        with tempfile.TemporaryDirectory() as directory:
            lead = self.store(directory, "/tmp/demo-repo", [
                ("run-par_worker_0", "run-par", "/tmp/demo-repo", say("Did feature/demo-transcripts")),
                ("run-par_worker_1", "run-par", "/tmp/demo-repo", say("private-" + "note-" + "sibling")),
            ])
            unit = pi_sessions.load_session(lead, demo_context())
        slicing.slice_to_work(unit, demo_context(), whole=False)
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("Did feature/demo-transcripts", pages[0])
        self.assertNotIn("private-note-sibling", pages[0])

    def test_overflow_reads_whose_notice_was_cut_off_are_withheld(self):
        sentinel = "private-" + "overflow-" + "cut"
        child = [
            {"role": "user", "content": [{"type": "text", "text": "Check prod for feature/demo-transcripts"}]},
            {"role": "assistant", "content": [{"type": "toolCall", "id": "k1", "name": "bash", "arguments": {"command": "psql -h db.prod.internal -c 'select 1'"}}]},
            # pi-subagents kept only the first 32 KiB: the trailing "Full output:" notice is gone.
            {"role": "toolResult", "toolCallId": "k1", "toolName": "bash", "content": [{"type": "text", "text": "row\n" * 10000}]},
            {"role": "assistant", "content": [{"type": "toolCall", "id": "k2", "name": "read", "arguments": {"path": "/tmp/pi-bash-9f3a.log"}}]},
            {"role": "toolResult", "toolCallId": "k2", "toolName": "read", "content": [{"type": "text", "text": sentinel}]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            lead = self.store(directory, "/tmp/demo-repo", [("run-par_delegate", "run-par", "/tmp/demo-repo", child)])
            unit = pi_sessions.load_session(lead, demo_context())
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertNotIn(sentinel, pages[0])

    def test_a_child_running_in_the_worktree_finds_its_lead(self):
        say = [{"role": "assistant", "content": [{"type": "text", "text": "Did the work"}]}]
        for child_cwd, expected in (("/work/demo/backend", True), ("/work/demo-other", False)):
            with tempfile.TemporaryDirectory() as directory:
                lead = self.store(directory, "/tmp/demo-repo", [("run-par_worker", "run-par", child_cwd, say)])
                context = demo_context()
                context.worktree_branches = {"/work/demo": "feature/demo-transcripts"}
                self.assertEqual(pi_sessions.find_sessions(context, Path(directory)), [lead] if expected else [], child_cwd)
                unit = pi_sessions.load_session(lead, context)
                child = unit.turns[0].items[0].tool.subagent
                self.assertEqual(child.cwd, child_cwd)
                self.assertEqual(bool(child.evidence), expected)
class CodexSlicingTests(unittest.TestCase):
    def test_codex_lead_keeps_only_the_child_on_this_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            day = Path(directory) / "2026" / "10" / "23"
            day.mkdir(parents=True)
            git = lambda branch: {"branch": branch, "repository_url": "git@github.com:DiversioTeam/demo.git"}
            call = lambda call_id, task: _codex("response_item", {"type": "function_call", "name": "spawn_agent", "call_id": call_id,
                                                                  "arguments": json.dumps({"task": task})}, 3)
            activity = lambda call_id, thread: _codex("event_msg", {"type": "item_completed", "item": {"type": "SubAgentActivity", "id": call_id,
                                                                                                       "kind": "started", "agent_thread_id": thread}}, 3)
            lead = [
                _codex("session_meta", {"id": "lead", "cwd": "/work/demo", "git": git("main")}, 0),
                _codex("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Run both tasks"}]}, 1),
                call("k1", "transcripts"), activity("k1", "child-good"),
                call("k2", "cleanup secret-cleanup"), activity("k2", "child-other"),
                _codex("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Unrelated lunch question"}]}, 4),
            ]
            children = {
                "child-good": [_codex("session_meta", {"id": "child-good", "parent_thread_id": "lead", "agent_nickname": "Curie", "cwd": "/work/demo",
                                                       "git": git("feature/demo-transcripts")}, 0),
                               _codex("response_item", {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Built transcripts"}]}, 1)],
                "child-other": [_codex("session_meta", {"id": "child-other", "parent_thread_id": "lead", "agent_nickname": "Noether", "cwd": "/work/demo",
                                                        "git": git("main")}, 0),
                                _codex("response_item", {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Cleaned secret-cleanup"}]}, 1)],
            }
            path = day / "rollout-2026-10-23T11-00-00-lead.jsonl"
            path.write_text("\n".join(json.dumps(record) for record in lead) + "\n")
            for thread, records in children.items():
                (day / f"rollout-2026-10-23T11-01-00-{thread}.jsonl").write_text("\n".join(json.dumps(record) for record in records) + "\n")
            self.assertEqual(codex_sessions.find_sessions(demo_context(), Path(directory)), [path])
            unit = codex_sessions.load_session(path, demo_context(), Path(directory))
        slicing.slice_to_work(unit, demo_context(), whole=False)
        self.assertEqual([mate.worker_key for mate in unit.teammates], ["child-good"])
        self.assertEqual([turn.text for turn in unit.turns], ["Run both tasks"])
        self.assertEqual([item.tool.links_to for turn in unit.turns for item in turn.items if item.tool], ["child-good"])
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("Built transcripts", pages[0])
        self.assertNotIn("secret-cleanup", pages[0])
        self.assertNotIn("lunch", pages[0])


class CodexReviewFindingsTests(unittest.TestCase):
    """Regressions for courage-bot's #118 findings."""

    def test_write_stdin_polls_inherit_the_terminal_sessions_withholding(self):
        with tempfile.TemporaryDirectory() as directory:
            day = Path(directory) / "2026" / "10" / "23"
            day.mkdir(parents=True)
            records = [
                _codex("session_meta", {"id": "t", "cwd": "/work/demo", "git": {"branch": "feature/demo-transcripts", "repository_url": "git@github.com:DiversioTeam/demo.git"}}, 0),
                _codex("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Tail the staging log"}]}, 1),
                _codex("response_item", {"type": "function_call", "name": "exec_command", "call_id": "x1", "arguments": json.dumps({"cmd": "ssh staging 'tail -f app.log'"})}, 2),
                _codex("response_item", {"type": "function_call_output", "call_id": "x1", "output": "Process running with session ID 12345"}, 3),
                _codex("response_item", {"type": "function_call", "name": "write_stdin", "call_id": "x2", "arguments": json.dumps({"session_id": 12345, "chars": ""})}, 4),
                _codex("response_item", {"type": "function_call_output", "call_id": "x2", "output": "staging-" + "secret-" + "line"}, 5),
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "x3", "input": "await tools.write_stdin({session_id: 12345, chars: ''})"}, 6),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "x3", "output": "staging-" + "secret-" + "line2"}, 7),
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "x4", "input": 'await tools.write_stdin({"session_id":12345,"chars":""})'}, 8),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "x4", "output": "staging-" + "secret-" + "line3"}, 9),
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "x5", "input": "await tools.write_stdin({session_id : '12345', chars: ''})"}, 10),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "x5", "output": "staging-" + "secret-" + "line4"}, 11),
            ]
            path = day / "rollout-2026-10-23T11-00-00-t.jsonl"
            path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
            unit = codex_sessions.load_session(path, demo_context(), Path(directory))
        self.assertEqual([item.tool.withheld for turn in unit.turns for item in turn.items if item.tool], ["prod or staging data access"] * 5)
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertNotIn("staging-secret-line", pages[0])

    def _rollout(self, directory, records):
        day = Path(directory) / "2026" / "10" / "23"
        day.mkdir(parents=True)
        head = [_codex("session_meta", {"id": "t", "cwd": "/work/demo", "git": {"branch": "feature/demo-transcripts", "repository_url": "git@github.com:DiversioTeam/demo.git"}}, 0),
                _codex("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Look into it"}]}, 1)]
        path = day / "rollout-2026-10-23T11-00-00-t.jsonl"
        path.write_text("\n".join(json.dumps(record) for record in [*head, *records]) + "\n")
        return codex_sessions.load_session(path, demo_context(), Path(directory))

    def test_code_mode_unresolved_shell_arguments_withhold_outputs_and_continuations(self):
        cases = [
            ('const cmd="printenv"; text(await tools.exec_command({cmd}));', True),
            ('text(await tools.exec_command({cmd: getCommand()}));', True),
            ('text(await tools.exec_command({cmd: "print" + "env"}));', True),
            ('await tools.exec_command({cmd: "git status"}); text(await tools.run(args));', True),
            ('text(await tools.exec_command({["cmd"]: "printenv"}));', True),
            ('text(await tools.exec_command(args));', True),
            ('text(await tools.exec_command({cmd: "git status", ...args}));', True),
            ('text(await tools.exec_command({cmd: `${command}`}));', True),
            ('text(await tools.exec_command({cmd: "git status"} && args));', True),
            ('const command="printenv"; text(await tools.run({command}));', True),
            ('text(await tools["run"]({command: commands[0]}));', True),
            ('text(await tools.run({[field]: "printenv"}));', True),
            ('text(await tools.run(args));', True),
            ('text(`${await tools.run(args)}`);', True),
            ('text(`${`prefix`} ${await tools.exec_command({cmd})}`);', True),
            ('/* " */ text(await tools.run(args)); /* " */', True),
            ("const note = 'tools.run('; text(await tools.exec_command({cmd}));", True),
            ('text(await tools.exec_command({cmd: "git status"}));', False),
            ("text(await tools.exec_command({cmd: 'git status'}));", False),
            ('text(await tools.exec_command({cmd: `git status`}));', False),
            ('text(await tools.exec_command({cmd: "git status"})); const note = `${label}`;', False),
            ('text(await tools.run({command: ["git", "status"]}));', False),
            ("""text(await tools.exec_command({cmd: "node -e 'console.log({ok: true})'"}));""", False),
            ("""text(await tools.exec_command({cmd: 'node -e "console.log({ok: true})"'}));""", False),
            ("""text(await tools.exec_command({cmd: `node -e 'console.log({ok: true})'`}));""", False),
            ("""text(await tools.exec_command({cmd: "rg -F 'tools.run(' src"}));""", True),
            ("""text(await tools.exec_command({cmd: 'rg -F "tools.run(" src'}));""", True),
            ("""text(await tools.exec_command({cmd: `rg -F 'tools.run(' src`}));""", True),
        ]
        sentinels = ["opaque-shell-output-sentinel", "opaque-terminal-output-sentinel", "opaque-cell-output-sentinel"]
        for code, unsafe in cases:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                unit = self._rollout(directory, [
                    _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "o1", "input": code}, 2),
                    _codex("response_item", {"type": "custom_tool_call_output", "call_id": "o1",
                                             "output": json.dumps({"session_id": 12345, "output": sentinels[0]})}, 3),
                    _codex("response_item", {"type": "function_call", "name": "write_stdin", "call_id": "o2",
                                             "arguments": json.dumps({"session_id": 12345, "chars": ""})}, 4),
                    _codex("response_item", {"type": "function_call_output", "call_id": "o2",
                                             "output": f"{sentinels[1]}\nScript running with cell ID 17"}, 5),
                    _codex("response_item", {"type": "function_call", "name": "wait", "call_id": "o3",
                                             "arguments": json.dumps({"cell_id": "17"})}, 6),
                    _codex("response_item", {"type": "function_call_output", "call_id": "o3", "output": sentinels[2]}, 7),
                ])
                pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
                for sentinel in sentinels:
                    if unsafe:
                        self.assertNotIn(sentinel, pages[0])
                    else:
                        self.assertIn(sentinel, pages[0])
                reasons = [item.tool.withheld for turn in unit.turns for item in turn.items if item.tool]
                self.assertEqual(reasons, ["unresolved shell command" if unsafe else None] * 3)

    def test_code_mode_unresolved_shell_keeps_credential_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            unit = self._rollout(directory, [
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "o1",
                                         "input": 'await tools.exec_command({cmd}); await tools.read_file({path: "/work/demo/.env"}); // private-input-sentinel'}, 2),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "o1", "output": "private-credential-output-sentinel"}, 3),
            ])
        self.assertEqual(unit.turns[0].items[0].tool.withheld, "credential file")
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertNotIn("private-input-sentinel", pages[0])
        self.assertNotIn("private-credential-output-sentinel", pages[0])

    def test_code_mode_keeps_nested_tool_meaning(self):
        patch = "*** Begin Patch\n*** Update File: /work/demo/.env\n@@\n-API_KEY=old\n+API_KEY=private-" + "patch-" + "value\n*** End Patch"
        with tempfile.TemporaryDirectory() as directory:
            unit = self._rollout(directory, [
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "q1",
                                         "input": 'text(await tools.mcp__postgres__query({"sql":"select note from accounts"}));'}, 2),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "q1", "output": "private-" + "db-" + "row"}, 3),
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "q2",
                                         "input": f"await tools.apply_patch({json.dumps(patch)});"}, 4),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "q2", "output": "Done"}, 5),
            ])
        self.assertEqual([item.tool.withheld for turn in unit.turns for item in turn.items if item.tool],
                         ["prod or staging data access", "credential file"])
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertNotIn("private-db-row", pages[0])
        self.assertNotIn("private-patch-value", pages[0])

    def test_terminals_opened_by_a_json_result_pass_on_withholding(self):
        with tempfile.TemporaryDirectory() as directory:
            unit = self._rollout(directory, [
                _codex("response_item", {"type": "function_call", "name": "exec_command", "call_id": "s1", "arguments": json.dumps({"cmd": "ssh staging 'tail -f app.log'"})}, 2),
                _codex("response_item", {"type": "function_call_output", "call_id": "s1", "output": json.dumps({"session_id": 12345, "output": ""})}, 3),
                _codex("response_item", {"type": "function_call", "name": "write_stdin", "call_id": "s2", "arguments": json.dumps({"session_id": 12345, "chars": ""})}, 4),
                _codex("response_item", {"type": "function_call_output", "call_id": "s2", "output": "staging-" + "json-" + "line"}, 5),
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "s3", "input": "await tools.write_stdin({session_id: 12345, chars: ''})"}, 6),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "s3", "output": "staging-" + "json-" + "line2"}, 7),
            ])
        self.assertEqual([item.tool.withheld for turn in unit.turns for item in turn.items if item.tool], ["prod or staging data access"] * 3)
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertNotIn("staging-json-line", pages[0])

    def test_code_mode_javascript_arguments_and_credential_precedence(self):
        patch = "*** Begin Patch\n*** Update File: /work/demo/.env\n+API_KEY=private-" + "mixed-" + "patch\n*** End Patch"
        with tempfile.TemporaryDirectory() as directory:
            unit = self._rollout(directory, [
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "j1",
                                         "input": 'text(await tools.read_file({path: "/work/demo/.env"}));'}, 2),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "j1", "output": "API_KEY=private-" + "js-" + "read"}, 3),
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "j2",
                                         "input": 'await tools.mcp__postgres__query({"sql":"select 1"});\n'
                                                  f"await tools.apply_patch({json.dumps(patch)});"}, 4),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "j2", "output": "Done"}, 5),
            ])
        self.assertEqual([item.tool.withheld for turn in unit.turns for item in turn.items if item.tool], ["credential file", "credential file"])
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertNotIn("private-js-read", pages[0])
        self.assertNotIn("private-mixed-patch", pages[0])

    def test_yielded_code_cells_pass_on_withholding(self):
        with tempfile.TemporaryDirectory() as directory:
            unit = self._rollout(directory, [
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "y1",
                                         "input": "await tools.exec_command({cmd: \"ssh staging 'tail -f app.log'\", yield_time_ms: 1000})"}, 2),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "y1", "output": "Script running with cell ID 17"}, 3),
                _codex("response_item", {"type": "function_call", "name": "wait", "call_id": "y2", "arguments": json.dumps({"cell_id": "17"})}, 4),
                _codex("response_item", {"type": "function_call_output", "call_id": "y2", "output": "staging-" + "cell-" + "line"}, 5),
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "y3", "input": "await functions.wait({cell_id: '17'})"}, 6),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "y3", "output": "staging-" + "cell-" + "line2"}, 7),
            ])
        self.assertEqual([item.tool.withheld for turn in unit.turns for item in turn.items if item.tool], ["prod or staging data access"] * 3)
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertNotIn("staging-cell-line", pages[0])

    def test_shorthand_and_untraceable_polls_stay_withheld(self):
        with tempfile.TemporaryDirectory() as directory:
            unit = self._rollout(directory, [
                _codex("response_item", {"type": "function_call", "name": "exec_command", "call_id": "p1", "arguments": json.dumps({"cmd": "ssh staging 'tail -f app.log'"})}, 2),
                _codex("response_item", {"type": "function_call_output", "call_id": "p1", "output": "Process running with session ID 12345"}, 3),
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "p2",
                                         "input": 'const session_id = 12345;\ntext(await tools.write_stdin({session_id, chars: ""}));'}, 4),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "p2", "output": "private-" + "staging-poll-" + "sentinel"}, 5),
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "p3",
                                         "input": "await tools.exec_command({cmd: \"ssh staging 'tail -f app.log'\", yield_time_ms: 1000})"}, 6),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "p3", "output": "Script running with cell ID 17"}, 7),
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "p4",
                                         "input": 'const cell_id = "17";\ntext(await functions.wait({cell_id}));'}, 8),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "p4", "output": "private-" + "staging-cell-" + "sentinel"}, 9),
                # A poll whose handle is computed, or names a terminal no recorded call opened, may be reading anything.
                _codex("response_item", {"type": "custom_tool_call", "name": "exec", "call_id": "p5", "input": "text(await tools.write_stdin(args));"}, 10),
                _codex("response_item", {"type": "custom_tool_call_output", "call_id": "p5", "output": "private-" + "computed-poll-" + "sentinel"}, 11),
                _codex("response_item", {"type": "function_call", "name": "write_stdin", "call_id": "p6", "arguments": json.dumps({"session_id": 999, "chars": ""})}, 12),
                _codex("response_item", {"type": "function_call_output", "call_id": "p6", "output": "private-" + "unknown-terminal-" + "sentinel"}, 13),
            ])
        self.assertEqual([item.tool.withheld for turn in unit.turns for item in turn.items if item.tool],
                         ["prod or staging data access"] * 4 + ["polling output of unknown origin"] * 2)
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        for sentinel in ("staging-poll", "staging-cell", "computed-poll", "unknown-terminal"):
            self.assertNotIn(f"private-{sentinel}-sentinel", pages[0])

    def test_rollouts_in_another_repository_need_the_pr_not_just_a_shared_branch_name(self):
        import argparse
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as empty:
            day = Path(directory) / "2026" / "10" / "23"
            day.mkdir(parents=True)

            def rollout(thread, cwd, repository, prompt):
                meta = {"id": thread, "cwd": cwd, "git": {"branch": "main", "repository_url": f"git@github.com:{repository}.git"}}
                path = day / f"rollout-2026-10-23T11-00-00-{thread}.jsonl"
                path.write_text("\n".join(json.dumps(record) for record in [
                    _codex("session_meta", meta, 0),
                    _codex("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": prompt}]}, 1)]) + "\n")
                return path

            rollout("other", "/work/other", "DiversioTeam/other", "Implement feature/demo-transcripts in this other repository: private-" + "other-repo-" + "sentinel")
            linked = rollout("coordinator", "/work/coordinator", "DiversioTeam/other", "Coordinate https://github.com/DiversioTeam/demo/pull/7")
            here = rollout("here", "/work/demo", "DiversioTeam/demo", "Continue feature/demo-transcripts here")
            self.assertEqual(sorted(path.name for path in codex_sessions.find_sessions(demo_context(), Path(directory))), sorted([linked.name, here.name]))
            args = argparse.Namespace(projects_root=empty, pi_root=empty, codex_root=directory, session=None, exclude=None, whole=None)
            units = agent_session.load_units(demo_context(), args)
        page = "".join(render_html.build_pages(demo_context(), units, redaction.Redactor(), "2027-10-23", "now")[0])
        self.assertIn("Coordinate https://github.com/DiversioTeam/demo/pull/7", page)
        self.assertIn("Continue feature/demo-transcripts here", page)
        self.assertNotIn("private-other-repo-sentinel", page)

    def test_children_older_than_a_week_before_the_leads_last_write_stay_attached(self):
        import os, time
        with tempfile.TemporaryDirectory() as directory:
            day = Path(directory) / "2026" / "10" / "23"
            day.mkdir(parents=True)
            git = lambda branch: {"branch": branch, "repository_url": "git@github.com:DiversioTeam/demo.git"}
            lead = day / "rollout-2026-10-23T11-00-00-lead.jsonl"
            child = day / "rollout-2026-10-23T11-01-00-kid.jsonl"
            lead.write_text("\n".join(json.dumps(record) for record in [
                _codex("session_meta", {"id": "lead", "cwd": "/w", "git": git("main")}, 0),
                _codex("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Delegate it"}]}, 1),
                _codex("response_item", {"type": "function_call", "name": "spawn_agent", "call_id": "k1", "arguments": "{}"}, 2),
                _codex("event_msg", {"type": "item_completed", "item": {"type": "SubAgentActivity", "id": "k1", "agent_thread_id": "kid"}}, 3)]) + "\n")
            child.write_text("\n".join(json.dumps(record) for record in [
                _codex("session_meta", {"id": "kid", "parent_thread_id": "lead", "cwd": "/w", "git": git("feature/demo-transcripts")}, 0),
                _codex("response_item", {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Child did the work"}]}, 1)]) + "\n")
            now = time.time()
            os.utime(child, (now - 10 * 86400, now - 10 * 86400))
            os.utime(lead, (now, now))
            unit = codex_sessions.load_session(lead, demo_context(), Path(directory))
        slicing.slice_to_work(unit, demo_context(), whole=False)
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("Child did the work", pages[0])
        self.assertIn("Delegate it", pages[0])

    def test_grandchildren_reach_the_transcript(self):
        self._assert_grandchildren_reach_the_transcript(since=0)

    def test_recent_grandchild_reaches_the_transcript_through_an_old_middle(self):
        for middle_on_branch in (False, True):
            with self.subTest(middle_on_branch=middle_on_branch):
                self._assert_grandchildren_reach_the_transcript(since=1792713600, middle_on_branch=middle_on_branch)  # 2026-10-23 UTC

    def test_copied_old_grandchild_is_not_fresh_work(self):
        self._assert_grandchildren_reach_the_transcript(since=1792713600, copied_sibling=True)

    def test_old_middle_keeps_only_delegation_not_historical_branch_mentions(self):
        for middle_on_branch in (False, True):
            with self.subTest(middle_on_branch=middle_on_branch):
                self._assert_grandchildren_reach_the_transcript(since=1792713600, middle_on_branch=middle_on_branch,
                                                              historical_mentions=True)

    def _assert_grandchildren_reach_the_transcript(self, since, middle_on_branch=False, copied_sibling=False, historical_mentions=False):
        context = demo_context()
        context.since = since
        with tempfile.TemporaryDirectory() as directory:
            day = Path(directory) / "2026" / "10" / "23"
            day.mkdir(parents=True)
            git = lambda branch: {"branch": branch, "repository_url": "git@github.com:DiversioTeam/demo.git"}
            write = lambda name, records: (day / f"rollout-2026-10-23T11-0{len(name)}-00-{name}.jsonl").write_text("\n".join(json.dumps(record) for record in records) + "\n")
            write("main", [_codex("session_meta", {"id": "main", "cwd": "/w", "git": git("main")}, 0),
                           _codex("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Delegate it"}]}, 1),
                           _codex("response_item", {"type": "function_call", "name": "spawn_agent", "call_id": "k1", "arguments": "{}"}, 2),
                           _codex("event_msg", {"type": "item_completed", "item": {"type": "SubAgentActivity", "id": "k1", "agent_thread_id": "child"}}, 3),
                           _codex("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Unrelated lead secret-lead-work"}]}, 4)])
            write("child", [_codex("session_meta", {"id": "child", "parent_thread_id": "main", "cwd": "/w", "git": git(context.branch if middle_on_branch else "main")}, 0),
                            _codex("response_item", {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Delegating further"}]}, 1),
                            _codex("response_item", {"type": "function_call", "name": "spawn_agent", "call_id": "g1", "arguments": "{}"}, 2),
                            _codex("event_msg", {"type": "item_completed", "item": {"type": "SubAgentActivity", "id": "g1", "agent_thread_id": "grandchild"}}, 3),
                            _codex("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Unrelated child prompt secret-child-work"}]}, 4),
                            _codex("response_item", {"type": "function_call", "name": "exec_command", "call_id": "u1", "arguments": json.dumps({"cmd": "ls"})}, 5),
                            _codex("response_item", {"type": "function_call_output", "call_id": "u1", "output": "secret-child-output"}, 6)])
            write("grandchild", [_codex("session_meta", {"id": "grandchild", "parent_thread_id": "child", "cwd": "/w", "git": git("feature/demo-transcripts")}, 0),
                                 _codex("response_item", {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Grandchild did the work"}]}, 1)])
            main = day / "rollout-2026-10-23T11-04-00-main.jsonl"
            if since:
                write("expired", [_codex("session_meta", {"id": "expired", "parent_thread_id": "main", "cwd": "/w", "git": git(context.branch)}, 0),
                                  _codex("response_item", {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "secret-expired-sibling"}]}, 1)])
                for name in ("main", "child", "expired"):
                    ancestor = next(day.glob(f"*-{name}.jsonl"))
                    os.utime(ancestor, (since - 86400, since - 86400))
                grandchild = next(day.glob("*-grandchild.jsonl"))
                os.utime(grandchild, (since + 86400, since + 86400))
            if copied_sibling:
                stale = "2026-10-20T11:00:00Z"
                write("copied", [_codex("session_meta", {"id": "copied", "parent_thread_id": "child", "cwd": "/w", "git": git(context.branch)}, 0, stale),
                                 _codex("response_item", {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "secret-copied-sibling"}]}, 1, stale)])
                copied = next(day.glob("*-copied.jsonl"))
                os.utime(copied, (since + 86400, since + 86400))
            if historical_mentions:
                child = next(day.glob("*-child.jsonl"))
                records = [json.loads(line) for line in child.read_text().splitlines()]
                records.insert(4, _codex("response_item", {"type": "message", "role": "assistant", "content": [
                    {"type": "output_text", "text": f"Historical {context.branch} secret-after-delegation"}]}, 3))
                records.extend([
                    _codex("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "secret-historical-prompt"}]}, 7),
                    _codex("response_item", {"type": "message", "role": "assistant", "content": [
                        {"type": "output_text", "text": f"Historical {context.branch} secret-historical-mention"}]}, 8),
                ])
                child.write_text("\n".join(json.dumps(record) for record in records) + "\n")
                os.utime(child, (since - 86400, since - 86400))
            self.assertEqual(codex_sessions.find_sessions(context, Path(directory)), [main])
            unit = codex_sessions.load_session(main, context, Path(directory))
        if historical_mentions:
            # Bridge pruning happens before shared slicing, including when a caller requests a whole session.
            bridge = next(mate for mate in unit.teammates if mate.worker_key == "child")
            text = "\n".join(turn.text + "\n" + "\n".join(item.text for item in turn.items) for turn in bridge.turns)
            self.assertIn("Delegating further", text)
            for sentinel in ("secret-historical-prompt", "secret-historical-mention", "secret-after-delegation"):
                self.assertNotIn(sentinel, text)
        slicing.slice_to_work(unit, context, whole=False)
        self.assertEqual([mate.worker_key for mate in unit.teammates], ["child", "grandchild"])
        if since:
            bridge = unit.teammates[0]
            omitted = 2 if historical_mentions else 1
            self.assertEqual(bridge.omitted_turns, omitted)
            bridge_pages, _ = render_html.build_pages(context, [bridge], redaction.Redactor(), "2027-10-23", "now")
            self.assertIn(f"{omitted} earlier or later turns in this session were about other work and are not included.", bridge_pages[0])
            slicing._trim_to_workers(bridge, {"grandchild"}, context.evidence_pattern())
            self.assertEqual(bridge.omitted_turns, omitted)
            repeated_pages, _ = render_html.build_pages(context, [bridge], redaction.Redactor(), "2027-10-23", "now")
            self.assertEqual(repeated_pages, bridge_pages)
        pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now")
        self.assertIn("Grandchild did the work", pages[0])
        self.assertIn("Delegate it", pages[0])
        self.assertNotIn("secret-child-work", pages[0])
        self.assertNotIn("secret-child-output", pages[0])
        self.assertNotIn("secret-lead-work", pages[0])
        self.assertNotIn("secret-expired-sibling", pages[0])
        self.assertNotIn("secret-copied-sibling", pages[0])
        self.assertNotIn("secret-historical-prompt", pages[0])
        self.assertNotIn("secret-historical-mention", pages[0])
        self.assertNotIn("secret-after-delegation", pages[0])

    def test_hook_keeps_argv_boundaries(self):
        import subprocess
        hook = Path(check_pr_hook.__file__)

        def run(command, cwd="/tmp"):
            return subprocess.run([sys.executable, str(hook)], input=json.dumps({"tool_input": {"command": command}, "cwd": cwd}),
                                  capture_output=True, text=True).returncode
        self.assertEqual(run(["gh", "pr", "create", "--repo", "DiversioTeam/demo", "--body", "No agent session: hand edited"]), 0)
        self.assertEqual(run(["gh", "pr", "create", "--repo", "DiversioTeam/demo", "--body", "Summary only"]), 2)
        self.assertEqual(run(["bash", "-lc", "gh pr create --repo DiversioTeam/demo --body 'No agent session: hand edited'"]), 0)
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "my body.md").write_text("No agent session: hand edited\n")
            self.assertEqual(run(["gh", "pr", "create", "--repo", "DiversioTeam/demo", "--body-file", "my body.md"], directory), 0)
class CourageExportTests(unittest.TestCase):
    def test_render_export_labels_courage_and_names_the_head(self):
        import contextlib, io
        with tempfile.TemporaryDirectory() as directory:
            export = build_pi_store(Path(directory) / "in", "/var/courage/workspaces/c1")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = agent_session.main(["render-export", "--file", str(export), "--repo-slug", "DiversioTeam/demo", "--branch", "courage/fix",
                                           "--head", HEAD, "--pr", "7", "--out", str(Path(directory) / "out")])
            self.assertEqual(code, 0)
            result = json.loads(out.getvalue())
            html = Path(result["files"][0]).read_text(encoding="utf-8")
        self.assertIn(f"-h{HEAD[:12]}-", result["names"][0])
        self.assertIn("Agents</dt><dd>Courage", html)
        self.assertIn("Courage conversation", html)
        self.assertNotIn(GITHUB_TOKEN, html)

    def test_each_source_keeps_its_own_line(self):
        dev = "https://internal-share.diversio.com/session-demo-x-20261023-h0123456789ab-aaaaaa.html"
        courage = "https://internal-share.diversio.com/session-demo-x-20261023-hfedcba987654-bbbbbb.html"
        body = f"## Summary\n\nx\n\n## Agent sessions\n\n- [Courage conversation transcript]({courage})\n- [Agent session transcript]({dev})\n\n## Testing\n"
        new_dev = dev.replace("aaaaaa", "cccccc")
        updated = pr_body.upsert(body, pr_body.section([("Agent session transcript", new_dev)]))
        self.assertIn(new_dev, updated)
        self.assertIn(courage, updated)
        self.assertNotIn(dev, updated)
        self.assertEqual(updated.count("## Agent sessions"), 1)
        self.assertIn("## Testing", updated)
        # Courage's line last: repeated shares change nothing.
        last = f"## Agent sessions\n\n- [Agent session transcript]({dev})\n- [Courage conversation transcript]({courage})\n\n## Testing\n"
        once = pr_body.upsert(last, pr_body.section([("Agent session transcript", new_dev)]))
        self.assertEqual(pr_body.upsert(once, pr_body.section([("Agent session transcript", new_dev)])), once)

    def test_render_export_redacts_known_secrets_before_rendering(self):
        import contextlib, io
        secret = "plain-db-" + "password-" + "93ab"
        with tempfile.TemporaryDirectory() as directory:
            export = Path(directory) / "conv.jsonl"
            export.write_text("\n".join(json.dumps(entry) for entry in [
                {"type": "session", "id": "c", "cwd": "courage"},
                {"type": "message", "id": "1", "parentId": None, "timestamp": "2026-10-23T10:00:00Z", "message": {"role": "user", "content": "echo the password"}},
                {"type": "message", "id": "2", "parentId": "1", "timestamp": "2026-10-23T10:00:01Z", "message": {"role": "assistant", "content": [{"type": "text", "text": f"It is {secret}"}]}},
            ]) + "\n")
            secrets_file = Path(directory) / "known"
            secrets_file.write_text(secret + "\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                agent_session.main(["render-export", "--file", str(export), "--repo-slug", "DiversioTeam/demo", "--branch", "x",
                                    "--head", HEAD, "--out", str(Path(directory) / "out"), "--known-secrets-file", str(secrets_file)])
            html = Path(json.loads(out.getvalue())["files"][0]).read_text(encoding="utf-8")
        self.assertNotIn(secret, html)
        self.assertIn("[redacted]", html)


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

    def test_malformed_final_status_cleans_uncertain_upload_or_records_debt(self):
        import subprocess
        self.failure = subprocess.CompletedProcess([], 0, "HTTP/2 409\r\n\r\nHTTP/2 4099\r\n", "")
        for succeeds in (True, False):
            with self.subTest(delete_succeeds=succeeds):
                self.remote.clear()
                self.deleted.clear()
                self.delete_succeeds = succeeds
                self.assertEqual(self.run_publish(), 1)
                self.assertEqual(self.deleted, self.names[:2])
                self.assertEqual(set(self.remote), set() if succeeds else set(self.names[:2]))
                self.assertEqual(store.cleanup_debt(self.context.repo_slug, self.context.branch),
                                 [] if succeeds else self.names[:2])
                self.assertIsNone(store.latest(self.context.repo_slug, self.context.branch))
        agent_session._update_pr_body.assert_not_called()

    def test_upload_uses_final_http_status_to_identify_conflict(self):
        import subprocess
        for headers, stderr, returncode, rejected in (
                ("HTTP/2 409\r\n", "", 0, True),
                ("", "HTTP/2 409\r\n", 22, True),
                ("HTTP/2 303\r\nlocation: /old.html\r\n\r\nHTTP/2 409\r\n", "", 0, True),
                ("HTTP/2 409\r\n\r\nHTTP/2 500\r\n", "", 0, False),
                ("HTTP/2 4099\r\n", "", 0, False),
                ("HTTP/2 409\r\n\r\nHTTP/2 4099\r\n", "", 0, False),
                ("HTTP/2 409\r\n", "HTTP/2 invalid\r\n", 0, False),
                ("HTTP/2 409\r\n\r\nHTTP/2\r\n", "", 0, False),
                ("HTTP/2 303\r\nlocation: /old.html\r\n\r\nHTTP/2 4099\r\n", "", 0, False),
                ("HTTP/2 4099\r\n\r\nHTTP/2 409\r\n", "", 0, True),
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
        (root / "pi").mkdir()
        self.args = ["--repo", str(self.repo), "--projects-root", str(root / "store"), "--pi-root", str(root / "pi"), "--codex-root", str(root / "pi"), "--out", str(root / "out")]
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
