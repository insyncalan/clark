"""#80 (Done-when 2): an in-place change from the Work items table (owner, due, status or priority on an action) is one step, and the
history read for that item shows one new entry with who made it, how and when.

Run: python3 dev/run_tests.py test_inline_history
The change goes through the real clark.changes (the one writer the server calls for POST /api/change) on a demo store (fictional
data); the history is read back with clark.history, as the item's history is read. No browser: the page's request is the same
JSON its cell sends (kind actions, op update, place "cell").
"""
import sqlite3
import unittest
from datetime import datetime

from _demo import USER, DemoStore
from clark import changes, history


class InPlaceHistory(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.a = self.demo.action(workstream="Build", owner="Sara Khan", priority="Medium", status="Open", due_date="2026-11-02")
        self.change = changes.make_change(self.demo.store.path, [], USER)

    def con(self):
        con = sqlite3.connect(str(self.demo.store.path))
        con.row_factory = sqlite3.Row
        self.addCleanup(con.close)
        return con

    def pick(self, **fields):
        """One in-place change, sent the way the Work items cell sends it. Returns (the number of events before, the reply body)."""
        before = len(history.history(self.con(), self.a))
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": self.a, "changes": fields, "place": "cell"})
        self.assertEqual((status, body.get("message")), (200, None), body)
        return before, body

    def check_one_new_entry(self, field, before_value, after_value):
        before, body = self.pick(**{field: after_value})
        events = history.history(self.con(), self.a)
        self.assertEqual(len(events), before + 1, f"{field}: one change is one new history entry")
        new = events[0]                                          # history is newest first
        self.assertEqual(new["field"], field)
        self.assertEqual((new["before"], new["after"]), (before_value, after_value), f"{field}: what it was and what it became")
        # who
        self.assertEqual(new["by_user"], USER, f"{field}: who made the change")
        # how: the route and the place the page sent (the cell)
        self.assertEqual((new["route"], new["place"]), ("dashboard", "cell"), f"{field}: how it was made")
        self.assertFalse(new["is_undo"])
        self.assertTrue(new["in_force"])
        self.assertEqual(new["step"], body["apply_id"], f"{field}: the step is the reply's")
        # when: a date and time the history can read back
        self.assertRegex(new["at"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}$", f"{field}: when it was made")
        datetime.strptime(new["at"], "%Y-%m-%d %H:%M:%S.%f")          # a real date and time, not just a shape
        return body

    def test_owner_change_is_one_entry_with_who_how_and_when(self):
        self.check_one_new_entry("owner", "Sara Khan", "Sam Example")

    def test_due_change_is_one_entry_with_who_how_and_when(self):
        self.check_one_new_entry("due_date", "2026-11-02", "2026-11-05")

    def test_status_change_is_one_entry_with_who_how_and_when(self):
        self.check_one_new_entry("status", "Open", "Delayed")

    def test_priority_change_is_one_entry_with_who_how_and_when(self):
        self.check_one_new_entry("priority", "Medium", "High")


if __name__ == "__main__":
    unittest.main()
