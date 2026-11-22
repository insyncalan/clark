"""Row 1409: the line under the rating matrix names Urgent's colour Maroon in Classic ("Urgent (Maroon)"); High stays "High (Red)", Medium
"Medium (Amber)", Low "Low (Green)". Cards (no Theme layer) keeps "Urgent (Red)". At 1400 and 900.
Run: python3 dev/run_tests.py test_matrix_urgent_maroon_1409"""
import unittest

import test_server  # noqa: F401  drives Chrome through the template harness
import test_tpl_workitems as base
import _testpage as testpage
from _real_server import real_server
from clark import page, theme
from test_server import chrome
from test_report_editor import tearDownModule  # noqa: F401

COMBOS = {"Low": ("Low", "Low"), "Medium": ("Medium", "Low"), "High": ("High", "Medium"), "Urgent": ("High", "High")}
CLASSIC = {"Low": "Low (Green)", "Medium": "Medium (Amber)", "High": "High (Red)", "Urgent": "Urgent (Maroon)"}
CARDS = dict(CLASSIC, Urgent="Urgent (Red)")


class Lines(base.PageBase):
    add, show = base.InThePage.add, base.InThePage.show
    classic = True

    def setUp(self):
        super().setUp()
        base.plant(self)
        if self.classic:
            self.s.close()
            css = theme.css("prototype-2.0")
            self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css), seam=self.seam)
            self.addCleanup(self.s.close)
        for lv, (im, li) in COMBOS.items():
            with self.store.step("dashboard", base.USER) as st:
                st.create("raid", {"project": "ABC", "type": "Risk", "description": f"Line {lv}", "raised": "2026-10-01", "source": "demo",
                                   "impact": im, "likelihood": li, "owner": "Pat Demo"})
        with self.store.step("dashboard", base.USER) as st:
            text = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 1})
        self.ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"], "max": 40}, after=text, beside=1)

    def lines(self, width):
        got = {}
        with chrome() as cdp:
            p = self.show(cdp, width)
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{self.ref}\"] .wil-table .cell-pick[data-cell^=\"ABC-0\"][data-cell$=\":priority\"]')", "cells drew")
            p.js(f"[...document.querySelectorAll('[data-id=\"{self.ref}\"] .wil-table .cell-pick[data-cell^=\"ABC-0\"][data-cell$=\":priority\"]')][0].click()")
            p.until("!!document.querySelector('[data-pop] .rmx-c')", "matrix opened")
            for lv, (im, li) in COMBOS.items():
                p.js(f"document.querySelector('[data-pop] .rmx-c[data-impact=\"{im}\"][data-likelihood=\"{li}\"]').focus()")
                p.js(f"document.querySelector('[data-pop] .rmx-c[data-impact=\"{im}\"][data-likelihood=\"{li}\"]').dispatchEvent(new Event('focus'))")
                p.until(f"document.querySelector('[data-pop] .rmx-hint').textContent.startsWith('{im} impact, {li} likelihood')", f"{lv}: hint follows")
                got[lv] = p.js("document.querySelector('[data-pop] .rmx-hint').textContent").split(": ", 1)[1]
        return got

    def test_the_line_words(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.assertEqual(self.lines(width), CLASSIC if self.classic else CARDS)


class CardsLines(Lines):
    classic = False


if __name__ == "__main__":
    unittest.main()
