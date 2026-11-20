"""Row 1300, slice 1: install_defaults, the install's one row of Defaults values (migration step 30). Table and migration only: no route, no page.

A new file and a file made before the step both hold one row at today's values (review days 14, Gantt tab off for editor and client, the
tab called Gantt); a second row is refused. Fictional data only.

Run: python3 dev/run_tests.py test_install_defaults_store
"""
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _paths import SRC
from clark import store as store_module
from clark.store import Invalid, open_store
from test_store_migration import version
from test_store_use_case_done_migration import make_at

STEP = 30
TODAY = (1, 14, 0, 0, "Gantt", None)
COLS = "id, review_days, gantt_editor, gantt_client, gantt_name, updated_at"


def rows(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute(f"SELECT {COLS} FROM install_defaults").fetchall()
    finally:
        con.close()


class Migrating(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_the_step_is_in_the_table_at_its_number(self):
        self.assertIn((STEP, store_module.migrate_install_defaults), store_module.MIGRATIONS)
        self.assertEqual(store_module.INSTALL_DEFAULTS_STEP, STEP)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))

    def test_a_new_file_has_one_row_at_todays_values(self):
        open_store(self.dir / "clark.db", onedrive_roots=[]).close()
        self.assertEqual(rows(self.dir / "clark.db"), [TODAY])

    def test_a_file_made_before_the_step_gets_the_same_row(self):
        path = make_at(self.dir, STEP - 1)
        con = sqlite3.connect(str(path))
        self.assertIsNone(con.execute("SELECT 1 FROM sqlite_master WHERE name = 'install_defaults'").fetchone())
        con.close()
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
            self.assertEqual(rows(path), [TODAY])
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)      # a migration is not a step: no Undo
        finally:
            s.close()

    def test_a_second_run_keeps_a_changed_value(self):
        path = self.dir / "clark.db"
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        con.execute("UPDATE install_defaults SET review_days = 21, gantt_name = 'Plan'")
        con.commit()
        store_module.migrate_install_defaults(con)
        con.commit()
        self.assertEqual(con.execute("SELECT review_days, gantt_name FROM install_defaults").fetchall(), [(21, "Plan")])
        con.close()

    def test_a_second_row_is_refused_by_the_table(self):
        path = self.dir / "clark.db"
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("INSERT INTO install_defaults (id) VALUES (2)")
        con.close()

    def test_the_two_switches_take_only_0_or_1(self):
        path = self.dir / "clark.db"
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        for col in ("gantt_editor", "gantt_client"):
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute(f"UPDATE install_defaults SET {col} = 2")
        con.close()

    def test_the_writer_refuses_a_new_or_cancelled_row(self):
        s = open_store(self.dir / "clark.db", onedrive_roots=[])
        try:
            for op, extra in (("new", {"values": {"id": 2}}), ("cancel", {"id": "1"})):
                with self.assertRaisesRegex(Invalid, re.escape(store_module.SETTINGS_ROW), msg=op):
                    store_module.write_item(s.con, dict(table="install_defaults", op=op, **extra), 1)
        finally:
            s.close()

    def test_the_one_row_can_be_changed_by_its_key_and_its_key_and_required_fields_are_listed(self):
        s = open_store(self.dir / "clark.db", onedrive_roots=[])
        try:
            self.assertEqual(store_module.KEYS["install_defaults"], ("id",))
            self.assertEqual(store_module.REQUIRED_NEW["install_defaults"], ("id",))
            self.assertEqual(store_module.REQUIRED_NEW["install_defaults"], store_module.REQUIRED_NEW["app_settings"])
            with s.step("dashboard", "Fictional Person", place="menu") as st:
                st.update("install_defaults", "1", {"review_days": 21})
            self.assertEqual(s.read("install_defaults", ref="1")["review_days"], 21)
            self.assertEqual(rows(self.dir / "clark.db")[0][:2], (1, 21))
        finally:
            s.close()

    def test_the_frozen_statements_match_schema_sql(self):
        text = (SRC / "clark" / "schema.sql").read_text(encoding="utf-8")
        want = re.search(r"CREATE TABLE IF NOT EXISTS install_defaults \(.*?\n\);", text, re.S).group(0)
        norm = lambda t: re.sub(r"\s+", " ", t.replace(";", "")).strip()
        self.assertEqual(norm(store_module.INSTALL_DEFAULTS_DDL[0]), norm(want))
        self.assertIn("INSERT OR IGNORE INTO install_defaults (id) VALUES (1)", text)


if __name__ == "__main__":
    unittest.main()
