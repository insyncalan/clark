"""Row 1534: schema step 35 (projects.column_orders). The step number is one literal (COLUMN_ORDERS_STEP); row 1365 took 34, so this row is the next number (this literal, SCHEMA_VERSION's line and the pins). Run: python3 dev/run_tests.py test_store_column_orders_migration_1534
"""
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import changes, publish, store as store_module
from clark.store import Invalid
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
        self.assertEqual(STEP, 35)
        self.assertEqual(store_module.SCHEMA_VERSION, STEP + 1)      # row 1417 is step 36 on top of this one

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


class SavedAndPublished(unittest.TestCase):
    """AP5 (data side): the order is saved with the project, written by the one writer, refused when it is not a list of the work columns starting
    with status then item, kept per project, and carried in the published file. The page that draws it is the B PR."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)

    def save(self, value, project="ABC"):
        return self.change({"project": project, "kind": "projects", "op": "update", "changes": {"column_orders": value}})

    def stored(self, project="ABC"):
        return self.s.con.execute("SELECT column_orders FROM projects WHERE code = ?", (project,)).fetchone()[0]

    def test_the_validator_takes_a_good_order_and_refuses_a_bad_one(self):
        self.assertEqual(store_module.column_orders({}), "{}")
        self.assertEqual(store_module.column_orders({"risks": ["status", "item", "due"]}), '{"risks":["status","item","due"]}')
        for bad in ({"milestones": ["status", "item"]}, {"risks": ["item", "status"]}, {"risks": ["status", "item", "due", "due"]},
                    {"risks": ["status", "item", "nope"]}, {"risks": "status"}, [], "not json"):
            with self.assertRaises(Invalid, msg=repr(bad)):
                store_module.column_orders(bad)

    def test_the_order_is_saved_in_the_project_and_is_published_for_everyone(self):
        self.assertEqual(self.stored(), "{}")
        order = ["status", "item", "due", "owner", "prio", "id"]
        status, body = self.save({"risks": order, "actions": ["status", "item", "owner"]})
        self.assertEqual((status, body.get("message")), (200, None), body)
        want = json.dumps({"actions": ["status", "item", "owner"], "risks": order}, sort_keys=True, separators=(",", ":"))
        self.assertEqual(self.stored(), want)                       # in the file, so a reload reads it
        self.assertEqual(self.s.read("projects", ref="ABC")["column_orders"], want)
        self.assertIn("column_orders", publish.PUBLISH_FIELDS["projects"])
        self.assertEqual(publish.build(self.s, "ABC")["published"]["data"]["project"]["column_orders"], want)

    def test_a_refused_order_changes_nothing_and_another_project_keeps_its_own(self):
        self.s.con.execute("INSERT INTO projects (code, name) VALUES ('XYZ', 'Second Programme')")
        self.assertEqual(self.save({"issues": ["status", "item", "id"]})[0], 200)
        self.assertEqual(self.stored("XYZ"), "{}")
        before = self.stored()
        self.assertNotEqual(self.save({"issues": ["item", "status"]})[0], 200)
        self.assertEqual(self.stored(), before)


if __name__ == "__main__":
    unittest.main()
