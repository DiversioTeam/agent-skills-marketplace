import argparse
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "plugins"
    / "visual-explainer"
    / "skills"
    / "visual-explainer"
    / "scripts"
    / "publish_internal_share.py"
)
SPEC = importlib.util.spec_from_file_location("publish_internal_share", SCRIPT_PATH)
assert SPEC and SPEC.loader
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


class PublishInternalShareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.html_path = Path(self.temp_dir.name) / "explainer.html"
        self.html_path.write_text("<html><body>test</body></html>", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def response(status: int, location: str = "") -> subprocess.CompletedProcess[str]:
        headers = f"HTTP/2 {status}\n"
        if location:
            headers += f"location: {location}\n"
        return subprocess.CompletedProcess([], 0, stdout=headers, stderr="")

    def test_main_authenticates_before_upload(self) -> None:
        events = []

        def authenticate(_: str) -> None:
            events.append("authenticate")

        def upload(_: str, __: Path, ___: str) -> str:
            events.append("upload")
            return "https://internal-share.diversio.com/shared-explainer.html"

        args = argparse.Namespace(
            html_path=str(self.html_path),
            title="Shared explainer",
            open_url=False,
        )
        with (
            mock.patch.object(publisher, "parse_args", return_value=args),
            mock.patch.object(publisher.shutil, "which", return_value="cloudflared"),
            mock.patch.object(publisher, "authenticate", side_effect=authenticate),
            mock.patch.object(publisher, "upload", side_effect=upload),
            mock.patch("builtins.print"),
        ):
            result = publisher.main()

        self.assertEqual(result, 0)
        self.assertEqual(events, ["authenticate", "upload"])

    def test_authenticate_uses_quiet_login_and_inherits_output(self) -> None:
        completed = subprocess.CompletedProcess([], 0)

        with (
            mock.patch.object(publisher.subprocess, "run", return_value=completed) as run,
            mock.patch("builtins.print"),
        ):
            publisher.authenticate("cloudflared")

        run.assert_called_once_with(
            [
                "cloudflared",
                "access",
                "login",
                "--quiet",
                publisher.INTERNAL_SHARE_URL,
            ],
            timeout=600,
            check=False,
        )

    def test_authenticate_raises_when_login_fails(self) -> None:
        completed = subprocess.CompletedProcess([], 1)

        with (
            mock.patch.object(publisher.subprocess, "run", return_value=completed),
            mock.patch("builtins.print"),
        ):
            with self.assertRaisesRegex(publisher.PublishError, "did not complete"):
                publisher.authenticate("cloudflared")

    def test_upload_returns_location_from_303(self) -> None:
        completed = self.response(303, "/shared-explainer.html")

        with mock.patch.object(publisher, "run_upload", return_value=completed):
            url = publisher.upload("cloudflared", self.html_path, "shared-explainer.html")

        self.assertEqual(
            url,
            "https://internal-share.diversio.com/shared-explainer.html",
        )

    def test_rejects_missing_and_oversized_files(self) -> None:
        with self.assertRaisesRegex(publisher.PublishError, "was not found"):
            publisher.ensure_publishable(Path(self.temp_dir.name) / "missing.html")

        self.html_path.write_bytes(b"")
        with self.html_path.open("r+b") as file:
            file.truncate(publisher.MAX_UPLOAD_BYTES + 1)

        with self.assertRaisesRegex(publisher.PublishError, "up to 25 MB"):
            publisher.ensure_publishable(self.html_path)


if __name__ == "__main__":
    unittest.main()
