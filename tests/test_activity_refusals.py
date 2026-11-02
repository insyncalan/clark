"""The Activity tab's rows say which changes Undo several would refuse, and why (the server part).
Run: python3 dev/run_tests.py test_activity_refusals

Each row of the item's changes carries `undo_refused`: the plain reason when Undo several would leave that change out whole, else an
empty string. One test for each route that is refused: an undo, an Excel import, a Word import, a change ask clark did not make
under its own name, and a change that has been undone already. The page withholds the tick from any row with a reason."""
import unittest
from unittest import mock

from _demo import USER, DemoStore
from clark import activity_read, changes
from clark import store as clark_store


class Refusals(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.item = self.demo.action(priority="Low")
        self.read = activity_read.make_read(self.store.path, self.store.data_for)

    def write(self, route, **kw):
        """One change to the item's priority on `route`; its step."""
        with self.store.step(route, USER, **kw) as st:
            st.update("actions", self.item, {"priority": "High" if route != "dashboard" else "Medium"})
        return self.demo.last_step()

    def reason(self, step):
        rows = [r for r in self.read("ABC", self.item)["rows"] if r["step"] == step]
        self.assertTrue(rows, "the step is in the item's changes")
        self.assertEqual(len({r["undo_refused"] for r in rows}), 1, "one reason for one step")
        return rows[0]["undo_refused"]

    def test_a_change_made_here_has_no_reason(self):
        self.assertEqual(self.reason(self.write("dashboard")), "")

    def test_an_undo_says_it_is_an_undo(self):
        step = self.write("dashboard")
        done = self.store.undo(step, USER)
        self.assertEqual(self.reason(done["step_id"]), changes.IS_AN_UNDO)

    def test_an_excel_import_says_it_cannot_be_undone_from_here(self):
        self.assertEqual(self.reason(self.write("excel")), changes.NOT_FROM_HERE)

    def test_a_word_import_says_it_cannot_be_undone_from_here(self):
        self.assertEqual(self.reason(self.write("word")), changes.NOT_FROM_HERE)

    def test_a_change_ask_clark_did_not_make_under_its_own_name_says_it_cannot_be_undone_from_here(self):
        self.assertEqual(self.reason(self.write("assistant", actor="you")), changes.NOT_FROM_HERE)

    def test_a_change_ask_clark_made_under_its_own_name_has_no_reason(self):
        self.assertEqual(self.reason(self.write("assistant", actor=changes.ASK_ACTOR)), "")

    def test_a_change_that_is_undone_already_says_so(self):
        step = self.write("dashboard")
        self.store.undo(step, USER)
        self.assertEqual(self.reason(step), changes.UNDONE_ALREADY)

    def test_the_reason_is_the_one_undo_several_gives(self):
        """A row withheld here is a row the preview would leave out, in the same words."""
        steps = {"excel": self.write("excel"), "done": self.write("dashboard")}
        self.store.undo(steps["done"], USER)
        status, got = changes.make_undo(self.store.path, [], USER)({"project": "ABC", "steps": list(steps.values()), "preview": True})
        self.assertEqual(status, 200, got)
        said = {s["step"]: s["why"] for s in got["skipped"]}
        self.assertEqual(set(said), set(steps.values()))
        for step in steps.values():
            self.assertEqual(said[step], self.reason(step))

    def test_a_step_with_no_rows_is_not_named(self):
        self.assertEqual(changes.undo_refusals(self.store, "ABC", {99999}), {})

    def test_the_reverted_set_is_read_once_per_activity_read(self):
        """#377: many steps, one scan of the undo history."""
        for _ in range(4):
            self.store.undo(self.write("dashboard"), USER)
        real, calls = clark_store.reverted_rowids, []
        with mock.patch.object(clark_store, "reverted_rowids", lambda con: calls.append(1) or real(con)):
            rows = self.read("ABC", self.item)["rows"]
        self.assertGreater(len({r["step"] for r in rows}), 3)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
