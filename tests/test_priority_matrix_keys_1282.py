"""Row 1282: killer tests for the Work items list's Priority drop-down of a risk or an issue (the peek's Impact x Likelihood matrix).

Run: python3 dev/run_tests.py test_priority_matrix_keys_1282
Part 1 reads the sources (no Chrome): the old two-list picker and its styles are gone. Part 2 drives the committed page in Chrome over a real
server and a real demo store (the helpers of test_inline_edits): a click on the cell opens the matrix, the arrows stop at the edges, Enter and
Space pick, Esc and a click outside close it with nothing sent, focus returns to the cell, an action keeps its plain list, and the change says "cell".
"""
import unittest
from pathlib import Path

import test_inline_edits as ie
from test_inline_edits import click, key
from test_server import chrome

SRC = Path(__file__).resolve().parents[1] / "src" / "clark" / "page"
CELL = "[data-cell='TUL-007:priority']"      # a risk: impact High, likelihood Medium
OPEN = "!!document.querySelector('[data-pop] .rmx')"
GONE = "document.querySelectorAll('[data-pop]').length === 0"
BACK = f"document.activeElement === document.querySelector(\"{CELL}\")"


class OldPickerGone(unittest.TestCase):
    def test_no_style_or_class_of_the_old_picker_is_left(self):
        for path in [SRC / "shell.css", *(SRC / "src").rglob("*.jsx"), *(SRC / "src").rglob("*.css")]:
            text = path.read_text(encoding="utf-8")
            for old in ("rpick", "rp-head", "RatingPick"):
                self.assertNotIn(old, text, f"{path.name} still has {old}")

    def test_an_action_keeps_the_plain_list_and_the_cell_names_its_place(self):
        text = (SRC / "src" / "edit" / "cells" / "PriorityPick.jsx").read_text(encoding="utf-8")
        self.assertIn("<MenuPick ", text)
        self.assertIn('place={place || "cell"}', text)


class Live(unittest.TestCase):
    setUp, read, row, steps, open_page, until, cell_text, toast, focused, no_panel, undo, changed_once = (
        ie.Live.setUp, ie.Live.read, ie.Live.row, ie.Live.steps, ie.Live.open_page, ie.Live.until, ie.Live.cell_text,
        ie.Live.toast, ie.Live.focused, ie.Live.no_panel, ie.Live.undo, ie.Live.changed_once)

    def at(self, cdp, sid):
        return cdp.js("document.activeElement.dataset.mx || ''", sid)

    def open_by_click(self, cdp, sid, cell=CELL):
        click(cdp, sid, cell)
        self.until(cdp, sid, OPEN, "the matrix opened")

    def test_a_click_opens_the_matrix_and_not_the_old_two_lists(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_by_click(cdp, sid)
            self.assertEqual(cdp.js("document.querySelectorAll('[data-pop] .rmx-c').length", sid), 9)
            self.assertEqual(cdp.js("document.querySelectorAll('[data-pop] .rpick, [data-pop] [role=group], [data-pop] [role=menuitem]').length", sid), 0,
                             "none of the old picker's lists")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-pop]').length", sid), 1, "one panel only")
            self.assertEqual(cdp.js("document.querySelector('[data-pop] .rmx-hint').textContent", sid), "High impact, Medium likelihood: High (Red)")
            self.assertEqual(cdp.js(f"document.querySelector(\"{CELL}\").getAttribute('aria-expanded')", sid), "true")

    def test_the_arrows_move_one_cell_and_stop_at_the_edges(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_by_click(cdp, sid)
            self.assertEqual(self.at(cdp, sid), "High|Medium")
            key(cdp, sid, "ArrowUp")
            self.assertEqual(self.at(cdp, sid), "High|Medium", "the top row is the edge")
            key(cdp, sid, "ArrowRight")
            self.assertEqual(self.at(cdp, sid), "High|High")
            key(cdp, sid, "ArrowRight")
            self.assertEqual(self.at(cdp, sid), "High|High", "the right column is the edge")
            key(cdp, sid, "ArrowDown")
            key(cdp, sid, "ArrowDown")
            self.assertEqual(self.at(cdp, sid), "Low|High")
            key(cdp, sid, "ArrowDown")
            self.assertEqual(self.at(cdp, sid), "Low|High", "the bottom row is the edge")
            key(cdp, sid, "ArrowLeft")
            key(cdp, sid, "ArrowLeft")
            self.assertEqual(self.at(cdp, sid), "Low|Low")
            key(cdp, sid, "ArrowLeft")
            self.assertEqual(self.at(cdp, sid), "Low|Low", "the left column is the edge")
            self.assertEqual(cdp.js("document.querySelector('[data-pop] [data-rmx-level]').textContent", sid), "Low", "the sentence follows the focus")
            self.assertEqual(len(self.sent), 0, "moving sends nothing")

    def test_enter_picks_the_cell_with_one_change_that_says_cell_and_focus_returns(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_by_click(cdp, sid)
            key(cdp, sid, "ArrowRight")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, GONE, "a pick closes it")
            self.until(cdp, sid, f"document.querySelector(\"{CELL}\").textContent === 'Urgent'", "the cell shows Urgent")
            self.assertEqual(len(self.sent), 1, "one change")
            self.assertEqual(self.sent[-1][1]["place"], "cell")
            self.assertEqual(self.sent[-1][1]["changes"], {"impact": "High", "likelihood": "High"})
            self.until(cdp, sid, BACK, "focus is back on the cell")

    def test_space_picks_too(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_by_click(cdp, sid)
            key(cdp, sid, "ArrowDown")
            key(cdp, sid, " ")
            self.until(cdp, sid, GONE, "Space picks and closes it")
            self.assertTrue(ie.wait(lambda: self.row("raid", "TUL-007")["impact"] == "Medium", 10), "Space picked Medium impact")   # the pop closes before the write lands: wait for it

    def test_the_cell_it_has_sends_nothing_but_still_closes(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_by_click(cdp, sid)
            key(cdp, sid, "Enter")
            self.until(cdp, sid, GONE, "closed")
            self.assertEqual(len(self.sent), 0, "no change, no step")
            self.until(cdp, sid, BACK, "focus is back on the cell")

    def test_escape_closes_with_nothing_sent_and_focus_on_the_cell_after_a_click_open(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_by_click(cdp, sid)
            key(cdp, sid, "ArrowLeft")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, GONE, "one Esc closes it")
            self.assertEqual(len(self.sent), 0)
            self.assertNotIn("item=", cdp.js("location.hash", sid), "Esc does not open a peek")
            self.until(cdp, sid, BACK, "focus is back on the cell")

    def test_a_click_outside_closes_it_and_sends_nothing(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_by_click(cdp, sid)
            click(cdp, sid, "body")
            self.until(cdp, sid, GONE, "closed")
            self.assertEqual(len(self.sent), 0)

    def test_an_issue_has_the_matrix_and_an_action_keeps_its_plain_list(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_by_click(cdp, sid, "[data-cell='TUL-010:priority']")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-pop] .rmx-c').length", sid), 9)
            key(cdp, sid, "Escape")
            self.until(cdp, sid, GONE, "closed")
            click(cdp, sid, "[data-cell='TUL-A-001:priority']")
            self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 1", "the action's list opened")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-pop] .rmx').length", sid), 0, "an action has no matrix")


if __name__ == "__main__":
    unittest.main()
