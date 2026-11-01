"""#120: numbered publications (schema version 10). Each publish takes the next number of its project, in the same transaction as
its row; a Local-only publish and a Word copy take one too; the File says "Publication N"; a lost race is refused and the files are
taken back; History gets one line per publish. Fictional data only.

Run: python3 dev/run_tests.py test_publication_numbers
"""
import json
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
                    "UPDATE publications SET word = 1", "UPDATE publications SET file_sha256 = '%s'" % ("b" * 64)):
            with self.assertRaises(sqlite3.DatabaseError, msg=sql):
                con.execute(sql)
        with self.assertRaises(sqlite3.DatabaseError):                   # REPLACE would remove the row without the delete trigger
            con.execute("INSERT OR REPLACE INTO publications (seq, project, local_path, file_sha256, checks, by_user, number) "
                        "VALUES (?, 'ABC', '/x/y.html', ?, 'not needed', 'u', 5)", (seq, SHA))
        with self.assertRaises(sqlite3.DatabaseError):
            con.execute("INSERT OR REPLACE INTO publications (project, local_path, file_sha256, checks, by_user, number) "
                        "VALUES ('ABC', '/x/y.html', ?, 'not needed', 'u', 1)", (SHA,))
        self.assertEqual(numbers(con), [1])
        con.execute("UPDATE publications SET client_path = '/x/c.html' WHERE seq = ?", (seq,))    # the client copy's path may be set

    def test_undo_never_frees_a_number(self):
        self.log()
        step = self.demo.update("projects", "ABC", {"publish_client": "/tmp/clark-fictional/client"})
        self.s.undo(step, USER)
        self.assertEqual(self.s.next_publication("ABC"), 2)


class TheShapeAndTheStep(unittest.TestCase):
    def test_the_step_is_number_10_and_the_table_has_no_gap(self):
        self.assertEqual(store_module.SCHEMA_VERSION, 10)
        self.assertEqual(store_module.MIGRATIONS[-1], (10, store_module.migrate_publication_numbers))
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, 11)))

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
        con.execute("COMMIT")

        def shape(c):
            return sorted((n, re.sub(r"\s+|\"|publications_v10", lambda m: "publications" if m.group(0) == "publications_v10" else "",
                                     re.sub(r"--[^\n]*", "", sql)))
                          for n, sql in c.execute("SELECT name, sql FROM sqlite_master WHERE tbl_name = 'publications' "
                                                  "AND sql IS NOT NULL"))
        self.assertEqual(shape(con), shape(fresh.store.con))
        self.assertEqual(len(shape(con)), 4, "the table and its three triggers")


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
        self.assertEqual(s.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], "10")
        # ABC by time: /x/2 (08:00 on the 1st) = 1, then /x/0 and /x/3 tie on the 2nd, seq order = 2, 3, then /x/5 = 4
        self.assertEqual(self.expected(s), {("/x/2.html", 1), ("/x/0.html", 2), ("/x/3.html", 3), ("/x/5.html", 4),
                                            ("/x/1.html", 1), ("/x/4.html", 2)})
        self.assertEqual(s.con.execute("SELECT count(*) FROM publications WHERE word = 1").fetchone()[0], 2)
        self.assertEqual(s.next_publication("ABC"), 5)
        self.assertEqual(s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER), 7, "the sequence goes on after the old rows")
        self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 2, "the migration is not a step")

    def test_a_version_2_file_moves_up_through_every_step_to_10(self):
        path = self.make(2)
        s = open_store(path, onedrive_roots=[])
        self.addCleanup(s.close)
        self.assertEqual(s.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], "10")
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
