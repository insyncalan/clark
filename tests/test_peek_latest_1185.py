"""Row 1185: the peek source draws the Latest update box for every kind that has the column (a source-level check; the box itself is
covered in test_peek_latest). Run: python3 dev/run_tests.py test_peek_latest_1185
"""
import re
import unittest

from _paths import SRC

PAGE = SRC / "clark" / "page" / "src"


class PeekSource(unittest.TestCase):
    def read(self, rel):
        return (PAGE / rel).read_text(encoding="utf-8")

    def test_the_box_is_not_gated_on_an_action(self):
        src = self.read("edit/PeekLatest.jsx")
        self.assertNotRegex(src, r"action\s*\?")
        self.assertNotIn('"actions"', src)          # the table comes from the row, not a fixed word

    def test_a_risk_row_carries_the_field_to_the_peek(self):
        src = self.read("workItems.js")
        raid = [l for l in src.splitlines() if "latest_update" in l]
        self.assertGreaterEqual(len(raid), 2, "actions and risks/issues both read latest_update")


if __name__ == "__main__":
    unittest.main()
