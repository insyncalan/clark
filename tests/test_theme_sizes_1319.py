"""Row 1319, Classic theme: segments, switches and text tabs have a 6px corner, segment buttons are 28px tall with padding 3px 14px, crumbs are 13px; primaries and plain buttons stay 8px.

Run: python3 dev/run_tests.py test_theme_sizes_1319
Fails, never skips, without Chrome. Computed styles at 1400 and 900. Cards (no Theme layer) keeps the pill and its own sizes.
"""
import unittest

from _paths import ROOT  # noqa: F401
from test_server import chrome
from test_theme_global_1319 import NAME, SIZES, Computed

from clark import page


class Sizes(Computed):
    def test_classic_sizes_at_each_width_in_light_and_dark(self):
        html = page.page_html(branding=page.NO_BRAND, theme=NAME)
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    sid = self.load(cdp, w, scheme, html)
                    w = f"{scheme} {w}"
                    for sel in ("#sg", "#sc", "#cs"):
                        self.assertEqual(self.style(cdp, sid, sel, "borderRadius"), "6px", f"{w} {sel}")
                    cdp.js("document.getElementById('probe').insertAdjacentHTML('beforeend', '<button class=\"msv-sw\" id=\"sw1\">S</button><button class=\"mv-txt\" id=\"tx1\">T</button><div class=\"seg lsw\" id=\"lw\"><button>L</button></div>')", sid)
                    for sel in ("#sw1", "#tx1"):
                        self.assertEqual(self.style(cdp, sid, sel, "borderRadius"), "6px", f"{w} {sel}")
                    for sel in ("#b1", "#b2", "#b3", "#b4"):
                        self.assertEqual(self.style(cdp, sid, sel, "borderRadius"), "8px", f"{w} {sel} primaries and plain buttons stay 8")
                    self.assertEqual(cdp.js("getComputedStyle(document.querySelector('#md'), '::before').borderRadius", sid), "6px", w)
                    for sel in ("#sg button", "#sc button", "#cs button"):
                        self.assertEqual(self.style(cdp, sid, sel, "minHeight"), "28px", f"{w} {sel}")
                        self.assertEqual(self.style(cdp, sid, sel, "paddingTop"), "3px", f"{w} {sel}")
                        self.assertEqual(self.style(cdp, sid, sel, "paddingBottom"), "3px", f"{w} {sel}")
                        self.assertEqual(self.style(cdp, sid, sel, "paddingLeft"), "14px", f"{w} {sel}")
                        self.assertEqual(self.style(cdp, sid, sel, "paddingRight"), "14px", f"{w} {sel}")
                    self.assertEqual(self.style(cdp, sid, "#lw button", "minHeight"), "32px", f"{w} layout switch keeps its height")
                    self.assertEqual(self.style(cdp, sid, "#lw button", "paddingLeft"), "12px", f"{w} layout switch keeps its padding")
                    self.assertEqual(self.style(cdp, sid, "#md button", "minHeight"), "32px", f"{w} top-bar switch unchanged")
                    for sel in (".crumbs", ".ucd-crumb", ".ucf-crumb"):
                        self.assertEqual(self.style(cdp, sid, "#probe " + sel, "fontSize"), "13px", f"{w} {sel}")
                    for sel in ("#b2", "#b3", "#b4"):
                        self.assertEqual(self.style(cdp, sid, sel, "minHeight"), "38px", f"{w} {sel}")

    def test_crumb_is_13px_at_each_width(self):
        # Row 1319, the crumb line: 13px (prototype index.html:49-51), measured from the rendered page.
        html = page.page_html(branding=page.NO_BRAND, theme=NAME)
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    sid = self.load(cdp, w, scheme, html)
                    for sel in (".crumbs", ".ucd-crumb", ".ucf-crumb"):
                        self.assertEqual(self.style(cdp, sid, "#probe " + sel, "fontSize"), "13px", f"{scheme} {w} {sel}")
                        self.assertEqual(self.style(cdp, sid, "#probe " + sel, "textTransform"), "none", f"{scheme} {w} {sel}")

    def test_mode_switch_pressed_text_is_navy_at_each_width(self):
        # Row 1319, pressed state of the header mode switch (View | Edit): navy text on the chosen half, the other half not navy-on-fill.
        # The fill itself is not pinned here: the ticket says white, the Classic page paints the aqua pill (needs a ruling).
        html = page.page_html(branding=page.NO_BRAND, theme=NAME)
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    sid = self.load(cdp, w, scheme, html)
                    tag = f"{scheme} {w}"
                    self.assertEqual(self.style(cdp, sid, "#md button[aria-pressed=true]", "color"), "rgb(6, 47, 58)", tag)
                    self.assertEqual(self.style(cdp, sid, "#md button[aria-pressed=true]", "backgroundImage"), "none", tag)
                    self.assertNotEqual(self.style(cdp, sid, "#md button[aria-pressed=false]", "color"), "rgb(6, 47, 58)", tag)

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
