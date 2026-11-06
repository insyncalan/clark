"""Row 893: the client wording of a work item can be cleared through the change route (the existing NULL path of the other
clearable fields): the column becomes empty, it is one step with one Undo that puts the old words back, the same clear twice makes
no second step, and the history says the wording was cleared. A cleared wording leaves the item with its title (the published
file and the exports read `client_message or title`). All rows are fictional.

Run: python3 dev/run_tests.py test_changes_clear_wording
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import changes, history


class ClearWording(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        a = self.demo.action(workstream="Build", owner="Sara Khan")
        with self.s.step("dashboard", USER) as st:
            r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "impact": "High",
                                   "likelihood": "Medium", "raised": "2026-10-01", "source": "demo"})
            d = st.create("decisions", {"project": "ABC", "decision": "Use the new tool", "status": "Pending",
                                        "needed_by": "2030-01-05", "source": "demo"})
        self.refs = {"actions": a, "raid": r, "decisions": d}
        self.title = {"actions": "description", "raid": "description", "decisions": "decision"}

    def send(self, kind, ref, value):
        return self.change({"project": "ABC", "kind": kind, "op": "update", "id": ref, "changes": {"client_message": value}, "place": "cell"})

    def counts(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return tuple(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("applies", "change_log"))
        finally:
            con.close()

    def test_a_clear_is_one_step_one_undo_and_the_same_clear_twice_makes_no_step(self):
        for kind, ref in self.refs.items():
            for blank in (None, "", "   "):
                with self.subTest(kind=kind, blank=blank):
                    status, put = self.send(kind, ref, "What the client reads")
                    self.assertEqual(status, 200, put)
                    before = self.s.read(kind, ref=ref)
                    steps = self.counts()
                    status, body = self.send(kind, ref, blank)
                    self.assertEqual((status, body["ok"], body["undoable"]), (200, True, True), body)
                    row = self.s.read(kind, ref=ref)
                    self.assertEqual(row["client_message"], "", "cleared: the column is NOT NULL, so no wording is the empty string")
                    self.assertEqual(row[self.title[kind]], before[self.title[kind]], "the title stays: it is what the client reads then")
                    self.assertEqual(self.counts()[0], steps[0] + 1, "one step")
                    status, again = self.send(kind, ref, blank)
                    self.assertEqual((status, again["ok"], again["undoable"]), (200, True, False), again)
                    self.assertEqual(self.counts()[0], steps[0] + 1, "the same clear twice makes no second step")
                    status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
                    self.assertEqual(status, 200, undone)
                    self.assertEqual(self.s.read(kind, ref=ref)["client_message"], "What the client reads", "one Undo restores the old words")

    def test_a_non_empty_wording_keeps_the_length_and_character_rules(self):
        kind, ref = "actions", self.refs["actions"]
        for bad, words in (("x" * 201, changes.ITEM_VALUE_WORDS), ("two\nlines", changes.ITEM_TEXT_WORDS)):
            status, body = self.send(kind, ref, bad)
            self.assertEqual((status, body["message"]), (400, words))

    def test_the_history_records_the_clear(self):
        kind, ref = "actions", self.refs["actions"]
        self.send(kind, ref, "What the client reads")
        self.send(kind, ref, None)
        con = sqlite3.connect(str(self.s.path))
        try:
            con.row_factory = sqlite3.Row
            events = [e for e in history.history(con, ref) if e["field"] == "client_message"]
            self.assertEqual([(e["before"], e["after"]) for e in events][0], ("What the client reads", ""), "newest first")
            rows = history.activity_for_item(con, ref)["rows"]
        finally:
            con.close()
        self.assertTrue(any("client" in str(r).lower() or "message" in str(r).lower() for r in rows), rows)


if __name__ == "__main__":
    unittest.main()
