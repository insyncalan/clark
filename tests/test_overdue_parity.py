"""Python and the page agree on what is overdue, status by status (workItems.js dueCell and glanceTiles.js tiles).

Run: python3 dev/run_tests.py test_overdue_parity
A Completed action still counts as open, but it is finished work: it is never overdue, in the page (the due cell, the Overdue tile,
the Overdue filter, the pill) and in Python (glance.is_overdue and every count built from it) and in the Word report's due cell
(excel_colours.is_late), as on the report's rows (sectionRows.js lateWord).
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
        self.assertFalse(glance.is_overdue(rows()[STATUSES.index("Completed")], TODAY))     # open, but finished work: late in neither
        self.assertTrue(glance.is_overdue(rows()[STATUSES.index("Open")], TODAY))
        self.assertTrue(glance.is_open(rows()[STATUSES.index("Completed")]))                # still open for the open counts
        self.assertFalse(glance.is_overdue(rows()[STATUSES.index("Closed")], TODAY))

    def test_the_overdue_tile_counts_the_same_in_python_and_the_page(self):
        code = bundled(PAGE / "glanceTiles.js", "GT")
        got = node(code + ";console.log(JSON.stringify(GT.tiles(%s, %s)[0].value))" % (json.dumps(rows()), json.dumps(TODAY)))
        self.assertEqual(got, glance._overdue_tile(rows(), TODAY)["value"])
        self.assertEqual(got, 4)            # Open, Delayed, In progress and Blocked; Completed is not counted

    def test_a_completed_item_keeps_its_date_but_has_no_late_words_tone_pill_or_bucket(self):
        done = {"id": "A1", "kind": "action", "status": "Completed", "due_date": "2020-01-01"}
        code = bundled() + ";console.log(JSON.stringify([WI.dueCell(%s, %s), WI.pillOf(%s, %s), WI.isLate(%s, %s)]))" % ((json.dumps(done), json.dumps(TODAY)) * 3)
        cell, pill, late = node(code)
        self.assertEqual((cell["words"], cell["tone"], late), ("", "", False))
        self.assertEqual(cell["date"], "01-01-2020")
        self.assertEqual(pill, glance.pill_of(done, TODAY))
        self.assertEqual(pill["text"], "Open")

    def test_the_word_due_cell_is_late_only_for_a_still_open_status(self):
        for s in STATUSES + ("Pending",):
            row = {"status": s, "due_date": "2020-01-01"}
            self.assertEqual(excel_colours.is_late("actions", "due_date", row, date(2026, 10, 28)), s in ("Open", "Delayed"), s)


if __name__ == "__main__":
    unittest.main()
