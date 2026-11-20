"""Row 1273 killers (full mutation sweep of the Move to menu): the lane line a card is in now is listed, ticked and not a choice,
and a click on a ticked line changes nothing. Desktop (1400) and 900 px only.

Run: python3 dev/run_tests.py test_work_board_move_here_1273
"""
import unittest

import test_work_board_page as wb
from test_work_board_page import setUpModule, tearDownModule  # noqa: F401  (the one shared Chrome of the board file)
from test_work_filters import click
from test_server import chrome  # noqa: F401  (the harness: this file drives Chrome, so the tier reader sees it)


class MoveHere(wb.Base):
    def _open(self, cdp, sid, lane):
        self.board(cdp, sid, "status", lane=lane)
        a = self.id_of("Order the laptops")                       # Data, Open
        click(cdp, sid, f"[data-move='{a}']")
        self.until(cdp, sid, "!!document.querySelector('.ddmenu')", "the menu")
        return a

    def test_the_lane_the_card_is_in_is_listed_ticked_and_not_a_choice(self):
        with wb.shared.page() as cdp:
            sid = self.visit(cdp)
            self._open(cdp, sid, "workstream")
            lanes = cdp.js("[...document.querySelectorAll('.ddmenu [data-lane=\"1\"]')].map(b => [b.getAttribute('data-to'), b.textContent, b.getAttribute('aria-disabled'), b.getAttribute('aria-current')])", sid)
            here = [l for l in lanes if l[0] == "Data"]
            self.assertEqual(here, [["Data", "✓Data", "true", "true"]], "the card's own lane: listed, ticked, disabled, current")
            self.assertTrue(all(l[2] is None and l[3] is None for l in lanes if l[0] != "Data"), "the other lanes are plain choices")

    def test_a_click_on_the_ticked_lane_or_column_changes_nothing(self):
        with wb.shared.page() as cdp:
            sid = self.visit(cdp)
            a = self._open(cdp, sid, "workstream")
            before = self.steps()
            for sel in (".ddmenu [data-lane='1'][data-to='Data']", ".ddmenu [data-to='Open']:not([data-lane])"):
                self.until(cdp, sid, "!!document.querySelector('.ddmenu')", "the menu")
                click(cdp, sid, sel)
                self.assertEqual(self.steps(), before, "a ticked line is not a choice: no step")
                self.assertEqual((self.row(a)["status"], self.row(a)["workstream"]), ("Open", "Data"))
                if not cdp.js("!!document.querySelector('.ddmenu')", sid):
                    click(cdp, sid, f"[data-move='{a}']")
                    self.until(cdp, sid, "!!document.querySelector('.ddmenu')", "the menu again")

    def test_the_ticked_line_is_the_current_one_for_assistive_tools(self):
        with wb.shared.page() as cdp:
            sid = self.visit(cdp)
            self._open(cdp, sid, "workstream")
            cur = cdp.js("[...document.querySelectorAll('.ddmenu [aria-current=\"true\"]')].map(b => b.getAttribute('data-to'))", sid)
            self.assertEqual(sorted(cur), ["Data", "Open"], "the column and the lane the card is in")


if __name__ == "__main__":
    unittest.main()
