"""#944 T2, the reader's findings on PR 957: every way a brand action can fail ends in the library's own refusal, and the
listing tells the truth about Undo. Real library, real server, temp folders only.

  - a zip cut short at its end record is the damaged-file refusal, not a raw struct.error
  - GET /api/brands says undo true after an install or a remove, false when there is nothing (or nothing valid) to put back
  - "from downloads" takes the newest of the last few zips that holds a brand manifest, whatever its name
  - an OSError in a write path (or in recover, or the file choice) is the "failed" refusal, with a stated state left behind
  - a member after a 12-byte data descriptor (no signature) is not an overlap

Run: python3 dev/run_tests.py test_brands_refusals
"""
import json
import os
import struct
import unittest
import zlib
from pathlib import Path
from unittest import mock

import _brand_zips as bz
from _brand_rig import branding, make_dirs, snapshot, write_zip
from test_brand_routes import Rig

from clark import brands, server as sv, updates


class Base(unittest.TestCase):
    def setUp(self):
        self.root, self.data, self.scratch = make_dirs(self)
        self.downloads = self.scratch / "Downloads"
        self.downloads.mkdir()
        self.picked = []
        self.rig = Rig(self, library=False)
        self.rig.httpd.brands = sv.BrandLibrary(self.root, self.data, choose=lambda *a, **k: self.picked[0] if self.picked else None,
                                                downloads=self.downloads)
        self.now = [1000.0]
        brands.clock = lambda: self.now[0]
        self.addCleanup(lambda: setattr(brands, "clock", __import__("time").time))
        self.addCleanup(lambda: setattr(brands, "after_write", None))

    def post(self, what, body=None):
        return self.rig.call("POST", "/api/brands/" + what, {} if body is None else body)

    def listing(self):
        status, got = self.rig.call("GET", "/api/brands")
        self.assertEqual(status, 200, got)
        return got

    def install(self, version="1.0.0", data=None):
        path = write_zip(self.scratch, data or bz.valid(), version=version)
        self.picked[:] = [path]
        status, got = self.post("review", {"from": "file"})
        self.assertEqual((status, got["ok"]), (200, True), got)
        status, got = self.post("install", {"review_id": got["review"]["review_id"]})
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.now[0] += 3600

    def failed(self, status_got, key):
        status, got = status_got
        self.assertEqual((status, got["ok"], got["code"]), (400, False, key), got)
        self.assertEqual(got["message"], brands.MESSAGES[key])
        return got


class EndRecord(Base):
    def test_a_file_ending_in_a_cut_short_end_record_is_the_damaged_refusal(self):
        for name, tail in (("signature only", b"PK\x05\x06"), ("signature and 5 bytes", b"PK\x05\x06" + bytes(5)),
                           ("signature and 21 bytes", b"PK\x05\x06" + bytes(17))):
            with self.subTest(name):
                path = self.scratch / ("clark-brand-%s-1.0.0.zip" % bz.BRAND_ID)
                path.write_bytes(os.urandom(200).replace(b"PK", b"xx") + tail)
                self.picked[:] = [path]
                got = self.failed(self.post("review", {"from": "file"}), "damaged")
                self.assertEqual(got["message"], updates.MESSAGES["damaged"])
                with self.assertRaises(brands.BrandError) as cm:       # and the library itself, not only the route
                    brands.review(path, self.root)
                self.assertEqual(cm.exception.key, "damaged")


class Undo(Base):
    def test_the_listing_says_undo_after_an_install_and_a_remove_and_not_before_or_after_the_undo(self):
        self.assertFalse(self.listing()["undo"])
        self.install()
        self.assertTrue(self.listing()["undo"])
        self.assertEqual([b["id"] for b in self.listing()["brands"]], [bz.BRAND_ID])
        self.assertEqual(self.post("undo")[0], 200)
        self.assertFalse(self.listing()["undo"])
        self.install()
        self.assertEqual(self.post("remove", {"id": bz.BRAND_ID})[0], 200)
        self.assertTrue(self.listing()["undo"])
        self.assertEqual(self.post("undo")[0], 200)
        self.assertFalse(self.listing()["undo"])

    def test_a_journal_that_is_not_valid_is_no_undo(self):
        journal = self.data / brands.JOURNAL
        for text in ("{nope", "[1]", json.dumps({"kind": "other", "id": bz.BRAND_ID}), json.dumps({"kind": "install", "id": "../x"}),
                     json.dumps({"kind": "remove", "id": bz.BRAND_ID, "backup": "gone-%s" % bz.BRAND_ID})):
            with self.subTest(text):
                journal.write_text(text, encoding="utf-8")
                self.assertFalse(self.listing()["undo"])
                self.assertFalse(brands.can_undo(self.root, self.data))


def _plain_zip(path):
    import zipfile
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("holiday/photo.txt", "not a brand")
    return path


class FromDownloads(Base):
    def test_the_newest_zip_holding_a_brand_manifest_is_taken_whatever_it_is_called(self):
        good = write_zip(self.downloads, bz.valid(), name="my kit.zip")
        os.utime(good, (100, 100))
        for name in ("holiday-photos.zip", "clark-brand-x.zip"):
            other = _plain_zip(self.downloads / name)
            os.utime(other, (500, 500))
        status, got = self.post("review", {"from": "downloads"})
        self.assertEqual((status, got["ok"], got["review"]["id"]), (200, True, bz.BRAND_ID), got)

    def test_a_newer_brand_zip_wins_over_an_older_one(self):
        old = write_zip(self.downloads, bz.valid(), name="old.zip")
        os.utime(old, (100, 100))
        new = write_zip(self.downloads, bz.valid(), name="new.zip")
        os.utime(new, (300, 300))
        with mock.patch.object(brands, "review", wraps=brands.review) as spy:
            self.assertEqual(self.post("review", {"from": "downloads"})[0], 200)
        self.assertEqual(Path(spy.call_args[0][0]).name, "new.zip")

    def test_only_the_newest_few_zips_are_looked_at(self):
        good = write_zip(self.downloads, bz.valid(), name="kit.zip")
        os.utime(good, (100, 100))
        for i in range(8):
            os.utime(_plain_zip(self.downloads / ("other%d.zip" % i)), (500 + i, 500 + i))
        self.assertEqual(self.post("review", {"from": "downloads"}), (200, {"ok": True, "review": None}))

    def test_no_zip_with_a_brand_manifest_is_no_file(self):
        _plain_zip(self.downloads / "holiday-photos.zip")
        (self.downloads / "broken.zip").write_bytes(b"PK\x03\x04")
        self.assertEqual(self.post("review", {"from": "downloads"}), (200, {"ok": True, "review": None}))

    def test_the_listing_says_whether_there_is_a_brand_file_to_review(self):
        self.assertIs(self.listing()["review_ready"], False)
        _plain_zip(self.downloads / "holiday-photos.zip")
        self.assertIs(self.listing()["review_ready"], False)
        write_zip(self.downloads, bz.valid(), name="whatever.zip")
        self.assertIs(self.listing()["review_ready"], True)

    def test_the_library_listing_review_ready_follows_the_downloads_folder(self):
        lib = sv.BrandLibrary(self.root, self.data, choose=lambda *a, **k: None, downloads=self.downloads)
        status, got = lib.listing()
        self.assertEqual((status, got["review_ready"]), (200, False))
        write_zip(self.downloads, bz.valid(), name="fabrikam-kit.zip")
        status, got = lib.listing()
        self.assertEqual((status, got["review_ready"]), (200, True))

    def test_a_brand_zip_is_found_as_the_last_one_looked_at_and_missed_one_further_down(self):
        for rank in (5, 6):       # the fifth newest is looked at, the sixth is not
            with self.subTest(rank=rank):
                for old in self.downloads.glob("*.zip"):
                    old.unlink()
                kit = write_zip(self.downloads, bz.valid(), name="fabrikam-kit.zip")
                os.utime(kit, (100, 100))
                for i in range(rank - 1):
                    os.utime(_plain_zip(self.downloads / ("other%d.zip" % i)), (500 + i, 500 + i))
                found = brands.newest_brand_zip(self.downloads)
                self.assertEqual(found, kit if rank == 5 else None)

    def test_a_file_chosen_by_hand_installs_whatever_it_is_called(self):
        self.picked[:] = [write_zip(self.scratch, bz.valid(), name="fabrikam notes (3).zip")]
        status, got = self.post("review", {"from": "file"})
        self.assertEqual((status, got["ok"]), (200, True), got)
        status, got = self.post("install", {"review_id": got["review"]["review_id"]})
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual([b["id"] for b in self.listing()["brands"]], [bz.BRAND_ID])


class DiskTrouble(Base):
    def test_undo_whose_backup_folder_is_gone_is_the_failed_refusal_and_changes_nothing(self):
        self.install()
        self.install(version="1.0.1", data=_second())
        import shutil
        shutil.rmtree(self.data / "brand-backups")
        before = snapshot(branding(self.root))
        self.assertFalse(self.listing()["undo"])
        self.failed(self.post("undo"), "failed")
        self.assertEqual(snapshot(branding(self.root)), before)

    def test_a_write_that_fails_is_the_failed_refusal_and_the_old_brand_stays(self):
        self.install()
        before = snapshot(branding(self.root))
        path = write_zip(self.scratch, _second(), version="1.0.1")
        self.picked[:] = [path]
        rid = self.post("review", {"from": "file"})[1]["review"]["review_id"]
        with mock.patch.object(brands, "_put", side_effect=OSError(28, "No space left on device")):
            self.failed(self.post("install", {"review_id": rid}), "failed")
        self.assertEqual(snapshot(branding(self.root)), before)         # the stage was removed; the old folder never moved
        self.assertEqual([p.name for p in branding(self.root).iterdir() if p.name.startswith(".")], [])

    def test_the_backup_and_the_journal_failing_are_the_failed_refusal(self):
        self.install()
        with mock.patch.object(brands, "_copy_tree", side_effect=PermissionError(13, "denied")):
            self.failed(self.post("remove", {"id": bz.BRAND_ID}), "failed")
        self.assertEqual([b["id"] for b in self.listing()["brands"]], [bz.BRAND_ID])       # nothing was taken out
        with mock.patch.object(brands, "_journal", side_effect=OSError(5, "I/O error")):
            self.failed(self.post("remove", {"id": bz.BRAND_ID}), "failed")
        # #944: the undo note is written before the brand is taken out, so when it cannot be written the brand stays: the next listing still answers
        self.assertEqual([b["id"] for b in self.listing()["brands"]], [bz.BRAND_ID])

    def test_recover_failing_before_an_action_is_the_failed_refusal(self):
        (branding(self.root) / (brands.HIDDEN_OLD + "ghost")).mkdir()
        path = write_zip(self.scratch, bz.valid())
        self.picked[:] = [path]
        with mock.patch.object(os, "rename", side_effect=OSError(1, "not permitted")):
            self.failed(self.post("review", {"from": "file"}), "failed")
            self.failed(self.post("undo"), "failed")
            self.failed(self.post("remove", {"id": "ghost"}), "failed")
        # the leftover is still there for the next recover(), which runs at startup and before every action
        brands.recover(self.root)

    def test_the_file_choice_or_the_downloads_folder_failing_is_the_failed_refusal(self):
        def boom(*a, **k):
            raise OSError(5, "I/O error")
        self.rig.httpd.brands.choose = boom
        self.failed(self.post("review", {"from": "file"}), "failed")
        self.rig.httpd.brands.downloads = self.scratch / "no" / "such"
        self.assertEqual(self.post("review", {"from": "downloads"}), (200, {"ok": True, "review": None}))


def _second():
    m = {bz.TOKENS: bz.TOKENS_CSS, bz.LOGO: bz._png((1, 2, 3)), "assets/cover-new.png": bz.COVER_PNG}
    return bz.build(m, manifest=bz.manifest_for(m, version="1.0.1"))


def _stream_zip(members, descriptor_signature):
    """A zip of stored members written the streaming way (flag bit 3, sizes and crc after the data), with a data descriptor
    of 16 bytes (signature) or 12 bytes (none)."""
    out, central = b"", b""
    for name, body in members:
        n = name.encode()
        crc = zlib.crc32(body)
        offset = len(out)
        out += struct.pack("<4sHHHHHIIIHH", b"PK\x03\x04", 20, 0x8, 0, 0, 0x21, 0, 0, 0, len(n), 0) + n + body
        out += (b"PK\x07\x08" if descriptor_signature else b"") + struct.pack("<III", crc, len(body), len(body))
        central += struct.pack("<4sHHHHHHIIIHHHHHII", b"PK\x01\x02", 3 << 8 | 20, 20, 0x8, 0, 0, 0x21, crc, len(body), len(body),
                               len(n), 0, 0, 0, 0, 0o100644 << 16, offset) + n
    end = struct.pack("<4sHHHHIIH", b"PK\x05\x06", 0, 0, len(members), len(members), len(central), len(out), 0)
    return out + central + end


class Descriptor(Base):
    def test_a_member_right_after_a_12_byte_data_descriptor_is_not_an_overlap(self):
        for signed in (True, False):
            with self.subTest("descriptor with signature" if signed else "12-byte descriptor"):
                path = self.scratch / "x.zip"
                path.write_bytes(_stream_zip([("top/a.txt", b"aaa"), ("top/b.txt", b"bbbb")], signed))
                members, _modes, _sha = brands._open_zip(path)
                self.assertEqual(members, {"top/a.txt": b"aaa", "top/b.txt": b"bbbb"})

    def test_overlap_is_still_refused(self):
        with self.assertRaises(brands.BrandError) as cm:
            brands._open_zip(write_zip(self.scratch, bz.overlapping()))
        self.assertEqual(cm.exception.key, "damaged")


if __name__ == "__main__":
    unittest.main()
