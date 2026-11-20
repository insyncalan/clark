"""Row 1319, Classic theme: segments and buttons have a 6px corner, segments and plain buttons are 28px tall with padding 3px 14px, crumbs are 13px.

Run: python3 dev/run_tests.py test_theme_sizes_1319
Fails, never skips, without Chrome. Computed styles at 1400 and 900. Cards (no Theme layer) keeps the pill and its own sizes.
"""
import unittest

from _paths import ROOT  # noqa: F401
from test_server import chrome
from test_theme_global_1319 import NAME, SIZES, Computed

from clark import page


class Sizes(Computed):
    def test_classic_sizes_at_each_width(self):
        html = page.page_html(branding=page.NO_BRAND, theme=NAME)
        with chrome() as cdp:
            for w in SIZES:
                sid = self.load(cdp, w, "light", html)
                for sel in ("#sg", "#sc", "#cs", "#b1", "#b2", "#b3", "#b4"):
                    self.assertEqual(self.style(cdp, sid, sel, "borderRadius"), "6px", f"{w} {sel}")
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('#md'), '::before').borderRadius", sid), "6px", w)
                for sel in ("#sg button", "#sc button", "#cs button", "#b1"):
                    self.assertEqual(self.style(cdp, sid, sel, "minHeight"), "28px", f"{w} {sel}")
                    self.assertEqual(self.style(cdp, sid, sel, "paddingTop"), "3px", f"{w} {sel}")
                    self.assertEqual(self.style(cdp, sid, sel, "paddingBottom"), "3px", f"{w} {sel}")
                    self.assertEqual(self.style(cdp, sid, sel, "paddingLeft"), "14px", f"{w} {sel}")
                    self.assertEqual(self.style(cdp, sid, sel, "paddingRight"), "14px", f"{w} {sel}")
                self.assertEqual(self.style(cdp, sid, "#md button", "minHeight"), "32px", f"{w} top-bar switch unchanged")
                for sel in (".crumbs", ".ucd-crumb", ".ucf-crumb"):
                    self.assertEqual(self.style(cdp, sid, "#probe " + sel, "fontSize"), "13px", f"{w} {sel}")
                for sel in ("#b2", "#b3", "#b4"):
                    self.assertEqual(self.style(cdp, sid, sel, "minHeight"), "38px", f"{w} {sel}")

    def test_cards_keeps_its_pill_and_sizes(self):
        html = page.page_html(branding=page.NO_BRAND)
        with chrome() as cdp:
            for w in SIZES:
                sid = self.load(cdp, w, "light", html)
                self.assertEqual(self.style(cdp, sid, "#b1", "borderRadius"), "999px", w)
                self.assertEqual(self.style(cdp, sid, "#sg button", "minHeight"), "32px", w)
                self.assertEqual(self.style(cdp, sid, "#b1", "paddingLeft"), "18px", w)


if __name__ == "__main__":
    unittest.main()
