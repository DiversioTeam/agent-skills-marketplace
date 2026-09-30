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

    def test_upload_returns_location_from_303(self) -> None:
        completed = self.response(303, "/shared-explainer.html")

        with mock.patch.object(publisher, "run_upload", return_value=completed):
            url = publisher.upload("cloudflared", self.html_path, "shared-explainer.html")

        self.assertEqual(
            url,
            "https://internal-share.diversio.com/shared-explainer.html",
        )

    def test_upload_authenticates_once_and_retries(self) -> None:
        login_redirect = self.response(302, "https://example.cloudflareaccess.com/login")
        uploaded = self.response(303, "/shared-explainer.html")

        with (
            mock.patch.object(
                publisher,
                "run_upload",
                side_effect=[login_redirect, uploaded],
            ) as run_upload,
            mock.patch.object(publisher, "authenticate") as authenticate,
            mock.patch("builtins.print"),
        ):
            url = publisher.upload("cloudflared", self.html_path, "shared-explainer.html")

        self.assertEqual(url, "https://internal-share.diversio.com/shared-explainer.html")
        authenticate.assert_called_once_with("cloudflared")
        self.assertEqual(run_upload.call_count, 2)

    def test_upload_fails_when_authentication_does_not_complete(self) -> None:
        login_redirect = self.response(302, "https://example.cloudflareaccess.com/login")

        with (
            mock.patch.object(publisher, "run_upload", return_value=login_redirect),
            mock.patch.object(publisher, "authenticate"),
            mock.patch("builtins.print"),
        ):
            with self.assertRaisesRegex(publisher.PublishError, "did not complete"):
                publisher.upload("cloudflared", self.html_path, "shared-explainer.html")

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
