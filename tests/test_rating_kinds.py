"""Which RAID types carry a rating: store.RATED decides it for every RAID type, store.RATING_TYPES is derived from it, changes.py uses that.

Run: python3 dev/run_tests.py test_rating_kinds
Pure Python over a real demo store (fictional data). The refusal itself is also covered in test_changes
(test_only_a_risk_or_issue_takes_a_rating_whatever_its_status); this pins the table to the RAID types so a new type cannot go undecided.
"""
import unittest

from _demo import USER, DemoStore
from clark import changes
from clark import store as clark_store


class RatingKinds(unittest.TestCase):
    def test_every_raid_type_has_a_rating_decision_and_no_other(self):
        self.assertEqual(set(clark_store.RATED), set(clark_store.ALLOWED[("raid", "type")]))

    def test_the_rated_types_are_pinned(self):
        self.assertEqual(clark_store.RATING_TYPES, ("Risk", "Issue"))
        self.assertIs(changes.RATING_KINDS, clark_store.RATING_TYPES)

    def test_through_the_real_path_risk_and_issue_take_a_rating_the_others_are_refused(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        change = changes.make_change(demo.store.path, [], USER)
        for t in clark_store.ALLOWED[("raid", "type")]:
            with demo.store.step("dashboard", USER) as st:
                ref = st.create("raid", {"project": "ABC", "type": t, "description": f"A {t}", "impact": "High", "likelihood": "Medium",
                                         "raised": "2026-10-01", "source": "demo"})
            status, body = change({"project": "ABC", "kind": "raid", "op": "update", "id": ref, "changes": {"impact": "Low"}, "place": "cell"})
            if t in ("Risk", "Issue"):
                self.assertEqual((status, body["ok"]), (200, True), body)
            else:
                self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.RATING_NOT_THIS_KIND), t)


if __name__ == "__main__":
    unittest.main()
