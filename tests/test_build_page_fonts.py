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
        return self.refusal()

    def refused_raw(self, text):
        (self.folder / "manifest.json").write_text(text, encoding="utf-8")
        return self.refusal()

    def refusal(self):
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
        self.assertIn("symbolic link) to something outside", self.refused(file="Link.woff2"))

    def test_non_font_renamed_woff2(self):
        (self.folder / "Fake.woff2").write_bytes(b"-----BEGIN " + b"PRIVATE KEY-----")
        self.assertIn("not a woff2 font (it may be another kind of file renamed to .woff2)", self.refused(file="Fake.woff2"))

    def test_wrong_extension(self):
        (self.folder / "Good.txt").write_bytes(b"wOF2")
        self.assertIn("must end in .woff2", self.refused(file="Good.txt"))

    def test_oversized(self):
        (self.folder / "Big.woff2").write_bytes(b"wOF2" + b"\0" * bp.MAX_FONT_BYTES)
        message = self.refused(file="Big.woff2")
        self.assertIn("bigger than 512 KB; use a smaller or trimmed (subset) version", message)
        self.assertNotIn("changed size", message)

    def test_a_typod_file_name_is_named(self):
        self.assertIn("'Goood.txt'", self.refused(file="Goood.txt"))

    def test_a_file_that_grows_while_read_has_its_own_wording(self):
        (self.folder / "Grow.woff2").write_bytes(b"wOF2" + b"\0" * bp.MAX_FONT_BYTES)
        self.manifest(file="Grow.woff2")
        real = os.stat

        def small(path, *a, **k):          # the size looks fine when checked; the file is bigger when read
            r = real(path, *a, **k)
            if str(path).endswith("Grow.woff2"):
                return mock.Mock(st_mode=r.st_mode, st_size=10)
            return r
        with mock.patch("build_page.os.stat", small), self.assertRaises(bp.FontManifestError) as ctx:
            bp.font_css([self.folder])
        self.assertIn("changed size while the build was reading it and is now over 512 KB; run the build again", str(ctx.exception))
        self.assertNotIn("bigger than", str(ctx.exception))

    def test_missing_file_and_directory(self):
        message = self.refused(file="Nope.woff2")
        self.assertIn("no file with that name is in the font's folder", message)
        self.assertIn("'Nope.woff2'", message)
        (self.folder / "Dir.woff2").mkdir()
        self.assertIn("a folder or another kind of item, not a font file", self.refused(file="Dir.woff2"))

    def test_a_symlink_to_a_file_in_the_same_folder_is_refused(self):
        try:
            os.symlink(self.folder / "Good.woff2", self.folder / "Alias.woff2")
        except (OSError, NotImplementedError):
            self.skipTest("cannot make a symlink here")
        message = self.refused(file="Alias.woff2")
        self.assertIn("symbolic link", message)
        self.assertNotIn("outside", message)

    def test_a_dangling_symlink_is_refused_as_not_there(self):
        try:
            os.symlink(self.folder / "Gone.woff2", self.folder / "Dangling.woff2")
        except (OSError, NotImplementedError):
            self.skipTest("cannot make a symlink here")
        self.assertIn("no file with that name is in the font's folder", self.refused(file="Dangling.woff2"))

    def test_a_dangling_symlink_to_outside_the_folder_is_refused_as_a_link_outside(self):
        try:
            os.symlink(self.tmp / "gone-outside.woff2", self.folder / "Out.woff2")
        except (OSError, NotImplementedError):
            self.skipTest("cannot make a symlink here")
        message = self.refused(file="Out.woff2")
        self.assertIn("symbolic link) to something outside", message)
        self.assertNotIn("gone-outside", message)

    def test_a_manifest_that_is_not_text_is_refused_as_text_not_as_json(self):
        (self.folder / "manifest.json").write_bytes(b'{"fonts": [], "package": "caf\xe9 \xff\xfe"}')       # Latin-1 bytes: not UTF-8
        message = self.refusal()
        self.assertIn("cannot be read as text", message)
        self.assertIn("UTF-8", message)
        self.assertNotIn("not valid JSON", message)

    def test_an_unknown_key_with_unusual_characters_is_refused_and_not_echoed_unsafely(self):
        odd = ("a" * 5000, "x" * 61, "two words", 'say "hi"', "it's", "caf\u00e9 \u65e5\u672c", "a/b", "a\\b", "C:x", "line\nbreak", "tab\there",
               "esc\x1b[31m", "csi\x9b31m", "nul\x00", "bidi\u202egnp", "sep\u2028x", "")
        item = dict(GOOD, file="Good.woff2")
        for key in odd:
            for where, body in (("manifest", {"fonts": [item], key: 1}), ("font", {"fonts": [dict(item, **{key: 1})]})):
                with self.subTest(key=key[:20], where=where):
                    message = self.refused_raw(json.dumps(body))
                    self.assertIn("is not a setting", message)
                    self.assertLess(len(message), 400, "a very long key is never echoed whole")
                    self.assertTrue(message.isprintable(), "no control, escape or line-break character reaches the message")
                    self.assertNotIn("\u202e", message)
        for key in ("two words", 'say "hi"', "caf\u00e9 \u65e5\u672c"):         # plain printable text is still named, so the fix is findable
            self.assertIn(f"'{key}'", self.refused_raw(json.dumps({"fonts": [item], key: 1})))
        self.assertIn("a key with unusual characters", self.refused_raw(json.dumps({"fonts": [item], "x" * 61: 1})))

    def test_an_unknown_key_in_a_font_is_refused_and_named(self):
        message = self.refused(extra="x")
        self.assertIn("'extra'", message)
        self.assertIn("font 1", message)

    def test_an_unknown_key_in_the_manifest_is_refused_and_named(self):
        item = dict(GOOD, file="Good.woff2")
        message = self.refused_raw(json.dumps({"fonts": [item], "extra": 1}))
        self.assertIn("'extra'", message)

    def test_the_files_and_package_keys_of_a_manifest_and_a_subset_are_allowed(self):
        item = dict(GOOD, file="Good.woff2", subset="latin")
        (self.folder / "manifest.json").write_text(json.dumps({"fonts": [item], "files": {}, "package": {"family": "Test"}}), encoding="utf-8")
        self.assertIn("@font-face", bp.font_css([self.folder]))

    def test_a_subset_that_is_not_a_plain_name_is_refused(self):
        for bad in ('latin; } body { x: y', "", 5, None, ["latin"], "Latin", "a" * 40):
            with self.subTest(subset=bad):
                self.assertIn("subset", self.refused(subset=bad))

    def test_a_file_that_is_not_a_name_is_refused(self):
        for bad in (None, 5, "", ["Good.woff2"], {"a": 1}, True):
            with self.subTest(file=bad):
                self.assertIn("'file' setting is empty or is not text", self.refused(file=bad))

    def test_a_missing_file_setting_is_refused(self):
        item = dict(GOOD)
        self.assertIn("'file' setting is empty or is not text", self.refused_raw(json.dumps({"fonts": [item]})))

    def test_a_manifest_that_is_not_an_object_with_a_list_of_font_objects_is_refused(self):
        item = dict(GOOD, file="Good.woff2")
        self.assertIn("one block of settings", self.refused_raw(json.dumps([item])))
        self.assertIn("one block of settings", self.refused_raw("5"))
        self.assertIn("no 'fonts' list", self.refused_raw(json.dumps({"files": {}})))
        self.assertIn("must be a list of fonts", self.refused_raw(json.dumps({"fonts": item})))
        self.assertIn("must be a list of fonts", self.refused_raw(json.dumps({"fonts": None})))
        for bad in ("x", 5, None, [item]):
            with self.subTest(entry=bad):
                message = self.refused_raw(json.dumps({"fonts": [bad]}))
                self.assertIn("font 1 is not a block of settings", message)

    def test_a_manifest_that_is_not_json_or_not_there_is_refused_in_its_own_words(self):
        self.assertIn("is not valid JSON", self.refused_raw("{not json"))
        (self.folder / "manifest.json").unlink()
        self.assertIn("is missing or cannot be opened", self.refusal())

    def test_each_field_refusal_says_what_is_allowed(self):
        self.assertIn("normal or italic", self.refused(style="bold"))
        self.assertIn("100, 200 ... 900", self.refused(weight="450"))
        self.assertIn("such as U+0000-00FF", self.refused(unicode_range="x"))
        self.assertIn("family is missing or has characters that are not allowed", self.refused(family="a;b"))

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
