"""#248 (from #197): holds and changed_after skip updated_at on purpose. The stamp follows every change and every undo, so
counting it would let an unrelated edit block an undo. A real field change still releases a hold and still counts as a
later change. This pins both halves at the store level.

Run: python3 dev/run_tests.py test_holds_ignore_updated_at
Each test makes a real store in a temporary folder with fictional data.
"""
import unittest

from _demo import DemoStore
from clark import store as sm


class HoldsIgnoreUpdatedAt(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.con = self.demo.store.con
        self.ref = self.demo.action()
        self.step = self.demo.update("actions", self.ref, {"status": "Delayed"})
        self.changes = [dict(r) for r in self.con.execute(
            "SELECT rowid, field, new_value FROM change_log WHERE apply_id = ? AND field IN ('status', 'updated_at')", (self.step,))]
        self.rowid = max(r["rowid"] for r in self.changes)
        self.assertIn("updated_at", {r["field"] for r in self.changes},     # #355: if the stamp row is not kept, the hold tests below
                      "the step's own rows include its stamp, so holds has a stamp to compare")   # could never fail on it

    def test_baseline_holds_and_nothing_later(self):
        self.assertTrue(sm.holds(self.con, "actions", self.ref, self.changes))
        self.assertIsNone(sm.changed_after(self.con, self.rowid, "actions", self.ref))

    def test_a_moved_stamp_alone_neither_releases_a_hold_nor_counts_as_changed(self):
        self.con.execute("UPDATE actions SET updated_at = ? WHERE id = ?", ("2031-01-01T00:00:00", self.ref))
        with self.demo.store.step("dashboard", "Demo User") as st:      # a step whose only row is the stamp
            sm.log(st.con, st, "actions", self.ref, "updated_at", "a", "b", "update")
        self.assertTrue(sm.holds(self.con, "actions", self.ref, self.changes))
        self.assertIsNone(sm.changed_after(self.con, self.rowid, "actions", self.ref))

    def test_a_real_field_change_releases_the_hold_and_counts_as_changed(self):
        later = self.demo.update("actions", self.ref, {"status": "Closed"})
        self.assertFalse(sm.holds(self.con, "actions", self.ref, self.changes))
        self.assertEqual(sm.changed_after(self.con, self.rowid, "actions", self.ref), later)

    def test_an_unrelated_field_edit_counts_as_changed_but_leaves_the_hold(self):
        later = self.demo.update("actions", self.ref, {"description": "Rewrite the cut-over plan"})
        self.assertTrue(sm.holds(self.con, "actions", self.ref, self.changes))
        self.assertEqual(sm.changed_after(self.con, self.rowid, "actions", self.ref), later)

    def test_a_real_undo_goes_ahead_when_only_the_stamp_has_moved(self):
        """#355: through Store.undo, not just holds and changed_after: a stamp that moved on its own does not stop the undo."""
        self.con.execute("UPDATE actions SET updated_at = ? WHERE id = ?", ("2031-01-01T00:00:00", self.ref))
        self.con.commit()
        with self.demo.store.step("dashboard", "Demo User") as st:
            sm.log(st.con, st, "actions", self.ref, "updated_at", "2031-01-01T00:00:00", "2031-01-02T00:00:00", "update")
        done = self.demo.store.undo(self.step, "Demo User")
        self.assertEqual(done["skipped"], [], "nothing is left as it is")
        self.assertIn("status", {e["field"] for e in done["reversed"]})
        self.assertNotEqual(sm.fetch(self.con, "actions", self.ref)["status"], "Delayed")

    def test_a_real_undo_leaves_a_field_that_a_real_later_change_moved(self):
        """#355: the other half through Store.undo: a real later change to the same field is not undone over."""
        self.demo.update("actions", self.ref, {"status": "Closed"})
        done = self.demo.store.undo(self.step, "Demo User")
        self.assertEqual(done["reversed"], [], "nothing is put back")
        self.assertIn("status", {e["field"] for e in done["skipped"]})
        self.assertEqual(sm.fetch(self.con, "actions", self.ref)["status"], "Closed")


if __name__ == "__main__":
    unittest.main()
