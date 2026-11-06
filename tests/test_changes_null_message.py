"""Item 611 (kept) and row 893: a work item's client wording may be cleared (null or a blank string becomes the empty string the column keeps, one step, one
Undo), while a value that is not text is still refused in plain words and every other not-null field is still refused when
cleared. All rows are fictional.

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

    def test_a_client_message_that_is_not_text_is_refused_and_nothing_is_saved(self):
        for kind, ref in self.refs.items():
            for bad in (5, ["x"], True):
                with self.subTest(kind=kind, bad=bad):
                    was, logged = self.s.read(kind, ref=ref), self.logged()
                    status, body = self.change({"project": "ABC", "kind": kind, "op": "update", "id": ref,
                                                "changes": {"client_message": bad}, "place": "menu"})
                    self.assertEqual((status, body["ok"]), (400, False), body)
                    self.assertTrue(body["message"].endswith(".") and "Traceback" not in body["message"], body)
                    self.assertEqual(self.s.read(kind, ref=ref), was)
                    self.assertEqual(self.logged(), logged)

    def test_the_other_not_null_fields_are_still_refused_when_cleared(self):
        self.assertNotIn("client_message", changes.ITEM_NOT_NULL)
        for field in ("status", "owner", "priority", "description", "decision", "impact", "likelihood"):
            with self.subTest(field=field), self.assertRaises(changes.Refused) as caught:
                changes._checked_item_changes({field: None}, blank_clears=("client_message",))
            self.assertEqual(str(caught.exception), changes.ITEM_VALUE_WORDS)
        with self.assertRaises(changes.Refused):
            changes._checked_item_changes({"description": "  "}, blank_clears=("client_message",))

    def test_a_blank_client_message_is_refused_on_a_new_row(self):
        for blank in ("", "  "):
            status, body = self.change({"project": "ABC", "kind": "actions", "op": "new", "place": "menu",
                                        "values": {"description": "Fresh step", "client_message": blank}})
            self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.ITEM_VALUE_WORDS))


if __name__ == "__main__":
    unittest.main()
