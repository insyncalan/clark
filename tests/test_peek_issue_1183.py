"""Row 1183: the Issue peek (mockup peek-issue, Layout A): its Rating row and 3 x 3 matrix, a status list without Red, Amber, Green,
and "Red kept" under a closed issue's pill. Built together with row 1182 (the Risk peek) on one matrix component.
Run: python3 dev/run_tests.py test_peek_issue_1183
"""
import unittest

import test_inline_edits as ie  # noqa: E402

_Live, click, key = ie.Live, ie.click, ie.key


class IssuePeek(unittest.TestCase):
    setUp = _Live.setUp
    read = _Live.read
    row = _Live.row
    steps = _Live.steps
    open_page = _Live.open_page
    until = _Live.until
    toast = _Live.toast
    undo = _Live.undo
    changed_once = _Live.changed_once

    ISSUE, RISK = "TUL-010", "TUL-007"

    def peek(self, cdp, width, ref):
        sid = self.open_page(cdp, width)
        cdp.js(f"clarkPage.openPeek('{ref}', 'item')", sid)
        self.until(cdp, sid, f"!!document.querySelector('#peek .pk-chips [data-row=priority]')", "the peek drew")
        self.until(cdp, sid, "document.querySelector('#peek').getAnimations({subtree: true}).length === 0", "the slide-in ended")
        return sid

    def label(self, cdp, sid):
        return cdp.js("document.querySelector('#peek .pk-chips [data-row=priority] button').getAttribute('aria-label').split(' of ')[0]", sid)

    def test_an_issue_peek_and_a_risk_peek_both_say_rating(self):
        with _chrome() as cdp:
            sid = self.peek(cdp, 1400, self.ISSUE)
            self.assertEqual(self.label(cdp, sid), "Rating")
            now = self.row("raid", self.ISSUE)
            self.assertEqual(cdp.js("document.querySelector('#peek .pk-chips [data-row=priority] .pkc-v').textContent.trim()", sid),
                             now["priority"])
            colour = "Red" if now["priority"] in ("Urgent", "High") else "Amber" if now["priority"] == "Medium" else "Green"
            self.assertEqual(cdp.js("document.querySelector('#peek .pk-chips [data-row=priority] button').dataset.tip", sid), colour + " rating, set from impact and likelihood")
        with _chrome() as cdp:
            sid = self.peek(cdp, 1400, self.RISK)
            self.assertEqual(self.label(cdp, sid), "Rating", "rows 1182 1183: a risk says Rating too")
            click(cdp, sid, "#peek .pk-chips [data-row=priority] button")
            self.until(cdp, sid, "!!document.querySelector('[data-pk-matrix]')", "the risk's matrix opened (the one component)")

    def test_the_matrix_sets_impact_and_likelihood_in_one_step_with_one_undo(self):
        for width in (1400, 900):
            with self.subTest(width=width), _chrome() as cdp:
                sid = self.peek(cdp, width, self.ISSUE)
                was = self.row("raid", self.ISSUE)
                click(cdp, sid, "#peek .pk-chips [data-row=priority] button")
                self.until(cdp, sid, "!!document.querySelector('[data-pk-matrix]')", "the matrix opened")
                self.assertEqual(cdp.js("document.querySelectorAll('[data-pk-matrix] [data-mx]').length", sid), 9)
                self.assertEqual(cdp.js("[...document.querySelectorAll('[data-pk-matrix] [data-mx]')].map(b => b.textContent).join()", sid),
                                 "High,High,Urgent,Medium,Medium,High,Low,Medium,High", "rows Impact High, Medium, Low; columns Likelihood Low, Medium, High")
                before = self.steps()
                target = "High|Low" if (was["impact"], was["likelihood"]) != ("High", "Low") else "Low|High"      # not a symmetric cell, so a swapped impact and likelihood shows
                click(cdp, sid, f"[data-pk-matrix] [data-mx='{target}']")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved, with Undo")
                im, li = target.split("|")
                now = self.row("raid", self.ISSUE)
                self.assertEqual((now["impact"], now["likelihood"]), (im, li))
                self.changed_once(before, "the matrix")
                self.assertIn(f"Impact of {self.ISSUE} is {im} and likelihood {li}.", self.toast(cdp, sid))
                self.undo(cdp, sid, "the matrix", f"Impact and likelihood of {self.ISSUE} are back to {was['impact']} and {was['likelihood']}.")
                now = self.row("raid", self.ISSUE)
                self.assertEqual((now["impact"], now["likelihood"]), (was["impact"], was["likelihood"]), "one Undo puts both back")

    def test_the_matrix_line_and_arrow_keys(self):
        with _chrome() as cdp:
            sid = self.peek(cdp, 1400, self.ISSUE)
            click(cdp, sid, "#peek .pk-chips [data-row=priority] button")
            self.until(cdp, sid, "!!document.querySelector('[data-pk-matrix]')", "the matrix opened")
            cdp.js("document.querySelector(\"[data-pk-matrix] [data-mx='High|Medium']\").focus()", sid)
            self.until(cdp, sid, "document.querySelector('[data-pk-matrix-say]').textContent === 'High impact, Medium likelihood: High (Red)'", "the line names the cell")
            key(cdp, sid, "ArrowRight")
            self.until(cdp, sid, "document.activeElement.dataset.mx === 'High|High'", "an arrow moves over the cells")
            before = self.steps()
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('[data-pk-matrix]')", "Esc closes it")
            self.assertEqual(self.steps(), before, "Esc changes nothing")

    def test_an_issue_status_list_has_no_rating_and_a_closed_issue_says_kept(self):
        with _chrome() as cdp:
            sid = self.peek(cdp, 1400, self.ISSUE)
            pcell = "#peek .pk-chips [data-row=status] button"
            click(cdp, sid, pcell)
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the menu opened")
            self.assertEqual(cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => b.dataset.value).join()", sid), "Open,Closed,Cancelled")
            click(cdp, sid, "[data-pop] [data-value=Closed]")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "saved")
            kept = {"Urgent": "Red", "High": "Red", "Medium": "Amber", "Low": "Green"}[self.row("raid", self.ISSUE)["priority"]]
            self.until(cdp, sid, f"((document.querySelector('#peek .pk-chips [data-row=priority] .pkc-sub') || {{}}).textContent || '').trim() === '{kept} kept'", "Red kept (or its colour)")


def _chrome():
    from test_server import chrome
    return chrome()


if __name__ == "__main__":
    unittest.main()
