"""#368 (guarded: store.py, schema.sql, past_reports.py): a web page and its Word copy share one publication number (schema version 13).
`UNIQUE (project, number, word)`; `log_publication(..., word=1, same_as=<web seq>)`; POST /api/word-export takes the web publish's
`publication` number. A lone Word export still takes the next number. Fictional data only.

Run: python3 dev/run_tests.py test_shared_publication_number
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _demo import USER, DemoStore
from clark import word_route
from clark import store as store_module
from clark.store import Invalid, open_store

SHA = "a" * 64
SHB = "b" * 64
WEB = Path("/tmp/clark-fictional/local/ABC-report-2026-10-23.html")
DOC = Path("/tmp/clark-fictional/local/ABC-report-2026-10-23.docx")
TODAY = "2026-10-29"


def rows(con, code="ABC"):
    return [(r["number"], r["word"]) for r in con.execute("SELECT number, word FROM publications WHERE project = ? ORDER BY seq", (code,))]


class SharedNumber(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})

    def web(self, code="ABC"):
        return self.s.log_publication(code, WEB, "2026-10-23", SHA, USER)

    def word(self, code="ABC", **kw):
        return self.s.log_publication(code, DOC, "2026-10-23", SHB, USER, word=1, **kw)

    def test_a_word_copy_of_a_web_page_takes_the_pages_number_and_the_next_publication_goes_on(self):
        self.web()
        page = self.web()
        copy = self.word(same_as=page)
        self.assertEqual((self.s.number_of(page), self.s.number_of(copy)), (2, 2))
        self.assertEqual(rows(self.s.con), [(1, 0), (2, 0), (2, 1)])
        self.assertEqual(self.s.next_publication("ABC"), 3)
        self.assertEqual(self.s.number_of(self.web()), 3)

    def test_a_word_export_on_its_own_takes_the_next_number_as_before(self):
        self.web()
        self.assertEqual(self.s.number_of(self.word()), 2)
        self.assertEqual(rows(self.s.con), [(1, 0), (2, 1)])

    def test_a_second_word_file_for_the_same_number_is_refused_and_writes_nothing(self):
        page = self.web()
        self.word(same_as=page)
        with self.assertRaises(Invalid):
            self.word(same_as=page)
        self.assertEqual(rows(self.s.con), [(1, 0), (1, 1)])

    def test_the_database_itself_refuses_two_web_pages_or_two_word_files_with_one_number(self):
        page = self.web()
        self.word(same_as=page)
        for word in (0, 1):
            with self.assertRaises(sqlite3.DatabaseError):
                self.s.con.execute("INSERT INTO publications (project, local_path, word, file_sha256, checks, by_user, number) "
                                   "VALUES ('ABC', '/x/y', ?, ?, 'not needed', 'u', 1)", (word, SHA))
        self.assertEqual(rows(self.s.con), [(1, 0), (1, 1)])

    def test_only_a_web_page_of_the_same_project_can_be_shared(self):
        mine = self.web()
        other = self.web("XYZ")
        word = self.word(same_as=mine)
        for bad in (other, word, 9999):
            with self.assertRaises(Invalid, msg=bad):
                self.word(same_as=bad)
        self.assertEqual(rows(self.s.con), [(1, 0), (1, 1)])

    def test_same_as_is_for_a_word_file_alone_and_never_with_a_number(self):
        page = self.web()
        with self.assertRaises(Invalid):
            self.s.log_publication("ABC", WEB, "2026-10-23", SHA, USER, same_as=page)
        with self.assertRaises(Invalid):
            self.word(same_as=page, number=2)
        for bad in ("1", True, 1.0):
            with self.assertRaises(Invalid, msg=bad):
                self.word(same_as=bad)
        self.assertEqual(rows(self.s.con), [(1, 0)])

    def test_a_word_copy_keeps_no_page_and_a_rows_number_never_changes(self):
        page = self.web()
        copy = self.word(same_as=page)
        with self.assertRaises(sqlite3.DatabaseError):
            self.s.con.execute("UPDATE publications SET number = 7 WHERE seq = ?", (copy,))
        with self.assertRaises(sqlite3.DatabaseError):
            self.s.con.execute("DELETE FROM publications WHERE seq = ?", (copy,))
        self.assertEqual(self.s.web_publication_seq("ABC", 1), page)
        self.assertIsNone(self.s.web_publication_seq("ABC", 2))
        self.assertTrue(self.s.word_copy_exists("ABC", 1))


class TheStep(unittest.TestCase):
    OLD = ("CREATE TABLE publications (seq INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL REFERENCES projects(code), "
           "at TEXT NOT NULL DEFAULT (datetime('now')), week_ending TEXT, local_path TEXT NOT NULL, client_path TEXT, "
           "word INTEGER NOT NULL DEFAULT 0 CHECK (word IN (0,1)), file_sha256 TEXT NOT NULL, "
           "checks TEXT NOT NULL CHECK (checks IN ('passed','not needed')), by_user TEXT NOT NULL, "
           "number INTEGER NOT NULL CHECK (number >= 1), UNIQUE (project, number))")

    def make(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        path = demo.store.path
        demo.store.close()
        con = sqlite3.connect(path, isolation_level=None)
        for t in ("publications_no_delete", "publications_number_fixed", "publications_never_replaced"):
            con.execute(f"DROP TRIGGER {t}")
        con.execute("DROP TABLE publications")
        con.execute(self.OLD)
        for i, (n, word) in enumerate(((1, 0), (2, 1), (3, 0))):
            con.execute("INSERT INTO publications (project, local_path, word, client_path, file_sha256, checks, by_user, number) "
                        "VALUES ('ABC', ?, ?, ?, ?, 'not needed', 'Sam Carter', ?)", (f"/x/{i}", word, f"/c/{i}" if word else None, SHA, n))
        con.execute("UPDATE meta SET v = '11' WHERE k = 'schema_version'")
        con.close()
        return path

    def test_step_13_is_in_the_chain(self):
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, 13)
        self.assertIn((13, store_module.migrate_publication_shared_number), store_module.MIGRATIONS)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))

    def test_a_version_11_file_keeps_every_row_number_and_seq_and_can_then_share_a_number(self):
        path = self.make()
        s = open_store(path, onedrive_roots=[])
        self.addCleanup(s.close)
        self.assertEqual(s.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(store_module.SCHEMA_VERSION))
        self.assertEqual([tuple(r) for r in s.con.execute("SELECT seq, number, word, local_path, client_path FROM publications ORDER BY seq")],
                         [(1, 1, 0, "/x/0", None), (2, 2, 1, "/x/1", "/c/1"), (3, 3, 0, "/x/2", None)])
        self.assertEqual(s.next_publication("ABC"), 4)
        copy = s.log_publication("ABC", DOC, "2026-10-23", SHB, USER, word=1, same_as=3)
        self.assertEqual(s.number_of(copy), 3)
        self.assertEqual(s.con.execute("SELECT count(*) FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'publications'").fetchone()[0], 3)
        with self.assertRaises(sqlite3.DatabaseError):
            s.con.execute("DELETE FROM publications WHERE seq = 1")

    def test_a_second_run_changes_nothing_and_a_new_database_has_the_same_table(self):
        s = DemoStore()
        self.addCleanup(s.close)
        before = [tuple(r) for r in s.store.con.execute("SELECT type, name, sql FROM sqlite_master WHERE tbl_name = 'publications' ORDER BY name")]
        s.store.con.execute("BEGIN")
        store_module.migrate_publication_shared_number(s.store.con)
        s.store.con.execute("COMMIT")
        after = [tuple(r) for r in s.store.con.execute("SELECT type, name, sql FROM sqlite_master WHERE tbl_name = 'publications' ORDER BY name")]
        self.assertEqual(before, after)
        self.assertIn("UNIQUE (project, number, word)", before[[b[1] for b in before].index("publications")][2])


class TheWordRoute(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-word-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.local = self.tmp / "Reports"
        self.local.mkdir()
        self.seam = word_route.make_word_export(self.store.path, [], USER, today=lambda: TODAY, choose_folder=lambda p: str(self.local))

    def post(self, **req):
        req.setdefault("project", "ABC")
        return self.seam(req)

    def publications(self):
        return [(r["number"], r["word"]) for r in self.store.con.execute("SELECT number, word FROM publications ORDER BY seq")]

    def test_a_word_copy_of_a_publish_carries_the_same_number_in_the_row_and_the_words_said(self):
        self.store.log_publication("ABC", WEB, "2026-10-23", SHA, USER)
        page = self.store.log_publication("ABC", WEB, "2026-10-23", SHA, USER)
        status, got = self.post(publication=2)
        self.assertEqual((status, got["ok"], got["number"]), (200, True, 2), got)
        self.assertIn("Publication 2", got["message"])
        self.assertEqual(self.publications(), [(1, 0), (2, 0), (2, 1)])
        self.assertEqual(self.store.number_of(page), self.store.number_of(got["seq"]))

    def test_a_word_export_on_its_own_takes_the_next_number(self):
        self.store.log_publication("ABC", WEB, "2026-10-23", SHA, USER)
        status, got = self.post()
        self.assertEqual((status, got["number"]), (200, 2))
        self.assertEqual(self.publications(), [(1, 0), (2, 1)])

    def test_a_second_word_file_for_the_same_publication_is_refused_before_anything_is_written(self):
        self.store.log_publication("ABC", WEB, "2026-10-23", SHA, USER)
        self.assertTrue(self.post(publication=1)[1]["ok"])
        files = sorted(p.name for p in self.local.iterdir())
        status, got = self.post(publication=1)
        self.assertEqual((status, got["code"]), (409, "word_copy_exists"))
        self.assertEqual((sorted(p.name for p in self.local.iterdir()), self.publications()), (files, [(1, 0), (1, 1)]))

    def test_a_publication_that_is_not_a_web_page_of_the_project_is_refused_and_nothing_is_written(self):
        self.store.log_publication("ABC", WEB, "2026-10-23", SHA, USER)
        self.store.log_publication("ABC", DOC, "2026-10-23", SHB, USER, word=1)         # number 2 is a Word file alone
        for n in (2, 9):
            status, got = self.post(publication=n)
            self.assertEqual((status, got["code"]), (409, "no_such_publication"), n)
        self.assertEqual((list(self.local.iterdir()), self.publications()), ([], [(1, 0), (2, 1)]))

    def test_a_bad_publication_value_is_refused(self):
        for bad in ("1", 0, -1, True, 1.5, [1]):
            status, got = self.post(publication=bad)
            self.assertEqual((status, got["code"]), (400, "bad_publication"), bad)
        self.assertEqual(list(self.local.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
