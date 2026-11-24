"""Row 1615: the Work items footer in Edit AND in View, at 1400 and 900, light and dark, for a pair like the one CI measured (left: Most 2 of 8 rows so Show all
items is drawn; right: Most 10 so it is not): Review all N items is ONE line (not wrapped to two) and the two Review all buttons are level.
Opens the browser (a separate file so test_wil_footer_buttons_1615.py stays quick tier); written where there is no Chrome, so not run there.
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_wil_footer_edit_1615.py"""
import json
import unittest

import test_wil_footer_one_row_1475 as F
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

# The footer of one section as drawn (the visible one: Edit and View may each hold a footer) with the box of each part.
VIS = """(ref => { const sec = document.querySelector('[data-id="' + ref + '"]'); const vis = (q) => [...sec.querySelectorAll(q)].find((e) => e.offsetParent !== null) || null;
  const foot = vis('[data-wil-foot]'); const r = (e) => { if (!e) return null; const b = e.getBoundingClientRect(); return {top: b.top, bottom: b.bottom, left: b.left, right: b.right, w: b.width, h: b.height}; };
  return {foot: r(foot), all: r(foot && foot.querySelector('[data-wil-all]')), rev: r(foot && foot.querySelector('[data-wil-review]')), count: r(foot && foot.querySelector('[data-wil-count]')),
    parts: foot ? [...foot.children].map((e) => { const c = getComputedStyle(e), b = e.getBoundingClientRect(); return {attr: [...e.attributes].map((a) => a.name).join(' '), w: b.width, h: b.height, ws: c.whiteSpace, shrink: c.flexShrink}; }) : null}; })"""


def vis(p, ref):
    return p.js(f"({VIS})({json.dumps(ref)})")


class FooterEdit(F.FooterOneRow):
    """The served Classic page again; main's own tests stay in main's file, so they are switched off here."""

    def check(self, p, a, b, width, where):
        ga, gb = vis(p, a), vis(p, b)
        self.assertIsNotNone(ga["all"], f"{where} {width}: Show all items is drawn in the left card: {ga}")
        self.assertIsNone(gb["all"], f"{where} {width}: the right card has no Show all items: {gb}")
        for g in (ga, gb):
            self.assertLessEqual(g["rev"]["h"], 36, f"{where} {width}: Review all N items is one line (not 42px, two lines): {g}")
        self.assertLessEqual(abs(ga["rev"]["top"] - gb["rev"]["top"]), 1, f"{where} {width}: the two Review all buttons are level: {ga} {gb}")

    def run_pair(self, edit):
        a, b = self.pair(2, 10)
        for width in self.widths():
            for dark in (False, True):
                with self.subTest(edit=edit, width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    self.drawn(p, a, b)
                    if edit:
                        p.edit()
                        p.until(f"!!document.querySelector('[data-id=\"{a}\"] [data-wil-review]')", "the footer is there in Edit")
                    self.check(p, a, b, width, "Edit" if edit else "View")

    def test_edit_mode_review_all_is_one_line_and_level_1400_and_900_light_and_dark(self):
        """Mutant: src/clark/themes/prototype-2.0/rules-2.css, the rule `.wil-foot .wil-all-b, .wil-foot .wil-review` loses `white-space: nowrap; flex: none;`
        (at 1400 the left card's Review all N items wraps to two lines, 42px high, and its top is 10px higher than the right card's)."""
        self.run_pair(True)

    def test_view_review_all_is_one_line_and_level_1400_and_900_light_and_dark(self):
        """Mutant: the same as the Edit test (View draws the same Foot)."""
        self.run_pair(False)


for _name in [n for n in dir(F.FooterOneRow) if n.startswith("test_")]:
    setattr(FooterEdit, _name, None)      # main's tests live in their own file; only this file's two run here

if __name__ == "__main__":
    unittest.main()
