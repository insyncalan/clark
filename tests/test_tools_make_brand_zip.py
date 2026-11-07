"""#944 T2: tools/make_brand_zip.py makes a brand zip that brands.review() accepts, the same bytes every time, and refuses
a bad folder with the same sentences review() gives. RED until tools/make_brand_zip.py and src/clark/brands.py exist.

The tool's input is a folder holding clark-brand.json ({"id", "name", "version"}, no file rows), tokens.css and assets/;
make(folder) -> bytes (the zip); main([folder, out_folder]) writes clark-brand-<id>-<version>.zip and returns 0.

Run: python3 dev/run_tests.py test_tools_make_brand_zip
"""
import hashlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import _brand_zips as bz
from _paths import ROOT

sys.path.insert(0, str(ROOT / "tools"))
try:
    from clark import brands
    import make_brand_zip as tool
    IMPORT_ERROR = None
except ImportError as e:                    # RED: neither module exists yet
    brands = tool = None
    IMPORT_ERROR = e


class Tool(unittest.TestCase):
    def setUp(self):
        self.assertIsNone(IMPORT_ERROR, "tools/make_brand_zip.py or src/clark/brands.py is missing: %s" % IMPORT_ERROR)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.src = self.base / "source"
        (self.src / "assets").mkdir(parents=True)
        self.out = self.base / "out"
        self.out.mkdir()
        (self.src / "clark-brand.json").write_text(json.dumps({"id": bz.BRAND_ID, "name": "Example Brand", "version": "1.0.0"}))
        (self.src / "tokens.css").write_bytes(bz.TOKENS_CSS)
        (self.src / "assets" / "cover.png").write_bytes(bz.COVER_PNG)
        (self.src / "assets" / "logo.png").write_bytes(bz.LOGO_PNG)

    def review(self, data):
        path = self.out / bz.zip_name()
        path.write_bytes(data)
        brands.clock = lambda: 1000.0
        self.addCleanup(lambda: setattr(brands, "clock", __import__("time").time))
        return brands.review(path, self.base / "app")

    def refused(self, key):
        with self.assertRaises(brands.BrandError) as cm:
            tool.make(self.src)
        self.assertEqual(cm.exception.key, key)
        self.assertEqual(cm.exception.message, brands.MESSAGES[key], "the same sentence review() gives")
        return cm.exception

    def test_round_trip_passes_review(self):
        got = self.review(tool.make(self.src))
        self.assertEqual((got["id"], got["name"], got["version"]), (bz.BRAND_ID, "Example Brand", "1.0.0"))
        self.assertEqual(set(got["added"]) - {bz.MANIFEST}, {bz.TOKENS, bz.COVER, bz.LOGO})

    def test_bytes_are_the_same_every_time(self):
        first = tool.make(self.src)
        for p in self.src.rglob("*"):
            os.utime(p, (1_900_000_000, 1_900_000_000))
        self.assertEqual(tool.make(self.src), first)

    def test_one_top_folder_unix_modes_and_every_file_has_a_row(self):
        with zipfile.ZipFile(io.BytesIO(tool.make(self.src))) as z:
            self.assertTrue(all(n.startswith(bz.BRAND_ID + "/") for n in z.namelist()))
            self.assertFalse([n for n in z.namelist() if n.endswith("/")], "no folder entries")
            for i in z.infolist():
                self.assertEqual(i.create_system, 3)
                self.assertIn(stat.S_IMODE(i.external_attr >> 16), (0o644, 0o755))
            man = json.loads(z.read(bz.BRAND_ID + "/clark-brand.json").decode())
            rows = {r["path"]: r for r in man["files"]}
            self.assertEqual(set(rows), {bz.TOKENS, bz.COVER, bz.LOGO})
            for path, r in rows.items():
                body = z.read(bz.BRAND_ID + "/" + path)
                self.assertEqual((r["size"], r["sha256"]), (len(body), hashlib.sha256(body).hexdigest()))
                self.assertEqual(r["mode"], "0644")
            self.assertEqual(man["id"], bz.BRAND_ID)

    def test_main_writes_the_named_zip_and_it_is_accepted(self):
        self.assertEqual(tool.main([str(self.src), str(self.out)]), 0)
        made = self.out / bz.zip_name()
        self.assertTrue(made.is_file())
        self.assertEqual(self.review(made.read_bytes())["id"], bz.BRAND_ID)

    def test_a_link_is_refused(self):
        os.symlink("/etc/passwd", self.src / "assets" / "logo-link.png")
        self.refused("link")

    def test_a_name_that_is_not_allowed_is_refused(self):
        (self.src / "assets" / "payload.exe").write_bytes(b"MZ")
        self.refused("file_name")

    def test_a_file_over_5_mb_is_refused(self):
        with open(self.src / "assets" / "cover-big.png", "wb") as f:
            f.truncate(bz.MEMBER_CAP + 1)
        self.refused("too_big")

    def test_a_picture_that_is_not_one_is_refused(self):
        (self.src / "assets" / "cover.png").write_bytes(bz.NOT_A_PICTURE)
        self.refused("picture")

    def test_a_deny_listed_word_is_refused_without_naming_it(self):
        word = next(w for w in brands.DENY_WORDS if w.isalnum() and w == w.lower())
        (self.src / "assets" / ("logo-%s.png" % word)).write_bytes(bz.COVER_PNG)
        err = self.refused("denied")
        self.assertNotIn(word, err.message.lower())

    def test_a_bad_id_is_refused(self):
        (self.src / "clark-brand.json").write_text(json.dumps({"id": "Bad_Id", "name": "n", "version": "1.0.0"}))
        with self.assertRaises(brands.BrandError) as cm:
            tool.make(self.src)
        self.assertEqual(cm.exception.key, "id")

    def test_the_tool_leaves_the_folder_alone(self):
        before = {str(p): p.read_bytes() for p in self.src.rglob("*") if p.is_file()}
        tool.make(self.src)
        self.assertEqual({str(p): p.read_bytes() for p in self.src.rglob("*") if p.is_file()}, before)


if __name__ == "__main__":
    unittest.main()
