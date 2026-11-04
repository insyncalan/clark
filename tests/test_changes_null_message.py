"""Item 611: a null client_message on a work item is refused in plain words and saves nothing. Today the field is also refused
earlier as one a work item does not take; the rule is kept in ITEM_NOT_NULL as well, so it holds once the field is accepted.
All rows are fictional.

Run: python3 dev/run_tests.py test_changes_null_message
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import changes


class NullMessage(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        a = self.demo.action(workstream="Build", owner="Sara Khan")
        with self.s.step("dashboard", USER) as st:
            r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "impact": "High",
                                   "likelihood": "Medium", "raised": "2026-10-01", "source": "demo"})
            d = st.create("decisions", {"project": "ABC", "decision": "Use the new tool", "status": "Pending",
                                        "needed_by": "2030-01-05", "source": "demo"})
        self.refs = {"actions": a, "raid": r, "decisions": d}

    def logged(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return con.execute("SELECT count(*) FROM change_log").fetchone()[0]
        finally:
            con.close()

    def test_a_null_client_message_is_refused_and_nothing_is_saved(self):
        for kind, ref in self.refs.items():
            with self.subTest(kind=kind):
                was, logged = self.s.read(kind, ref=ref), self.logged()
                status, body = self.change({"project": "ABC", "kind": kind, "op": "update", "id": ref,
                                            "changes": {"client_message": None}, "place": "menu"})
                self.assertEqual((status, body["ok"]), (400, False), body)
                self.assertTrue(body["message"].endswith(".") and "Traceback" not in body["message"], body)
                self.assertEqual(self.s.read(kind, ref=ref), was)
                self.assertEqual(self.logged(), logged)

    def test_the_rule_lives_in_the_not_null_list(self):
        self.assertIn("client_message", changes.ITEM_NOT_NULL)
        with self.assertRaises(changes.Refused) as caught:
            changes._checked_item_changes({"client_message": None})
        self.assertEqual(str(caught.exception), changes.ITEM_VALUE_WORDS)


if __name__ == "__main__":
    unittest.main()
