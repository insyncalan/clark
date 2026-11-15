"""Row 1195: migration step 26, decisions.priority and decisions.latest_update (src/clark/store.py migrate_decision_peek, guarded).

The step adds two columns at the end of decisions (ALTER TABLE ... ADD COLUMN): no table is made again, no existing value changes, every
decision already there gets the priority Medium and no latest update (NULL). A safety copy is taken first by the runner. A second run
changes nothing. Fictional data only.

Run: python3 dev/run_tests.py test_store_decision_peek_migration
"""
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _paths import SRC
from clark import store as store_module
from clark.store import open_store
from test_store_migration import version
from test_store_use_case_done_migration import make_at

STEP = 26
NEW = ("priority", "latest_update")


def add_rows(path):
    con = sqlite3.connect(str(path), isolation_level=None)
    con.execute("INSERT INTO decisions (id, project, decision, made_by, status, date, source) VALUES ('ABC-D-001', 'ABC', 'Use the new supplier', 'Carol Example', 'Made', '2026-10-02', 'test')")
    con.execute("INSERT INTO decisions (id, project, decision, status, needed_by, source) VALUES ('ABC-D-002', 'ABC', 'Pick a go-live date', 'Pending', '2026-11-20', 'test')")
    con.close()


def names(path):
    con = sqlite3.connect(str(path))
    try:
        return [c[1] for c in con.execute("PRAGMA table_info(decisions)")]
    finally:
        con.close()


def rows(path, leave_out=()):
    con = sqlite3.connect(str(path))
    try:
        kept = ", ".join(f'"{c}"' for c in names(path) if c not in leave_out)
        return con.execute(f'SELECT rowid, {kept} FROM decisions ORDER BY rowid').fetchall()
    finally:
        con.close()


class Migrating(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_the_step_is_in_the_table_at_its_number_and_the_literal_and_the_table_agree(self):
        self.assertIn((STEP, store_module.migrate_decision_peek), store_module.MIGRATIONS)
        self.assertEqual(store_module.DECISION_PEEK_STEP, STEP)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        src = (SRC / "clark" / "store.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^SCHEMA_VERSION = (\d+)", src, re.M), [str(store_module.SCHEMA_VERSION)])

    def test_a_populated_layout_25_file_gains_both_columns_last_and_keeps_every_value(self):
        path = make_at(self.dir, STEP - 1)
        add_rows(path)
        self.assertEqual(version(path), str(STEP - 1))
        for c in NEW:
            self.assertNotIn(c, names(path))
        before = rows(path)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)      # a migration is not a step: no Undo
        finally:
            s.close()
        self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
        self.assertEqual(names(path)[-2:], list(NEW))
        self.assertEqual(rows(path, NEW), before, "no existing value changed")
        con = sqlite3.connect(str(path))
        self.assertEqual(con.execute("SELECT priority, latest_update FROM decisions ORDER BY id").fetchall(), [("Medium", None), ("Medium", None)])
        con.close()

    def test_the_priority_takes_the_four_words_and_nothing_else_and_is_never_empty(self):
        path = make_at(self.dir, STEP)
        add_rows(path)
        con = store_module.connect(path)
        for word in ("Urgent", "High", "Medium", "Low"):
            con.execute("UPDATE decisions SET priority = ? WHERE id = 'ABC-D-001'", (word,))
        for bad in ("Critical", "", None):
            with self.assertRaises(sqlite3.IntegrityError, msg=repr(bad)):
                con.execute("UPDATE decisions SET priority = ? WHERE id = 'ABC-D-001'", (bad,))
        con.close()

    def test_a_safety_copy_is_taken_and_a_second_open_changes_nothing(self):
        path = make_at(self.dir, STEP - 1)
        add_rows(path)
        open_store(path, onedrive_roots=[]).close()
        copies = sorted((self.dir / "backups").glob("*-migrate.db"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(version(copies[0]), str(STEP - 1))
        shutil.rmtree(self.dir / "backups", ignore_errors=True)
        was = rows(path)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(rows(path), was)
        self.assertFalse((self.dir / "backups").exists())

    def test_the_step_is_safe_to_run_twice_and_keeps_a_value_already_set(self):
        path = make_at(self.dir, STEP)
        add_rows(path)
        con = store_module.connect(path)
        con.execute("UPDATE decisions SET latest_update = '<p>Chased</p>', priority = 'High' WHERE id = 'ABC-D-001'")
        store_module.migrate_decision_peek(con)
        self.assertEqual([tuple(r) for r in con.execute("SELECT latest_update, priority FROM decisions ORDER BY id")], [("<p>Chased</p>", "High"), (None, "Medium")])
        con.close()


if __name__ == "__main__":
    unittest.main()
