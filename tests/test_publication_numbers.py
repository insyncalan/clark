"""#120: numbered publications (schema version 10). Each publish takes the next number of its project, in the same transaction as
its row; a Local-only publish and a Word copy take one too; the File says "Publication N"; a lost race is refused and the files are
taken back; History gets one line per publish. Fictional data only.

Run: python3 dev/run_tests.py test_publication_numbers
"""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

import _paths  # noqa: F401
import _publish_fixture as fx
from _demo import USER, DemoStore
from clark import history, publish
from clark import store as store_module
from clark.store import Invalid, NumberTaken, open_store
from test_publish_route import DAY, EMPTY_BRANDING, Rig

SHA = "a" * 64
LOCAL = Path("/tmp/clark-fictional/local/ABC-report-2026-10-23.html")


def numbers(con, code="ABC"):
    return [r[0] for r in con.execute("SELECT number FROM publications WHERE project = ? ORDER BY seq", (code,))]


class TheCounter(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})

    def log(self, code="ABC", **kw):
        return self.s.log_publication(code, LOCAL, "2026-10-23", SHA, USER, **kw)

    def test_the_numbers_run_1_2_3_for_a_project_and_each_project_has_its_own(self):
        a, b, c = self.log(), self.log(), self.log("XYZ")
        self.assertEqual([self.s.number_of(x) for x in (a, b, c)], [1, 2, 1])
        self.assertEqual(self.s.next_publication("ABC"), 3)
        self.assertEqual(self.s.next_publication("XYZ"), 2)

    def test_a_local_only_publish_and_a_word_copy_take_a_number_too(self):
        local = self.log()                                              # no client copy: Local only
        word = self.log(word=1)
        client = self.log(client_path=Path("/tmp/clark-fictional/client/ABC.html"))
        self.assertEqual([self.s.number_of(x) for x in (local, word, client)], [1, 2, 3])

    def test_a_number_the_file_was_made_with_must_still_be_the_next_one(self):
        self.log()
        with self.assertRaises(NumberTaken):
            self.log(number=1)                                          # made when 1 was next; another publish took it
        self.assertEqual(numbers(self.s.con), [1], "nothing was recorded")
        self.log(number=2)
        self.assertEqual(numbers(self.s.con), [1, 2])

    def test_a_refused_publication_uses_no_number(self):
        with self.assertRaises(Invalid):
            self.s.log_publication("ABC", LOCAL, "2026-10-23", "nope", USER)
        self.assertEqual(self.log() and numbers(self.s.con), [1])

    def test_two_connections_publishing_at_once_never_take_one_number(self):
        got, errors = [], []

        def go():
            store = open_store(self.s.path, onedrive_roots=[])          # a store belongs to the thread that made it
            try:
                for _ in range(8):
                    got.append(store.number_of(store.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER)))
            except Exception as e:                                     # a busy database may refuse; a repeated number never
                errors.append(e)
            finally:
                store.close()
        threads = [threading.Thread(target=go) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(got), 16)
        self.assertEqual(sorted(got), list(range(1, 17)))
        self.assertEqual(numbers(self.s.con), list(range(1, 17)))

    def test_a_publication_cannot_be_deleted_changed_or_replaced(self):
        seq = self.log()
        con = self.s.con
        for sql in ("DELETE FROM publications", "UPDATE publications SET number = 9", "UPDATE publications SET project = 'XYZ'",
                    "UPDATE publications SET word = 1", "UPDATE publications SET file_sha256 = '%s'" % ("b" * 64),
                    "UPDATE publications SET seq = 99", "UPDATE publications SET at = '2020-01-01'", "UPDATE publications SET week_ending = '2020-01-03'",
                    "UPDATE publications SET local_path = '/x/z.html'", "UPDATE publications SET checks = 'passed'",
                    "UPDATE publications SET client_path = '/x/c.html'", "UPDATE publications SET by_user = 'Someone Else'"):
            with self.assertRaises(sqlite3.DatabaseError, msg=sql):
                con.execute(sql)
        with self.assertRaises(sqlite3.DatabaseError):                   # REPLACE would remove the row without the delete trigger
            con.execute("INSERT OR REPLACE INTO publications (seq, project, local_path, file_sha256, checks, by_user, number) "
                        "VALUES (?, 'ABC', '/x/y.html', ?, 'not needed', 'u', 5)", (seq, SHA))
        with self.assertRaises(sqlite3.DatabaseError):
            con.execute("INSERT OR REPLACE INTO publications (project, local_path, file_sha256, checks, by_user, number) "
                        "VALUES ('ABC', '/x/y.html', ?, 'not needed', 'u', 1)", (SHA,))
        self.assertEqual(numbers(con), [1])

    def test_the_step_replaces_a_narrower_trigger_a_dev_file_kept(self):          # #325
        con = self.s.con
        seq = self.log()
        con.execute("DROP TRIGGER publications_number_fixed")
        con.execute("CREATE TRIGGER publications_number_fixed BEFORE UPDATE OF number ON publications "
                    "BEGIN SELECT RAISE(ABORT, 'narrow'); END")
        con.execute("UPDATE publications SET client_path = '/x/c.html' WHERE seq = ?", (seq,))       # the narrow one lets it through
        con.execute("BEGIN")
        store_module.migrate_publication_numbers(con)
        con.execute("COMMIT")
        with self.assertRaises(sqlite3.DatabaseError):
            con.execute("UPDATE publications SET client_path = '/x/d.html' WHERE seq = ?", (seq,))

    def test_undo_never_frees_a_number(self):
        self.log()
        step = self.demo.update("projects", "ABC", {"publish_client": "/tmp/clark-fictional/client"})
        self.s.undo(step, USER)
        self.assertEqual(self.s.next_publication("ABC"), 2)


class TheShapeAndTheStep(unittest.TestCase):
    def test_the_step_is_number_10_and_the_table_has_no_gap(self):
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, 15)   # #269 is step 15, after #412 (11), #325 (12), #368 (13) and #171 (14); #709 is 16
        self.assertIn((10, store_module.migrate_publication_numbers), store_module.MIGRATIONS)
        self.assertIn((15, store_module.migrate_publication_pdf_name), store_module.MIGRATIONS)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))

    def test_the_frozen_step_makes_what_schema_sql_makes(self):
        fresh = DemoStore()
        self.addCleanup(fresh.close)
        old = DemoStore()
        self.addCleanup(old.close)
        con = old.store.con
        for t in ("publications_no_delete", "publications_number_fixed", "publications_never_replaced"):
            con.execute(f"DROP TRIGGER {t}")
        con.execute("DROP TABLE publications")
        con.execute("CREATE TABLE publications (seq INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL REFERENCES projects(code), "
                    "at TEXT NOT NULL DEFAULT (datetime('now')), week_ending TEXT, local_path TEXT NOT NULL, client_path TEXT, "
                    "word INTEGER NOT NULL DEFAULT 0 CHECK (word IN (0,1)), file_sha256 TEXT NOT NULL, "
                    "checks TEXT NOT NULL CHECK (checks IN ('passed','not needed')), by_user TEXT NOT NULL)")
        con.execute("BEGIN")
        store_module.migrate_publication_numbers(con)
        store_module.migrate_publication_shared_number(con)           # #368: step 13 widens the key, so both steps make what schema.sql makes
        store_module.migrate_publication_pdf_name(con)          # #269: step 15 adds the PDF's name to what steps 10 and 13 made
        con.execute("COMMIT")

        def shape(c):
            return sorted((n, re.sub(r"\s+|\"|publications_v10", lambda m: "publications" if m.group(0) == "publications_v10" else "",
                                     re.sub(r"--[^\n]*", "", sql)))
                          for n, sql in c.execute("SELECT name, sql FROM sqlite_master WHERE tbl_name = 'publications' "
                                                  "AND sql IS NOT NULL"))
        self.assertEqual(shape(con), shape(fresh.store.con))
        self.assertEqual(len(shape(con)), 4, "the table and its three triggers")


class TheTriggerStepTwelve(unittest.TestCase):
    """#325: 0.6.0 ships step 10 with the narrow publications UPDATE trigger, so step 12 makes it again with client_path named."""

    NARROW = ("CREATE TRIGGER publications_number_fixed BEFORE UPDATE OF seq, at, week_ending, local_path, checks, number, project, word, "
              "file_sha256, by_user ON publications BEGIN SELECT RAISE(ABORT, 'narrow'); END")

    def old_file(self, level):
        demo = DemoStore()
        self.addCleanup(demo.close)
        path = demo.store.path
        demo.store.close()
        con = sqlite3.connect(path, isolation_level=None)
        con.execute("INSERT INTO publications (project, local_path, file_sha256, checks, by_user, number) "
                    "VALUES ('ABC', '/x/a.html', ?, 'not needed', 'Sam Carter', 1)", (SHA,))
        con.execute("DROP TRIGGER publications_number_fixed")
        con.execute(self.NARROW)
        con.execute("UPDATE meta SET v = ? WHERE k = 'schema_version'", (str(level),))
        con.close()
        return path

    def test_the_step_is_number_12_and_the_version_says_so(self):
        self.assertIn((12, store_module.migrate_publication_trigger_client_path), store_module.MIGRATIONS)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, 12)

    def test_a_file_at_step_10_or_11_with_the_narrow_trigger_is_upgraded_and_refuses_a_client_path_update(self):
        for level in (10, 11):
            with self.subTest(level=level):
                path = self.old_file(level)
                con = sqlite3.connect(path, isolation_level=None)
                con.execute("UPDATE publications SET client_path = '/x/c.html'")             # the narrow one lets it through
                con.close()
                s = open_store(path, onedrive_roots=[])
                self.addCleanup(s.close)
                self.assertEqual(s.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(store_module.SCHEMA_VERSION))
                with self.assertRaises(sqlite3.DatabaseError):
                    s.con.execute("UPDATE publications SET client_path = '/x/d.html'")
                self.assertEqual(s.con.execute("SELECT client_path FROM publications").fetchone()[0], "/x/c.html")

    def test_the_step_is_safe_to_repeat(self):
        s = open_store(self.old_file(11), onedrive_roots=[])
        self.addCleanup(s.close)

        def dump():
            return sorted(tuple(r) for r in s.con.execute("SELECT type, name, sql FROM sqlite_master WHERE tbl_name = 'publications'"))
        once = dump()
        for _ in range(2):
            s.con.execute("BEGIN")
            store_module.migrate_publication_trigger_client_path(s.con)
            s.con.execute("COMMIT")
        self.assertEqual(dump(), once)
        self.assertEqual(len([r for r in once if r[0] == "trigger"]), 3)


class OlderFiles(unittest.TestCase):
    """A real older database file: the table as version 9 made it, rows in several projects, a Word row and a tie."""

    OLD = ("CREATE TABLE publications (seq INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL REFERENCES projects(code), "
           "at TEXT NOT NULL DEFAULT (datetime('now')), week_ending TEXT, local_path TEXT NOT NULL, client_path TEXT, "
           "word INTEGER NOT NULL DEFAULT 0 CHECK (word IN (0,1)), file_sha256 TEXT NOT NULL, "
           "checks TEXT NOT NULL CHECK (checks IN ('passed','not needed')), by_user TEXT NOT NULL)")
    ROWS = (("ABC", "2026-10-02 09:00:00", 0), ("XYZ", "2026-10-01 09:00:00", 0), ("ABC", "2026-10-01 08:00:00", 0),
            ("ABC", "2026-10-02 09:00:00", 1), ("XYZ", "2026-10-05 10:00:00", 1), ("ABC", "2026-10-09 10:00:00", 0))

    def make(self, level=9):
        demo = DemoStore()
        self.addCleanup(demo.close)
        with demo.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
        path = demo.store.path
        demo.store.close()
        con = sqlite3.connect(path, isolation_level=None)
        for t in ("publications_no_delete", "publications_number_fixed", "publications_never_replaced"):
            con.execute(f"DROP TRIGGER {t}")
        con.execute("DROP TABLE publications")
        con.execute(self.OLD)
        for i, (code, at, word) in enumerate(self.ROWS):
            con.execute("INSERT INTO publications (project, at, local_path, word, file_sha256, checks, by_user) "
                        "VALUES (?, ?, ?, ?, ?, 'not needed', 'Sam Carter')", (code, at, f"/x/{i}.html", word, SHA))
        con.execute("UPDATE meta SET v = ? WHERE k = 'schema_version'", (str(level),))
        con.close()
        return path

    def expected(self, s):
        return {(r["local_path"], r["number"]) for r in s.con.execute("SELECT local_path, number FROM publications")}

    def test_a_version_9_file_is_numbered_per_project_by_date_then_seq_and_keeps_every_row(self):
        path = self.make()
        s = open_store(path, onedrive_roots=[])
        self.addCleanup(s.close)
        self.assertEqual(s.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(store_module.SCHEMA_VERSION))
        # ABC by time: /x/2 (08:00 on the 1st) = 1, then /x/0 and /x/3 tie on the 2nd, seq order = 2, 3, then /x/5 = 4
        self.assertEqual(self.expected(s), {("/x/2.html", 1), ("/x/0.html", 2), ("/x/3.html", 3), ("/x/5.html", 4),
                                            ("/x/1.html", 1), ("/x/4.html", 2)})
        self.assertEqual(s.con.execute("SELECT count(*) FROM publications WHERE word = 1").fetchone()[0], 2)
        self.assertEqual(s.next_publication("ABC"), 5)
        self.assertEqual(s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER), 7, "the sequence goes on after the old rows")
        self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 2, "the migration is not a step")

    def test_a_version_2_file_moves_up_through_every_step_to_the_latest(self):
        path = self.make(2)
        s = open_store(path, onedrive_roots=[])
        self.addCleanup(s.close)
        self.assertEqual(s.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(store_module.SCHEMA_VERSION))
        self.assertEqual((numbers(s.con), numbers(s.con, "XYZ")), ([2, 1, 3, 4], [1, 2]))

    def test_the_file_is_copied_first_a_second_open_changes_nothing_and_the_step_is_safe_to_repeat(self):
        path = self.make()
        open_store(path, onedrive_roots=[]).close()
        self.assertTrue(list((Path(path).parent / "backups").glob("*")), "a safety copy was taken before the step")
        con = sqlite3.connect(path)
        before = list(con.iterdump())
        con.close()
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(path)
        self.assertEqual(list(con.iterdump()), before)
        con.isolation_level = None
        con.execute("BEGIN")
        store_module.migrate_publication_numbers(con)         # again, by hand: it finds the column and changes nothing
        con.execute("COMMIT")
        self.assertEqual(list(con.iterdump()), before)
        con.close()

    def test_a_failure_inside_the_step_leaves_the_file_as_it_was(self):
        path = self.make()
        con = sqlite3.connect(path)
        before = list(con.iterdump())
        con.close()
        real = store_module.PUBLICATION_TRIGGERS
        try:
            store_module.PUBLICATION_TRIGGERS = ("CREATE TRIGGER broken BEFORE nonsense",)
            with self.assertRaises(Invalid):
                open_store(path, onedrive_roots=[])
        finally:
            store_module.PUBLICATION_TRIGGERS = real
        con = sqlite3.connect(path)
        self.assertEqual(list(con.iterdump()), before)
        con.close()


class ThroughThePublisher(unittest.TestCase):
    def test_the_file_says_its_number_and_the_reply_names_it_for_a_local_only_publish(self):
        rig = Rig(self)
        status, got = rig.publish()                                      # no To client: Local only
        self.assertEqual((status, got["ok"], got["number"], got["publication"]), (200, True, 1, 1), got)
        self.assertIn("Published (Publication 1).", got["message"])
        html = (rig.local / "chosen.html").read_text(encoding="utf-8")
        block = json.loads(re.search(r'id="clark-data">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(block["publication"], {"n": 1})
        rig.save_to = rig.local / "second.html"
        status, got = rig.publish(to_client=True)
        self.assertEqual((status, got["number"]), (200, 2), got)
        self.assertIn("Published (Publication 2).", got["message"])
        self.assertEqual([r["number"] for r in rig.rows()], [1, 2])
        self.assertEqual(json.loads(re.search(r'id="clark-data">(.*?)</script>', (rig.client / "PUB-report-2026-10-23.html").read_text(
            encoding="utf-8"), re.S).group(1))["publication"], {"n": 2})

    def test_a_preview_is_not_numbered_and_takes_no_number(self):
        rig = Rig(self)
        built = publish.build(rig.store, "PUB", DAY, EMPTY_BRANDING, number=0)
        self.assertNotIn(b'"publication"', built["body"])
        self.assertEqual(rig.store.next_publication("PUB"), 1)

    def test_a_lost_race_is_refused_and_the_files_are_taken_back(self):
        rig = Rig(self)
        real = store_module.Store.log_publication

        def late(store, *a, **kw):            # another window publishes between the file being written and its record
            real(store, "PUB", Path("/tmp/clark-fictional/other.html"), None, SHA, "Someone Else")
            return real(store, *a, **kw)
        store_module.Store.log_publication = late
        try:
            status, got = rig.publish(to_client=True)
        finally:
            store_module.Store.log_publication = real
        self.assertEqual((status, got["ok"], got["code"]), (409, False, "number_taken"), got)
        self.assertFalse((rig.local / "chosen.html").exists(), "the Local file was taken back")
        self.assertEqual(rig.listing(rig.client), [], "and so was the client copy")
        self.assertEqual([r["number"] for r in rig.rows()], [1], "only the other window's publication is recorded")

    def test_a_lost_race_puts_back_a_file_it_replaced(self):
        rig = Rig(self)
        (rig.local / "chosen.html").write_text("an earlier report", encoding="utf-8")
        real = store_module.Store.log_publication

        def late(store, *a, **kw):
            real(store, "PUB", Path("/tmp/clark-fictional/other.html"), None, SHA, "Someone Else")
            return real(store, *a, **kw)
        store_module.Store.log_publication = late
        try:
            status, got = rig.publish()
        finally:
            store_module.Store.log_publication = real
        self.assertEqual(got["code"], "number_taken", got)
        self.assertEqual((rig.local / "chosen.html").read_text(encoding="utf-8"), "an earlier report")

    def test_a_lost_race_after_an_overwrite_puts_the_clients_earlier_report_back(self):
        rig = Rig(self)
        status, got = rig.publish(to_client=True)                        # the client folder now holds a report
        self.assertEqual((status, got["ok"]), (200, True), got)
        taken = rig.client / "PUB-report-2026-10-23.html"
        taken.write_bytes(b"<!doctype html>the client's earlier report")
        earlier = taken.read_bytes()
        rig.save_to = rig.local / "second.html"
        real = store_module.Store.log_publication

        def late(store, *a, **kw):            # another window publishes between the copy and its record
            real(store, "PUB", Path("/tmp/clark-fictional/other.html"), None, SHA, "Someone Else")
            return real(store, *a, **kw)
        store_module.Store.log_publication = late
        try:
            status, got = rig.publish(to_client=True, on_clash="overwrite", confirmed=True)
        finally:
            store_module.Store.log_publication = real
        self.assertEqual((status, got["code"]), (409, "number_taken"), got)
        self.assertEqual(taken.read_bytes(), earlier, "the client's earlier report is back, byte for byte")
        self.assertEqual(rig.listing(rig.client), [taken.name], "and nothing else is left in the client folder")
        self.assertFalse((rig.local / "second.html").exists(), "the Local file was taken back")

    def test_publish_publish_returns_the_number_and_takes_its_file_back_on_a_lost_race(self):
        tmp = tempfile.mkdtemp(prefix="clark-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        db = fx.build_db(Path(tmp) / "clark.db")
        store = open_store(db, onedrive_roots=[])
        self.addCleanup(store.close)
        folder = Path(tmp) / "out"
        folder.mkdir()
        done = publish.publish(store, "PUB", folder, by_user=USER, now=DAY, branding=EMPTY_BRANDING)
        self.assertEqual(done["number"], 1)
        second = Path(tmp) / "out2"
        second.mkdir()
        real = store_module.Store.next_publication
        store_module.Store.next_publication = lambda self, code: 1               # a stale view of the counter
        try:
            with self.assertRaises(publish.PublishError) as caught:
                publish.publish(store, "PUB", second, by_user=USER, now="2026-10-29", branding=EMPTY_BRANDING)
        finally:
            store_module.Store.next_publication = real
        self.assertIn("Publish again", str(caught.exception))
        self.assertEqual(list(second.iterdir()), [], "the second file was taken back")
        self.assertEqual(numbers(store.con, "PUB"), [1])


    def _overwrite_rig(self):
        tmp = tempfile.mkdtemp(prefix="clark-test-")
        self.addCleanup(shutil.rmtree, tmp, True)
        store = open_store(fx.build_db(Path(tmp) / "clark.db"), onedrive_roots=[])
        self.addCleanup(store.close)
        folder = Path(tmp) / "out"
        folder.mkdir()
        return store, folder

    def _lost_race(self, store, folder, **kw):
        real = store_module.Store.next_publication
        store_module.Store.next_publication = lambda self, code: 1               # a stale view of the counter
        try:
            return publish.publish(store, "PUB", folder, by_user=USER, now=DAY, branding=EMPTY_BRANDING, **kw)
        finally:
            store_module.Store.next_publication = real

    def test_overwrite_with_a_lost_race_puts_the_earlier_file_back_byte_for_byte(self):
        store, folder = self._overwrite_rig()
        publish.publish(store, "PUB", folder, by_user=USER, now=DAY, branding=EMPTY_BRANDING)       # takes number 1
        dest = next(folder.iterdir())
        earlier = b"an earlier report \xe2\x80\x93 kept exactly"
        dest.write_bytes(earlier)
        with self.assertRaises(publish.PublishError):
            self._lost_race(store, folder, overwrite=True)
        self.assertEqual(dest.read_bytes(), earlier)
        self.assertEqual([p.name for p in folder.iterdir()], [dest.name], "nothing numbered or half-written is left")
        self.assertEqual(numbers(store.con, "PUB"), [1])

    def test_overwrite_with_a_lost_race_puts_back_a_link_it_replaced(self):
        store, folder = self._overwrite_rig()
        publish.publish(store, "PUB", folder, by_user=USER, now=DAY, branding=EMPTY_BRANDING)       # takes number 1
        dest = next(folder.iterdir())
        target = folder.parent / "elsewhere.html"
        target.write_bytes(b"the file the link points at")
        dest.unlink()
        try:
            os.symlink(target, dest)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("this system cannot make links")
        with self.assertRaises(publish.PublishError):
            self._lost_race(store, folder, overwrite=True)
        self.assertTrue(os.path.islink(dest), "the link is back, not removed and not turned into a file")
        self.assertEqual(os.readlink(dest), str(target))
        self.assertEqual(target.read_bytes(), b"the file the link points at")
        self.assertEqual([p.name for p in folder.iterdir()], [dest.name])

    def test_a_link_that_cannot_be_put_back_leaves_the_report_not_an_empty_folder(self):
        store, folder = self._overwrite_rig()
        publish.publish(store, "PUB", folder, by_user=USER, now=DAY, branding=EMPTY_BRANDING)       # takes number 1
        dest = next(folder.iterdir())
        target = folder.parent / "elsewhere.html"
        target.write_bytes(b"the file the link points at")
        dest.unlink()
        try:
            os.symlink(target, dest)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("this system cannot make links")
        real = os.symlink

        def refuse(src, dst, *a, **kw):                                  # the put-back's link cannot be made
            raise OSError(13, "Permission denied")
        os.symlink = refuse
        try:
            with self.assertRaises(publish.PublishError):
                self._lost_race(store, folder, overwrite=True)
        finally:
            os.symlink = real
        self.assertEqual([p.name for p in folder.iterdir()], [dest.name], "the file is still there and no temporary name is left")
        self.assertTrue(dest.read_bytes().startswith(b"<!doctype html"), "the report is kept, not removed")
        self.assertEqual(target.read_bytes(), b"the file the link points at")

    def test_a_link_that_cannot_be_put_back_is_said_plainly(self):          # #605
        store, folder = self._overwrite_rig()
        publish.publish(store, "PUB", folder, by_user=USER, now=DAY, branding=EMPTY_BRANDING)       # takes number 1
        dest = next(folder.iterdir())
        target = folder.parent / "elsewhere.html"
        target.write_bytes(b"the file the link points at")
        dest.unlink()
        try:
            os.symlink(target, dest)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("this system cannot make links")
        real = os.symlink

        def refuse(src, dst, *a, **kw):
            raise OSError(13, "Permission denied")
        os.symlink = refuse
        try:
            with self.assertRaises(publish.PublishError) as caught:
                self._lost_race(store, folder, overwrite=True)
        finally:
            os.symlink = real
        self.assertIn("Another publication was made", str(caught.exception), "the reason for the refusal is still given")
        self.assertIn(f"The link that was at {dest.name} could not be put back", str(caught.exception))

    def _link_rig(self):
        store, folder = self._overwrite_rig()
        publish.publish(store, "PUB", folder, by_user=USER, now=DAY, branding=EMPTY_BRANDING)       # takes number 1
        dest = next(folder.iterdir())
        target = folder.parent / "elsewhere.html"
        target.write_bytes(b"the file the link points at")
        dest.unlink()
        try:
            os.symlink(target, dest)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("this system cannot make links")
        return store, folder, dest

    def test_a_link_whose_file_cannot_be_moved_aside_is_said_plainly(self):          # #605, reader's LOW 1(a)
        store, folder, dest = self._link_rig()
        real = os.rename

        def refuse(src, dst, *a, **kw):
            if str(dst).endswith(".aside"):
                raise OSError(13, "Permission denied")
            return real(src, dst, *a, **kw)
        os.rename = refuse
        try:
            with self.assertRaises(publish.PublishError) as caught:
                self._lost_race(store, folder, overwrite=True)
        finally:
            os.rename = real
        self.assertIn("Another publication was made", str(caught.exception))
        self.assertIn(f"The link that was at {dest.name} could not be put back", str(caught.exception))
        self.assertEqual([p.name for p in folder.iterdir()], [dest.name], "our report is still at its name, nothing left beside it")
        self.assertTrue(dest.read_bytes().startswith(b"<!doctype html"))

    def test_a_put_back_that_cannot_restore_the_report_keeps_it_under_the_aside_name(self):          # #605, reader's LOW 1(b)
        store, folder, dest = self._link_rig()
        real_sym, real_move = os.symlink, publish.platform.move_unless_exists

        def refuse(*a, **kw):
            raise OSError(13, "Permission denied")
        os.symlink = refuse
        publish.platform.move_unless_exists = refuse
        try:
            with self.assertRaises(publish.PublishError) as caught:
                self._lost_race(store, folder, overwrite=True)
        finally:
            os.symlink, publish.platform.move_unless_exists = real_sym, real_move
        self.assertIn("Another publication was made", str(caught.exception), "the refusal is still given")
        self.assertIn("The report could not be put back in the folder under its name. It is still in the folder under a hidden name.",
                      str(caught.exception), "the owner's sentence (A), verbatim")
        self.assertNotIn(".aside", str(caught.exception), "no hidden name or path in the message")
        names = [p.name for p in folder.iterdir()]
        self.assertEqual(len(names), 1)
        self.assertTrue(names[0].endswith(".aside"), "the report is kept under its aside name, not lost")
        self.assertTrue((folder / names[0]).read_bytes().startswith(b"<!doctype html"))

    # issue 616: every return path of put_link_back, and what the person is told (or not) by the caller.
    PLAIN = "Another publication was made"
    KEPT = "The link that was at {name} could not be put back, so this report is still there under that name."
    ASIDE = "The report could not be put back in the folder under its name. It is still in the folder under a hidden name."

    def _plain_refuse(self, *a, **kw):
        raise OSError(13, "Permission denied")

    def _patch(self, obj, name, value):
        real = getattr(obj, name)
        setattr(obj, name, value)
        self.addCleanup(setattr, obj, name, real)

    def _ours_at(self, folder, data=b"ours"):
        dest = folder / "PUB-report.html"
        dest.write_bytes(data)
        return dest, hashlib.sha256(data).hexdigest()

    def _hidden(self, folder):
        return sorted(p for p in folder.iterdir() if p.name.endswith(".aside"))

    def test_616_path_kept_rename_fails_and_the_file_is_ours(self):
        """kept (path 1): the file cannot be moved aside and is still ours: left in place, nothing hidden."""
        folder = self._folder()
        dest, digest = self._ours_at(folder)
        self._patch(os, "rename", self._plain_refuse)
        self.assertEqual(publish.put_link_back(dest, folder / "x.html", digest), "kept")
        self.assertEqual(dest.read_bytes(), b"ours")
        self.assertEqual([p.name for p in folder.iterdir()], [dest.name])

    def test_616_path_other_rename_fails_and_the_file_is_not_ours(self):
        """other-silent (path 2): cannot be moved aside and is not ours: left alone."""
        folder = self._folder()
        dest, _ = self._ours_at(folder, b"theirs")
        self._patch(os, "rename", self._plain_refuse)
        self.assertEqual(publish.put_link_back(dest, folder / "x.html", "0" * 64), "other")
        self.assertEqual(dest.read_bytes(), b"theirs")
        self.assertEqual([p.name for p in folder.iterdir()], [dest.name])

    def test_616_path_other_theirs_is_put_back(self):
        """other-silent (path 3): a file that is not ours was moved aside and put straight back, byte for byte."""
        folder = self._folder()
        dest, _ = self._ours_at(folder, b"theirs")
        self.assertEqual(publish.put_link_back(dest, folder / "x.html", "0" * 64), "other")
        self.assertEqual(dest.read_bytes(), b"theirs")
        self.assertEqual([p.name for p in folder.iterdir()], [dest.name])

    def test_616_path_other_theirs_and_the_name_was_taken_meanwhile(self):
        """other-silent (path 4): theirs cannot go back because the name is taken: theirs stays under its hidden name, not deleted."""
        folder = self._folder()
        dest, _ = self._ours_at(folder, b"theirs")
        self._patch(publish.platform, "move_unless_exists", lambda *a, **kw: False)
        self.assertEqual(publish.put_link_back(dest, folder / "x.html", "0" * 64), "other")
        self.assertEqual([p.read_bytes() for p in self._hidden(folder)], [b"theirs"])

    def test_616_path_aside_theirs_cannot_be_put_back(self):
        """aside (path 5): their file cannot be put back at all: it exists under the hidden name, dest is empty."""
        folder = self._folder()
        dest, _ = self._ours_at(folder, b"theirs")
        self._patch(publish.platform, "move_unless_exists", self._plain_refuse)
        self.assertEqual(publish.put_link_back(dest, folder / "x.html", "0" * 64), "aside")
        self.assertFalse(dest.exists())
        self.assertEqual([p.read_bytes() for p in self._hidden(folder)], [b"theirs"])

    def test_616_path_kept_the_link_cannot_be_made_and_ours_goes_back(self):
        """kept (path 6): the link cannot be made; our file is put back at its name."""
        folder = self._folder()
        dest, digest = self._ours_at(folder)
        self._patch(os, "symlink", self._plain_refuse)
        self.assertEqual(publish.put_link_back(dest, folder / "x.html", digest), "kept")
        self.assertEqual(dest.read_bytes(), b"ours")
        self.assertEqual([p.name for p in folder.iterdir()], [dest.name])

    def test_616_path_other_the_link_cannot_be_made_and_the_name_was_taken(self):
        """other-silent (path 7): link cannot be made, the name was taken meanwhile: ours is the extra copy and is cleared."""
        folder = self._folder()
        dest, digest = self._ours_at(folder)
        self._patch(os, "symlink", self._plain_refuse)
        self._patch(publish.platform, "move_unless_exists", lambda *a, **kw: False)
        self.assertEqual(publish.put_link_back(dest, folder / "x.html", digest), "other")
        self.assertEqual(list(folder.iterdir()), [])

    def test_616_path_aside_the_link_cannot_be_made_and_ours_cannot_go_back(self):
        """aside (path 8): link cannot be made and our report cannot go back: kept under the hidden name."""
        folder = self._folder()
        dest, digest = self._ours_at(folder)
        self._patch(os, "symlink", self._plain_refuse)
        self._patch(publish.platform, "move_unless_exists", self._plain_refuse)
        self.assertEqual(publish.put_link_back(dest, folder / "x.html", digest), "aside")
        self.assertFalse(dest.exists())
        self.assertEqual([p.read_bytes() for p in self._hidden(folder)], [b"ours"])

    def test_616_the_caller_says_kept_unchanged(self):
        store, folder, dest = self._link_rig()
        self._patch(os, "symlink", self._plain_refuse)
        with self.assertRaises(publish.PublishError) as caught:
            self._lost_race(store, folder, overwrite=True)
        msg = str(caught.exception)
        self.assertTrue(msg.startswith(self.PLAIN))
        self.assertTrue(msg.endswith(self.KEPT.format(name=dest.name)))
        self.assertEqual([p.name for p in folder.iterdir()], [dest.name])
        self.assertTrue(dest.read_bytes().startswith(b"<!doctype html"))

    def test_616_the_caller_says_the_ruled_aside_sentence_and_nothing_leaks(self):
        store, folder, dest = self._link_rig()
        self._patch(os, "symlink", self._plain_refuse)
        self._patch(publish.platform, "move_unless_exists", self._plain_refuse)
        with self.assertRaises(publish.PublishError) as caught:
            self._lost_race(store, folder, overwrite=True)
        msg = str(caught.exception)
        self.assertTrue(msg.startswith(self.PLAIN))
        self.assertTrue(msg.endswith(" " + self.ASIDE))
        self.assertNotIn("could not be put back in the folder. It is still there", msg, "the old sentence is gone")
        for leak in (".aside", dest.name, str(folder), "Permission"):
            self.assertNotIn(leak, msg)
        self.assertEqual(len(self._hidden(folder)), 1, "the report is kept under the hidden name")

    def _assert_caller_silent(self, store, folder, dest):
        with self.assertRaises(publish.PublishError) as caught:
            self._lost_race(store, folder, overwrite=True)
        msg = str(caught.exception)
        self.assertTrue(msg.startswith(self.PLAIN))
        for added in ("put back", "hidden", "still there", "link", dest.name):
            self.assertNotIn(added, msg, "'other' adds no sentence: the publish reports its own plain error")

    def test_616_the_caller_stays_silent_when_the_file_is_not_ours(self):
        """other-silent via the caller: another program's file is at the name when the link is to be put back."""
        store, folder, dest = self._link_rig()
        real = os.rename

        def swap_then_rename(src, dst, *a, **kw):
            if str(dst).endswith(".aside"):
                Path(src).write_bytes(b"someone else's report")
            return real(src, dst, *a, **kw)
        self._patch(os, "rename", swap_then_rename)
        self._assert_caller_silent(store, folder, dest)
        self.assertEqual(dest.read_bytes(), b"someone else's report", "their file is never deleted or overwritten")

    def test_616_the_caller_stays_silent_when_the_name_was_taken_meanwhile(self):
        """other-silent via the caller: the link cannot be made and the name was taken meanwhile."""
        store, folder, dest = self._link_rig()
        self._patch(os, "symlink", self._plain_refuse)
        self._patch(publish.platform, "move_unless_exists", lambda *a, **kw: False)
        self._assert_caller_silent(store, folder, dest)

    def test_put_link_back_says_which_failure_it_was(self):
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, folder, True)
        dest = folder / "PUB-report.html"
        dest.write_bytes(b"ours")
        digest = hashlib.sha256(b"ours").hexdigest()
        real_sym, real_move, real_rename = os.symlink, publish.platform.move_unless_exists, os.rename

        def refuse(*a, **kw):
            raise OSError(13, "Permission denied")
        os.rename = refuse
        try:
            self.assertEqual(publish.put_link_back(dest, folder / "x.html", digest), "kept")
            self.assertEqual(publish.put_link_back(dest, folder / "x.html", "0" * 64), "other", "not ours and not moved: nothing claimed")
        finally:
            os.rename = real_rename
        os.symlink = publish.platform.move_unless_exists = refuse
        try:
            self.assertEqual(publish.put_link_back(dest, folder / "x.html", digest), "aside")
        finally:
            os.symlink, publish.platform.move_unless_exists = real_sym, real_move

    def test_put_link_back_reports_a_foreign_file_it_could_not_put_back(self):     # item 388: back()'s result is not ignored
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, folder, True)
        dest = folder / "PUB-report.html"
        dest.write_bytes(b"theirs")
        real_move = publish.platform.move_unless_exists

        def refuse(*a, **kw):
            raise OSError(13, "Permission denied")
        publish.platform.move_unless_exists = refuse
        try:
            self.assertEqual(publish.put_link_back(dest, folder / "x.html", "0" * 64), "aside")
        finally:
            publish.platform.move_unless_exists = real_move
        self.assertFalse(dest.exists())
        self.assertEqual([p.read_bytes() for p in folder.iterdir()], [b"theirs"], "their bytes are kept, not deleted")

    def test_put_link_back_raises_publish_error_when_the_aside_name_cannot_be_removed(self):      # item 388: seen, not a bare OSError
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, folder, True)
        dest = folder / "PUB-report.html"
        digest = hashlib.sha256(b"ours").hexdigest()
        real_unlink, real_sym, real_move = os.unlink, os.symlink, publish.platform.move_unless_exists

        def refuse(*a, **kw):
            raise OSError(13, "Permission denied")
        os.unlink = refuse
        try:
            dest.write_bytes(b"ours")
            with self.assertRaises(publish.PublishError) as caught:
                publish.put_link_back(dest, folder / "x.html", digest)
            self.assertEqual(str(caught.exception), "The old copy could not be cleared.", "the owner's sentence (B), verbatim")
            self.assertNotIn("Permission", str(caught.exception))
            self.assertNotIn(dest.name, str(caught.exception))
            self.assertIsInstance(caught.exception.__cause__, OSError, "the os error stays on the cause")
            self.assertTrue(os.path.islink(dest), "the link is in place")
            real_unlink(dest)
            dest.write_bytes(b"ours")
            os.symlink = refuse
            publish.platform.move_unless_exists = lambda *a, **kw: False       # the name was taken meanwhile
            with self.assertRaises(publish.PublishError):
                publish.put_link_back(dest, folder / "x.html", digest)
        finally:
            os.unlink, os.symlink, publish.platform.move_unless_exists = real_unlink, real_sym, real_move

    def test_a_link_is_never_put_over_a_file_that_is_not_ours(self):       # #604: no gap between the check and the swap
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, folder, True)
        dest = folder / "PUB-report.html"
        dest.write_bytes(b"someone else's report, put there a moment ago")
        ours = hashlib.sha256(b"what this publish wrote").hexdigest()
        self.assertEqual(publish.put_link_back(dest, folder / "elsewhere.html", ours), "other")
        self.assertFalse(os.path.islink(dest))
        self.assertEqual(dest.read_bytes(), b"someone else's report, put there a moment ago")
        self.assertEqual([p.name for p in folder.iterdir()], [dest.name], "nothing is left beside it")
        dest.write_bytes(b"what this publish wrote")
        self.assertEqual(publish.put_link_back(dest, folder / "elsewhere.html", ours), "linked")
        self.assertTrue(os.path.islink(dest))
        self.assertEqual([p.name for p in folder.iterdir()], [dest.name])

    def _folder(self):
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, folder, True)
        return folder

    def _swap_in_during_the_check(self, dest, data):
        """The moment after the check runs, another program saves `data` at `dest` (the window #604 is about)."""
        real = publish.still_ours

        def check_then_swap(path, digest):
            answer = real(path, digest)
            dest.write_bytes(data)
            return answer
        publish.still_ours = check_then_swap
        self.addCleanup(setattr, publish, "still_ours", real)

    def test_a_link_swapped_in_is_put_back_as_that_link_not_followed(self):               # #604
        folder = self._folder()
        theirs = folder / "theirs.html"
        theirs.write_bytes(b"the file their link points at")
        dest = folder / "PUB-report.html"
        try:
            os.symlink(theirs, dest)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("this system cannot make links")
        ours = hashlib.sha256(b"what this publish wrote").hexdigest()
        real_link = os.link

        def following_link(src, dst, *, follow_symlinks=True, **kw):         # as on systems where a plain link follows links
            return real_link(os.path.realpath(src) if follow_symlinks else src, dst, follow_symlinks=False, **kw)
        real_move = publish.platform.move_unless_exists

        def move(src, dst, link=None, **kw):                                # a plain os.link here is that following one
            return real_move(src, dst, link=os.link if link in (None, real_link) else link, **kw)
        os.link, publish.platform.move_unless_exists = following_link, move
        self.addCleanup(setattr, publish.platform, "move_unless_exists", real_move)
        self.addCleanup(setattr, os, "link", real_link)
        self.assertEqual(publish.put_link_back(dest, folder / "elsewhere.html", ours), "other")
        self.assertTrue(os.path.islink(dest))
        self.assertEqual(os.readlink(dest), str(theirs))
        self.assertEqual(publish.take_back(dest, ours), False)
        self.assertEqual(os.readlink(dest), str(theirs))
        self.assertEqual(sorted(p.name for p in folder.iterdir()), sorted([dest.name, theirs.name]))

    def test_take_back_never_removes_a_file_that_is_not_ours(self):                       # #604: take_back has the same shape
        folder = self._folder()
        dest = folder / "PUB-report.html"
        dest.write_bytes(b"someone else's report")
        ours = hashlib.sha256(b"what this publish wrote").hexdigest()
        self.assertFalse(publish.take_back(dest, ours))
        self.assertEqual(dest.read_bytes(), b"someone else's report")
        self.assertEqual([p.name for p in folder.iterdir()], [dest.name], "nothing is left beside it")
        dest.write_bytes(b"what this publish wrote")
        self.assertTrue(publish.take_back(dest, ours))
        self.assertEqual(list(folder.iterdir()), [])
        self.assertTrue(publish.take_back(dest, ours), "a file already gone is gone")

    def test_take_back_never_removes_a_file_saved_during_the_check(self):                 # #604
        folder = self._folder()
        dest = folder / "PUB-report.html"
        dest.write_bytes(b"what this publish wrote")
        ours = hashlib.sha256(b"what this publish wrote").hexdigest()
        self._swap_in_during_the_check(dest, b"someone else's report, saved during the check")
        self.assertTrue(publish.take_back(dest, ours), "our bytes are gone")
        self.assertEqual(dest.read_bytes(), b"someone else's report, saved during the check")
        self.assertEqual([p.name for p in folder.iterdir()], [dest.name])

    def test_take_back_puts_our_file_back_when_it_will_not_go(self):
        folder = self._folder()
        dest = folder / "PUB-report.html"
        dest.write_bytes(b"what this publish wrote")
        ours = hashlib.sha256(b"what this publish wrote").hexdigest()
        real, refused = os.unlink, []

        def refuse(path, *a, **kw):                                         # the removal is refused once, then works
            if not refused:
                refused.append(path)
                raise OSError(13, "Permission denied")
            return real(path, *a, **kw)
        os.unlink = refuse
        try:
            self.assertFalse(publish.take_back(dest, ours))
        finally:
            os.unlink = real
        self.assertEqual(dest.read_bytes(), b"what this publish wrote")
        self.assertEqual([p.name for p in folder.iterdir()], [dest.name], "not left under a hidden name")

    def test_a_put_back_refused_by_the_platform_still_ends_in_a_publish_error(self):      # replace_file raises PlatformError
        store, folder, dest = self._link_rig()
        real_sym, real_move = os.symlink, publish.platform.move_unless_exists

        def refuse_link(*a, **kw):
            raise OSError(13, "Permission denied")

        def refuse_move(*a, **kw):
            raise publish.platform.PlatformError("The file is in use by another program.")
        os.symlink = refuse_link
        publish.platform.move_unless_exists = refuse_move
        try:
            with self.assertRaises(publish.PublishError) as caught:
                self._lost_race(store, folder, overwrite=True)
        finally:
            os.symlink, publish.platform.move_unless_exists = real_sym, real_move
        self.assertIn("Another publication was made", str(caught.exception), "the refusal is still given, not the platform's")
        names = [p.name for p in folder.iterdir()]
        self.assertEqual(len(names), 1)
        self.assertTrue(names[0].endswith(".aside"), "the report is kept under its aside name, not lost")
        self.assertTrue((folder / names[0]).read_bytes().startswith(b"<!doctype html"))

    def test_overwrite_with_a_lost_race_and_no_earlier_file_leaves_nothing(self):
        store, folder = self._overwrite_rig()
        store.log_publication("PUB", Path("/tmp/clark-fictional/other.html"), None, SHA, "Someone Else")
        with self.assertRaises(publish.PublishError):
            self._lost_race(store, folder, overwrite=True)
        self.assertEqual(list(folder.iterdir()), [])

    def test_overwrite_refuses_a_file_too_big_to_keep_a_copy_of(self):          # #326
        store, folder = self._overwrite_rig()
        dest = folder / "PUB-report-2026-10-23.html"
        with open(dest, "wb") as f:
            f.truncate(64 * 1048576 + 1)                                        # one byte over what is kept to put back
        with self.assertRaises(publish.PublishError) as caught:
            publish.publish(store, "PUB", folder, by_user=USER, now=DAY, branding=EMPTY_BRANDING, overwrite=True)
        self.assertIn("was not replaced", str(caught.exception))
        self.assertEqual(dest.stat().st_size, 64 * 1048576 + 1, "the big file is untouched")
        self.assertEqual(numbers(store.con, "PUB"), [], "and nothing was recorded")

    def test_the_publisher_refuses_a_local_file_too_big_to_keep_a_copy_of(self):  # #326
        rig = Rig(self)
        big = rig.local / "chosen.html"
        with open(big, "wb") as f:
            f.truncate(64 * 1048576 + 1)
        status, got = rig.publish()
        self.assertEqual((status, got["ok"], got["code"]), (409, False, "earlier_too_big"), got)
        self.assertIn("Nothing was published.", got["message"])
        self.assertEqual(big.stat().st_size, 64 * 1048576 + 1)
        self.assertEqual(rig.rows(), [])

    def test_overwrite_without_a_race_still_replaces_the_file(self):
        store, folder = self._overwrite_rig()
        first = publish.publish(store, "PUB", folder, by_user=USER, now=DAY, branding=EMPTY_BRANDING)
        dest = Path(first["path"])
        dest.write_bytes(b"old")
        second = publish.publish(store, "PUB", folder, by_user=USER, now=DAY, branding=EMPTY_BRANDING, overwrite=True)
        self.assertEqual(second["path"], first["path"])
        self.assertEqual(second["number"], 2)
        self.assertEqual(dest.read_bytes()[:15].lower(), b"<!doctype html>")
        self.assertEqual(numbers(store.con, "PUB"), [1, 2])

    def test_a_lost_race_without_overwrite_leaves_nothing(self):
        store, folder = self._overwrite_rig()
        store.log_publication("PUB", Path("/tmp/clark-fictional/other.html"), None, SHA, "Someone Else")
        with self.assertRaises(publish.PublishError):
            self._lost_race(store, folder)
        self.assertEqual(list(folder.iterdir()), [])


class StillOurs(unittest.TestCase):
    """#597: still_ours is true only for an ordinary file with the bytes; a link to such a file is not ours."""

    def test_a_link_to_the_same_bytes_is_not_still_ours_but_the_file_is(self):
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, folder, True)
        real, link = folder / "real.html", folder / "link.html"
        real.write_bytes(b"<p>ours</p>")
        try:
            link.symlink_to(real)
        except (OSError, NotImplementedError):
            self.skipTest("no symlinks here")
        digest = hashlib.sha256(b"<p>ours</p>").hexdigest()
        self.assertTrue(publish.still_ours(real, digest))
        self.assertFalse(publish.still_ours(link, digest))
        self.assertFalse(publish.still_ours(folder / "missing.html", digest))


class TheHistoryLine(unittest.TestCase):
    def test_each_publish_is_one_line_in_all_and_in_no_other_filter(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        s = demo.store
        s.log_publication("ABC", LOCAL, "2026-10-23", SHA, "Sam Carter")
        s.log_publication("ABC", LOCAL, "2026-10-23", SHA, "Sam Carter", word=1)
        rows = [r for r in history.rows_for_project(s.con, "ABC") if r["kind"] == "Published"]
        self.assertEqual([r["to"] for r in rows], ["Published as Publication 2 (Word copy)", "Published as Publication 1"])
        self.assertEqual({r["who"] for r in rows}, {"Sam Carter"})
        self.assertRegex(rows[0]["when"], r"^\d\d-\d\d-\d{4} \d\d:\d\d$")
        self.assertEqual([r for r in history.rows_for_project(s.con, "ABC", "changes") if r["kind"] == "Published"], [])
        self.assertEqual([r for r in history.rows_for_project(s.con, "ABC", "comments") if r["kind"] == "Published"], [])
        self.assertEqual([r for r in history.rows_for_item(s.con, "ABC-M-001") if r["kind"] == "Published"], [])
        blob = json.dumps(rows)
        self.assertNotIn(str(LOCAL), blob)
        self.assertNotIn(SHA, blob)

    def test_a_publish_through_the_publisher_adds_its_line(self):
        rig = Rig(self)
        rig.publish()
        rows = [r for r in history.rows_for_project(rig.store.con, "PUB") if r["kind"] == "Published"]
        self.assertEqual([r["to"] for r in rows], ["Published as Publication 1"])
        self.assertEqual(rows[0]["who"], "Sam Carter")


if __name__ == "__main__":
    unittest.main()
