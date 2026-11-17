"""Row 1282: the Work items list's Priority drop-down of a risk or an issue is the peek's own Impact x Likelihood matrix, one shared component.

Run: python3 dev/run_tests.py test_priority_one_control_1282
These checks read the page's source, so they run without Chrome. The browser run of the same behaviour is in test_priority_rating_cell.
"""
import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "clark" / "page" / "src" / "edit"


class OneControl(unittest.TestCase):
    def test_the_list_picker_for_a_risk_or_an_issue_is_the_peeks_matrix(self):
        text = (SRC / "cells" / "PriorityPick.jsx").read_text(encoding="utf-8")
        self.assertRegex(text, r'import \{ Matrix \} from "\.\./PeekRating\.jsx"')
        self.assertRegex(text, r'row\.kind !== "action"\) return <Matrix ')

    def test_the_peek_uses_the_same_component(self):
        self.assertIn("<Matrix ", (SRC / "PeekProps.jsx").read_text(encoding="utf-8"))

    def test_there_is_no_second_copy_of_the_two_stacked_lists(self):
        self.assertFalse((SRC / "cells" / "RatingPick.jsx").exists(), "the old two-list picker is gone")
        for path in SRC.rglob("*.jsx"):
            self.assertNotIn("RatingPick.jsx", path.read_text(encoding="utf-8"), path.name)

    def test_the_change_says_where_it_was_made(self):
        text = (SRC / "PeekRating.jsx").read_text(encoding="utf-8")
        self.assertRegex(text, r'function Matrix\(\{[^}]*place = "peek"')
        self.assertIsNone(re.search(r'place: "peek"', text), "the place is the one the caller gave, not fixed to the peek")


if __name__ == "__main__":
    unittest.main()
