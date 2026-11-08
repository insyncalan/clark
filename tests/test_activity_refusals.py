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

    def test_the_reason_is_the_one_undo_several_gives_for_an_undo_and_a_flagged_step(self):
        """#600: the undo case, and a step whose applies row says undone_at: the tab and the preview ask the same questions."""
        step = self.write("dashboard")
        undo = self.store.undo(step, USER)["step_id"]
        flagged = self.write("dashboard")
        self.store.con.execute("UPDATE applies SET undone_at = '2026-11-07T00:00:00Z' WHERE apply_id = ?", (flagged,))
        self.store.con.commit()
        steps = [undo, flagged]
        status, got = changes.make_undo(self.store.path, [], USER)({"project": "ABC", "steps": steps, "preview": True})
        self.assertEqual(status, 200, got)
        said = {s["step"]: s["why"] for s in got["skipped"]}
        self.assertEqual(set(said), set(steps))
        self.assertEqual(self.reason(flagged), changes.UNDONE_ALREADY, "the tick is withheld for a step Undo several would skip")
        self.assertEqual(self.reason(undo), changes.IS_AN_UNDO)
        for step in steps:
            self.assertEqual(said[step], self.reason(step), "the same words in the tab and in the preview")

    def test_step_undone_follows_the_applies_flag_that_undo_several_uses(self):
        step = self.write("dashboard")
        self.assertFalse(self.store.step_undone(step))
        self.store.con.execute("UPDATE applies SET undone_at = '2026-11-07T00:00:00Z' WHERE apply_id = ?", (step,))
        self.store.con.commit()
        self.assertTrue(self.store.step_undone(step))
        self.assertEqual(self.store.step_undone(99999), False, "a step that is not there is not undone")

    def two_row_step(self):
        """One step that changes two fields of the item; its step."""
        with self.store.step("dashboard", USER) as st:
            st.update("actions", self.item, {"priority": "High", "status": "Delayed"})
        return self.demo.last_step()

    def test_a_two_row_step_undone_on_one_row_only_has_no_reason_until_both_are_back(self):
        first = self.two_row_step()
        self.demo.update("actions", self.item, {"status": "Open"})        # a later change to one of its two fields
        later = self.demo.last_step()
        partly = self.store.undo(first, USER)
        self.assertEqual([d["field"] for d in partly["reversed"]], ["priority"], "only one row went back")
        self.assertEqual(self.reason(first), "", "one row is still in force, so the step can be chosen")
        self.store.undo(later, USER)
        self.store.undo(first, USER)
        self.assertEqual(self.reason(first), changes.UNDONE_ALREADY)

    def test_a_step_handed_to_another_project_is_not_named_as_an_undo(self):
        """A step looked at from a project that does not own it is left out whole, in the words for a change not made here."""
        step = self.write("dashboard")
        self.assertEqual(changes.undo_refusals(self.store, "ZZZ", {step}), {step: changes.NOT_FROM_HERE})
        self.assertEqual(changes.undo_refusals(self.store, "ABC", {step}), {})

    def test_the_page_says_an_undo_in_the_servers_words(self):
        """One check over both: the page withholds an undo row with the server's sentence, whatever the page's own words are."""
        import json
        import subprocess
        import shutil
        from pathlib import Path
        node = shutil.which("node")
        src = (Path(__file__).resolve().parent.parent / "src/clark/page/src/edit/activityUndo.js").read_text(encoding="utf-8")
        self.assertIn("r.undo_refused", src)
        self.assertLess(src.index("r.undo_refused"), src.index('r.kind === "Comment"'), "the server's reason is asked first")
        if node:
            row = {"kind": "Priority undone", "step": 3, "undo_refused": changes.IS_AN_UNDO}
            js = "import('" + (Path(__file__).resolve().parent.parent / "src/clark/page/src/edit/activityUndo.js").as_uri() + "')" \
                 ".then(m => console.log(JSON.stringify(m.whyNot(" + json.dumps(row) + "))))"
            out = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=30)
            self.assertEqual(json.loads(out.stdout), changes.IS_AN_UNDO, out.stderr)

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
