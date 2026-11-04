"""#342 (from #125, follow-on 1): every publish keeps its file and a copy of its data, written once and never changed; nothing is
pruned; an old one can be archived, not deleted (guarded: published_copies.py, store.py, past_reports.py). Fictional data only;
no browser.

The data copy is `PUB-N.json` beside the kept page `PUB-N.html` in clark's own `published-copies` folder: the very JSON of the
page's clark-data block, so it carries nothing the published file did not. A later view (#344's week picker, #346's compare with
the publication before) reads it with published_copies.read_data, which checks it against the page whose SHA-256 the row holds.

Run: python3 dev/run_tests.py test_keep_published
"""
import hashlib
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
import _publish_fixture as fx
from _demo import USER
from clark import past_reports, publish, published_copies as pc
from clark.store import Invalid, open_store
from test_publish_route import DAY, EMPTY_BRANDING


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.data_dir = self.root / "clark-data"
        self.data_dir.mkdir()
        self.db = self.data_dir / "clark.db"
        self.plant = fx.load()
        fx.build_db(self.db, self.plant)
        self.store = open_store(self.db, onedrive_roots=[])
        self.addCleanup(self.store.close)
        self.copies = self.data_dir / pc.FOLDER
        self.n = 0

    def publish(self, now=DAY):
        self.n += 1
        folder = self.root / f"Local{self.n}"
        folder.mkdir()
        done = publish.publish(self.store, "PUB", str(folder), by_user=USER, now=now, branding=EMPTY_BRANDING)
        return done, Path(done["path"]).read_bytes()

    def page(self, n):
        return self.copies / f"PUB-{n}.html"

    def data(self, n):
        return self.copies / f"PUB-{n}.json"


class KeepsTheDataToo(Base):
    def test_a_publish_keeps_its_page_and_a_copy_of_its_data(self):
        done, body = self.publish()
        n = done["number"]
        self.assertEqual(sha(self.page(n).read_bytes()), done["sha256"])
        kept = self.data(n).read_bytes()
        self.assertEqual(kept, pc.data_of(body), "the data copy is the published file's own data block")
        got = json.loads(kept)
        self.assertEqual(got["publication"], {"n": n})
        self.assertEqual(got["as_at"], DAY)
        self.assertEqual(pc.read_data(self.data_dir, "PUB", n, done["sha256"]), (pc.OK, got))

    def test_the_data_copy_carries_nothing_the_published_file_did_not(self):
        done, body = self.publish()
        kept = self.data(done["number"]).read_bytes()
        self.assertIn(kept, body, "every byte of the data copy is in the published file")
        text = kept.decode("ascii")
        for where, marker in self.plant["markers"].items():
            for spelled in fx.spellings(marker):
                with self.subTest(where=where):
                    self.assertNotIn(spelled, text)
        for key in ("internal_note", "source", "publish_local", "publish_client", "file_sha256", "local_path", "clark-boot"):
            self.assertNotIn(f'"{key}"', text)
        self.assertNotIn(str(self.root), text)

    def test_a_second_publish_keeps_the_first_page_and_data_unchanged(self):
        first, _ = self.publish()
        n = first["number"]
        before = (sha(self.page(n).read_bytes()), sha(self.data(n).read_bytes()))
        for i in range(11):                                       # past the ten the list shows: nothing is pruned
            self.publish(now=f"2026-11-{i + 1:02d}")
        self.assertEqual((sha(self.page(n).read_bytes()), sha(self.data(n).read_bytes())), before)
        self.assertEqual(len([p for p in self.copies.iterdir() if p.suffix == ".json"]), 12)

    def test_a_write_to_a_kept_copy_is_refused(self):
        done, body = self.publish()
        n = done["number"]
        data_before = self.data(n).read_bytes()
        other = self.root / "other.html"
        other.write_bytes(body.replace(b'"as_at":"', b'"as_at":"X', 1))
        self.assertFalse(pc.keep(self.data_dir, "PUB", n, other, sha(other.read_bytes())), "a second keep is refused")
        self.assertFalse(pc._write_once(self.copies, f"PUB-{n}.json", b"{}"), "the data copy is never replaced")
        self.assertEqual(self.data(n).read_bytes(), data_before)
        for path in (self.page(n), self.data(n)):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o222, 0, "read-only")
            if os.geteuid() != 0:
                with self.assertRaises(PermissionError):
                    path.write_bytes(b"changed")
        self.assertEqual([p.name for p in self.copies.iterdir() if p.name.startswith(".")], [], "no temporary file is left")


class WhenKeepingFails(Base):
    def test_a_data_copy_that_cannot_be_written_does_not_fail_the_publish(self):
        self.copies.mkdir(mode=0o700)
        (self.copies / "PUB-1.json").mkdir()                     # something else already holds the name
        done, body = self.publish()
        self.assertEqual(done["number"], 1)
        self.assertEqual(self.page(1).read_bytes(), body, "the page is kept and the publication stands")
        self.assertEqual(pc.read_data(self.data_dir, "PUB", 1, done["sha256"]), (pc.CHANGED, None), "never read past it")

    def test_a_kept_folder_that_cannot_be_used_does_not_fail_the_publish(self):
        self.copies.write_bytes(b"not a folder")
        done, _ = self.publish()
        self.assertEqual(self.store.number_of(done["seq"]), done["number"])
        self.assertEqual(pc.read_data(self.data_dir, "PUB", done["number"], done["sha256"]), (pc.MISSING, None))

    def test_a_fault_while_writing_leaves_no_copy_and_no_temporary_file(self):
        source = self.root / "page.html"
        source.write_bytes(b"<html><body></body></html>")
        with mock.patch.object(pc.os, "write", side_effect=OSError("disk full")):
            self.assertFalse(pc.keep(self.data_dir, "PUB", 1, source, sha(source.read_bytes())))
        self.assertEqual(list(self.copies.iterdir()), [])
        self.assertTrue(pc.keep(self.data_dir, "PUB", 1, source, sha(source.read_bytes())), "it can be kept once it can be written")

    def test_a_file_system_without_links_still_writes_once(self):
        source = self.root / "page.html"
        source.write_bytes(b"<html><body></body></html>")
        with mock.patch.object(pc.os, "link", side_effect=PermissionError("no links here")):
            self.assertTrue(pc.keep(self.data_dir, "PUB", 1, source, sha(source.read_bytes())))
            self.assertFalse(pc.keep(self.data_dir, "PUB", 1, source, sha(source.read_bytes())))
        self.assertEqual([p.name for p in self.copies.iterdir()], ["PUB-1.html"], "no data block, no data copy; no temporary file")

    def test_a_data_copy_that_no_longer_matches_its_page_is_changed_not_read(self):
        done, _ = self.publish()
        n = done["number"]
        os.chmod(self.data(n), 0o644)
        self.data(n).write_bytes(b'{"v":1}')
        self.assertEqual(pc.read_data(self.data_dir, "PUB", n, done["sha256"]), (pc.CHANGED, None))
        self.assertEqual(pc.read_data(self.data_dir, "PUB", n, "b" * 64), (pc.CHANGED, None), "the page is checked first")

    def test_a_page_kept_before_data_copies_is_read_from_its_own_block(self):
        done, body = self.publish()
        n = done["number"]
        os.unlink(self.data(n))
        self.assertEqual(pc.read_data(self.data_dir, "PUB", n, done["sha256"]), (pc.OK, json.loads(pc.data_of(body))))

    def test_only_the_block_where_publish_puts_it_is_data(self):
        self.assertEqual(pc.DATA_BLOCK.pattern.decode().replace("([^<]*)", "[^<]*"), publish.DATA_BLOCK.pattern)
        self.assertIsNone(pc.data_of(b"<html><body>no data</body></html>"))
        self.assertIsNone(pc.data_of(b'<script type="application/json" id="clark-data">[1]</script>\n</body>'), "an object only")
        self.assertIsNone(pc.data_of(b'<script type="application/json" id="clark-data">{</script>\n</body>'))
        self.assertIsNone(pc.data_of(b'<script type="application/json" id="clark-data">{}</script>\n<p></p></body>'), "not before </body>")
        self.assertIsNone(pc.data_of("text"))


class Archive(Base):
    def test_archive_hides_one_without_deleting_it(self):
        made = [self.publish(now=f"2026-11-{i + 1:02d}") for i in range(3)]
        n, digest = made[0][0]["number"], made[0][0]["sha256"]
        before = {p.name: sha(p.read_bytes()) for p in self.copies.iterdir()}
        self.assertTrue(self.store.archive_publication("PUB", n))
        status, body = past_reports.PastReports(self.db).listing("PUB")
        self.assertEqual(status, 200)
        self.assertEqual([p["number"] for p in body["publications"]], [3, 2], "the archived one is hidden")
        self.assertEqual((body["total"], body["archived"]), (2, 1))
        after = {p.name: sha(p.read_bytes()) for p in self.copies.iterdir() if p.suffix != pc.ARCHIVED}
        self.assertEqual(after, before, "nothing is removed or changed")
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM publications").fetchone()[0], 3, "the row stays")
        self.assertEqual(past_reports.PastReports(self.db).visit("PUB", n)[0], 200, "it is still kept and still opens")
        self.assertEqual(pc.read_data(self.data_dir, "PUB", n, digest)[0], pc.OK)

    def test_archive_is_refused_in_plain_words(self):
        done, _ = self.publish()
        self.store.archive_publication("PUB", done["number"])
        with self.assertRaisesRegex(Invalid, "already archived"):
            self.store.archive_publication("PUB", done["number"])
        with self.assertRaisesRegex(Invalid, "There is no Publication 9"):
            self.store.archive_publication("PUB", 9)
        for code, number in (("../x", 1), ("PUB", 0), ("PUB", "1"), ("PUB", True)):
            with self.subTest(code=code, number=number), self.assertRaises(Invalid):
                self.store.archive_publication(code, number)
        self.assertEqual(sorted(p.name for p in self.copies.iterdir() if p.suffix == pc.ARCHIVED), ["PUB-1.archived"])

    def test_the_list_still_shows_ten_when_older_ones_are_archived(self):
        for i in range(12):
            self.publish(now=f"2026-11-{i + 1:02d}")
        self.store.archive_publication("PUB", 12)
        status, body = past_reports.PastReports(self.db).listing("PUB")
        self.assertEqual([p["number"] for p in body["publications"]], list(range(11, 1, -1)))
        self.assertEqual((body["total"], body["shown"], body["archived"]), (11, 10, 1))


if __name__ == "__main__":
    unittest.main()
