"""#236: build_page.py takes a font manifest as data. A manifest that points outside its own font folder, at something that is
not a font, or at something too big stops the build in plain words and no page is written.

Run: python3 dev/run_tests.py test_build_page_fonts
Everything is built in a temporary folder; the "secret" is a made-up file. Runs on Python 3.9 and later.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401  (puts dev/tools/ on the path)
import build_page as bp

GOOD = {"family": "Test Sans", "style": "normal", "weight": "400", "unicode_range": "U+0000-00FF, U+0131"}


class FontManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.folder = self.tmp / "fonts" / "test"
        self.folder.mkdir(parents=True)
        (self.folder / "Good.woff2").write_bytes(b"wOF2" + b"\0" * 100)
        self.secret = self.tmp / "secret.txt"
        self.secret.write_bytes(b"wOF2 pretend outside file")      # even with a font signature, outside the folder is refused

    def manifest(self, **entry):
        item = dict(GOOD, file="Good.woff2")
        item.update(entry)
        (self.folder / "manifest.json").write_text(json.dumps({"fonts": [item]}), encoding="utf-8")

    def refused(self, **entry):
        self.manifest(**entry)
        with self.assertRaises(bp.FontManifestError) as ctx:
            bp.font_css([self.folder])
        message = str(ctx.exception)
        self.assertNotIn(str(self.tmp), message, "the error names the manifest entry, never a resolved path")
        self.assertIn("manifest.json", message)
        return message

    def test_a_normal_manifest_builds(self):
        self.manifest()
        css = bp.font_css([self.folder])
        self.assertIn("@font-face", css)
        self.assertIn("data:font/woff2;base64,", css)

    def test_absolute_path(self):
        self.assertIn("absolute", self.refused(file=str(self.secret)))

    def test_dot_dot(self):
        self.assertIn("'..'", self.refused(file="../../secret.txt"))

    def test_sub_folder(self):
        (self.folder / "sub").mkdir()
        (self.folder / "sub" / "A.woff2").write_bytes(b"wOF2")
        self.assertIn("sub-folder", self.refused(file="sub/A.woff2"))

    def test_symlink_out(self):
        link = self.folder / "Link.woff2"
        try:
            os.symlink(self.secret, link)
        except (OSError, NotImplementedError):
            self.skipTest("cannot make a symlink here")
        self.assertIn("link", self.refused(file="Link.woff2"))

    def test_non_font_renamed_woff2(self):
        (self.folder / "Fake.woff2").write_bytes(b"-----BEGIN " + b"PRIVATE KEY-----")
        self.assertIn("not a woff2 font", self.refused(file="Fake.woff2"))

    def test_wrong_extension(self):
        (self.folder / "Good.txt").write_bytes(b"wOF2")
        self.assertIn("woff2 font name", self.refused(file="Good.txt"))

    def test_oversized(self):
        (self.folder / "Big.woff2").write_bytes(b"wOF2" + b"\0" * bp.MAX_FONT_BYTES)
        self.assertIn("too big", self.refused(file="Big.woff2"))

    def test_missing_file_and_directory(self):
        self.assertIn("not there", self.refused(file="Nope.woff2"))
        (self.folder / "Dir.woff2").mkdir()
        self.assertIn("not a regular file", self.refused(file="Dir.woff2"))

    def test_css_injection_in_each_field(self):
        for field, bad in (("family", 'x"; } body { display:none } @font-face { font-family: "y'), ("style", "normal; x: y"),
                           ("weight", "400; x: y"), ("unicode_range", "U+0000; } body { x: y")):
            with self.subTest(field=field):
                self.assertIn(field, self.refused(**{field: bad}))

    def test_a_refused_font_writes_no_page(self):
        self.manifest(file=str(self.secret))
        out, out_view = self.tmp / "page.html", self.tmp / "page-view.html"
        out.write_text("old", encoding="utf-8")
        with mock.patch.object(bp, "FONTS", (self.folder,)), mock.patch.object(bp, "OUT", out), \
                mock.patch.object(bp, "OUT_VIEW", out_view), mock.patch.object(bp, "bundle", return_value=""), \
                mock.patch("sys.stderr"):
            self.assertEqual(bp.main([]), 1)
        self.assertEqual(out.read_text(encoding="utf-8"), "old")
        self.assertFalse(out_view.exists())

    def test_the_real_repo_is_clean(self):
        self.assertEqual(bp.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
