"""Row 1257 part B: the Risk and Issue peek's Rating chip text and its matrix, to the approved mockup (peek-redesign, layout A).
Run: CLARK_CHROME=$CREAITE_CHROME python3 dev/run_tests.py test_peek_rating_1257.py
Headless Chrome, demo data (fictional), 1400 and 900 px only. Mockup numbers: matrix 268 wide, padding 8, radius 12, cells radius 6 and padding 7 / 2 and weight 600,
a Low / Medium / High header row under the grid; the level pill is bold (700); the chip icon takes the colour word's colour; one tooltip for Risk and Issue.
Sizes stay on the page's type scale (the mockup's 11 and 10 px are under the readable floor).
"""
import unittest

import test_server  # noqa: F401  (a test that drives Chrome)
import test_inline_edits as T
from test_inline_edits import click, chrome


class RatingChip(unittest.TestCase):
    setUp = T.Live.setUp
    read = T.Live.read
    row = T.Live.row
    open_page = T.Live.open_page
    until = T.Live.until

    def peek(self, cdp, sid, ref):
        cdp.js(f"clarkPage.openPeek('{ref}', 'item')", sid)
        self.until(cdp, sid, f"document.querySelector('#peek').dataset.peek === '{ref}' && !!document.querySelector('#peek .pk-chips [data-row=priority] button')", "the peek drew")
        self.until(cdp, sid, "document.querySelector('#peek').getAnimations({subtree: true}).length === 0", "the slide-in has ended")

    def test_the_icon_follows_the_colour_word_and_the_tip_is_one_text(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                for ref in ("TUL-007", "TUL-010"):
                    self.peek(cdp, sid, ref)
                    got = cdp.js("(() => { const c = document.querySelector('#peek .pk-chips [data-row=priority]'); const b = c.querySelector('button'); const p = c.querySelector('.pkc-sub');"
                                 " return {word: c.querySelector('.pkc-v').textContent.trim(), ic: c.querySelector('.pkc-ic').className, tip: b.dataset.tip, weight: getComputedStyle(p).fontWeight}; })()", sid)
                    tone = {"Red": "ic-r", "Amber": "ic-a", "Green": "ic-g"}[got["word"]]
                    self.assertIn(tone, got["ic"].split(), f"{ref}: the icon is the colour word's colour")
                    self.assertEqual(got["tip"], "Priority from impact and likelihood", ref)
                    self.assertEqual(got["weight"], "700", f"{ref}: the level pill is bold")

    def test_the_matrix_is_268_wide_for_both_with_a_column_header_row_under_it(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                for ref in ("TUL-007", "TUL-010"):
                    self.peek(cdp, sid, ref)
                    click(cdp, sid, "#peek .pk-chips [data-row=priority] button")
                    self.until(cdp, sid, "!!document.querySelector('[data-pop] .rmx')", "the matrix opened")
                    got = cdp.js("(() => { const pop = document.querySelector('[data-pop]'), g = document.querySelector('[data-pop] .rmx'), cs = getComputedStyle(pop), c = getComputedStyle(g.querySelector('.rmx-c'));"
                                 " const heads = [...g.querySelectorAll('.rmx-col')], cells = [...g.querySelectorAll('.rmx-c')], lastY = Math.max(...cells.map((b) => b.getBoundingClientRect().bottom));"
                                 " return {w: pop.getBoundingClientRect().width, pad: cs.paddingLeft, rad: cs.borderTopLeftRadius, words: heads.map((h) => h.textContent),"
                                 " below: heads.every((h) => h.getBoundingClientRect().top >= lastY), cellRad: c.borderTopLeftRadius, cellW: c.fontWeight, cellPad: [c.paddingTop, c.paddingLeft], over: g.scrollWidth > g.clientWidth}; })()", sid)
                    self.assertEqual(round(got["w"]), 268, f"{ref} at {width}")
                    self.assertEqual((got["pad"], got["rad"]), ("8px", "12px"), ref)
                    self.assertEqual(got["words"], ["Low", "Medium", "High"], ref)
                    self.assertTrue(got["below"], f"{ref}: the column words sit under the matrix")
                    self.assertEqual((got["cellRad"], got["cellW"], got["cellPad"]), ("6px", "600", ["7px", "2px"]), ref)
                    self.assertFalse(got["over"], f"{ref}: nothing spills")
                    cdp.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))", sid)
                    self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "closed")


if __name__ == "__main__":
    unittest.main()
