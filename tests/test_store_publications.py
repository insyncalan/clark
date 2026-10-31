"""#43: Store.log_publication, the one writer of `publications`, with the client copy's path. A publication is a record of
a file, not an edit: no step, no change_log row, nothing for Undo to meet."""
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark.store import Invalid

SHA = "a" * 64
LOCAL = Path("/tmp/clark-fictional/local/ABC-report-2026-10-23.html")
CLIENT = Path("/tmp/clark-fictional/client/ABC-report-2026-10-23.html")


class Publications(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store

    def tearDown(self):
        self.demo.close()

    def rows(self):
        return [dict(r) for r in self.s.con.execute("SELECT * FROM publications ORDER BY seq")]

    def test_a_local_publication_has_no_client_path(self):
        seq = self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER)
        row = self.rows()[0]
        self.assertEqual((row["seq"], row["client_path"], row["local_path"], row["checks"], row["word"]),
                         (seq, None, str(LOCAL), "not needed", 0))

    def test_a_client_publication_records_both_paths_the_hash_and_who(self):
        self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER, client_path=CLIENT)
        row = self.rows()[0]
        self.assertEqual((row["project"], row["local_path"], row["client_path"], row["file_sha256"], row["by_user"],
                          row["week_ending"], row["checks"]),
                         ("ABC", str(LOCAL), str(CLIENT), SHA, USER, "2026-10-23", "not needed"))
        self.assertRegex(row["at"], r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")

    def test_it_writes_no_step_and_no_change_log_and_leaves_the_project_row(self):
        before = (self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0],
                  self.s.con.execute("SELECT count(*) FROM change_log").fetchone()[0],
                  self.s.read("projects", ref="ABC"))
        self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER, client_path=CLIENT)
        after = (self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0],
                 self.s.con.execute("SELECT count(*) FROM change_log").fetchone()[0], self.s.read("projects", ref="ABC"))
        self.assertEqual(before, after, "a publication is not an edit, so Undo never meets it")

    def test_undo_of_the_last_step_leaves_the_publications_alone(self):
        self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER, client_path=CLIENT)
        step = self.demo.update("projects", "ABC", {"publish_client": "/tmp/clark-fictional/client"})
        done = self.s.undo(step, USER)
        self.assertEqual(done["skipped"], [])
        self.assertIsNone(self.s.read("projects", ref="ABC")["publish_client"])
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows()[0]["client_path"], str(CLIENT))

    def test_each_publish_is_its_own_row(self):
        self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER)
        self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER, client_path=CLIENT)
        self.assertEqual([r["client_path"] for r in self.rows()], [None, str(CLIENT)])

    def test_the_client_path_must_be_a_full_path_and_not_the_local_file(self):
        for bad, words in (("client/ABC.html", "full path"), (LOCAL, "can't be the Local file")):
            with self.subTest(bad=str(bad)), self.assertRaisesRegex(Invalid, words):
                self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER, client_path=bad)
        self.assertEqual(self.rows(), [])

    def test_a_refused_publication_leaves_nothing_behind(self):
        with self.assertRaisesRegex(Invalid, "isn't here"):
            self.s.log_publication("NOPE", LOCAL, "2026-10-23", SHA, USER, client_path=CLIENT)
        with self.assertRaisesRegex(Invalid, "SHA-256"):
            self.s.log_publication("ABC", LOCAL, "2026-10-23", "xyz", USER, client_path=CLIENT)
        self.assertEqual(self.rows(), [])
        self.assertFalse(self.s.con.in_transaction)

    def test_it_cannot_be_recorded_in_the_middle_of_a_step(self):
        with self.s.step("dashboard", USER):
            with self.assertRaisesRegex(Invalid, "middle of a step"):
                self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER, client_path=CLIENT)
        self.assertEqual(self.rows(), [])


class Latest(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store

    def tearDown(self):
        self.demo.close()

    def test_none_until_something_is_published(self):
        self.assertIsNone(self.s.latest_publication("ABC"))

    def test_the_latest_row_says_when_and_whether_it_went_to_the_client_and_nothing_else(self):
        self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER, client_path=CLIENT)
        got = self.s.latest_publication("ABC")
        self.assertEqual(sorted(got), ["at", "to_client"])
        self.assertTrue(got["to_client"])
        self.s.log_publication("ABC", LOCAL, "2026-10-23", SHA, USER)
        self.assertFalse(self.s.latest_publication("ABC")["to_client"], "the latest one was local only")
        self.assertIsNone(self.s.latest_publication("OTH"))


if __name__ == "__main__":
    unittest.main()
