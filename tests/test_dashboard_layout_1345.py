"""Row 1345, re-spec rows: the Classic dashboard's page padding, section heading line, section padding and At a glance flat strip, measured in Chrome at 1400
(a 1385 px page: the window less a 15 px scrollbar) and 900, against prototype 2.0 index.html lines 88, 92, 112-113, 120-123 and 785.
Chrome is required: these tests fail, never skip, without it. Fictional data only.

Run: python3 dev/run_tests.py test_dashboard_layout_1345
"""
import unittest

from test_classic_dashboard_1345 import Dash, theme_folder

MARK = "/* Row 1345 layout rows"

P = ("(function(){var g=function(e){return getComputedStyle(e)}, m=g(document.querySelector('main')), s=g(document.querySelector('#report .secs > .sec:not(.is-hidden)')),"
     "h=g(document.querySelector('#report .secs > .sec:not(.is-hidden) .sec-h')), cs=[...document.querySelectorAll('.glance[data-glance] > .tcell')].filter(e => e.offsetWidth > 0), out=[];"
     "return {main: [m.paddingTop, m.paddingRight, m.paddingBottom, m.paddingLeft], head: [h.fontSize, h.lineHeight, h.fontWeight], sec: [s.paddingTop, s.paddingRight, s.paddingBottom, s.paddingLeft],"
     "cells: cs.map(function(e){var c=g(e); return [c.paddingTop, c.paddingRight, c.paddingBottom, c.paddingLeft, c.marginRight, c.marginLeft, c.borderRightWidth, c.borderRightStyle, c.borderRightColor, c.borderLeftWidth];}),"
     "line: (function(){var t=document.createElement('i'); t.style.color='var(--grey-200)'; document.body.appendChild(t); var c=g(t).color; t.remove(); return c;})(), n: cs.length};})()")


class Layout(Dash):
    def probe(self, width, density="compact"):
        from test_server import chrome
        with chrome() as cdp:
            p = self.at(cdp, width)
            p.js("document.documentElement.dataset.density = %r" % density)
            p.until("getComputedStyle(document.querySelector('.sec-h')).fontSize !== ''", "the density is applied")
            return p.js(P)

    def test_at_1400_page_padding_is_32_top_84_right_56_bottom_66_left(self):
        self.assertEqual(self.probe(1400)["main"], ["32px", "84px", "56px", "66px"])

    def test_at_1400_section_heading_is_20_with_line_25(self):
        self.assertEqual(self.probe(1400)["head"], ["20px", "25px", "600"])

    def test_at_900_section_heading_is_20_with_line_25(self):
        self.assertEqual(self.probe(900)["head"], ["20px", "25px", "600"])

    def test_at_1400_section_padding_is_20_22_18_22(self):
        self.assertEqual(self.probe(1400)["sec"], ["20px", "22px", "18px", "22px"])

    def test_at_900_section_padding_is_20_22_18_22(self):
        self.assertEqual(self.probe(900)["sec"], ["20px", "22px", "18px", "22px"])

    def check_strip(self, width):
        got = self.probe(width)
        cells = got["cells"]
        self.assertGreaterEqual(got["n"], 2)
        if width == 900:       # Project health sits alone on the first row (row 1313): no rule after it
            self.assertEqual(cells[0][6], "0px")
            cells = cells[1:]
        for c in cells[:-1]:
            self.assertEqual(c, ["0px", "20px", "0px", "0px", "20px", "0px", "1px", "solid", got["line"], "0px"], width)
        self.assertEqual(cells[-1][6], "0px", width)        # the last has no rule
        self.assertEqual(cells[-1][9], "0px", width)        # no rule on the left

    def test_at_1400_glance_cells_have_padding_margin_and_a_right_rule_but_the_last(self):
        self.check_strip(1400)

    def test_at_900_glance_cells_have_padding_margin_and_a_right_rule_but_the_last(self):
        self.check_strip(900)

    def test_comfortable_keeps_its_section_padding_and_heading_line(self):
        got = self.probe(1400, "comfortable")
        self.assertNotEqual(got["sec"][1:3], ["22px", "18px"])
        self.assertNotEqual(got["head"][1], "25px")


class Text(unittest.TestCase):
    def test_the_layout_block_is_one_comment_then_these_lines(self):
        rules = (theme_folder() / "rules.css").read_text(encoding="utf-8")
        start = rules.index(MARK)
        block = rules[start:rules.index("/* Row ", start + 1)]
        self.assertEqual(rules.count(MARK), 1)
        self.assertEqual([l for l in block.split("\n")[1:] if l.strip()], LINES)


LINES = [
    '@media screen and (min-width: 1000px) {',
    '  html:has(.rbar + #report .cnt-grid) main { padding-top: 32px; padding-bottom: 56px; }',
    '}',
    'html:not([data-density="comfortable"]) .rbar + #report .secs > .sec:not(.slot-right) { padding-right: 22px; padding-bottom: 18px; }',
    'html:not([data-density="comfortable"]) .rbar + #report .sec-h { line-height: 1.25; }',
    'html:not([data-density="comfortable"]) .rbar + #report .glance[data-glance] .tcell { padding: 0 20px 0 0; margin: 0 20px 0 0; border-left: 0; border-right: 1px solid var(--grey-200); }',
    'html:not([data-density="comfortable"]) .rbar + #report .glance[data-glance] .tcell:last-child { border-right: 0; margin-right: 0; padding-right: 0; }',
    '@media (max-width: 1180px) { html:not([data-density="comfortable"]) .rbar + #report .glance[data-glance] .tcell.health { border-right: 0; } }',
]

if __name__ == "__main__":
    unittest.main()
