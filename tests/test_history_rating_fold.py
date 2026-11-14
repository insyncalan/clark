"""Item 1182: impact, likelihood and priority changes made in one step are ONE Activity line, field "Rating".

Run: python3 dev/run_tests.py test_history_rating_fold
Pure Python over a real demo store (fictional data): history.rows_for_item folds the step's rows.
"""
import unittest

from _demo import USER, DemoStore
from clark import changes, history


class RatingFold(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        with self.s.step("dashboard", USER) as st:
            self.risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier late", "impact": "Low",
                                           "likelihood": "Low", "raised": "2026-10-01", "source": "demo"})

    def send(self, changes_):
        return self.change({"project": "ABC", "kind": "raid", "op": "bulk", "ids": [self.risk], "changes": changes_, "place": "cell"})

    def lines(self, step):
        return [r for r in history.rows_for_item(self.s.con, self.risk) if r.get("step") == step and r["kind"] == "Changed"]

    def test_impact_likelihood_and_priority_are_one_line(self):
        status, body = self.send({"impact": "High", "likelihood": "Medium"})
        self.assertEqual((status, body["ok"]), (200, True), body)
        got = self.lines(body["apply_id"])
        self.assertEqual(len(got), 1, [(r["field"], r["from"], r["to"]) for r in got])
        self.assertEqual(got[0]["field"], "Rating")
        self.assertEqual(got[0]["from"], "Low impact, Low likelihood: Low")
        self.assertEqual(got[0]["to"], "High impact, Medium likelihood: High")

    def test_one_field_and_its_priority_is_one_line(self):
        status, body = self.send({"impact": "High"})
        got = self.lines(body["apply_id"])
        self.assertEqual([(r["field"], r["to"]) for r in got], [("Rating", "High impact: High")])


if __name__ == "__main__":
    unittest.main()
