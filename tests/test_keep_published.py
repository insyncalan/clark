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
import re
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
        # Row 1077: a published file carries each item's Source by NAME (source_name.py), so the key is in the copy; what it holds is never a path.
        for value in re.findall(r'"source":"([^"]*)"', text):
            self.assertNotRegex(value, r"[/\\\\]", "a source is a file name, never a path")
        for key in ("internal_note", "publish_local", "publish_client", "file_sha256", "local_path", "clark-boot"):
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


class NotKeptIsLogged(Base):
    """#577: a copy that could not be kept is not silent: one log line says it, with no path and no hash in it."""

    def test_a_copy_that_could_not_be_kept_logs_why_without_a_path_or_a_hash(self):
        self.copies.write_bytes(b"not a folder")                  # the kept folder cannot be used
        with self.assertLogs("clark.store", level="WARNING") as cap:
            done, _ = self.publish()
        text = "\n".join(cap.output)
        self.assertIn("published copy not kept", text)
        self.assertIn("PUB", text)
        self.assertNotIn(str(self.root), text, "no path in the line")
        self.assertNotIn(done["sha256"], text, "no hash in the line")

    def test_a_fault_while_keeping_logs_the_kind_of_fault_only(self):
        with mock.patch.object(pc, "keep", side_effect=OSError("/secret/place disk full")):
            with self.assertLogs("clark.store", level="WARNING") as cap:
                done, _ = self.publish()
        text = "\n".join(cap.output)
        self.assertIn("OSError", text)
        self.assertNotIn("/secret/place", text, "the fault's own words can hold a path: only its kind is logged")
        self.assertEqual(self.store.number_of(done["seq"]), done["number"], "the publication stands")

    def test_a_copy_that_was_kept_logs_nothing(self):
        with self.assertLogs("clark.store", level="WARNING") as cap:
            import logging
            logging.getLogger("clark.store").warning("marker")      # assertLogs needs one line to pass; the marker is the only one
            self.publish()
        self.assertEqual(cap.output, ["WARNING:clark.store:marker"])


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

    def test_restore_takes_the_mark_off_and_nothing_else(self):
        made = [self.publish(now=f"2026-11-{i + 1:02d}") for i in range(2)]
        n = made[0][0]["number"]
        self.store.archive_publication("PUB", n)
        before = {p.name: sha(p.read_bytes()) for p in self.copies.iterdir() if p.suffix != pc.ARCHIVED}
        self.assertTrue(self.store.unarchive_publication("PUB", n))
        self.assertEqual([p.name for p in self.copies.iterdir() if p.suffix == pc.ARCHIVED], [], "the mark is gone")
        self.assertEqual({p.name: sha(p.read_bytes()) for p in self.copies.iterdir()}, before, "the page and the data are as they were")
        self.assertEqual([p["number"] for p in past_reports.PastReports(self.db).listing("PUB")[1]["publications"]], [2, 1])
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM publications").fetchone()[0], 2)
        self.assertTrue(self.store.archive_publication("PUB", n), "it can be archived again")

    def test_restore_is_refused_in_plain_words_and_removes_nothing_that_is_not_the_mark(self):
        done, _ = self.publish()
        with self.assertRaisesRegex(Invalid, "is not archived"):
            self.store.unarchive_publication("PUB", done["number"])
        with self.assertRaisesRegex(Invalid, "There is no Publication 9"):
            self.store.unarchive_publication("PUB", 9)
        for code, number in (("../x", 1), ("PUB", 0), ("PUB", "1"), ("PUB", True)):
            with self.subTest(code=code, number=number), self.assertRaises(Invalid):
                self.store.unarchive_publication(code, number)
        self.assertEqual(sorted(p.name for p in self.copies.iterdir()), ["PUB-1.html", "PUB-1.json"])
        self.assertFalse(pc.unarchive(self.data_dir, "../x", 1))
        (self.copies / "PUB-1.archived").write_bytes(b"not an empty mark")
        self.assertFalse(pc.unarchive(self.data_dir, "PUB", 1), "only an empty ordinary file written by clark is taken off")
        self.assertTrue((self.copies / "PUB-1.archived").exists())

    def test_a_mark_that_could_not_be_changed_rolls_its_history_line_back(self):
        done, _ = self.publish()
        n = done["number"]
        with mock.patch.object(pc, "archive", return_value=False), self.assertRaisesRegex(Invalid, "could not be archived"):
            self.store.archive_publication("PUB", n)
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM change_log WHERE tbl = 'publications'").fetchone()[0], 0)
        self.store.archive_publication("PUB", n)
        with mock.patch.object(pc, "unarchive", return_value=False), self.assertRaisesRegex(Invalid, "could not be restored"):
            self.store.unarchive_publication("PUB", n)
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM change_log WHERE tbl = 'publications'").fetchone()[0], 1, "only the archive line")

    def test_archive_and_restore_are_in_the_history_and_an_undo_never_takes_them_back(self):
        from clark import history
        done, _ = self.publish()
        n = done["number"]
        self.store.archive_publication("PUB", n, "Sam Example")
        self.store.unarchive_publication("PUB", n, "Sam Example")
        rows = self.store.con.execute("SELECT tbl, item_id, field, old_value, new_value, op FROM change_log WHERE tbl = 'publications' ORDER BY rowid").fetchall()
        self.assertEqual([tuple(r) for r in rows], [("publications", f"PUB-{n}", "archived", "0", "1", "update"),
                                                    ("publications", f"PUB-{n}", "archived", "1", "0", "update")])
        shown = [(r["kind"], r["who"]) for r in history.rows_for_project(self.store.con, "PUB") if r["table"] == "publications" and r["kind"] != "Published"]
        self.assertEqual(shown, [("Restored", "Sam Example"), ("Archived", "Sam Example")], "newest first")
        steps = [r[0] for r in self.store.con.execute("SELECT DISTINCT apply_id FROM change_log WHERE tbl = 'publications' ORDER BY apply_id")]
        self.assertEqual(len(steps), 2)
        for step in steps:
            result = self.store.undo(step, "Sam Example")
            self.assertEqual(result["reversed"], [], "an Undo puts nothing back")
            self.assertTrue(result["skipped"])
        self.assertFalse(pc.is_archived(self.data_dir, "PUB", n), "the mark is as Restore left it")
        self.store.archive_publication("PUB", n)
        for step in steps:
            self.store.undo(step, "Sam Example")
        self.assertTrue(pc.is_archived(self.data_dir, "PUB", n), "and an Undo of the older step does not remove a mark")

    def test_the_list_still_shows_ten_when_older_ones_are_archived(self):
        for i in range(12):
            self.publish(now=f"2026-11-{i + 1:02d}")
        self.store.archive_publication("PUB", 12)
        status, body = past_reports.PastReports(self.db).listing("PUB")
        self.assertEqual([p["number"] for p in body["publications"]], list(range(11, 1, -1)))
        self.assertEqual((body["total"], body["shown"], body["archived"]), (11, 10, 1))


if __name__ == "__main__":
    unittest.main()
