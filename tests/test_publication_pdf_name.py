"""#269: the publications row names the PDF file saved with it (schema version 15, `publications.pdf_name`). The step adds the
column to a version 10 file and keeps every row; a publish that saves a PDF puts its name on its own row once the PDF is saved;
a publish with no PDF, or whose PDF was not saved, leaves it empty. Fictional data only.

Run: python3 dev/run_tests.py test_publication_pdf_name
"""
import sqlite3
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from _demo import USER, DemoStore
from clark import pdf, publish_pdf
from clark import pdf_text as pdftext
from clark import store as store_module
from clark.store import Invalid, open_store
from test_publish_route import Rig

SHA = "a" * 64
LOCAL = Path("/tmp/clark-fictional/local/ABC-report-2026-10-23.html")


def columns(con, table="publications"):
    return [tuple(r)[1:4] for r in con.execute(f"PRAGMA table_info({table})")]


class TheColumnAndTheStep(unittest.TestCase):
    def make_v10(self):
        """A real version 10 file: the table as step 10 made it (no pdf_name), its triggers, two rows."""
        demo = DemoStore()
        self.addCleanup(demo.close)
        path = demo.store.path
        demo.store.close()
        con = sqlite3.connect(path, isolation_level=None)
        for t in ("publications_no_delete", "publications_number_fixed", "publications_never_replaced"):
            con.execute(f"DROP TRIGGER {t}")
        con.execute("DROP TABLE publications")
        con.execute(store_module.PUBLICATIONS_NUMBERED)
        con.execute("ALTER TABLE publications_v10 RENAME TO publications")
        for statement in store_module.PUBLICATION_TRIGGERS:
            con.execute(statement)
        for i in (1, 2):
            con.execute("INSERT INTO publications (project, local_path, file_sha256, checks, by_user, number) "
                        "VALUES ('ABC', ?, ?, 'not needed', 'A Tester', ?)", (f"/x/{i}.html", SHA, i))
        con.execute("UPDATE meta SET v = '10' WHERE k = 'schema_version'")
        con.close()
        return path

    def test_the_step_is_number_15_and_follows_step_14(self):
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, 15)       # #709 is step 16 after it
        steps = [n for n, _ in store_module.MIGRATIONS]
        self.assertEqual(steps, list(range(2, store_module.SCHEMA_VERSION + 1)))
        self.assertIn((14, store_module.migrate_review_after_days), store_module.MIGRATIONS)
        self.assertIn((15, store_module.migrate_publication_pdf_name), store_module.MIGRATIONS)

    def test_a_version_10_file_gets_the_column_keeps_every_row_and_is_copied_first(self):
        path = self.make_v10()
        con = sqlite3.connect(path)
        self.assertNotIn("pdf_name", [c[0] for c in columns(con)])
        con.close()
        s = open_store(path, onedrive_roots=[])
        self.addCleanup(s.close)
        self.assertEqual(s.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(store_module.SCHEMA_VERSION))
        self.assertEqual([tuple(r) for r in s.con.execute("SELECT number, local_path, pdf_name FROM publications ORDER BY seq")],
                         [(1, "/x/1.html", None), (2, "/x/2.html", None)])
        self.assertTrue(list((Path(path).parent / "backups").glob("*")), "a safety copy was taken before the step")
        self.assertEqual(s.next_publication("ABC"), 3)
        self.assertEqual(s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER), 3, "the sequence goes on")

    def test_a_second_open_and_a_second_run_of_the_step_change_nothing(self):
        path = self.make_v10()
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(path)
        before = list(con.iterdump())
        con.close()
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(path)
        self.assertEqual(list(con.iterdump()), before)
        con.isolation_level = None
        con.execute("BEGIN")
        store_module.migrate_publication_pdf_name(con)
        con.execute("COMMIT")
        self.assertEqual(list(con.iterdump()), before)
        con.close()

    def test_the_migrated_table_has_the_columns_a_new_file_has(self):
        path = self.make_v10()
        old = open_store(path, onedrive_roots=[])
        self.addCleanup(old.close)
        fresh = DemoStore()
        self.addCleanup(fresh.close)
        self.assertEqual(columns(old.con), columns(fresh.store.con))
        self.assertEqual(columns(fresh.store.con)[-1][0], "pdf_name")
        triggers = "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'publications' ORDER BY name"
        self.assertEqual(list(old.con.execute(triggers)), list(fresh.store.con.execute(triggers)))

    def test_a_failure_inside_the_step_leaves_the_file_as_it_was(self):
        path = self.make_v10()
        con = sqlite3.connect(path)
        before = list(con.iterdump())
        con.close()
        broken = lambda c: (c.execute("ALTER TABLE publications ADD COLUMN pdf_name TEXT"), c.execute("SELECT nonsense FROM nowhere"))  # noqa: E731
        steps = tuple((n, broken if n == 15 else fn) for n, fn in store_module.MIGRATIONS)
        with mock.patch.object(store_module, "MIGRATIONS", steps):
            with self.assertRaises(Invalid):
                open_store(path, onedrive_roots=[])
        con = sqlite3.connect(path)
        self.assertEqual(list(con.iterdump()), before)
        con.close()


class TheName(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.seq = self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER)

    def name(self):
        return self.s.con.execute("SELECT pdf_name FROM publications WHERE seq = ?", (self.seq,)).fetchone()[0]

    def test_a_new_publication_has_no_pdf_name(self):
        self.assertIsNone(self.name())

    def test_the_name_is_written_once_and_never_changed(self):
        self.assertTrue(self.s.record_pdf_name(self.seq, "report.pdf"))
        self.assertEqual(self.name(), "report.pdf")
        self.assertFalse(self.s.record_pdf_name(self.seq, "other.pdf"))
        self.assertEqual(self.name(), "report.pdf")

    def test_a_row_that_is_not_there_changes_nothing(self):
        self.assertFalse(self.s.record_pdf_name(self.seq + 40, "report.pdf"))
        self.assertIsNone(self.name())

    def test_only_a_file_name_is_taken(self):
        for bad in ("", None, "a/b.pdf", "a\\b.pdf", "x" * 256, "a\x00.pdf"):
            with self.assertRaises(Invalid, msg=repr(bad)):
                self.s.record_pdf_name(self.seq, bad)
        self.assertIsNone(self.name())
        with self.assertRaises(sqlite3.IntegrityError):           # the table says the same, whoever writes to it
            self.s.con.execute("UPDATE publications SET pdf_name = '../x.pdf' WHERE seq = ?", (self.seq,))

    def test_the_rest_of_the_row_still_never_changes(self):
        self.s.record_pdf_name(self.seq, "report.pdf")
        with self.assertRaises(sqlite3.DatabaseError):
            self.s.con.execute("UPDATE publications SET number = 9 WHERE seq = ?", (self.seq,))
        with self.assertRaises(sqlite3.DatabaseError):
            self.s.con.execute("DELETE FROM publications WHERE seq = ?", (self.seq,))


class APublishRecordsItsPdf(unittest.TestCase):
    def publish(self, rig, **body):
        def fake_print(page, out, orientation="portrait", footer_left=None, **kw):
            Path(out).write_bytes(b"%PDF-1.4\n")
            return Path(out)
        with mock.patch.object(pdf, "find_chrome", return_value="/x"), mock.patch.object(pdf, "make_pdf", fake_print), \
                mock.patch.object(pdftext, "text_of", return_value="All fine."):
            return rig.publish(**body)

    def test_a_local_pdf_publish_puts_the_pdfs_name_on_its_row(self):
        rig = Rig(self)
        status, got = self.publish(rig, pdf=True)
        self.assertEqual((status, got["ok"], got["pdf_name"]), (200, True, "chosen.pdf"), got)
        self.assertEqual([(r["number"], r["pdf_name"]) for r in rig.rows()], [(got["number"], "chosen.pdf")])
        self.assertTrue((rig.local / "chosen.pdf").exists())

    def test_with_a_client_copy_the_row_names_the_local_pdf(self):
        rig = Rig(self)
        status, got = self.publish(rig, to_client=True, pdf=True)
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual([r["pdf_name"] for r in rig.rows()], ["chosen.pdf"], "one row, naming the Local file")

    def test_each_publish_names_its_own_pdf(self):
        rig = Rig(self)
        for name in ("one.html", "two.html"):
            rig.save_to = rig.local / name
            status, got = self.publish(rig, pdf=True)
            self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual([r["pdf_name"] for r in rig.rows()], ["one.pdf", "two.pdf"])

    def test_a_publish_with_no_pdf_leaves_the_name_empty(self):
        rig = Rig(self)
        with mock.patch.object(publish_pdf, "make", side_effect=AssertionError("no PDF was asked for")):
            status, got = rig.publish(to_client=True)
        self.assertEqual((status, got["ok"]), (200, True))
        self.assertEqual([r["pdf_name"] for r in rig.rows()], [None])

    def test_a_pdf_that_was_not_saved_is_not_named(self):
        rig = Rig(self)
        with mock.patch.object(publish_pdf.platform, "move_unless_exists", return_value=False):
            status, got = self.publish(rig, pdf=True)
        self.assertEqual((status, got["ok"], got["pdf_saved"]), (200, True, False), got)
        self.assertNotIn("pdf_name", got)
        self.assertEqual([r["pdf_name"] for r in rig.rows()], [None])
        self.assertFalse((rig.local / "chosen.pdf").exists())

    def test_a_pdf_that_is_held_back_publishes_nothing_and_names_nothing(self):
        rig = Rig(self)
        with mock.patch.object(pdf, "find_chrome", return_value="/x"), mock.patch.object(pdf, "make_pdf", side_effect=pdf.PdfError("no")), \
                mock.patch.object(pdftext, "text_of", return_value="All fine."):
            status, got = rig.publish(pdf=True)
        self.assertEqual((status, got["ok"]), (409, False))
        self.assertEqual(rig.rows(), [])


if __name__ == "__main__":
    unittest.main()
