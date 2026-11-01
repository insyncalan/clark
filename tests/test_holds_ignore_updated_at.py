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
        # #355: if the stamp row were not kept here, the hold tests below could never fail on it
        self.assertIn("updated_at", {r["field"] for r in self.changes},
                      "the step's own rows include its stamp, so holds has a stamp to compare")

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

    def stamp_only_step(self, ref):
        """A later step whose only row is the stamp of `ref`, with the stamp itself moved on."""
        self.con.execute("UPDATE actions SET updated_at = ? WHERE id = ?", ("2031-01-01T00:00:00", ref))
        self.con.commit()
        with self.demo.store.step("dashboard", "Demo User") as st:
            sm.log(st.con, st, "actions", ref, "updated_at", "2031-01-01T00:00:00", "2031-01-02T00:00:00", "update")
        return self.demo.last_step()

    def test_undoing_an_add_goes_ahead_when_only_the_stamp_has_moved(self):
        """#355: the created-row path is the one that calls holds. Its rows include the stamp, so if holds stopped
        skipping it, or changed_after counted a stamp-only step, the add could not be undone."""
        ref = self.demo.action(description="Book the review room")
        add = self.demo.last_step()
        self.assertIn("updated_at", {r["field"] for r in self.con.execute(
            "SELECT field FROM change_log WHERE apply_id = ?", (add,))}, "the add's own rows include the stamp")
        self.stamp_only_step(ref)
        done = self.demo.store.undo(add, "Demo User")
        self.assertEqual(done["skipped"], [], "nothing is left as it is")
        self.assertIsNone(sm.fetch(self.con, "actions", ref), "the added row is removed")

    def test_a_skipped_undo_names_the_real_later_step_not_a_newer_stamp_only_one(self):
        """#355: changed_after names the newest later step that changed a field; a stamp-only step after it is not one."""
        real = self.demo.update("actions", self.ref, {"status": "Closed"})
        self.stamp_only_step(self.ref)                                  # newer than the real change
        done = self.demo.store.undo(self.step, "Demo User")
        self.assertEqual(done["reversed"], [], "a real later change to the same field is not undone over")
        self.assertEqual([e["by_step"] for e in done["skipped"]], [real],
                         "the real step is named, not the stamp-only one")
        self.assertEqual(sm.fetch(self.con, "actions", self.ref)["status"], "Closed")


if __name__ == "__main__":
    unittest.main()
