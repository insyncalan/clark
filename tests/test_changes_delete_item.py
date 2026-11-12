"""Item 658 (server side): delete an action, RAID item or decision through the change route, with its links, labels and hiding
from the report, in one step; one Undo puts all of it back; refusals in plain words; other tables still refuse a delete.

Run: python3 dev/run_tests.py test_changes_delete_item
"""
import json
import unittest

from _demo import USER, DemoStore
from clark import changes, history
from clark.store import Invalid, REMOVED


class DeleteItem(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.con = self.s.con
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        self.a = self.demo.action()
        self.b = self.demo.action(description="Second")
        with self.s.step("dashboard", USER) as st:
            self.dec = st.create("decisions", {"project": "ABC", "decision": "Go", "date": "2026-10-01", "source": "demo"})
            self.raid = st.create("raid", {"project": "ABC", "type": "Risk", "description": "d", "raised": "2026-10-01", "source": "demo"})
            st.create("labels", {"name": "Hot", "builtin": 0})
            st.create("item_labels", {"item_id": self.a, "label": "Hot"})
            st.create("links", {"from_item": self.a, "to_item": self.b, "kind": "blocks", "source": "demo"})
            st.create("report_hidden", {"project": "ABC", "item_id": self.a})

    def delete(self, kind, ref, project="ABC"):
        return self.change({"project": project, "kind": kind, "op": "delete", "id": ref})

    def count(self, table):
        return self.con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def test_delete_removes_the_row_its_links_labels_and_hiding_in_one_step(self):
        status, body = self.delete("actions", self.a)
        self.assertEqual((status, body["ok"], body["ref"], body["undoable"]), (200, True, self.a, True), body)
        self.assertIsNone(self.s.read("actions", ref=self.a))
        self.assertEqual((self.count("links"), self.count("item_labels"), self.count("report_hidden")), (0, 0, 0))
        self.assertIsNotNone(self.s.read("actions", ref=self.b))
        steps = {r[0] for r in self.con.execute("SELECT apply_id FROM change_log WHERE field = ?", (REMOVED,))}
        self.assertEqual(steps, {body["apply_id"]})

    def test_all_three_item_kinds_delete(self):
        for kind, ref in (("raid", self.raid), ("decisions", self.dec)):
            status, body = self.delete(kind, ref)
            self.assertEqual((status, body["ok"]), (200, True), (kind, body))
            self.assertIsNone(self.s.read(kind, ref=ref))

    def test_undo_puts_back_the_row_its_links_and_labels(self):
        before = dict(self.s.read("actions", ref=self.a))
        _, body = self.delete("actions", self.a)
        status, back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, back["ok"], back["skipped"]), (200, True, []), back)
        self.assertEqual(dict(self.s.read("actions", ref=self.a)), before)
        self.assertEqual([tuple(r) for r in self.con.execute("SELECT from_item, to_item, kind FROM links")], [(self.a, self.b, "blocks")])
        self.assertEqual([tuple(r) for r in self.con.execute("SELECT item_id, label FROM item_labels")], [(self.a, "Hot")])
        self.assertEqual(self.count("report_hidden"), 1)

    def test_one_removed_row_for_the_item_and_it_reads_in_the_project_history(self):
        self.delete("actions", self.a)
        n = self.con.execute("SELECT count(*) FROM change_log WHERE tbl = 'actions' AND item_id = ? AND field = ?", (self.a, REMOVED)).fetchone()[0]
        self.assertEqual(n, 1)
        rows = [r for r in history.rows_for_project(self.con, "ABC") if r["table"] == "actions" and r["item_id"] == self.a and r["kind"] == "Removed"]
        self.assertEqual(len(rows), 1, rows)

    def test_the_id_is_never_reused(self):
        self.delete("actions", self.b)
        with self.s.step("dashboard", USER) as st:
            new = st.create("actions", {"project": "ABC", "description": "n", "raised": "2026-10-01", "source": "demo"})
        self.assertNotEqual(new, self.b)
        self.assertGreater(new, self.b)

    def test_an_item_a_decision_replaces_is_refused_naming_the_pointer(self):
        with self.s.step("dashboard", USER) as st:
            newer = st.create("decisions", {"project": "ABC", "decision": "Newer", "date": "2026-10-02", "source": "demo", "replaces": self.dec})
        status, body = self.delete("decisions", self.dec)
        self.assertEqual((status, body["ok"]), (400, False))
        self.assertIn("a decision " + newer, body["message"])
        self.assertIsNotNone(self.s.read("decisions", ref=self.dec))

    def test_an_archived_project_is_refused_and_nothing_is_written(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        n = self.count("change_log")
        status, body = self.delete("actions", self.a)
        self.assertEqual((status, body["message"]), (400, changes.PROJECT_NOT_ACTIVE))
        self.assertEqual(self.count("change_log"), n)

    def test_an_archived_item_and_another_projects_item_are_refused(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", self.b)
        self.assertEqual(self.delete("actions", self.b)[1]["message"], changes.ITEM_NOT_MINE)
        self.assertEqual(self.delete("actions", "XYZ-A-001")[1]["message"], changes.ITEM_NOT_MINE)

    def test_the_store_refuses_a_delete_of_any_other_table(self):
        for table, ref in (("milestones", self.demo.milestone), ("use_cases", self.demo.use_case), ("projects", "ABC")):
            with self.subTest(table=table), self.assertRaises(Invalid):
                with self.s.step("dashboard", USER) as st:
                    st.delete(table, ref)
        self.assertEqual(self.s.read("milestones", ref=self.demo.milestone)["id"], self.demo.milestone)

    def test_the_route_refuses_delete_for_other_kinds(self):
        for kind, ref in (("milestones", self.demo.milestone), ("use_cases", self.demo.use_case), ("documents", "ABC|d1")):
            status, body = self.delete(kind, ref)
            self.assertEqual((status, body["ok"]), (400, False), kind)

    def test_cancel_of_an_item_still_closes_it_and_never_deletes(self):
        with self.s.step("dashboard", USER) as st:
            st.cancel("actions", self.b)
        self.assertEqual(self.s.read("actions", ref=self.b)["status"], "Cancelled")

    def test_no_new_sentence_says_it_cannot_be_brought_back(self):
        text = json.dumps(self.delete("actions", "XYZ-A-001")[1])
        self.assertNotIn("brought back", text)


if __name__ == "__main__":
    unittest.main()
