"""Row 811: an item's "needed from the client" flag through the one writer (changes.py): set, unset, Undo as one step, History,
what is refused.

Run: python3 dev/run_tests.py test_changes_client_action
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import changes, history


class Flag(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.action = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            self.risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Portal supplier late", "raised": "2026-10-01",
                                           "impact": "High", "likelihood": "Medium", "source": "demo"})
            self.decision = st.create("decisions", {"project": "ABC", "decision": "Keep the archive read-only", "status": "Pending",
                                                    "needed_by": "2030-01-01", "source": "demo"})
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def edit(self, kind, ref, fields):
        return self.change({"project": "ABC", "kind": kind, "op": "update", "id": ref, "changes": fields, "place": "peek"})

    def ok(self, kind, ref, fields):
        status, body = self.edit(kind, ref, fields)
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def counts(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return con.execute("SELECT (SELECT count(*) FROM applies), (SELECT count(*) FROM change_log)").fetchone()
        finally:
            con.close()

    def items(self):
        return (("actions", self.action), ("raid", self.risk))

    def test_a_new_item_is_off(self):
        for table, ref in self.items():
            self.assertEqual(self.s.read(table, ref=ref)["client_action"], 0)

    def test_set_and_unset_are_each_one_step_with_one_undo(self):
        for table, ref in self.items():
            with self.subTest(table=table):
                on = self.ok(table, ref, {"client_action": 1})
                self.assertEqual((self.s.read(table, ref=ref)["client_action"], on["item"]["client_action"], on["undoable"]), (1, 1, True))
                off = self.ok(table, ref, {"client_action": 0})
                self.assertEqual((self.s.read(table, ref=ref)["client_action"], off["item"]["client_action"], off["undoable"]), (0, 0, True))
                status, undone = self.undo({"project": "ABC", "apply_id": off["apply_id"]})
                self.assertEqual((status, undone["ok"]), (200, True), undone)
                self.assertEqual(self.s.read(table, ref=ref)["client_action"], 1)
                self.assertIn("Needed from the client", undone["words"])
                status, undone = self.undo({"project": "ABC", "apply_id": on["apply_id"]})
                self.assertEqual((status, undone["ok"]), (200, True), undone)
                self.assertEqual(self.s.read(table, ref=ref)["client_action"], 0)

    def test_the_same_value_again_makes_no_step(self):
        self.ok("actions", self.action, {"client_action": 1})
        body = self.ok("actions", self.action, {"client_action": 1})
        self.assertEqual((body["apply_id"], body["undoable"]), (None, False))

    def test_with_another_field_it_is_still_one_step(self):
        body = self.ok("actions", self.action, {"client_action": 1, "priority": "High"})
        self.assertEqual(len({r["via"] for r in self.s.step_rows(body["apply_id"])}), 1)
        status, _ = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200)
        row = self.s.read("actions", ref=self.action)
        self.assertEqual((row["client_action"], row["priority"]), (0, "Medium"))

    def test_history_labels_the_field_with_the_switch_label(self):
        self.ok("actions", self.action, {"client_action": 1})
        made = [e for e in history.history(self.s.con, self.action) if e["field"] == "client_action"]
        self.assertTrue([e for e in made if str(e["after"]) == "1" and str(e["before"]) == "0"], made)
        self.assertEqual(history.field_name("actions", "client_action"), "Needed from the client")
        self.assertEqual(history.field_name("raid", "client_action"), "Needed from the client")

    def test_a_decision_has_no_flag_and_a_wrong_value_is_refused_and_writes_nothing(self):
        before = self.counts()
        status, body = self.edit("decisions", self.decision, {"client_action": 1})
        self.assertEqual(status, 400, body)
        for bad in (2, -1, True, "1", None, 1.0, [1]):
            with self.subTest(bad=bad):
                status, body = self.edit("actions", self.action, {"client_action": bad})
                self.assertEqual((status, body["ok"]), (400, False), body)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.s.read("actions", ref=self.action)["client_action"], 0)

    def test_the_store_refuses_a_value_that_is_not_0_or_1_whichever_route_writes_it(self):
        from clark.store import Invalid
        with self.assertRaises(Invalid):
            with self.s.step("excel", USER) as st:
                st.update("actions", self.action, {"client_action": 2})

    def test_the_data_feed_carries_the_flag(self):
        self.ok("raid", self.risk, {"client_action": 1})
        feed = self.s.data_for("ABC")
        self.assertEqual({r["id"]: r["client_action"] for r in feed["raid"]}[self.risk], 1)
        self.assertEqual({r["id"]: r["client_action"] for r in feed["actions"]}[self.action], 0)


if __name__ == "__main__":
    unittest.main()
