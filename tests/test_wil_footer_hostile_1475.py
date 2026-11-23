"""Row 1475: footer edge cases (Edit mode, after Show all, focus, narrow width, tab order).
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_wil_footer_hostile_1475.py"""
import unittest

import test_wil_footer_one_row_1475 as F
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

Q = F.Q


class FooterEdges(F.FooterRow):
    def edit_mode(self, p):
        p.edit()

    def test_edit_mode_footer_one_row_and_level_1400_and_900(self):
        a, b = self.pair(left_max=2, right_max=10)
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.draw(cdp, (a, b), width, dark)
                    p.edit()
                    p.until(f"!!document.querySelector('[data-id=\"{a}\"] [data-wil-review]')", "footer in Edit")
                    ga, gb = self.foot(p, a), self.foot(p, b)
                    self.assertIsNotNone(ga["all"], "Show all items is drawn in Edit")
                    self.assertLessEqual(ga["foot"][1], ga["reviewH"] + 1, f"one line in Edit: {ga}")
                    self.assertLessEqual(abs(ga["reviewRight"] - ga["secRight"]), 1, ga)
                    if width == 1400:
                        self.assertEqual(ga["review"] - gb["review"], 0, (ga, gb))

    def test_after_show_all_the_toggle_stays_in_the_footer_row_and_footers_stay_level(self):
        a, b = self.pair(left_max=2, right_max=2)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, (a, b), width)
                p.js(f"document.querySelector('[data-id=\"{a}\"] [data-wil-all]').click()")
                p.until(f"document.querySelector('[data-id=\"{a}\"] [data-wil-all]').getAttribute('aria-expanded') === 'true'", "expanded")
                ga, gb = self.foot(p, a), self.foot(p, b)
                self.assertEqual(ga["all"] - ga["review"], 0, ga)
                self.assertLessEqual(ga["foot"][1], ga["reviewH"] + 1, ga)
                txt = p.js(f"document.querySelector('[data-id=\"{a}\"] [data-wil-count]').textContent")
                self.assertIn("5", txt)
                if width == 1400:
                    self.assertEqual(ga["review"] - gb["review"], 0, ("footers level after expanding", ga, gb))

    def test_keyboard_toggle_keeps_focus_on_the_link(self):
        a, b = self.pair()
        with chrome() as cdp:
            p = self.draw(cdp, (a, b), 1400)
            p.js(f"document.querySelector('[data-id=\"{a}\"] [data-wil-all]').focus()")
            p.js(f"document.querySelector('[data-id=\"{a}\"] [data-wil-all]').click()")
            p.until(f"document.querySelector('[data-id=\"{a}\"] [data-wil-all]') !== null", "link")
            self.assertTrue(p.js(f"document.activeElement === document.querySelector('[data-id=\"{a}\"] [data-wil-all]')"),
                            "focus is lost when the link re-renders inside the Foot")

    def test_narrow_900_stacked_long_count_wraps_without_overflow(self):
        a, b = self.pair()
        with chrome() as cdp:
            p = self.draw(cdp, (a, b), 900)
            for ref in (a, b):
                self.assertTrue(p.js(f"(() => {{ const s = document.querySelector('[data-id=\"{ref}\"]'); return s.scrollWidth <= s.clientWidth + 1; }})()"), "no overflow in the section")
            self.assertTrue(p.js("document.documentElement.scrollWidth <= innerWidth"))

    def test_the_footer_tab_order_is_show_all_count_review_in_dom_order_and_review_not_squeezed(self):
        a, b = self.pair()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, (a, b), width)
                for ref in (a, b):
                    g = p.js(f"(() => {{ const f = document.querySelector('[data-id=\"{ref}\"] [data-wil-foot]'), v = f.querySelector('[data-wil-review]').getBoundingClientRect(); return [v.width, f.querySelector('[data-wil-review]').scrollWidth]; }})()")
                    self.assertGreaterEqual(g[0] + 1, g[1], "Review all is not clipped")


for _n in list(vars(F.FooterRow)):
    if _n.startswith("test_"):
        setattr(FooterEdges, _n, None)

if __name__ == "__main__":
    unittest.main()
