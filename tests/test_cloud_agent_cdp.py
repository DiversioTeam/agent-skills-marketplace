"""Regression tests for the cloud-agent-onboarding browser helper (scripts/cdp.mjs).

The helper must only ever talk to the Chrome the operator launched: with no
CDP_PORT it must exit before any network call (so a failed setup can't reach
another session's browser on 9222), and with CDP_PORT it must contact exactly
that port.
"""

import http.server
import json
import os
import shutil
import subprocess
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CDP = ROOT / "plugins/cloud-agent-onboarding/skills/cloud-agent-onboarding/scripts/cdp.mjs"
# Preloaded before cdp.mjs: any network attempt prints a marker and exits 3.
TRAP = (
    "data:text/javascript,"
    "globalThis.fetch=()=>{console.log('NETWORK-ATTEMPT');process.exit(3)};"
    "globalThis.WebSocket=function(){console.log('NETWORK-ATTEMPT');process.exit(3)};"
)


def run_cdp(env_overrides, *args, trap=False):
    env = {k: v for k, v in os.environ.items() if k not in ("CDP_PORT", "TAB")}
    env.update(env_overrides)
    cmd = ["node"] + (["--import", TRAP] if trap else []) + [str(CDP), *args]
    return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)


@unittest.skipUnless(shutil.which("node"), "node is required")
class CdpPortTests(unittest.TestCase):
    def test_refuses_without_cdp_port_before_any_network_call(self):
        result = run_cdp({}, "text", trap=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("set CDP_PORT", result.stdout)
        self.assertNotIn("NETWORK-ATTEMPT", result.stdout)

    def test_refuses_non_numeric_cdp_port(self):
        result = run_cdp({"CDP_PORT": "9222;x"}, "text", trap=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("NETWORK-ATTEMPT", result.stdout)

    def test_uses_only_the_given_port(self):
        seen = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - http.server API
                seen.append(self.path)
                body = json.dumps([]).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            result = run_cdp({"CDP_PORT": str(port), "TAB": "claude.ai"}, "text")
        finally:
            server.shutdown()
        # No tabs on the stub browser: the helper reports it and fails, after asking only this port.
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("no tab", result.stdout)
        self.assertEqual(seen, ["/json/list"])


if __name__ == "__main__":
    unittest.main()
