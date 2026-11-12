"""Mutation sweep of schema steps 19 to 21 (src/clark/store.py, guarded): the cases the survivors showed were not pinned.
Step 21 (Candidate becomes Planned 2026) rewrites exactly the value 'Candidate', on every use case whatever its flags, and touches
no other column; step 19 (report_sections takes 'gantt') makes the table when it is missing. Fictional data only.

Run: python3 dev/run_tests.py test_store_migration_mutants
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from clark import store as store_module
from clark.store import open_store
from test_store_use_case_done_migration import make_at

STEP = 21
STAMP = "2026-10-30 09:00:00"


def plant(path, rows):
    """rows: (commitment, archived, client_visible)."""
    con = sqlite3.connect(str(path), isolation_level=None)
    for n, (flag, archived, visible) in enumerate(rows, 1):
        con.execute("INSERT INTO use_cases (id, project, ref, title, status, headline, standing, sort_order, client_visible, archived, source, updated_at, commitment) "
                    "VALUES (?, 'ABC', ?, ?, 'On track', 'h', '<p>s</p>', ?, ?, ?, 'test', ?, ?)",
                    (f"ABC-U-00{n}", f"1.{n}", f"Case {n}", n, visible, archived, STAMP, flag))
    con.close()


def read(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("SELECT commitment, archived, client_visible, updated_at FROM use_cases ORDER BY id").fetchall()
    finally:
        con.close()


class Step21AndStep19(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_candidate_is_rewritten_whatever_the_flags_and_updated_at_is_kept(self):
        path = make_at(self.dir, STEP - 1)
        plant(path, [("Candidate", 1, 1), ("Candidate", 0, 0), ("Candidate", 1, 0), ("Candidate", 0, 1)])
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(read(path), [("Planned 2026", 1, 1, STAMP), ("Planned 2026", 0, 0, STAMP),
                                      ("Planned 2026", 1, 0, STAMP), ("Planned 2026", 0, 1, STAMP)],
                         "an archived or hidden use case is rewritten too, and no column but commitment changes")

    def test_only_the_exact_word_is_rewritten(self):
        path = make_at(self.dir, STEP - 1)
        odd = ["Candidate 2", "Candidates", "Cand", "candidate", " Candidate"]
        plant(path, [(w, 0, 1) for w in odd])
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual([r[0] for r in read(path)], odd, "there is no CHECK on commitment, so a near word is left as it was")

    def test_step_19_makes_report_sections_when_it_is_missing(self):
        con = sqlite3.connect(":memory:", isolation_level=None)
        self.addCleanup(con.close)
        store_module.migrate_gantt_section_type(con)
        sql = con.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'report_sections'").fetchone()
        self.assertIsNotNone(sql)
        self.assertIn("'gantt'", sql[0])
        self.assertEqual(con.execute("SELECT count(*) FROM report_sections").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
