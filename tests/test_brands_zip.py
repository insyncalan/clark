"""#944 T2: brands.review() refuses every hostile brand zip with one plain sentence and writes nothing. RED until
src/clark/brands.py exists. Zips come from tests/_brand_zips.py and are written to temp folders; nothing is allocated over
a few MB (big sizes are declared in the headers only).

Refusal keys are identifiers (the sentence for each is spec 944 section 2). Every zip-structure failure (encrypted, method 99,
zip64, overlap, bomb, lying size, comment, bad zip) is the update zip's "damaged" refusal, no new sentence.

Run: python3 dev/run_tests.py test_brands_zip
"""
import unittest
import warnings
import zipfile
import zlib
from unittest import mock

import _brand_zips as bz
from _brand_rig import branding, make_dirs, snapshot, write_zip

try:
    from clark import brands, updates
    IMPORT_ERROR = None
except ImportError as e:                    # RED: src/clark/brands.py does not exist yet
    brands = updates = None
    IMPORT_ERROR = e

# the refusal keys (identifiers) the builder's BrandError uses; the damaged-file refusal is the update zip's own
NAME, DAMAGED, TOO_BIG, TOO_MANY = "name", "damaged", "too_big", "too_many"
UNSAFE_NAME, LINK, MODE, FOLDER = "unsafe_name", "link", "mode", "folder"
ID, RESERVED, DENIED, MANIFEST = "id", "reserved", "denied", "manifest"
HASH, TOKENS, PICTURE, FILE_NAME, EXPIRED = "hash", "tokens", "picture", "file_name", "expired"


class Base(unittest.TestCase):
    def setUp(self):
        self.assertIsNone(IMPORT_ERROR, "src/clark/brands.py is missing: %s" % IMPORT_ERROR)
        self.root, self.data, self.scratch = make_dirs(self)
        self.before = snapshot(branding(self.root))
        brands.clock = lambda: 1000.0
        self.addCleanup(lambda: setattr(brands, "clock", __import__("time").time))

    def review(self, data, brand_id=bz.BRAND_ID, name=None):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return brands.review(write_zip(self.scratch, data, brand_id, name=name), self.root)

    def refused(self, data, key, brand_id=bz.BRAND_ID, name=None, msg=None):
        """review() raises BrandError with `key`, one sentence that holds no deny-list word and no path, and nothing is written."""
        with self.assertRaises(brands.BrandError, msg=msg) as cm:
            self.review(data, brand_id, name)
        err = cm.exception
        self.assertEqual(err.key, key, "%s: %s" % (msg, err.detail))
        self.assertTrue(err.message and isinstance(err.message, str))
        for word in brands.DENY_WORDS:
            self.assertNotIn(word.lower(), err.message.lower())
        self.assertNotIn(str(self.scratch), err.message)
        self.assertNotIn(str(self.root), err.message)
        self.assertEqual(snapshot(branding(self.root)), self.before, "nothing was written")
        self.assertEqual(list(self.data.iterdir()), [], "no backup was made either")
        return err


class Valid(Base):
    def test_valid_zip_reviews_clean(self):
        zdata = bz.valid()
        got = self.review(zdata)
        self.assertEqual(set(got), {"review_id", "id", "name", "version", "zip_sha256", "added", "replaced", "removed"})
        self.assertEqual((got["id"], got["name"], got["version"]), (bz.BRAND_ID, "Example Brand", "1.0.0"))
        import hashlib
        self.assertEqual(got["zip_sha256"], hashlib.sha256(zdata).hexdigest())
        self.assertEqual(set(got["added"]) - {bz.MANIFEST}, {bz.TOKENS, bz.COVER, bz.LOGO})
        self.assertEqual((got["replaced"], got["removed"]), ([], []))
        self.assertTrue(got["review_id"])
        self.assertEqual(snapshot(branding(self.root)), self.before)

    def test_other_pictures_and_a_data_font_are_accepted(self):
        for name, fn in (("jpeg", bz.valid_jpeg), ("webp", bz.valid_webp), ("data font", bz.valid_data_font),
                         ("50 entries", lambda: bz.exactly(50)), ("a 1 KB zip comment", lambda: bz.long_comment(1024)),
                         ("tokens at 256 KB", bz.tokens_at_256k), ("a 60 KB member at over 100x", bz.small_member_high_ratio),
                         ("mode 0755", lambda: bz.odd_mode(0o100755))):
            with self.subTest(name):
                self.assertTrue(self.review(fn())["review_id"])

    def test_the_ids_the_rules_allow(self):
        for brand_id in ("a", "a-1", "x" * 40, "0"):
            with self.subTest(brand_id):
                self.assertEqual(self.review(bz.with_id(brand_id), brand_id)["id"], brand_id)


class Names(Base):
    def test_zip_slip_four_ways(self):
        for name, fn in (("dot dot", bz.path_traversal), ("absolute", bz.absolute_path), ("backslash", bz.backslash_path),
                         ("drive letter", bz.drive_letter)):
            with self.subTest(name):
                self.refused(fn(), UNSAFE_NAME, msg=name)

    def test_any_zip_file_name_is_accepted_and_the_manifest_names_the_brand(self):
        for name in ("brand.zip", "clark-brand-%s.zip" % bz.BRAND_ID, "clark-brand-UPPER-1.0.0.zip", "My Kit (3).zip",
                     "clark-brand-another-brand-1.0.0.zip", "clark-update-1.0.0.zip"):
            with self.subTest(name):
                got = self.review(bz.valid(), name=name)
                self.assertEqual((got["id"], got["name"], got["version"]), (bz.BRAND_ID, "Example Brand", "1.0.0"))

    def test_duplicates_and_case_clash(self):
        self.refused(bz.duplicate_names(), UNSAFE_NAME, msg="duplicate")
        self.refused(bz.case_clash(), UNSAFE_NAME, msg="case clash")

    def test_one_top_folder_named_as_the_id(self):
        self.refused(bz.two_top_folders(), FOLDER, msg="two top folders")
        self.refused(bz.no_top_folder(), FOLDER, msg="no top folder")
        self.refused(bz.id_differs(), FOLDER, msg="manifest id differs from the folder")

    def test_id_rules(self):
        for label, brand_id in (("41 characters", "a" * 41), ("uppercase", "Brand"), ("underscore", "my_brand"), ("a space", "my brand")):
            with self.subTest(label):
                self.refused(bz.with_id(brand_id), ID, brand_id=brand_id, msg=label)
        for brand_id in bz.RESERVED_IDS:
            with self.subTest(brand_id):
                self.refused(bz.with_id(brand_id), RESERVED, brand_id=brand_id, msg=brand_id)
        self.refused(bz.manifest_edit(id=""), ID, msg="empty id in the manifest")


class Modes(Base):
    def test_symlink_member(self):
        self.refused(bz.symlink_member(), LINK)

    def test_odd_mode_not_unix_and_folder_entry(self):
        self.refused(bz.odd_mode(0o100666), MODE, msg="0666")
        self.refused(bz.odd_mode(0o104755), MODE, msg="setuid")
        self.refused(bz.not_unix(), MODE, msg="made on another system")
        self.refused(bz.link_dir_entry(), MODE, msg="a folder entry")


class Sizes(Base):
    def test_declared_over_the_member_cap(self):
        self.refused(bz.member_over_cap(), TOO_BIG)

    def test_file_count_boundary(self):
        self.assertTrue(self.review(bz.exactly(bz.FILE_COUNT_CAP))["review_id"])
        self.refused(bz.exactly(bz.FILE_COUNT_CAP + 1), TOO_MANY, msg="51")
        self.refused(bz.too_many_files(), TOO_MANY, msg="69")

    def test_the_count_comes_from_the_end_record_before_members_are_parsed(self):
        with mock.patch.object(zipfile.ZipFile, "infolist", side_effect=AssertionError("members were parsed")), \
                mock.patch.object(zipfile.ZipFile, "namelist", side_effect=AssertionError("members were parsed")):
            try:
                self.review(bz.too_many_files())
            except brands.BrandError as e:
                self.assertEqual(e.key, TOO_MANY)

    def test_a_file_on_disk_over_16_mb(self):
        path = self.scratch / bz.zip_name()
        with open(path, "wb") as f:
            f.truncate(bz.ZIP_CAP + 1)
        with self.assertRaises(brands.BrandError) as cm:
            brands.review(path, self.root)
        self.assertEqual(cm.exception.key, DAMAGED)
        self.assertEqual(cm.exception.message, updates.MESSAGES["damaged"])
        self.assertEqual(snapshot(branding(self.root)), self.before)

    def test_a_file_that_is_a_link_or_missing(self):
        real = write_zip(self.scratch, bz.valid(), name="real.zip")
        link = self.scratch / bz.zip_name()
        link.symlink_to(real)
        for path in (link, self.scratch / "clark-brand-gone-1.0.0.zip"):
            with self.subTest(path.name):
                with self.assertRaises(brands.BrandError):
                    brands.review(path, self.root)


class Bombs(Base):
    """Every zip-structure failure is the update zip's damaged-file refusal, with its exact sentence."""

    def damaged(self, data, msg):
        err = self.refused(data, DAMAGED, msg=msg)
        self.assertEqual(err.message, updates.MESSAGES["damaged"], msg)

    def recording(self):
        """Patch the reads of a member so the bytes handed out are counted; returns the list [total]."""
        total = [0]
        real_read, real_read1 = zipfile.ZipExtFile.read, zipfile.ZipExtFile.read1

        def counted(real):
            def read(this, *a, **k):
                got = real(this, *a, **k)
                total[0] += len(got)
                return got
            return read
        p1 = mock.patch.object(zipfile.ZipExtFile, "read", counted(real_read))
        p2 = mock.patch.object(zipfile.ZipExtFile, "read1", counted(real_read1))
        p1.start(), p2.start()
        self.addCleanup(p1.stop), self.addCleanup(p2.stop)
        return total

    def test_each_structure_failure_is_the_damaged_refusal(self):
        for name, fn in (("encrypted", bz.encrypted), ("method 99 (AES)", bz.method_99), ("method 12 (bzip2)", bz.method_12),
                         ("zip64", bz.zip64), ("overlapping members", bz.overlapping), ("a 1025 byte comment", bz.long_comment),
                         ("not a zip", lambda: b"PK\x03\x04 this is not a zip at all"), ("empty file", lambda: b"")):
            with self.subTest(name):
                self.damaged(fn(), name)

    def test_a_reader_that_raises_is_a_refusal_never_a_traceback(self):
        for exc in (RuntimeError("password required"), NotImplementedError("compression type 99"), zipfile.BadZipFile("bad"),
                    EOFError("eof"), zlib.error("bad data"), OSError("disk"), ValueError("value")):
            with self.subTest(type(exc).__name__):
                built = bz.valid()       # built before the patch: the injected error is the library's to meet, not the builder's
                with mock.patch.object(zipfile.ZipFile, "open", side_effect=exc), \
                        mock.patch.object(zipfile.ZipFile, "read", side_effect=exc), \
                        mock.patch.object(zipfile.ZipExtFile, "read", side_effect=exc):
                    self.damaged(built, type(exc).__name__)

    def test_a_member_over_64_kb_at_over_100x_is_refused_and_not_read_whole(self):
        total = self.recording()
        self.damaged(bz.bomb_ratio(), "per-member ratio")
        self.assertLess(total[0], 1024 * 1024, "refused before the member was held")

    def test_a_member_of_64_kb_or_less_at_over_100x_is_allowed(self):
        self.assertTrue(self.review(bz.small_member_high_ratio())["review_id"])

    def test_a_total_over_20x_is_refused(self):
        self.damaged(bz.total_ratio(), "total ratio")

    def test_total_unpacked_over_24_mb_by_the_central_directory_sum(self):
        total = self.recording()
        self.damaged(bz.total_unpacked_declared(), "declared total")
        self.assertEqual(total[0], 0, "refused from the headers, before any member was read")

    def test_total_unpacked_over_24_mb_by_the_bytes_actually_read(self):
        total = self.recording()
        self.damaged(bz.lying_total(), "actual total, declared sizes lie")
        self.assertLess(total[0], 5 * 1024 * 1024, "stopped counting at the first lie, long before 24 MB")

    def test_a_stream_longer_than_declared_stops_at_the_declared_size(self):
        total = self.recording()
        self.damaged(bz.stream_longer_than_declared(), "stream longer than declared")
        self.assertLess(total[0], 1024 * 1024)

    def test_an_unbounded_whole_member_read_is_not_used(self):
        asked = []
        real = zipfile.ZipExtFile.read

        def spy(this, n=-1):
            asked.append(n)
            return real(this, n)
        with mock.patch.object(zipfile.ZipExtFile, "read", spy):
            self.refused_quietly(bz.lying_total())
        self.assertTrue(all(isinstance(n, int) and n > 0 for n in asked), "every read is bounded: %r" % asked[:5])

    def refused_quietly(self, data):
        with self.assertRaises(brands.BrandError):
            self.review(data)

    def test_the_end_record_comment_boundary(self):
        self.assertTrue(self.review(bz.long_comment(bz.COMMENT_CAP))["review_id"])


class Manifest(Base):
    def test_manifest_cases(self):
        cases = (("a listed file is missing from the zip", bz.row_without_file, MANIFEST),
                 ("a file the manifest does not list", bz.extra_file_not_in_manifest, MANIFEST),
                 ("the logo is not listed", bz.manifest_missing_file, MANIFEST),
                 ("sha256 differs", bz.sha_mismatch, HASH), ("size differs", bz.size_mismatch, HASH),
                 ("bad version", lambda: bz.manifest_edit(version="1.0"), MANIFEST),
                 ("version is not a string", lambda: bz.manifest_edit(version=3), MANIFEST),
                 ("no name", lambda: bz.manifest_edit(name=None), MANIFEST),
                 ("no files", lambda: bz.manifest_edit(files=None), MANIFEST),
                 ("not JSON", lambda: bz.manifest_raw(b"not json"), MANIFEST),
                 ("a list, not an object", lambda: bz.manifest_raw(b"[]"), MANIFEST),
                 ("nested far too deep", bz.manifest_deep, MANIFEST), ("a 5000 digit number", bz.manifest_long_int, MANIFEST))
        for label, fn, key in cases:
            with self.subTest(label):
                self.refused(fn(), key, msg=label)

    def test_a_manifest_mode_that_is_not_the_files_is_refused(self):
        man = bz.manifest_for(bz.valid_members())
        man["files"][0]["mode"] = "0755"
        self.refused(bz.build(manifest=man), MANIFEST)


class Denied(Base):
    def word(self):
        for w in brands.DENY_WORDS:
            if w.isalnum() and w == w.lower():
                return w
        self.fail("brands.DENY_WORDS holds no plain lower-case word to build a file name from")

    def test_the_word_in_the_name_in_an_allowed_file_name_and_in_tokens(self):
        w = self.word()
        for label, data in (("name", bz.denied_brand_name(w)), ("file name", bz.denied_name(w)), ("tokens.css", bz.tokens_with_word(w)),
                            ("upper case", bz.denied_brand_name(w.upper()))):
            with self.subTest(label):
                err = self.refused(data, DENIED, msg=label)
                self.assertNotIn(w, err.message.lower())

    def test_the_file_name_is_allowed_but_for_the_word(self):
        self.assertTrue(self.review(bz.denied_name("fine"))["review_id"], "assets/logo-<word>.png is an allowed name")


class Tokens(Base):
    def test_refused(self):
        for label, fn in (("not UTF-8", bz.tokens_not_utf8), ("over 256 KB", bz.tokens_over_256k), ("over 1 MB", bz.tokens_over_1mb),
                          ("@import", bz.tokens_with_import), ("url() to an address", bz.tokens_with_url),
                          ("url() to a picture", bz.tokens_with_picture_url), ("@font-face from an address", bz.tokens_import_url_font),
                          ("</style> inside", bz.tokens_style_close)):
            with self.subTest(label):
                self.refused(fn(), TOKENS, msg=label)

    def test_check_brand_and_outside_addresses_both_run_on_a_style(self):
        from clark import publish
        seen = {}
        real_check, real_out = publish.check_brand, publish.outside_addresses
        mock_check = mock.patch.object(publish, "check_brand", lambda t: (seen.setdefault("check", t), real_check(t))[1])
        mock_out = mock.patch.object(publish, "outside_addresses", lambda t: (seen.setdefault("out", t), real_out(t))[1])
        with mock_check, mock_out:
            self.review(bz.valid())
        self.assertTrue(seen["check"].startswith("<style>") and seen["check"].endswith("</style>"))
        self.assertIn("out", seen)


class Pictures(Base):
    def test_refused(self):
        for label, fn in (("a GIF named .png", bz.not_a_picture), ("PNG with a bad CRC", bz.png_bad_crc), ("PNG over 1 MB", bz.png_over_1mb),
                          ("Excel picture over 2000 px", bz.png_too_wide), ("JPEG cut short", bz.jpeg_cut_short),
                          ("WebP with a wrong length", bz.webp_wrong_length)):
            with self.subTest(label):
                self.refused(fn(), PICTURE, msg=label)

    def test_a_name_outside_the_allowed_list(self):
        self.refused(bz.name_outside_list(), FILE_NAME)


class Held(Base):
    def test_a_review_is_held_15_minutes_and_by_one_id(self):
        got = self.review(bz.valid())
        self.assertNotEqual(got["review_id"], self.review(bz.valid())["review_id"], "each review has its own id")
        brands.clock = lambda: 1000.0 + 15 * 60 + 1
        with self.assertRaises(brands.BrandError) as cm:
            brands.install(got["review_id"], self.root, self.data)
        self.assertEqual(cm.exception.key, EXPIRED)
        with self.assertRaises(brands.BrandError) as cm:
            brands.install("no-such-review", self.root, self.data)
        self.assertEqual(cm.exception.key, EXPIRED)
        self.assertEqual(snapshot(branding(self.root)), self.before)

    def test_just_inside_15_minutes_still_installs(self):
        got = self.review(bz.valid())
        brands.clock = lambda: 1000.0 + 15 * 60 - 1
        brands.install(got["review_id"], self.root, self.data)
        self.assertEqual([b["id"] for b in brands.installed(self.root)], [bz.BRAND_ID])


if __name__ == "__main__":
    unittest.main()
