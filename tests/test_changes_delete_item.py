"""Item 658 (server side): delete an action, RAID item or decision through the change route, with its links, labels and hiding
from the report, in one step; one Undo puts all of it back; refusals in plain words; other tables still refuse a delete.

Run: python3 dev/run_tests.py test_changes_delete_item
"""
import json
import unittest

from _demo import USER, DemoStore
from clark import changes, history
from clark import store as store_module
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
        self.assertEqual(self.delete("actions", self.b)[1]["message"], f"{self.b} is archived. Restore it first.")
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
        n = self.count("actions")
        with self.s.step("dashboard", USER) as st:
            st.cancel("actions", self.b)
        row = self.s.read("actions", ref=self.b)
        self.assertIsNotNone(row)                                          # the row is still there, only closed
        self.assertEqual(row["status"], "Cancelled")
        self.assertEqual(self.count("actions"), n)
        self.assertEqual(self.con.execute("SELECT count(*) FROM change_log WHERE field = ?", (REMOVED,)).fetchone()[0], 0)
        self.assertEqual(self.links(), [(self.a, self.b, "blocks")])      # its link survives a cancel

    def test_undo_restores_the_hidden_row_too(self):
        _, body = self.delete("actions", self.a)
        self.assertEqual(self.count("report_hidden"), 0)
        self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual([tuple(r) for r in self.con.execute("SELECT project, item_id FROM report_hidden")], [("ABC", self.a)])

    def test_a_past_publication_still_opens_unchanged_after_a_delete(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from clark import published_copies
        page = b'<html><body>' + self.a.encode() + b'<script type="application/json" id="clark-data">{"a": 1}</script>\n</body></html>'
        sha = hashlib.sha256(page).hexdigest()
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src.html"
            src.write_bytes(page)
            self.assertTrue(published_copies.keep(Path(d), "ABC", 1, src, sha))
            self.delete("actions", self.a)
            self.assertEqual(published_copies.read(Path(d), "ABC", 1, sha), (published_copies.OK, page))
            status, data = published_copies.read_data(Path(d), "ABC", 1, sha)
            self.assertEqual(status, published_copies.OK)
            self.assertEqual(json.loads(data) if isinstance(data, (bytes, str)) else data, {"a": 1})

    def test_counts_and_pickers_drop_the_deleted_item(self):
        ids = lambda: {r["id"] for r in self.s.read("actions", project="ABC", archived=False)}
        self.assertIn(self.a, ids())
        self.delete("actions", self.a)
        self.assertNotIn(self.a, ids())
        self.assertIn(self.b, ids())
        self.assertEqual(self.count("links"), 0)
        self.assertEqual(self.count("item_labels"), 0)

    def links(self):
        return [tuple(r) for r in self.con.execute("SELECT from_item, to_item, kind FROM links")]

    def test_two_linked_items_deleted_undo_in_either_order_is_lossless(self):
        for first in ("a", "b"):
            with self.subTest(first=first):
                self.setUp()
                _, da = self.delete("actions", self.a)
                _, db = self.delete("actions", self.b)
                one, two = (da, db) if first == "a" else (db, da)
                status, back = self.undo({"project": "ABC", "apply_id": one["apply_id"]})
                self.assertEqual(status, 200, back)
                self.assertEqual(self.links(), [])                         # the other end is still gone: no link yet
                hid = f"Put back: {self.a} is back; {self.a} is hidden from the report again."       # a carried the hiding
                plain = f"Put back: {self.b} is back."
                self.assertEqual(back["words"], hid if first == "a" else plain)
                status, back = self.undo({"project": "ABC", "apply_id": two["apply_id"]})
                self.assertEqual((status, back["skipped"]), (200, []), back)
                self.assertEqual(back["words"], plain if first == "a" else hid)
                self.assertEqual(self.links(), [(self.a, self.b, "blocks")])
                self.assertEqual(self.count("item_labels"), 1)

    def test_bulk_and_hand_over_steps_with_a_since_deleted_item_leave_it_out_cleanly(self):
        self.delete("actions", self.b)
        for body in ({"project": "ABC", "kind": "actions", "op": "bulk", "ids": [self.a, self.b], "changes": {"owner": "Sam"}},
                     {"project": "ABC", "kind": "actions", "op": "handover", "ids": [self.a, self.b], "to": "Sam"}):
            status, out = self.change(body)
            self.assertEqual((status, out["ok"]), (200, True), body)
            self.assertEqual(out["left_out"], [{"id": self.b, "why": changes.BULK_GONE}], body)
            self.assertEqual((out["changed"], out["unchanged"]), ([self.a], []) if body["op"] == "bulk" else ([], [self.a]), body)
        self.assertIsNone(self.s.read("actions", ref=self.b))

    def test_a_second_instance_editing_a_deleted_item_gets_a_clean_refusal_and_nothing_is_written(self):
        self.delete("actions", self.b)
        n = self.count("change_log")
        for body in ({"project": "ABC", "kind": "actions", "op": "update", "id": self.b, "changes": {"owner": "Sam"}},
                     {"project": "ABC", "kind": "actions", "op": "delete", "id": self.b},
                     {"project": "ABC", "kind": "actions", "op": "archive", "id": self.b}):
            status, out = self.change(body)
            self.assertEqual((status, out["ok"]), (400, False), body)
            self.assertEqual(out["message"], "That isn't in this project. Reload the page and try again." if body["op"] == "archive" else "That item isn't in this project.", body)
        self.assertEqual(self.count("change_log"), n)

    def test_deleting_an_archived_item_says_restore_it_first(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", self.b)
        self.assertEqual(self.delete("actions", self.b)[1]["message"], f"{self.b} is archived. Restore it first.")

    def test_milestone_and_use_case_delete_are_refused_by_the_store_and_the_row_stays(self):
        for table, ref in (("milestones", self.demo.milestone), ("use_cases", self.demo.use_case)):
            n = self.count("change_log")
            with self.subTest(table=table):
                with self.assertRaises(Invalid) as e:
                    with self.s.step("dashboard", USER) as st:
                        st.delete(table, ref)
                self.assertIn("never deleted", str(e.exception))
                self.assertEqual(self.count("change_log"), n)
                self.assertIsNotNone(self.s.read(table, ref=ref))

    def test_the_store_delete_item_itself_refuses_an_archived_item_and_writes_nothing(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", self.b)
        n = self.count("change_log")
        row = dict(self.s.read("actions", ref=self.b))
        with self.assertRaises(Invalid) as e:
            with self.s.step("dashboard", USER) as st:
                store_module.delete_item(self.con, "actions", self.b, row, st)             # direct: not through write_item's own check
        self.assertEqual(str(e.exception), f"{self.b} is archived. Restore it first.")
        with self.assertRaises(Invalid):
            with self.s.step("dashboard", USER) as st:
                st.delete("actions", self.b)
        self.assertEqual(self.count("change_log"), n)
        self.assertIsNotNone(self.s.read("actions", ref=self.b))

    def test_the_store_delete_item_itself_refuses_an_item_a_decision_replaces(self):
        with self.s.step("dashboard", USER) as st:
            newer = st.create("decisions", {"project": "ABC", "decision": "Newer", "date": "2026-10-02", "source": "demo", "replaces": self.dec})
        n = self.count("change_log")
        row = dict(self.s.read("decisions", ref=self.dec))
        with self.assertRaises(Invalid) as e:
            with self.s.step("dashboard", USER) as st:
                store_module.delete_item(self.con, "decisions", self.dec, row, st)
        self.assertEqual(str(e.exception), f"{self.dec} can't be deleted: something refers to it (a decision {newer}).")
        self.assertEqual(self.count("change_log"), n)
        self.assertIsNotNone(self.s.read("decisions", ref=self.dec))

    def test_the_store_delete_item_itself_refuses_an_archived_project_in_exact_words(self):
        row = dict(self.s.read("actions", ref=self.b))
        self.con.execute("UPDATE projects SET archived = 1, active = 0 WHERE code = ?", (row["project"],))
        with self.assertRaises(Invalid) as e:
            with self.s.step("dashboard", USER) as st:
                store_module.delete_item(self.con, "actions", self.b, row, st)
        self.assertEqual(str(e.exception), f"{row['project']} is archived. Restore it first.")

    def test_an_item_whose_id_says_this_project_but_whose_row_says_another_is_refused(self):
        self.con.execute("PRAGMA foreign_keys = OFF")
        self.con.execute("UPDATE actions SET project = 'XYZ' WHERE id = ?", (self.b,))     # the id says ABC, the row says XYZ
        self.con.commit()
        n = self.count("change_log")
        status, body = self.delete("actions", self.b)
        self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.ITEM_NOT_MINE))
        self.assertEqual(self.count("change_log"), n)
        self.assertIsNotNone(self.s.read("actions", ref=self.b))


if __name__ == "__main__":
    unittest.main()
