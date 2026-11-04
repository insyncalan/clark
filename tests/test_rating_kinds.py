"""Which RAID types carry a rating: the store names them (store.RATING_TYPES) and changes.py uses that one list.

Run: python3 dev/run_tests.py test_rating_kinds
Pure Python over a real demo store (fictional data). The refusal itself is also covered in test_changes
(test_only_a_risk_or_issue_takes_a_rating_whatever_its_status); this pins the two lists together so they cannot drift.
"""
import unittest

from _demo import USER, DemoStore
from clark import changes
from clark import store as clark_store


class RatingKinds(unittest.TestCase):
    def test_one_list_and_every_entry_is_a_raid_type(self):
        self.assertIs(changes.RATING_KINDS, clark_store.RATING_TYPES)
        self.assertEqual(tuple(changes.RATING_KINDS), ("Risk", "Issue"))
        self.assertTrue(set(clark_store.RATING_TYPES) <= set(clark_store.ALLOWED[("raid", "type")]))

    def test_every_other_raid_type_is_refused_a_rating_through_the_real_path(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        change = changes.make_change(demo.store.path, [], USER)
        self.assertTrue([t for t in clark_store.ALLOWED[("raid", "type")] if t not in clark_store.RATING_TYPES])
        for t in clark_store.ALLOWED[("raid", "type")]:
            with demo.store.step("dashboard", USER) as st:
                ref = st.create("raid", {"project": "ABC", "type": t, "description": f"A {t}", "impact": "High", "likelihood": "Medium",
                                         "raised": "2026-10-01", "source": "demo"})
            status, body = change({"project": "ABC", "kind": "raid", "op": "update", "id": ref, "changes": {"impact": "Low"}, "place": "cell"})
            if t in clark_store.RATING_TYPES:
                self.assertEqual((status, body["ok"]), (200, True), body)
            else:
                self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.RATING_NOT_THIS_KIND), t)


if __name__ == "__main__":
    unittest.main()
