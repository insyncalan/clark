"""Row 1107: a use case linked straight to a milestone (store.py, schema.sql, migration step 24: guarded). Fictional data only.
The link table, linking and unlinking with history kept, listing both ways, the migration from layout 23, and the work item path left alone.
Run: python3 dev/run_tests.py test_uc_milestones_store
"""
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _demo import DemoStore, USER
from _paths import SRC
from clark import store as sm
from clark.store import Invalid, open_store
from test_store_migration import version
from test_store_use_case_done_migration import make_at

STEP = 24


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


class Links(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s, self.uc, self.ms = self.demo.store, self.demo.use_case, self.demo.milestone
        with self.s.step("dashboard", USER) as st:
            self.ms2 = st.create("milestones", {"project": "ABC", "name": "Go live", "baseline_date": "2030-06-01", "source": "demo"})

    def link(self, uc=None, ms=None, who="Sam"):
        with self.s.step("dashboard", USER):
            return sm.link_use_case_milestone(self.s.con, uc or self.uc, ms or self.ms, who)

    def unlink(self, ms=None, who="Sam"):
        with self.s.step("dashboard", USER):
            return sm.unlink_use_case_milestone(self.s.con, self.uc, ms or self.ms, who)

    def test_link_lists_both_ways_and_a_second_link_is_not_made(self):
        self.assertTrue(self.link())
        self.assertTrue(self.link(ms=self.ms2))
        self.assertFalse(self.link())
        self.assertEqual(sm.use_case_milestone_ids(self.s.con, self.uc), sorted([self.ms, self.ms2]))
        self.assertEqual(sm.milestone_use_case_ids(self.s.con, self.ms), [self.uc])

    def test_unlinking_keeps_the_row_with_who_and_when_and_linking_again_adds_a_row(self):
        self.link()
        self.assertTrue(self.unlink(who="Pat"))
        self.assertFalse(self.unlink())
        self.assertEqual(sm.use_case_milestone_ids(self.s.con, self.uc), [])
        (row,) = sm.use_case_milestone_history(self.s.con, self.uc)
        self.assertEqual((row["created_by"], row["removed_by"]), ("Sam", "Pat"))
        self.assertTrue(row["created_at"] and row["removed_at"])
        self.assertTrue(self.link())
        self.assertEqual(len(sm.use_case_milestone_history(self.s.con, self.uc, self.ms)), 2)
        self.assertEqual(sm.use_case_milestone_ids(self.s.con, self.uc), [self.ms])

    def test_the_database_itself_refuses_two_live_rows_for_a_pair(self):
        self.link()
        with self.assertRaises(sqlite3.IntegrityError):
            self.s.con.execute("INSERT INTO use_case_milestones (use_case, milestone, created_at) VALUES (?, ?, 'x')", (self.uc, self.ms))
            self.s.con.commit()

    def test_a_missing_item_another_project_or_an_archived_one_is_refused_in_plain_words(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "DEF", "name": "Other", "health": "On track"})
            other = st.create("milestones", {"project": "DEF", "name": "Elsewhere", "baseline_date": "2030-06-01", "source": "demo"})
        for uc, ms, words in ((self.uc, "ABC-M-099", "There is no milestone"), ("ABC-U-099", self.ms, "There is no use case"),
                              (self.uc, other, "own project")):
            with self.assertRaises(Invalid) as e:
                self.link(uc, ms)
            self.assertIn(words, str(e.exception))
        with self.s.step("dashboard", USER) as st:
            st.archive("milestones", self.ms2)
        with self.assertRaises(Invalid) as e:
            self.link(ms=self.ms2)
        self.assertIn("Restore it first", str(e.exception))
        self.assertEqual(sm.use_case_milestone_history(self.s.con), [])

    def test_the_work_item_path_is_unchanged_and_the_page_data_carries_only_the_live_direct_links(self):
        a = self.demo.action(milestone=self.ms2, use_case=self.uc)
        self.link()
        self.link(ms=self.ms2)
        self.unlink(ms=self.ms2)
        d = self.s.data_for("ABC")
        self.assertEqual(d["uc_milestones"], [{"use_case": self.uc, "milestone": self.ms}])
        self.assertEqual(self.s.read("actions", ref=a)["milestone"], self.ms2)

    def test_the_helpers_are_not_in_the_generic_writer_and_the_check_still_holds(self):
        self.assertNotIn("use_case_milestones", sm.TABLES)
        self.assertEqual(self.s.con.execute("PRAGMA foreign_key_check").fetchall(), [])


class Layout(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_step_24_is_the_newest_and_its_statements_are_schema_sqls(self):
        self.assertIn((STEP, sm.migrate_use_case_milestones), sm.MIGRATIONS)
        self.assertEqual(sm.UC_MILESTONES_STEP, STEP)
        self.assertEqual(re.findall(r"^SCHEMA_VERSION = (\d+)", (SRC / "clark" / "store.py").read_text(encoding="utf-8"), re.M), [str(sm.SCHEMA_VERSION)])
        sql = (SRC / "clark" / "schema.sql").read_text(encoding="utf-8")
        for stmt in (sm.UC_MILESTONES_TABLE,) + sm.UC_MILESTONES_INDEXES:
            self.assertIn(squash(stmt), squash(sql))

    def test_a_layout_23_file_gets_an_empty_table_and_no_value_changes(self):
        path = make_at(self.dir, STEP - 1)
        con = sqlite3.connect(str(path))
        con.execute("INSERT INTO use_cases (id, project, title, status, source) VALUES ('ABC-U-001', 'ABC', 'T', 'On track', 't')")
        con.commit()
        con.close()
        self.assertEqual(version(path), str(STEP - 1))
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), str(sm.SCHEMA_VERSION))
            self.assertEqual(s.con.execute("SELECT count(*) FROM use_case_milestones").fetchone()[0], 0)
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)
            self.assertEqual(s.read("use_cases", ref="ABC-U-001")["title"], "T")
            sm.migrate_use_case_milestones(s.con)            # a second run changes nothing
        finally:
            s.close()
        self.assertEqual(len(list((self.dir / "backups").glob("*-migrate.db"))), 1)


if __name__ == "__main__":
    unittest.main()
