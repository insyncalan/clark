"""Item 1183: the Issue peek is the Risk peek with the kind changed. Run: python3 dev/run_tests.py test_peek_issue_1183

Every check of test_peek_risk_1182 (the Rating chip, the 3 x 3 matrix, one change with both fields and one Undo, the keys, the three-value
Status, "Red kept") runs here on an open Urgent issue of the demo store, so an issue's impact and likelihood are shown to be the same fields,
set the same way, as a risk's. The ticket's open check, answered in the store: an issue is a row of the same raid table, rated (store.RATED).
The browser parts are required: they fail, never skip, without Chrome (set CLARK_CHROME to its path).
"""
import unittest

from clark import store
from test_peek_risk_1182 import Peek


class IssuePeek(Peek, unittest.TestCase):
    REF, KIND = "TUL-010", "issue"
    WORD, LEVEL = "Red", "Urgent"
    FROM = ("High", "High")
    CHOICE = ("Low", "Low")
    TO_LEVEL, TO_WORD = "Low", "Green"


class StoreSide(unittest.TestCase):
    def test_an_issue_is_rated_in_the_same_way_as_a_risk(self):
        self.assertTrue(store.RATED["Issue"])
        self.assertTrue(store.RATED["Risk"])
        self.assertEqual(store.priority("High", "High"), "Urgent")


if __name__ == "__main__":
    unittest.main()
