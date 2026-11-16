"""Row 1182: the Risk peek (the approved mockup, button Risk). Run: python3 dev/run_tests.py test_risk_peek_1182
The page runs in headless Chrome (set CLARK_CHROME to its path).

A risk's peek has a Rating chip (not Priority; also an issue's, row 1183; the chip row of row 1180) that opens a 3 x 3 matrix of impact and likelihood: one click sets both, in
one step with one Undo. The peek's status picker lists Open, Closed and Cancelled only (no Red, Amber, Green); a closed risk says
"<colour> kept" under its Rating. The table's own Status picker keeps its Rating section.
"""
import unittest

import test_inline_edits as T
from test_inline_edits import click, key, chrome


class RiskPeek(unittest.TestCase):
    setUp = T.Live.setUp
    read = T.Live.read
    row = T.Live.row
    steps = T.Live.steps
    open_page = T.Live.open_page
    until = T.Live.until
    toast = T.Live.toast
    undo = T.Live.undo
    changed_once = T.Live.changed_once

    def peek(self, cdp, sid, ref):
        cdp.js(f"clarkPage.openPeek('{ref}', 'item')", sid)
        self.until(cdp, sid, f"!!document.querySelector('#peek [data-peek], #peek[data-peek=\"{ref}\"]')", "the peek drew")
        self.until(cdp, sid, "document.querySelector('#peek').getAnimations({subtree: true}).length === 0", "the slide-in has ended")

    def open_matrix(self, cdp, sid):
        click(cdp, sid, "#peek .pk-chips [data-row=priority] button")
        self.until(cdp, sid, "!!document.querySelector('[data-pop] .rmx')", "the matrix opened")

    def test_the_rating_chip_replaces_priority(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                self.peek(cdp, sid, "TUL-007")
                self.assertEqual(cdp.js("document.querySelector('#peek .pk-chips [data-row=priority] button').getAttribute('aria-label')", sid), "Rating of TUL-007: High. Change")
                self.assertEqual(cdp.js("document.querySelector('#peek .pk-chips [data-row=priority] .pkc-v').textContent", sid), "High")
                self.peek(cdp, sid, "TUL-010")      # rows 1182 1183: an issue says Rating too
                self.assertEqual(cdp.js("document.querySelector('#peek .pk-chips [data-row=priority] button').getAttribute('aria-label').split(' of ')[0]", sid), "Rating")

    def test_the_matrix_sets_both_fields_in_one_step_with_one_undo(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.peek(cdp, sid, "TUL-007")
            self.open_matrix(cdp, sid)
            self.assertEqual(cdp.js("[...document.querySelectorAll('[data-pop] .rmx-c')].map(b => b.dataset.impact[0] + b.dataset.likelihood[0] + ':' + b.textContent)", sid),
                             ["HL:High", "HM:High", "HH:Urgent", "ML:Medium", "MM:Medium", "MH:High", "LL:Low", "LM:Medium", "LH:High"], "rows Impact High, Medium, Low; columns Likelihood Low, Medium, High")
            self.assertEqual(cdp.js("document.querySelector('[data-pop] [aria-label=\"Impact Low, likelihood Low: Low, Green\"]').textContent", sid), "Low")
            cdp.js("document.querySelector('[data-pop] [data-impact=High][data-likelihood=Medium]').focus()", sid)
            self.until(cdp, sid, "document.querySelector('[data-rmx-hint]').textContent === 'High impact, Medium likelihood: High (Red)'", "the line under the matrix")
            self.assertEqual(cdp.js("document.activeElement.getAttribute('aria-pressed')", sid), "true", "the risk's own cell is marked")
            before = self.steps()
            click(cdp, sid, "[data-pop] [data-impact=Low][data-likelihood=Low]")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved, with Undo")
            r = self.row("raid", "TUL-007")
            self.assertEqual((r["impact"], r["likelihood"], r["priority"]), ("Low", "Low", "Low"))
            self.changed_once(before, "both fields from the matrix")
            self.until(cdp, sid, "document.querySelector('#peek [data-row=priority] .pkc-v').textContent === 'Low'", "the peek says Low")
            self.assertEqual(self.toast(cdp, sid), "Impact of TUL-007 is Low and likelihood Low. Its priority is now Low.")
            self.undo(cdp, sid, "the matrix pick", "Impact and likelihood of TUL-007 are back to High and Medium.")
            r = self.row("raid", "TUL-007")
            self.assertEqual((r["impact"], r["likelihood"], r["priority"]), ("High", "Medium", "High"), "one Undo puts back both")

    def test_every_cell_is_laid_out_alike_and_the_row_labels_are_not_cells(self):
        # a red cell once took the row label's class (right-aligned, centred): all cells share one alignment, the labels another
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.peek(cdp, sid, "TUL-007")
            self.open_matrix(cdp, sid)
            got = cdp.js("(() => { const cs = (e) => { const s = getComputedStyle(e); return [s.textAlign, s.alignSelf]; };"
                         " return {cells: [...document.querySelectorAll('[data-pop] .rmx-c')].map((b) => [b.dataset.level, ...cs(b)]),"
                         " labels: [...document.querySelectorAll('[data-pop] .rmx-l')].map((l) => [l.textContent, ...cs(l)]),"
                         " asLabel: document.querySelectorAll('[data-pop] .rmx-c.rmx-l').length}; })()", sid)
            self.assertEqual(len(got["cells"]), 9)
            self.assertEqual(len({(a, b) for _, a, b in got["cells"]}), 1, f"all nine cells share text-align and align-self: {got['cells']}")
            self.assertEqual({a for _, a, _ in got["cells"]} & {"right"}, set(), "no cell is right-aligned like a label")
            self.assertEqual([l for l, _, _ in got["labels"]], ["High", "Medium", "Low"])
            self.assertTrue(all(a == "right" for _, a, _ in got["labels"]), "the row labels are right-aligned")
            self.assertEqual(got["asLabel"], 0, "no cell carries the label class")

    def test_the_matrix_keys(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.peek(cdp, sid, "TUL-007")
            self.open_matrix(cdp, sid)
            self.assertEqual(cdp.js("document.activeElement.dataset.impact + document.activeElement.dataset.likelihood", sid), "HighMedium", "focus starts on the risk's cell")
            key(cdp, sid, "ArrowDown")
            key(cdp, sid, "ArrowRight")
            self.assertEqual(cdp.js("document.activeElement.dataset.impact + document.activeElement.dataset.likelihood", sid), "MediumHigh")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "Esc closes it")
            self.assertEqual(cdp.js("!!document.querySelector('#peek')", sid), True, "and leaves the peek open")
            self.assertEqual(cdp.js("!!document.activeElement.closest('[data-row=priority]')", sid), True)

    def test_the_peeks_status_picker_has_no_colours_but_the_tables_keeps_them(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.peek(cdp, sid, "TUL-007")
            click(cdp, sid, "#peek [data-cell='peek:TUL-007:status']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the peek's menu opened")
            self.assertEqual(cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => b.dataset.value)", sid), ["Open", "Closed", "Cancelled"])
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "closed")
            click(cdp, sid, "[data-cell='TUL-007:status']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the table's menu opened")
            self.assertEqual(cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => b.dataset.value)", sid), ["Open", "Closed", "Cancelled", "rating:Red", "rating:Amber", "rating:Green"])

    def test_a_closed_risk_says_its_colour_kept_an_issue_does_not(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.peek(cdp, sid, "TUL-008")
            self.assertEqual(cdp.js("document.querySelector('#peek [data-row=priority] .pk-chip-sub').textContent", sid), "Amber kept")
            self.peek(cdp, sid, "TUL-012")      # a cancelled issue
            self.assertEqual(cdp.js("(document.querySelector('#peek [data-row=priority] .pk-chip-sub') || {}).textContent", sid), "Red kept", "an issue keeps its word as it did (row 1180)")


if __name__ == "__main__":
    unittest.main()
