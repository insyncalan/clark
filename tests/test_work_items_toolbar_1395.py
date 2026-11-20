"""Row 1395: the Classic Work items toolbar at 1400 as the prototype draws it (filter input 15px and count 13px, the chosen layout tile 36 x 32 in the brand tint with the brand blue glyph, the dashed grey Add tile).

Run: python3 dev/run_tests.py test_work_items_toolbar_1395
Classic only: the rules sit in the Classic theme layer; shell.css (Cards) carries none of it. The look is pinned in Chrome at 1400, light.
"""
import re
import unittest

import tempfile

from clark import page, theme
from _real_server import real_server
from test_server import chrome
from test_work_items_classic_1314 import RULES, SHELL
from test_work_board_page import Base

START = RULES.index("/* Row 1395")
END = RULES.index("/* Row ", START + 1)
OWN = RULES[START:END]


class Source(unittest.TestCase):
    def test_the_block_sits_before_row_1314_which_stays_last(self):
        self.assertEqual(RULES.count("/* Row 1395"), 1)
        self.assertLess(START, END)
        names = [l.split()[2].rstrip(":,") for l in RULES.split("\n") if l.startswith("/* Row ")]
        self.assertEqual(names[-1], "1314")
        self.assertLess(names.index("1395"), names.index("1314"))

    def test_the_block_has_no_colour_literals_and_every_rule_is_under_the_work_page(self):
        body = [l for l in OWN.split("\n")[1:] if l.strip()]
        self.assertEqual(len(body), 5)
        for l in body:
            self.assertTrue(l.startswith("#work "), l)
            self.assertNotRegex(l, r"#[0-9a-fA-F]{3,8}\b")
        self.assertNotIn("!important", OWN)

    def test_cards_stylesheet_has_none_of_it(self):
        self.assertNotIn("1395", SHELL)
        self.assertNotIn("tile-on", SHELL)


class Look(Base):
    """The Classic page (the Classic theme layered), 1400, light."""

    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css), seam=lambda real, which: real)
        self.addCleanup(self.s.close)

    def probe(self, js):
        with chrome() as cdp:
            sid = self.visit(cdp, width=1400)
            cdp.js("document.documentElement.dataset.theme = 'light'", sid)
            self.line(cdp, sid, "late")
            self.until(cdp, sid, "!!document.querySelector('#work .fk.k-txt')", "the typed word is drawn")
            return cdp.js(js, sid)

    def test_row1_the_filter_input_is_15px_and_the_count_13px(self):
        got = self.probe("(() => { const f = (s) => getComputedStyle(document.querySelector(s)).fontSize; return {input: f('#work #fline-input'), drawn: f('#work .fhi'), count: f('#work .fcount')}; })()")
        self.assertEqual(got, {"input": "15px", "drawn": "15px", "count": "13px"})

    def test_row1_the_drawn_text_stays_on_the_input_line(self):
        got = self.probe("(() => { const i = document.querySelector('#fline-input').getBoundingClientRect(), o = document.querySelector('#work .fhi').getBoundingClientRect(), w = document.querySelector('#work .fk.k-txt').getBoundingClientRect(); return {iTop: i.top, oTop: o.top, iH: i.height, oH: o.height, inside: w.top >= o.top && w.bottom <= o.bottom}; })()")
        self.assertEqual((got["iTop"], got["iH"]), (got["oTop"], got["oH"]), got)
        self.assertTrue(got["inside"], got)

    def test_row2_the_chosen_layout_tile_is_brand_tint_with_a_brand_glyph_36_by_32(self):
        got = self.probe("(() => { const b = document.querySelector('#work .lsw button[aria-pressed=true]'), s = getComputedStyle(b), r = b.getBoundingClientRect(); return {bg: s.backgroundColor, fg: s.color, glyph: getComputedStyle(b.querySelector('svg')).color, w: r.width, h: r.height}; })()")
        self.assertEqual(got, {"bg": "rgb(236, 233, 251)", "fg": "rgb(91, 71, 216)", "glyph": "rgb(91, 71, 216)", "w": 36, "h": 32})

    def test_row2_the_other_layout_tile_is_36_by_32_and_unfilled(self):
        got = self.probe("(() => { const b = document.querySelector('#work .lsw button[aria-pressed=false]'), r = b.getBoundingClientRect(); return {bg: getComputedStyle(b).backgroundColor, w: r.width, h: r.height}; })()")
        self.assertEqual(got, {"bg": "rgba(0, 0, 0, 0)", "w": 36, "h": 32})

    def test_row3_the_add_tile_is_dashed_grey_radius_6_clear_and_brand_blue(self):
        got = self.probe("(() => { const s = getComputedStyle(document.querySelector('#work #newBtn')); return {st: s.borderTopStyle, w: s.borderTopWidth, c: s.borderTopColor, r: s.borderTopLeftRadius, bg: s.backgroundColor, fg: s.color}; })()")
        self.assertEqual(got, {"st": "dashed", "w": "1px", "c": "rgb(135, 148, 179)", "r": "6px", "bg": "rgba(0, 0, 0, 0)", "fg": "rgb(91, 71, 216)"})

    def test_row3_the_add_tile_hover_is_unchanged_brand_fill(self):
        with chrome() as cdp:
            sid = self.visit(cdp, width=1400)
            cdp.js("document.documentElement.dataset.theme = 'light'", sid)
            cdp.js("document.querySelector('#work #newBtn').dispatchEvent(new MouseEvent('mouseover', {bubbles: true}))", sid)
            r = cdp.js("(() => { const b = document.querySelector('#work #newBtn').getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; })()", sid)
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r[0], "y": r[1]}, sid)
            self.until(cdp, sid, "document.querySelector('#work #newBtn').matches(':hover') && getComputedStyle(document.querySelector('#work #newBtn')).backgroundColor === 'rgb(91, 71, 216)'", "the hover fill")


if __name__ == "__main__":
    unittest.main()
