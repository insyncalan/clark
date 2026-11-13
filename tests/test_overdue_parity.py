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

from clark import client_filters, excel_colours, glance
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

    def test_every_other_rule_of_the_page_agrees_a_completed_past_due_action_is_not_late(self):
        """One check per file that holds the rule: each fails if that one file goes back to main."""
        P = lambda *a: PAGE.joinpath(*a)
        today = TODAY
        done = {"id": "A1", "kind": "action", "status": "Completed", "due_date": "2020-01-01", "title": "x"}
        live = dict(done, id="A2", status="Open")
        # minimap.js countOf: the Actions count of late items
        mm = bundled(P("logic", "minimap.js"), "MM")
        count = lambda rows: node(mm + ";console.log(JSON.stringify(MM.countOf({type:'actions'}, {actions: %s}, %s)))" % (json.dumps(rows), json.dumps(today)))
        self.assertEqual(count([done]), {"text": "1", "hot": False})
        self.assertEqual(count([done, live]), {"text": "1 late", "hot": True})
        # iconColours.js dateTone
        ic = bundled(P("iconColours.js"), "IC")
        tone = lambda r: node(ic + ";console.log(JSON.stringify(IC.dateTone(%s, %s)))" % (json.dumps(r), json.dumps(today)))
        self.assertEqual((tone(done), tone(live)), ("b", "r"))
        # peekLatest.js warnFor
        pl = bundled(P("edit", "peekLatest.js"), "PL")
        warn = lambda r: node(pl + ";console.log(JSON.stringify(PL.warnFor(%s, %s)))" % (json.dumps(r), json.dumps(today)))
        self.assertIsNone(warn(dict(done, due_date="2020-01-02")))      # a Thursday: no weekend bar either
        self.assertEqual(warn(dict(live, due_date="2020-01-02"))["kind"], "overdue")
        # filters.js dueBucket (published, as the client page) against client_filters.bucket_of
        fl = bundled(P("filters.js"), "FL")
        bucket = lambda r: node(fl + ";FL.setPublished(true);console.log(JSON.stringify(FL.dueBucket(%s, %s)))" % (json.dumps(r), json.dumps(today)))
        for r in (done, live, dict(done, status="Closed"), dict(done, due_date="2030-01-01")):
            self.assertEqual(bucket(r), client_filters.bucket_of(dict(r, due=r["due_date"]), today), r)
        self.assertEqual(client_filters.bucket_of(dict(done, due="2020-01-01"), today), "past")
        self.assertEqual(client_filters.bucket_of(dict(live, due="2020-01-01"), today), "overdue")
        # filterLine.js due:overdue and is:overdue
        fline = bundled(P("logic", "filterLine.js"), "FLN")
        shown = lambda line: node(fline + ";console.log(JSON.stringify(FLN.apply(%s, %s, {today: %s}).map((r) => r.id)))" % (json.dumps([done, live]), json.dumps(line), json.dumps(today)))
        self.assertEqual(shown("due:overdue"), ["A2"])
        self.assertEqual(shown("is:overdue"), ["A2"])

    def test_the_board_due_column_has_no_overdue_card_for_a_completed_action(self):
        board = bundled(PAGE / "logic" / "board.js", "BD")
        col = lambda r: node(board + ";console.log(JSON.stringify(BD.cellOf('due', %s, {today: %s})))" % (json.dumps(r), json.dumps(TODAY)))
        done = {"id": "A1", "kind": "action", "table": "actions", "status": "Completed", "due_date": "2020-01-01"}
        self.assertEqual(col(done), "__none")
        self.assertEqual(col(dict(done, status="Open")), "overdue")
        self.assertEqual(col(dict(done, due_date="2030-01-01")), "later")

    def test_the_work_item_list_filter_never_buckets_a_completed_past_due_action_as_overdue(self):
        from clark.section_kinds import workitems as wk
        code = bundled(PAGE / "templates" / "workItemsList.js", "WL")
        rs = [{"id": "A1", "kind": "action", "status": "Completed", "due": "2020-01-01"},
              {"id": "A2", "kind": "action", "status": "Open", "due": "2020-01-01"}]
        f = {"mode": "all", "kinds": [], "status": [], "due": ["overdue"], "owner": [], "workstream": [], "use_case": [], "priority": [], "sort": "id", "max": 10}
        got = node(code + ";console.log(JSON.stringify(WL.matching(%s, %s, %s)))" % (json.dumps(f), json.dumps(rs), json.dumps(TODAY)))
        self.assertEqual(got, ["A2"])
        self.assertEqual([r["id"] for r in rs if wk._bucket(r, TODAY) == "overdue"], ["A2"])


if __name__ == "__main__":
    unittest.main()
