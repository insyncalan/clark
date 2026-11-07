"""The #944 brand-zip fixtures (tests/_brand_zips.py) really contain what their names say."""
import hashlib
import io
import json
import stat
import struct
import unittest
import warnings
import zipfile

import _paths  # noqa: F401
import _brand_zips as bz


def _open(data):
    return zipfile.ZipFile(io.BytesIO(data))


def _manifest(z):
    return json.loads(z.read(bz.MANIFEST).decode("utf-8"))


def _names(data):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with _open(data) as z:
            return z.namelist()


class ValidBrand(unittest.TestCase):
    def test_valid_is_honest(self):
        with _open(bz.valid()) as z:
            self.assertIsNone(z.testzip())
            top = bz.BRAND_ID + "/"
            self.assertTrue(all(n.startswith(top) for n in z.namelist()), "one top folder")
            man = json.loads(z.read(top + bz.MANIFEST).decode("utf-8"))
            self.assertEqual(sorted(man), ["files", "id", "name", "version"])
            self.assertEqual(man["id"], bz.BRAND_ID)
            listed = {f["path"]: f for f in man["files"]}
            self.assertEqual(sorted(listed), sorted(n[len(top):] for n in z.namelist() if n != top + bz.MANIFEST))
            for path, f in listed.items():
                body = z.read(top + path)
                self.assertEqual(f["size"], len(body))
                self.assertEqual(f["sha256"], hashlib.sha256(body).hexdigest())
                self.assertEqual(f["mode"], "0644")
                self.assertEqual(z.getinfo(top + path).external_attr >> 16, 0o100644)
            self.assertTrue(z.read(top + "assets/cover.png").startswith(b"\x89PNG\r\n\x1a\n"))
            css = z.read(top + "tokens.css").decode()
            self.assertIn(":root", css)
            self.assertNotIn("url(", css)

    def test_deterministic(self):
        self.assertEqual(bz.valid(), bz.valid())
        for name, fn in bz.HOSTILE.items():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.assertEqual(fn(), fn(), name)

    def test_dates_fixed_and_sorted(self):
        with _open(bz.valid()) as z:
            self.assertTrue(all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in z.infolist()))
            rest = [n for n in z.namelist() if not n.endswith(bz.MANIFEST)]
            self.assertEqual(rest, sorted(rest))

    def test_counts_at_the_boundary(self):
        self.assertEqual(len(_names(bz.exactly(bz.FILE_COUNT_CAP))), 50)
        self.assertEqual(len(_names(bz.exactly(bz.FILE_COUNT_CAP + 1))), 51)
        self.assertGreater(len(_names(bz.too_many_files())), 51)

    def test_the_other_valid_pictures(self):
        self.assertIn("example-brand/assets/cover.jpg", _names(bz.valid_jpeg()))
        self.assertIn("example-brand/assets/cover.webp", _names(bz.valid_webp()))
        self.assertEqual(bz.WEBP[4:8], struct.pack("<I", len(bz.WEBP) - 8))
        self.assertNotEqual(bz.WEBP_WRONG_LENGTH[4:8], bz.WEBP[4:8])
        self.assertTrue(bz.JPEG.endswith(b"\xff\xd9") and not bz.JPEG_CUT.endswith(b"\xff\xd9"))


class HostileBrands(unittest.TestCase):
    def test_all_open_as_zips_or_say_why_not(self):
        for name, fn in bz.HOSTILE.items():
            with self.subTest(name):
                try:
                    _names(fn())
                except zipfile.BadZipFile:
                    self.assertIn(name, ("zip64",), "only zip64 may fail to open")

    def test_names(self):
        self.assertIn("example-brand/../x", _names(bz.path_traversal()))
        self.assertTrue(any(n.startswith("/") for n in _names(bz.absolute_path())))
        self.assertIn("example-brand/C:evil.png", _names(bz.drive_letter()))
        self.assertTrue(any("\\" in n for n in _names(bz.backslash_path())))
        self.assertEqual(_names(bz.duplicate_names()).count("example-brand/assets/logo.png"), 2)
        lowered = [n.lower() for n in _names(bz.case_clash())]
        self.assertEqual(len(lowered) - len(set(lowered)), 1)
        self.assertEqual(len({n.split("/")[0] for n in _names(bz.two_top_folders())}), 2)
        self.assertNotIn("example-brand/clark-brand.json", _names(bz.no_top_folder()))
        self.assertIn("clark-brand.json", _names(bz.no_top_folder()))
        self.assertIn("example-brand/assets/", _names(bz.link_dir_entry()))

    def test_modes_and_system(self):
        with _open(bz.symlink_member()) as z:
            self.assertTrue(stat.S_ISLNK(z.getinfo("example-brand/assets/link.png").external_attr >> 16))
        with _open(bz.odd_mode(0o4755)) as z:
            self.assertEqual(z.getinfo("example-brand/assets/cover.png").external_attr >> 16, 0o4755)
        with _open(bz.not_unix()) as z:
            self.assertEqual({i.create_system for i in z.infolist()}, {0})

    def test_sizes_declared_only(self):
        for fn in (bz.member_over_cap, bz.total_unpacked_declared):
            self.assertLess(len(fn()), 12000)
        with _open(bz.member_over_cap()) as z:
            self.assertEqual(z.getinfo("example-brand/assets/big.png").file_size, bz.MEMBER_CAP + 1)
        with _open(bz.total_unpacked_declared()) as z:
            self.assertGreater(sum(i.file_size for i in z.infolist()), bz.TOTAL_CAP)
            self.assertTrue(all(i.file_size <= bz.MEMBER_CAP for i in z.infolist()))
        with _open(bz.lying_total()) as z:
            self.assertLess(sum(i.file_size for i in z.infolist()), 20000)
            self.assertGreater(len(bz.lying_total()), 1000)

    def test_ratios(self):
        def ratio(data, name=None):
            with _open(data) as z:
                infos = [i for i in z.infolist() if name is None or i.filename.endswith(name)]
                return sum(i.file_size for i in infos) / sum(i.compress_size for i in infos)
        with _open(bz.bomb_ratio()) as z:
            i = z.getinfo("example-brand/tokens.css")
            self.assertGreater(i.file_size, 64 * 1024)
            self.assertGreater(i.file_size / i.compress_size, 100)
        self.assertLess(ratio(bz.bomb_ratio()), 20, "only the member is hostile, not the total")
        with _open(bz.small_member_high_ratio()) as z:
            i = z.getinfo("example-brand/tokens.css")
            self.assertLessEqual(i.file_size, 64 * 1024)
            self.assertGreater(i.file_size / i.compress_size, 100)
        self.assertLess(ratio(bz.small_member_high_ratio()), 20)
        self.assertGreater(ratio(bz.total_ratio()), 20)
        with _open(bz.total_ratio()) as z:
            self.assertTrue(all(i.file_size <= 64 * 1024 for i in z.infolist()))
        with _open(bz.stream_longer_than_declared()) as z:
            self.assertEqual(z.getinfo("example-brand/assets/cover.png").file_size, 100)

    def test_structure_patches(self):
        with _open(bz.encrypted()) as z:
            self.assertTrue(z.getinfo("example-brand/assets/cover.png").flag_bits & 1)
        with _open(bz.method_99()) as z:
            self.assertEqual(z.getinfo("example-brand/assets/cover.png").compress_type, 99)
        with _open(bz.method_12()) as z:
            self.assertEqual(z.getinfo("example-brand/assets/cover.png").compress_type, 12)
        with _open(bz.overlapping()) as z:
            self.assertEqual(z.getinfo("example-brand/assets/logo.png").header_offset, z.getinfo("example-brand/assets/cover.png").header_offset)
        with _open(bz.long_comment()) as z:
            self.assertEqual(len(z.comment), 1025)
        with _open(bz.long_comment(1024)) as z:
            self.assertEqual(len(z.comment), 1024)

    def test_manifest_cases(self):
        def man(data):
            with _open(data) as z:
                return json.loads(z.read("example-brand/clark-brand.json").decode())
        self.assertEqual(man(bz.id_differs())["id"], "other-brand")
        self.assertEqual(man(bz.manifest_edit(version=3))["version"], 3)
        self.assertNotIn("id", man(bz.manifest_edit(id=None)))
        self.assertTrue(any(f["size"] != 0 for f in man(bz.size_mismatch())["files"]))
        self.assertIn("assets/cover-9.png", [f["path"] for f in man(bz.row_without_file())["files"]])
        with _open(bz.with_id("generic")) as z:
            self.assertEqual(json.loads(z.read("generic/clark-brand.json").decode())["id"], "generic")
        with _open(bz.manifest_deep()) as z:
            self.assertIn(b"[[[[", z.read("example-brand/clark-brand.json"))

    def test_sha_and_listing(self):
        with _open(bz.sha_mismatch()) as z:
            man = json.loads(z.read("example-brand/clark-brand.json").decode())
            bad = [f for f in man["files"] if hashlib.sha256(z.read("example-brand/" + f["path"])).hexdigest() != f["sha256"]]
            self.assertEqual(len(bad), 1)
        with _open(bz.manifest_missing_file()) as z:
            man = json.loads(z.read("example-brand/clark-brand.json").decode())
            self.assertNotIn(bz.LOGO, [f["path"] for f in man["files"]])
            self.assertIn("example-brand/" + bz.LOGO, z.namelist())
        with _open(bz.extra_file_not_in_manifest()) as z:
            self.assertIn("example-brand/assets/extra.png", z.namelist())

    def test_tokens(self):
        def css(data):
            with _open(data) as z:
                return z.read("example-brand/tokens.css")
        self.assertIn(b"url(http://", css(bz.tokens_with_url()))
        self.assertIn(b"@import", css(bz.tokens_with_import()))
        self.assertIn(b"body {", css(bz.tokens_with_rules()))
        self.assertIn(b"</style>", css(bz.tokens_style_close()))
        self.assertIn(b"src: url(http://", css(bz.tokens_import_url_font()))
        self.assertIn(b"url(data:image", css(bz.tokens_with_picture_url()))
        self.assertIn(b"url(data:font", css(bz.valid_data_font()))
        with self.assertRaises(UnicodeDecodeError):
            css(bz.tokens_not_utf8()).decode("utf-8")
        self.assertEqual(len(css(bz.tokens_over_256k())), bz.TOKENS_CAP + 1)
        self.assertEqual(len(css(bz.tokens_at_256k())), bz.TOKENS_CAP)
        self.assertEqual(len(css(bz.tokens_over_1mb())), 1024 * 1024 + 1)
        self.assertIn(b"apple", css(bz.tokens_with_word("apple")))
        self.assertLess(len(bz.tokens_over_1mb()), bz.ZIP_CAP)

    def test_pictures(self):
        with _open(bz.not_a_picture()) as z:
            body = z.read("example-brand/assets/cover.png")
            self.assertFalse(body.startswith((b"\x89PNG", b"\xff\xd8\xff", b"RIFF")))
        with _open(bz.png_bad_crc()) as z:
            body = z.read("example-brand/assets/cover.png")
            self.assertNotEqual(body, bz.COVER_PNG)
            self.assertEqual(len(body), len(bz.COVER_PNG))
        with _open(bz.png_over_1mb()) as z:
            self.assertGreater(len(z.read("example-brand/assets/cover.png")), bz.PICTURE_CAP)
        with _open(bz.png_too_wide()) as z:
            self.assertEqual(struct.unpack(">I", z.read("example-brand/assets/logo.png")[16:20])[0], 2001)
        self.assertIn("example-brand/assets/payload.exe", _names(bz.name_outside_list()))
        self.assertIn("example-brand/assets/logo-apple.png", _names(bz.denied_name("apple")))
        with _open(bz.denied_brand_name("apple")) as z:
            self.assertIn("apple", json.loads(z.read("example-brand/clark-brand.json").decode())["name"])


if __name__ == "__main__":
    unittest.main()
