import importlib
import json
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


def build_store(root: Path) -> Path:
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
            names = publish.build_names("demo", "feature/demo-transcripts", 4, HEAD)
            pages, _ = render_html.build_pages(demo_context(), [unit], redaction.Redactor(), "2027-10-23", "now", names)
        finally:
            render_html.MAX_PART_BYTES = original
        self.assertEqual(len(pages), 4)
        self.assertIn(f'href="{names[3]}"', pages[0])
        self.assertIn("Session 11111111 (1 of 3)", pages[0])
        self.assertIn("Teammate: renderer", pages[3])

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


class PrBodyAndHookTests(unittest.TestCase):
    LINK = "https://internal-share.diversio.com/session-demo-feature-demo-20261023-a1b2c3.html"

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
        build_store(root / "store")
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

    def test_declare_none_records_and_links(self):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agent_session.main(["declare-none", "hand-edited a config value", "--repo", str(self.repo)]), 0)
        self.assertEqual(store.latest("DiversioTeam/demo", "feature/demo-transcripts")["none"], "hand-edited a config value")
        self.assertIn("No agent session: hand-edited a config value", self.bodies[0][1])
