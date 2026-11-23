"""Row 1475: in Work items sections the link "Show all items" (left) and "Review all N items" (right) share ONE footer row, and the footers
of two half-width sections are level at any list length (the footer sits at the bottom of its section). Stacked at 900 px each section has
its own single row. A published file has neither link. Classic theme, served page (View), 1400 and 900 px. Fictional data only.
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_wil_footer_one_row_1475.py"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import _testpage as testpage
import test_tpl_workitems as base
from _demo import USER
from _real_server import real_server
from clark import page, publish, theme
from test_report_editor import EMPTY_BRANDING, Pg, tearDownModule  # noqa: F401
from test_server import chrome

NAME = "prototype-2.0"

Q = json.dumps
FOOT = """(ref => { const s = document.querySelector('[data-id="' + ref + '"]'), r = (e) => e && e.getBoundingClientRect(), f = s.querySelector('[data-wil-foot]'),
  a = s.querySelector('[data-wil-all]'), v = s.querySelector('[data-wil-review]'), sr = r(s), cs = getComputedStyle(s), fr = r(f);
  return { foot: fr && [fr.top, fr.height], all: a && r(a).top, allLeft: a && r(a).left, review: v && r(v).top, reviewRight: v && r(v).right, reviewH: v && r(v).height,
    secLeft: sr.left + parseFloat(cs.paddingLeft) + parseFloat(cs.borderLeftWidth), secRight: sr.right - parseFloat(cs.paddingRight) - parseFloat(cs.borderRightWidth),
    footLeft: fr && fr.left, footRight: fr && fr.right }; })"""


class FooterRow(base.PageBase):
    """The served page with the Classic theme layered (as the neighbour's Look does)."""
    add, show = base.InThePage.add, base.InThePage.show      # the helpers only: the neighbour's own tests are not run again here

    def setUp(self):
        super().setUp()
        base.plant(self)
        self.s.close()
        css = theme.css(NAME)
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css), seam=self.seam)
        self.addCleanup(self.s.close)
        self.store.con.execute("UPDATE app_settings SET theme = 'classic' WHERE id = 1")
        for owner, n in (("Ann Demo", 5), ("Bo Demo", 6)):
            for i in range(n):
                self.demo.action(description=f"Fictional step {owner[:3]}{i}", owner=owner, due_date=f"2030-02-0{i + 1}")

    def pair(self, left_max=2, right_max=2, beside=True):
        cols = ["id", "owner", "due"]
        a = self.add({"mode": "all", "columns": cols, "owner": ["Ann Demo"], "max": left_max}, title="Left list")
        b = self.add({"mode": "all", "columns": cols, "owner": ["Bo Demo"], "max": right_max}, title="Right list", after=a, beside=1 if beside else 0)
        return a, b

    def draw(self, cdp, refs, width, dark=False):
        p = self.show(cdp, width, dark)
        for r in refs:
            p.until(f"!!document.querySelector('[data-id=\"{r}\"] [data-wil-review]')", "the footer drew")
        return p

    def foot(self, p, ref):
        return p.js(f"({FOOT})({Q(ref)})")

    def test_show_all_and_review_all_share_one_footer_line_at_half_width_1400_and_900(self):
        a, b = self.pair()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, (a, b), width)
                for ref in (a, b):
                    g = self.foot(p, ref)
                    self.assertIsNotNone(g["all"], "Show all items is drawn")
                    self.assertEqual(g["all"] - g["review"], 0, g)      # an equal-height pair: tops are the same (both buttons are min-height tall)
                    self.assertLessEqual(g["foot"][1], g["reviewH"] + 1, f"the footer is one line high: {g}")

    def test_review_all_is_at_the_right_edge_and_show_all_at_the_left_1400_and_900(self):
        a, b = self.pair()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, (a, b), width)
                for ref in (a, b):
                    g = self.foot(p, ref)
                    self.assertLessEqual(abs(g["reviewRight"] - g["secRight"]), 1, g)
                    self.assertLessEqual(abs(g["allLeft"] - g["secLeft"]), 1, g)

    def test_a_section_without_show_all_keeps_review_all_level_with_its_neighbour_1400_and_900(self):
        a, b = self.pair(left_max=10, right_max=2)      # Ann has 5 rows (no Show all items), Bo has 6 over a max of 2
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, (a, b), width)
                ga, gb = self.foot(p, a), self.foot(p, b)
                self.assertIsNone(ga["all"], ga)
                self.assertIsNotNone(gb["all"], gb)
                self.assertLessEqual(abs(ga["reviewRight"] - ga["secRight"]), 1, ga)
                if width == 1400:
                    self.assertEqual(ga["review"] - gb["review"], 0, (ga, gb))

    def test_footers_of_two_half_width_sections_are_level_with_lists_of_different_length_at_1400(self):
        a, b = self.pair(left_max=10, right_max=10)      # 5 rows beside 6 rows, neither has Show all items
        with chrome() as cdp:
            p = self.draw(cdp, (a, b), 1400)
            ga, gb = self.foot(p, a), self.foot(p, b)
            self.assertEqual(ga["review"] - gb["review"], 0, (ga, gb))
            self.assertEqual(ga["foot"][0] - gb["foot"][0], 0, (ga, gb))

    def test_stacked_sections_each_have_one_footer_row_at_900(self):
        a, b = self.pair()
        with chrome() as cdp:
            p = self.draw(cdp, (a, b), 900)
            ga, gb = self.foot(p, a), self.foot(p, b)
            self.assertGreater(gb["foot"][0], ga["foot"][0] + 50, "the sections are stacked")
            for g in (ga, gb):
                self.assertEqual(g["all"] - g["review"], 0, g)
                self.assertLessEqual(g["foot"][1], g["reviewH"] + 1, g)
                self.assertLessEqual(abs(g["reviewRight"] - g["secRight"]), 1, g)
                self.assertLessEqual(abs(g["allLeft"] - g["secLeft"]), 1, g)

    def test_full_width_one_footer_row_and_tab_order_show_all_then_review_all_light_and_dark(self):
        a = self.add({"mode": "all", "columns": ["id", "owner", "due"], "owner": ["Bo Demo"], "max": 2}, title="Full list")
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.draw(cdp, (a,), width, dark)
                    g = self.foot(p, a)
                    self.assertEqual(g["all"] - g["review"], 0, g)
                    self.assertLessEqual(g["foot"][1], g["reviewH"] + 1, g)
                    order = p.js(f"(() => {{ const s = document.querySelector('[data-id=\"{a}\"]'), t = [...s.querySelectorAll('button, [tabindex=\"0\"], a')].filter(e => e.tabIndex >= 0);"
                                 " const i = t.findIndex(e => e.hasAttribute('data-wil-all')), j = t.findIndex(e => e.hasAttribute('data-wil-review')); return [i, j]; })()")
                    self.assertTrue(0 <= order[0] < order[1], order)

    def test_a_published_file_has_no_footer_links_1400_and_900(self):
        a, b = self.pair()
        out = tempfile.mkdtemp(prefix="clark-1475-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=USER, now=base.TODAY, branding=EMPTY_BRANDING)["path"])
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                p = Pg(self, cdp, sid)
                p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
                p.until(f"!!document.querySelector('[data-id=\"{a}\"] .wil-table, [data-id=\"{a}\"] .wil-lines')", "the list drew")
                self.assertEqual(p.js("document.querySelectorAll('[data-wil-all], [data-wil-review], [data-wil-foot]').length"), 0)


if __name__ == "__main__":
    unittest.main()
