"""#67: the store can undo a row hidden from the report (REVERT_CREATED holds report_hidden; store.py is guarded).

Run: python3 dev/run_tests.py test_hidden_store
Fictional demo data in a temporary store.
"""
import unittest

from _demo import USER, DemoStore
from clark import store as store_module


class HiddenUndo(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def hide(self, item):
        with self.s.step("dashboard", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": item})
        return self.demo.last_step()

    def test_the_kind_is_listed_once(self):
        self.assertEqual(store_module.REVERT_CREATED.count("report_hidden"), 1)

    def test_undoing_a_hide_removes_the_row_and_undoing_that_puts_it_back(self):
        a = self.demo.action()
        step = self.hide(a)
        self.assertEqual([r["item_id"] for r in self.s.read("report_hidden", "ABC")], [a])
        done = self.s.undo(step, USER)
        self.assertEqual((self.s.read("report_hidden", "ABC"), done["skipped"]), ([], []))
        self.assertEqual({e["change"] for e in done["reversed"]}, {"removed"})
        again = self.s.undo(done["step_id"], USER)
        self.assertEqual([r["item_id"] for r in self.s.read("report_hidden", "ABC")], [a])
        self.assertEqual(again["skipped"], [])

    def test_a_hide_that_was_shown_and_hidden_again_is_not_undone_by_the_first_step(self):
        a = self.demo.action()
        first = self.hide(a)
        with self.s.step("dashboard", USER) as st:
            st.cancel("report_hidden", f"ABC|{a}")
        self.hide(a)
        done = self.s.undo(first, USER)
        self.assertEqual(done["reversed"], [])
        self.assertEqual([s["why"] for s in done["skipped"]], ["has changed since: left as it is"])
        self.assertEqual([r["item_id"] for r in self.s.read("report_hidden", "ABC")], [a])


if __name__ == "__main__":
    unittest.main()
