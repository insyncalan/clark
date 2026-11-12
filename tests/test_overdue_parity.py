"""Python and the page agree on what is overdue, status by status (workItems.js dueCell and glanceTiles.js tiles).

Run: python3 dev/run_tests.py test_overdue_parity
The Work items list and the At a glance Overdue tile count a Completed action as open, so an overdue Completed action is counted
there, in Python and in the page alike; the Word report's due cell (excel_colours.is_late) says "(overdue)" only for a still-open
status, so a Completed action is never drawn late there, as on the report's rows (sectionRows.js lateWord).
"""
import json
import unittest
from datetime import date

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import excel_colours, glance
from test_completed_blue import node
from test_work_items import bundled

TODAY = "2026-10-28"
STATUSES = ("Open", "Delayed", "Completed", "Closed", "Cancelled", "In progress", "Blocked")
PAGE = SRC / "clark" / "page" / "src"


def rows():
    out = [{"id": f"A{i}", "kind": "action", "status": s, "due_date": "2020-01-01"} for i, s in enumerate(STATUSES)]
    out += [{"id": f"D{s}", "kind": "decision", "status": s, "needed_by": "2020-01-01", "date": "2020-01-01"} for s in ("Pending", "Made", "Withdrawn")]
    return out


class Parity(unittest.TestCase):
    def test_is_overdue_matches_the_pages_due_cell_for_every_status(self):
        got = node(bundled() + ";console.log(JSON.stringify(%s.map((r) => WI.dueCell(r, %s).tone === 'late')))" % (json.dumps(rows()), json.dumps(TODAY)))
        self.assertEqual(got, [glance.is_overdue(r, TODAY) for r in rows()])
        self.assertTrue(glance.is_overdue(rows()[STATUSES.index("Completed")], TODAY))      # open in both, so counted by both
        self.assertFalse(glance.is_overdue(rows()[STATUSES.index("Closed")], TODAY))

    def test_the_overdue_tile_counts_the_same_in_python_and_the_page(self):
        code = bundled(PAGE / "glanceTiles.js", "GT")
        got = node(code + ";console.log(JSON.stringify(GT.tiles(%s, %s)[0].value))" % (json.dumps(rows()), json.dumps(TODAY)))
        self.assertEqual(got, glance._overdue_tile(rows(), TODAY)["value"])

    def test_the_word_due_cell_is_late_only_for_a_still_open_status(self):
        for s in STATUSES + ("Pending",):
            row = {"status": s, "due_date": "2020-01-01"}
            self.assertEqual(excel_colours.is_late("actions", "due_date", row, date(2026, 10, 28)), s in ("Open", "Delayed"), s)


if __name__ == "__main__":
    unittest.main()
