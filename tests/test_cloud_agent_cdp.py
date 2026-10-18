"""Regression tests for the cloud-agent-onboarding browser helper (scripts/cdp.mjs).

The helper must only ever talk to the Chrome the operator launched: with no
CDP_PORT it must exit before any network call (so a failed setup can't reach
another session's browser on 9222), and with CDP_PORT it must contact exactly
that port.
"""

import base64
import hashlib
import http.server
import json
import os
import shutil
import signal
import socket
import socketserver
import struct
import subprocess
import tempfile
import threading
import time
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


class RefusingCdp(socketserver.ThreadingTCPServer):
    """A fake Chrome: lists one claude.ai tab and answers every CDP command with an error envelope."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), RefusingCdpHandler)
        self.methods = []


class RefusingCdpHandler(socketserver.BaseRequestHandler):
    def handle(self):
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.request.recv(4096)
            if not chunk:
                return
            head += chunk
        lines = head.decode().split("\r\n")
        path = lines[0].split(" ")[1]
        headers = {k.lower(): v for k, _, v in (line.partition(": ") for line in lines[1:] if line)}
        port = self.server.server_address[1]
        if path == "/json/list":
            body = json.dumps([{"type": "page", "url": "https://claude.ai/code",
                                "webSocketDebuggerUrl": f"ws://127.0.0.1:{port}/devtools/page/1"}]).encode()
            self.request.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                                 + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body)
            return
        accept = base64.b64encode(hashlib.sha1(
            (headers["sec-websocket-key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        self.request.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                             b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n")
        while True:
            message = self._read_frame()
            if message is None:
                return
            request = json.loads(message)
            self.server.methods.append(request["method"])
            reply = json.dumps({"id": request["id"], "error": {"code": -32000, "message": "command refused"}})
            self._send_frame(reply.encode())

    def _recv(self, n):
        data = b""
        while len(data) < n:
            chunk = self.request.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _read_frame(self):
        header = self._recv(2)
        if header is None or header[0] & 0x0F == 0x8:
            return None
        length = header[1] & 0x7F
        if length == 126:
            length = struct.unpack(">H", self._recv(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._recv(8))[0]
        mask = self._recv(4)
        payload = self._recv(length)
        return bytes(b ^ mask[i % 4] for i, b in enumerate(payload)).decode()

    def _send_frame(self, payload):
        n = len(payload)
        prefix = bytes([0x81, n]) if n < 126 else bytes([0x81, 126]) + struct.pack(">H", n)
        self.request.sendall(prefix + payload)


@unittest.skipUnless(shutil.which("node"), "node is required")
class CdpProtocolErrorTests(unittest.TestCase):
    def test_refused_input_command_exits_nonzero(self):
        server = RefusingCdp()
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            result = run_cdp({"CDP_PORT": str(server.server_address[1]), "TAB": "claude.ai"}, "enter")
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("refused", result.stdout)
        self.assertEqual(server.methods, ["Input.dispatchKeyEvent"])


def find_chrome():
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if shutil.which(name):
            return shutil.which(name)
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    return mac if os.path.exists(mac) else None


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


COMPOSER_PAGE = """<!doctype html><meta charset=utf-8><title>composer</title>
<div data-testid="code-prompt-input"><textarea id=t>human draft</textarea></div>"""


def stop_browser(chrome, profile):
    """Stop every process of the test-owned Chrome, then wait until none still uses the profile."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(chrome.pid, sig)  # Chrome was started in its own process group
        except (ProcessLookupError, PermissionError):
            break  # the group is gone (macOS reports EPERM once the leader has exited)
        try:
            chrome.wait(timeout=10)
        except subprocess.TimeoutExpired:
            continue
    try:
        chrome.wait(timeout=5)  # reap the leader even when the group was already gone
    except subprocess.TimeoutExpired:
        chrome.kill()
    deadline = time.time() + 15
    while time.time() < deadline:
        users = subprocess.run(["pgrep", "-f", str(profile)], capture_output=True, text=True).stdout.split()
        if not users:
            return
        for pid in users:
            try:
                os.kill(int(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, ValueError):
                pass
        time.sleep(0.2)


def remove_tree(path):
    """Remove a directory, retrying while late writers finish; bounded so a test never hangs."""
    for _ in range(25):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(0.2)
    shutil.rmtree(path, ignore_errors=True)


@unittest.skipUnless(shutil.which("node") and shutil.which("pgrep") and find_chrome(), "node, pgrep and Chrome are required")
class CdpComposerTests(unittest.TestCase):
    def test_send_refuses_a_textarea_that_holds_a_draft(self):
        tmp = Path(tempfile.mkdtemp(prefix="cdp-composer-"))
        self.addCleanup(remove_tree, tmp)
        page = tmp / "composer.html"
        page.write_text(COMPOSER_PAGE)
        prompt = tmp / "prompt.txt"
        prompt.write_text("probe prompt")
        profile = tmp / "profile"
        port = free_port()
        chrome = subprocess.Popen(
            [find_chrome(), "--headless=new", f"--remote-debugging-port={port}",
             f"--user-data-dir={profile}", "--no-first-run", "--no-sandbox", page.as_uri()],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            env = {"CDP_PORT": str(port), "TAB": "composer.html"}
            deadline = time.time() + 20
            while time.time() < deadline:
                if run_cdp(env, "tabs").returncode == 0:
                    break
                time.sleep(0.5)
            result = run_cdp(env, "send", str(prompt))
            value = run_cdp(env, "eval", "document.getElementById('t').value").stdout.strip()
        finally:
            stop_browser(chrome, profile)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("composer is not empty", result.stdout)
        self.assertEqual(value, '"human draft"')


if __name__ == "__main__":
    unittest.main()
