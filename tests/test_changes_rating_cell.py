"""#210: a risk's or issue's Priority cell sets its impact or likelihood, sent as a bulk change of that one item from the cell.

Run: python3 dev/run_tests.py test_changes_rating_cell
Pure Python over a real demo store (fictional data). The page sends {kind: raid, op: bulk, ids: [one id], changes: {impact or
likelihood}, place: cell}: clark writes it in one step with one Undo, works the priority out again, and logs who, how ("cell",
said "in the table") and when. Every value that is not High, Medium or Low, and every field or kind the cell never sends, is
refused with nothing written. No change to clark/changes.py: these are the bulk change's own checks (#196).
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import changes, history
from clark import store as clark_store


class RatingCell(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        self.action = self.demo.action(owner="Ada Quillfeather", priority="High", status="Open")
        with self.s.step("dashboard", USER) as st:
            self.risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier late", "impact": "Medium",
                                           "likelihood": "Low", "raised": "2026-10-01", "source": "demo"})
            self.issue = st.create("raid", {"project": "ABC", "type": "Issue", "description": "Server down", "impact": "Low",
                                            "likelihood": "Low", "raised": "2026-10-01", "source": "demo"})
            self.decision = st.create("decisions", {"project": "ABC", "decision": "Go", "made_by": "Board", "status": "Pending",
                                                    "source": "demo"})

    def send(self, changes_, ids=None, kind="raid", place="cell"):
        return self.change({"project": "ABC", "kind": kind, "op": "bulk", "ids": ids or [self.risk], "changes": changes_, "place": place})

    def counts(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return con.execute("SELECT (SELECT count(*) FROM applies), (SELECT count(*) FROM change_log), "
                               "(SELECT count(*) FROM item_events)").fetchone()
        finally:
            con.close()

    def refused(self, changes_, words, **more):
        before, row = self.counts(), self.s.read("raid", ref=self.risk)
        got, body = self.send(changes_, **more)
        self.assertEqual((got, body["ok"], body["message"]), (400, False, words), body)
        self.assertEqual(self.counts(), before, "nothing was written")
        self.assertEqual(self.s.read("raid", ref=self.risk), row)

    def test_the_cells_pick_is_one_step_with_one_undo_and_the_priority_follows(self):
        self.assertEqual(self.s.read("raid", ref=self.risk)["priority"], "Medium")
        before = self.counts()[0]
        status, body = self.send({"impact": "High"})
        self.assertEqual((status, body["ok"], body["changed"], body["left_out"]), (200, True, [self.risk], []), body)
        self.assertTrue(body["undoable"])
        self.assertEqual(self.counts()[0], before + 1, "one step")
        row = self.s.read("raid", ref=self.risk)
        self.assertEqual((row["impact"], row["likelihood"], row["priority"]), ("High", "Low", "High"), "the priority is worked out again")
        line = [e for e in self.s.history(self.risk) if e["field"] == "impact" and e["step"] == body["apply_id"]]
        self.assertEqual(len(line), 1)
        self.assertEqual((line[0]["before"], line[0]["after"], line[0]["place"], line[0]["by_user"]), ("Medium", "High", "cell", USER), "who and how")
        self.assertTrue(line[0]["at"], "when")
        self.assertEqual(history.HOW_PLACES["cell"], history.HOW_TABLE, "said as made in the table")
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["ok"]), (200, True), undone)
        row = self.s.read("raid", ref=self.risk)
        self.assertEqual((row["impact"], row["priority"]), ("Medium", "Medium"), "one Undo puts the impact and the priority back")

    def test_an_issues_likelihood_too(self):
        status, body = self.send({"likelihood": "High"}, ids=[self.issue])
        self.assertEqual((status, body["changed"]), (200, [self.issue]), body)
        self.assertEqual(self.s.read("raid", ref=self.issue)["priority"], "High")

    def test_the_store_takes_only_high_medium_or_low(self):
        self.assertEqual(clark_store.ALLOWED[("raid", "impact")], ("High", "Medium", "Low"))
        self.assertEqual(clark_store.ALLOWED[("raid", "likelihood")], ("High", "Medium", "Low"))

    def test_each_bad_value_is_refused_with_nothing_written(self):
        for field in ("impact", "likelihood"):
            for bad in ("Urgent", "Critical", "high", "HIGH", "Red", "Very high", "Hi gh"):
                with self.subTest(field=field, bad=bad):
                    self.refused({field: bad}, changes.NOT_A_CHOICE)
            with self.subTest(field=field, bad=""):
                self.refused({field: ""}, "That value isn't one clark can use.")

    def test_a_value_of_the_wrong_type_is_refused_with_nothing_written(self):
        for field in ("impact", "likelihood"):
            for bad in (3, 1.5, True, ["High"], {"v": "High"}):
                with self.subTest(field=field, bad=bad):
                    before = self.counts()
                    got, body = self.send({field: bad})
                    self.assertEqual((got, body["ok"]), (400, False), body)
                    self.assertEqual(self.counts(), before, "nothing was written")

    def test_the_priority_itself_is_never_taken(self):
        before = self.counts()
        got, body = self.send({"priority": "Low"})
        self.assertEqual((got, body["ok"]), (400, False), body)
        self.assertEqual(self.counts(), before)

    def test_impact_on_an_action_or_a_decision_is_refused(self):
        for kind, ref in (("actions", self.action), ("decisions", self.decision)):
            with self.subTest(kind=kind):
                before = self.counts()
                got, body = self.send({"impact": "High"}, ids=[ref], kind=kind)
                self.assertEqual((got, body["ok"]), (400, False), body)
                self.assertEqual(self.counts(), before)

    def test_a_place_that_is_not_the_pages_is_refused(self):
        self.refused({"impact": "High"}, changes.BAD_PLACE, place="excel")


if __name__ == "__main__":
    unittest.main()
