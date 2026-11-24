"""Row 1288, tight menus (Classic only): the rich editor's buttons are 34 high, and every float panel of it (the Text style menu, the more-blocks menu, the
/ list, the selection bubble) has radius 12, padding 4, and rows of 4px 10px at 13.5px (the measured values of the chosen mock-up, ticket comment 19-11 21:37).
The browser part mounts the real editor with the Classic theme layered and reads computed style at 1400 and 900. Cards (no theme) keeps production.

Run: python3 dev/run_tests.py test_rich_menus_tight_1288
"""
import json
import unittest
from unittest import mock

from _paths import ROOT

import _rich_page as rp  # noqa: E402
import build_page  # noqa: E402
from clark import page, theme  # noqa: E402
from test_server import chrome  # noqa: E402,F401  (the runner tells a browser file by this import)

NAME = "prototype-2.0"
RULES = "\n".join((ROOT / "src" / "clark" / "themes" / NAME / f).read_text(encoding="utf-8") for f in ("rules.css", "rules-2.css"))      # the theme's rules in the order the page layers them; row 1288 is in rules-2.css
SHELL = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
EDIT = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "edit.css").read_text(encoding="utf-8")

PANEL = "(e => { const c = getComputedStyle(e); return {r: c.borderTopLeftRadius, p: c.paddingTop + ' ' + c.paddingRight + ' ' + c.paddingBottom + ' ' + c.paddingLeft}; })"
ROW = "(e => { const c = getComputedStyle(e); return {p: c.paddingTop + ' ' + c.paddingRight + ' ' + c.paddingBottom + ' ' + c.paddingLeft, f: c.fontSize}; })"
BTN = "(e => { const c = getComputedStyle(e), r = e.getBoundingClientRect(); return {h: r.height, w: r.width, mw: c.minWidth}; })"
PANEL_WANT = {"r": "12px", "p": "4px 4px 4px 4px"}
ROW_WANT = {"p": "4px 10px 4px 10px", "f": "13.5px"}


def setUpModule():
    css = theme.css(NAME)
    orig = build_page.page_css
    p = mock.patch.object(build_page, "page_css", lambda *a, **k: orig(*a, **k) + "\n" + css)
    p.start()
    unittest.addModuleCleanup(p.stop)


class Static(unittest.TestCase):
    def test_the_rules_are_in_rules_2_css_below_row_1318_and_above_row_1314_and_the_old_32_stays(self):
        i = RULES.index("Row 1288, tight menus")
        self.assertLess(RULES.index("/* Row 1318"), i)
        self.assertLess(i, RULES.index("/* Row 1314"))
        self.assertIn("min-width: 32px; height: 32px", SHELL, "shell.css keeps the old 32")
        self.assertNotIn("1288", SHELL)
        self.assertNotIn("Row 1288, tight", EDIT)

    def test_cards_page_holds_no_row_1288_tight_rule(self):
        rule = ".rt-bar .rt-btn, .rt-bubble .rt-btn, .rt-link .rt-btn { height: 34px; }"
        self.assertNotIn(rule, page.page_html(branding=page.NO_BRAND, theme=None))
        self.assertIn(rule, page.page_html(branding=page.NO_BRAND, theme=NAME))


class Look(unittest.TestCase):
    def read(self, h, sel, fn):
        self.assertTrue(h.until(f"!!document.querySelector({json.dumps(sel)})"), f"{sel} is drawn")
        return h.ev(f"({fn})(document.querySelector({json.dumps(sel)}))")

    def test_buttons_are_34_high_and_the_four_panels_are_radius_12_padding_4_with_rows_4_10_at_13_5(self):
        with rp.Harness(chrome) as h:
            for w in (1400, 900):
                h.resize(w)
                h.mount("<p>Title words</p>")
                b = self.read(h, ".rt-bar .rt-btn[aria-label='Bold']", BTN)
                self.assertEqual((b["h"], b["w"]), (34, 34), f"{w}: Bold button")
                s = self.read(h, ".rt-bar .rt-style", BTN)
                self.assertEqual(s["h"], 34, f"{w}: style button height")
                self.assertGreaterEqual(s["w"], 96, f"{w}: the style button keeps its own width")
                h.ev("document.querySelector('.rt-bar .rt-style').click()")
                self.assertEqual(self.read(h, ".rt-bar [role=menu]", PANEL), PANEL_WANT, f"{w}: style menu panel")
                self.assertEqual(self.read(h, ".rt-bar [role=menu] [role=menuitemradio]", ROW), {"p": "7px 10px 7px 10px", "f": "15px"}, f"{w}: style menu row (AP3: the Style menu keeps the 15px prototype rows)")
                h.key("Escape", 0, "Escape", 27)
                h.ev("document.querySelector('.rt-bar .rt-more') && document.querySelector('.rt-bar .rt-more').click()")
                if h.ev("!!document.querySelector('.rt-bar .rt-more')"):
                    self.assertEqual(self.read(h, ".rt-bar [role=menu]", PANEL), PANEL_WANT, f"{w}: more menu panel")
                    self.assertEqual(self.read(h, ".rt-bar [role=menu] [role=menuitem]", ROW), ROW_WANT, f"{w}: more menu row")
                    h.key("Escape", 0, "Escape", 27)
                h.mount("")
                h.type("/")
                self.assertEqual(self.read(h, ".rt-slash", PANEL), PANEL_WANT, f"{w}: / list panel")
                self.assertEqual(self.read(h, ".rt-slash .rt-opt", ROW), ROW_WANT, f"{w}: / list row")
                h.key("Escape", 0, "Escape", 27)
                h.mount("<p>Some words here</p>")
                h.select_all()
                self.assertEqual(self.read(h, ".rt-bubble", PANEL), PANEL_WANT, f"{w}: bubble panel")
                self.assertEqual(self.read(h, ".rt-bubble .rt-btn", BTN)["h"], 34, f"{w}: bubble button height")
                h.ev("window.unmount(); true")


if __name__ == "__main__":
    unittest.main()
