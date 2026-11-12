"""Row 1061: the commitment word Candidate becomes Planned 2026. Schema step 21 (src/clark/store.py, guarded) rewrites the stored
value on every use case that still holds Candidate. History lines (item_events and the changes log) are not touched: they keep the
word they were written with. Fictional data only.

Run: python3 dev/run_tests.py test_store_planned_2026_migration
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from clark import store as store_module
from clark.store import open_store
from test_store_migration import version
from test_store_use_case_done_migration import make_at

STEP = 21


def plant(path, flags):
    con = sqlite3.connect(str(path), isolation_level=None)
    for n, flag in enumerate(flags, 1):
        con.execute("INSERT INTO use_cases (id, project, ref, title, status, headline, standing, sort_order, client_visible, archived, source, updated_at, commitment) "
                    "VALUES (?, 'ABC', ?, ?, 'On track', 'h', '<p>s</p>', ?, 1, 0, 'test', '2026-10-30 09:00:00', ?)",
                    (f"ABC-U-00{n}", f"1.{n}", f"Case {n}", n, flag))
    con.close()


def flags(path):
    con = sqlite3.connect(str(path))
    try:
        return [r[0] for r in con.execute("SELECT commitment FROM use_cases ORDER BY id")]
    finally:
        con.close()


class PlannedTwentySix(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_the_words_and_the_step(self):
        self.assertEqual(store_module.COMMITMENTS, ("Planned 2026", "Committed", "Planned 2027"))
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))
        self.assertIn(STEP, [n for n, _ in store_module.MIGRATIONS])

    def test_candidate_becomes_planned_2026_and_other_values_stay(self):
        path = make_at(self.dir, STEP - 1)
        plant(path, ["Candidate", "Committed", "Planned 2027", None, "Candidate"])
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
        self.assertEqual(flags(path), ["Planned 2026", "Committed", "Planned 2027", None, "Planned 2026"])

    def test_old_history_lines_keep_the_word_candidate(self):
        path = make_at(self.dir, STEP - 1)
        plant(path, ["Candidate"])
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO item_events (at, item_id, kind, route, actor, src_ref) "
                    "VALUES ('2026-10-30 09:00:00', 'ABC-U-001', 'change', 'dashboard', 'you', 'commitment Candidate')")
        con.close()
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        try:
            rows = con.execute("SELECT src_ref FROM item_events WHERE item_id = 'ABC-U-001'").fetchall()
        finally:
            con.close()
        self.assertEqual(rows, [("commitment Candidate",)], "the migration writes no history line and rewrites none")

    def test_old_change_log_lines_keep_the_word_candidate(self):
        path = make_at(self.dir, STEP - 1)
        plant(path, ["Candidate"])
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO change_log (at, apply_id, tbl, item_id, field, old_value, new_value, op, via) "
                    "VALUES ('2026-10-30 09:00:00', 'a1', 'use_cases', 'ABC-U-001', 'commitment', 'Candidate', 'Committed', 'update', 'dashboard')")
        con.close()
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        try:
            rows = con.execute("SELECT old_value, new_value FROM change_log WHERE field = 'commitment'").fetchall()
        finally:
            con.close()
        self.assertEqual(rows, [("Candidate", "Committed")], "the migration rewrites no history line")

    def test_a_second_open_changes_nothing(self):
        path = make_at(self.dir, STEP - 1)
        plant(path, ["Candidate"])
        open_store(path, onedrive_roots=[]).close()
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(flags(path), ["Planned 2026"])


if __name__ == "__main__":
    unittest.main()
