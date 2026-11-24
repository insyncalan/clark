"""Row 1534: schema step 34 (projects.column_orders). The step number is one literal (COLUMN_ORDERS_STEP); row 1365 also asks for 34 and whoever merges second
takes the next number (this literal, SCHEMA_VERSION's line and the pins). Run: python3 dev/run_tests.py test_store_column_orders_migration_1534
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from clark import store as store_module
from clark.store import open_store
from test_store_use_case_done_migration import make_at
from test_store_migration import version

STEP = store_module.COLUMN_ORDERS_STEP


class Migrating(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def cols(self, path):
        con = sqlite3.connect(str(path))
        try:
            return {r[1]: r for r in con.execute("PRAGMA table_info(projects)")}
        finally:
            con.close()

    def test_the_numbers_have_no_gap_and_the_step_is_in_the_chain(self):
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))
        self.assertIn((STEP, store_module.migrate_column_orders), store_module.MIGRATIONS)
        self.assertEqual(STEP, 34)
        self.assertEqual(store_module.SCHEMA_VERSION, STEP)

    def test_a_file_one_step_back_gets_an_empty_order_on_every_project_and_the_new_version(self):
        path = make_at(self.dir, STEP - 1)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO projects (code, name) VALUES ('DEF', 'Other Programme')")
        con.close()
        self.assertNotIn("column_orders", self.cols(path))
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
        con = sqlite3.connect(str(path))
        self.assertEqual(dict(con.execute("SELECT code, column_orders FROM projects")), {"ABC": "{}", "DEF": "{}"})
        con.close()

    def test_a_second_run_changes_nothing_and_a_new_file_has_the_column(self):
        path = make_at(self.dir, STEP - 1)
        open_store(path, onedrive_roots=[]).close()
        con = store_module.connect(path)
        store_module.migrate_column_orders(con)
        con.close()
        self.assertEqual(self.cols(path)["column_orders"][2:5], ("TEXT", 1, "'{}'"))

    def test_the_column_text_is_the_same_in_schema_sql_and_the_migration(self):
        sql = (Path(store_module.__file__).parent / "schema.sql").read_text(encoding="utf-8")
        self.assertIn(store_module.COLUMN_ORDERS_COLUMN, sql)


if __name__ == "__main__":
    unittest.main()
