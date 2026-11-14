"""Items 1182 and 1183: a risk and an issue keep a Latest update (raid.latest_update, migration step 25), as an action does.

Run: python3 dev/run_tests.py test_raid_latest_update
Fictional data only.
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import changes, history
from clark import store as store_module
from clark.store import open_store
from test_store_migration import version
from test_store_use_case_done_migration import make_at

STEP = 25


class Stored(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        with self.s.step("dashboard", USER) as st:
            self.ids = {t: st.create("raid", {"project": "ABC", "type": t, "description": t + " one", "impact": "Low",
                                              "likelihood": "Low", "raised": "2026-10-01", "source": "demo"}) for t in ("Risk", "Issue")}

    def test_a_risk_and_an_issue_store_and_read_back_a_latest_update(self):
        for t, ref in self.ids.items():
            self.assertIsNone(self.s.read("raid", ref=ref)["latest_update"])
            status, body = self.change({"project": "ABC", "kind": "raid", "op": "update", "id": ref,
                                        "changes": {"latest_update": "<p>Supplier confirmed " + t + "</p>"}, "place": "peek"})
            self.assertEqual((status, body.get("ok")), (200, True), body)
            self.assertIn("Supplier confirmed " + t, self.s.read("raid", ref=ref)["latest_update"])

    def test_a_blank_latest_update_clears_it_and_history_shows_one_line(self):
        ref = self.ids["Risk"]
        self.change({"project": "ABC", "kind": "raid", "op": "update", "id": ref, "changes": {"latest_update": "Agreed"}, "place": "peek"})
        status, body = self.change({"project": "ABC", "kind": "raid", "op": "update", "id": ref, "changes": {"latest_update": ""}, "place": "peek"})
        self.assertEqual((status, body.get("ok")), (200, True), body)
        self.assertIsNone(self.s.read("raid", ref=ref)["latest_update"])
        lines = [r for r in history.rows_for_item(self.s.con, ref) if r.get("step") == body["apply_id"] and r["kind"] == "Changed"]
        self.assertEqual([r["field"] for r in lines], ["Latest update"])


class Migrating(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_the_step_is_in_the_table_and_the_version_is_at_least_it(self):
        self.assertIn((STEP, store_module.migrate_raid_latest_update), store_module.MIGRATIONS)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)

    def test_an_old_file_keeps_its_rows_and_gains_an_empty_column(self):
        path = make_at(self.dir, STEP - 1)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO raid (id, project, type, description, raised, source) VALUES ('ABC-001', 'ABC', 'Issue', 'Portal down', '2026-10-01', 'test')")
        self.assertNotIn("latest_update", [c[1] for c in con.execute("PRAGMA table_info(raid)")])
        con.close()
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
            row = s.read("raid", ref="ABC-001")
            self.assertEqual((row["description"], row["latest_update"]), ("Portal down", None))
        finally:
            s.close()

    def test_the_step_is_safe_to_run_twice(self):
        path = make_at(self.dir, STEP - 1)
        con = store_module.connect(path)
        try:
            con.execute("BEGIN IMMEDIATE")
            store_module.migrate_raid_latest_update(con)
            store_module.migrate_raid_latest_update(con)
            con.execute("COMMIT")
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
