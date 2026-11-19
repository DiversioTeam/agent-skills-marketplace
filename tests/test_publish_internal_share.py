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
        self.html_path.write_text((SCRIPT_PATH.parents[1] / "templates" / "diagram.html").read_text(encoding="utf-8"), encoding="utf-8")

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

    def test_the_checked_copy_is_the_one_uploaded(self) -> None:
        passing = self.html_path.read_text(encoding="utf-8")
        uploaded = []

        def authenticate(_: str) -> None:
            # Someone saves an unfinished revision while the browser sign-in is open.
            self.html_path.write_text("<p>unfinished revision</p>", encoding="utf-8")

        def upload(_: str, staged: Path, __: str) -> str:
            uploaded.append(staged.read_text(encoding="utf-8"))
            return "https://internal-share.diversio.com/shared-explainer.html"

        args = argparse.Namespace(html_path=str(self.html_path), title="Shared explainer", open_url=False)
        with (
            mock.patch.object(publisher, "parse_args", return_value=args),
            mock.patch.object(publisher.shutil, "which", return_value="cloudflared"),
            mock.patch.object(publisher, "authenticate", side_effect=authenticate),
            mock.patch.object(publisher, "upload", side_effect=upload),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(publisher.main(), 0)
        self.assertEqual(uploaded, [passing])

    def test_a_missing_page_checker_is_a_clear_message(self) -> None:
        with mock.patch.object(publisher, "__file__", str(Path(self.temp_dir.name) / "publish_internal_share.py")):
            with self.assertRaises(publisher.PublishError) as raised:
                publisher.load_page_checker()
        self.assertIn("reinstall the visual-explainer plugin", str(raised.exception))

    def test_main_refuses_a_page_below_the_standard_before_signing_in(self) -> None:
        self.html_path.write_text("<html><body><h2>Details</h2><p>test</p></body></html>", encoding="utf-8")
        args = argparse.Namespace(html_path=str(self.html_path), title="Shared explainer", open_url=False)
        printed = []
        with (
            mock.patch.object(publisher, "parse_args", return_value=args),
            # Without cloudflared, as on CI: the page feedback must still come first.
            mock.patch.object(publisher.shutil, "which", return_value=None),
            mock.patch.object(publisher, "authenticate") as authenticate,
            mock.patch.object(publisher, "upload") as upload,
            mock.patch("builtins.print", side_effect=lambda *values, **_: printed.append(" ".join(map(str, values)))),
        ):
            result = publisher.main()

        self.assertEqual(result, 1)
        authenticate.assert_not_called()
        upload.assert_not_called()
        output = "\n".join(printed)
        self.assertIn("The page was not uploaded", output)
        self.assertIn("Start with the answer", output)
        self.assertIn("prefers-color-scheme: dark", output)

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

    def test_main_refuses_an_oversized_source_before_copying_it(self) -> None:
        self.html_path.write_bytes(b"")
        with self.html_path.open("r+b") as file:
            file.truncate(publisher.MAX_UPLOAD_BYTES + 1)
        args = argparse.Namespace(html_path=str(self.html_path), title="Shared explainer", open_url=False)
        printed = []
        with (
            mock.patch.object(publisher, "parse_args", return_value=args),
            mock.patch.object(publisher.shutil, "copy2") as copy2,
            mock.patch.object(publisher, "authenticate") as authenticate,
            mock.patch("builtins.print", side_effect=lambda *values, **_: printed.append(" ".join(map(str, values)))),
        ):
            self.assertEqual(publisher.main(), 1)
        copy2.assert_not_called()
        authenticate.assert_not_called()
        self.assertIn("up to 25 MB", "\n".join(printed))

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
