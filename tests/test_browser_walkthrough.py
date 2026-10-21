"""Local-only capture helper checks; real encoding when FFmpeg is installed."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/browser-walkthrough-recording/skills/browser-walkthrough-recording/scripts"


class CaptureTests(unittest.TestCase):
    def test_local_url_and_reading_time(self):
        subprocess.run(
            ["node", "-e", """
const assert = require('node:assert/strict');
const helpers = require(process.argv[1]);
for (const address of ['http://localhost:8000', 'http://demo.localhost', 'http://127.0.0.1', 'http://[::1]']) {
  assert.ok(helpers.validate_local_url(address));
}
for (const address of ['https://production.example.com', 'file:///tmp/a', 'http://localhost.evil.test', 'http://user:secret@localhost']) {
  assert.throws(() => helpers.validate_local_url(address));
}
assert.equal(helpers.get_caption_duration('One short caption'), 2500);
assert.equal(helpers.get_caption_duration('word '.repeat(20)), 7000);
""", str(SCRIPTS / "capture-template.cjs")],
            check=True,
        )

    def test_missing_encoder_tools_have_actionable_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.webm"
            source.touch()
            output = Path(directory) / "output.mp4"
            tools = Path(directory) / "bin"
            tools.mkdir()
            command = [shutil.which("bash"), str(SCRIPTS / "to-mp4.sh"), str(source), str(output)]
            for missing in ("ffmpeg", "ffprobe"):
                with self.subTest(missing=missing):
                    result = subprocess.run(
                        command, env={"PATH": str(tools)}, capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(f"Missing {missing}: install", result.stderr)
                    self.assertIn("PATH", result.stderr)
                    self.assertFalse(output.exists())
                    self.assertTrue(source.exists())
                    self.assertFalse(list(Path(directory).glob(".walkthrough-encode.*")))
                # The second pass has ffmpeg on PATH but no ffprobe.
                if missing == "ffmpeg":
                    (tools / "ffmpeg").symlink_to(shutil.which("true"))

    def test_invalid_encoder_arguments(self):
        result = subprocess.run(["bash", str(SCRIPTS / "to-mp4.sh")], capture_output=True)
        self.assertEqual(result.returncode, 2)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class EncoderTests(unittest.TestCase):
    def test_encoding_preserves_source_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.webm"
            output = Path(directory) / "output.mp4"
            subprocess.run([
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                "color=c=blue:s=320x180:r=10:d=0.5", "-c:v", "libvpx-vp9", str(source),
            ], check=True)
            command = ["bash", str(SCRIPTS / "to-mp4.sh"), str(source), str(output)]
            subprocess.run(command, check=True, capture_output=True)
            self.assertTrue(source.exists())
            original = output.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), original)
            details = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output),
            ]))
            self.assertEqual(len(details["streams"]), 1)
            self.assertEqual(details["streams"][0]["codec_name"], "h264")
            self.assertEqual(details["streams"][0]["pix_fmt"], "yuv420p")
            self.assertFalse(list(Path(directory).glob(".walkthrough-encode.*")))

    def test_failed_encoding_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "invalid.webm"
            source.write_text("not a video")
            output = Path(directory) / "output.mp4"
            result = subprocess.run(
                ["bash", str(SCRIPTS / "to-mp4.sh"), str(source), str(output)], capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            self.assertTrue(source.exists())
            self.assertFalse(list(Path(directory).glob(".walkthrough-encode.*")))


if __name__ == "__main__":
    unittest.main()
