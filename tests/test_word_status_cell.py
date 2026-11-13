"""Row 1021 (mutation hardening): the Word copy's Status cell, one decision at a time.

Run: python3 dev/run_tests.py test_word_status_cell
test_word_status_word pins the WORDS against the page. This file pins what it did not: the cell's colour, a risk and an issue
reading alike, and an assumption or a dependency keeping its own status word, with no colour.
"""
import unittest

from _paths import SRC  # noqa: F401  (puts src/ on the path)

import test_word_status_word as w
from clark import docx_build

TODAY = "2026-10-28"


def cell(row, kind):
    ctx = docx_build._Ctx(docx_build.palette(None), TODAY)
    body, fill = docx_build._status_cell(row, kind, ctx)
    return body, fill, ctx


class StatusColour(unittest.TestCase):
    def test_each_word_has_its_own_fill(self):
        for kind, row, word, colour in (
            ("action", {"status": "Open", "due_date": "2026-10-20"}, "Overdue", "red"),
            ("action", {"status": "Delayed", "due_date": "2026-12-20"}, "Delayed", "amber"),
            ("action", {"status": "Open", "due_date": "2026-10-30"}, "Due soon", "amber"),
            ("action", {"status": "Open", "due_date": "2026-12-20"}, "On track", "green"),
            ("risk", {"status": "Open", "priority": "High"}, "Red", "red"),
            ("risk", {"status": "Open", "priority": "Medium"}, "Amber", "amber"),
            ("issue", {"status": "Open", "priority": "Low"}, "Green", "green"),
        ):
            body, fill, ctx = cell(row, kind)
            self.assertIn(word, body, (kind, row))
            self.assertEqual(fill, ctx.hexes(colour)[0], (kind, row))

    def test_an_unrated_risk_has_no_fill(self):
        body, fill, _ = cell({"status": "Open", "priority": None}, "risk")
        self.assertIn("Not rated", body)
        self.assertIsNone(fill)


class OtherKindsOfRaidRow(unittest.TestCase):
    def test_an_issue_reads_by_its_priority_like_a_risk(self):
        for priority, word in (("Urgent", "Red"), ("Medium", "Amber"), ("Low", "Green")):
            body, _, _ = cell({"status": "Open", "priority": priority}, "issue")
            self.assertIn(word, body, priority)

    def test_an_assumption_or_a_dependency_keeps_its_own_status_and_no_fill(self):
        for kind in ("assumption", "dependency"):
            body, fill, _ = cell({"status": "Open", "priority": "High", "due_date": "2026-10-20"}, kind)
            self.assertIn(">Open<", body, kind)
            self.assertNotIn("Red", body, kind)
            self.assertIsNone(fill, kind)

    def test_in_the_built_file_an_assumption_row_says_its_own_status(self):
        got = w.word_status(w.edit("raid", "PUB-001", type="Assumption", status="Open", priority="High"))
        self.assertEqual(got.get("PUB-001"), "Open", got)


if __name__ == "__main__":
    unittest.main()
