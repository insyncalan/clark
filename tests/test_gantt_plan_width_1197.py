"""Row 1197: on the Gantt page the plan (the toolbar and the chart or the table) is as wide as the page band, as the Dashboard's tiles are (row 1152).

Run: python3 dev/run_tests.py test_gantt_plan_width_1197
The rule lives in the Classic theme (themes/prototype-2.0/rules.css), not in shell.css, so Cards is unchanged.
The real page against the real server (the rig of test_gantt_e2e), Comfortable spacing, 1400 and 900 px, chart and table, View and Edit.
"""
import time
import unittest

import _paths  # noqa: F401
from clark import page
from test_publish_route import EMPTY_BRANDING
from test_gantt_e2e import Browser, E2E
from test_server import chrome

EDGES = "(r => [Math.round(r.left), Math.round(r.right)])"


class PlanWidth(E2E):
    test_the_gantt_from_settings_to_the_published_file = None      # the e2e's own flow is not run again here
    theme = "prototype-2.0"      # Classic: the rule lives in the Classic theme; the Cards test sets None

    def setUp(self):
        super().setUp()
        theme = self.theme if "cards" not in self._testMethodName else None
        self.rig.httpd.page_html = lambda: page.page_html(EMPTY_BRANDING, theme=theme)

    def test_the_plan_runs_the_width_of_the_page_band(self):
        with chrome() as cdp:
            br = Browser(self, cdp, self.rig.httpd.server_port)
            self.settings_and_the_tab(br)
            for width in (1400, 900):
                br.width(width)
                time.sleep(0.4)
                for layout in ("chart", "table"):
                    if br.js("document.querySelector('#gantt-page').dataset.gpShown") != layout:
                        br.click(f"[data-gp-layout={layout}]")      # the toolbar's own button for the other layout
                    br.until(f"document.querySelector('#gantt-page').dataset.gpShown === '{layout}'", layout)
                    for edit in (False, True):
                        with self.subTest(width=width, layout=layout, edit=edit):
                            want = "edit" if edit else "view"
                            if br.js("document.querySelector('#gantt-page').dataset.mode") != want:
                                br.click(f".modes [data-mode={want}]" if self.theme and "cards" not in self._testMethodName else f"[data-gp-mode={want}]")      # Classic: the pill; Cards: the text button, which names the mode it goes to
                            br.until(f"document.querySelector('#gantt-page').dataset.mode === '{want}'", want)
                            band = br.js(EDGES + "(document.querySelector('#gantt-page').getBoundingClientRect())")
                            plan = br.js(EDGES + "(document.querySelector('[data-gp-plan]').getBoundingClientRect())")
                            self.assertEqual(plan, band, "the plan's edges are the page band's edges")

    def test_the_plan_is_flush_only_above_900_and_in_comfortable(self):
        """The breakpoint and the density are the rule's: 901 and 1400 comfortable are flush; 900 comfortable and compact (901, 1400) keep the frame's room."""
        with chrome() as cdp:
            br = Browser(self, cdp, self.rig.httpd.server_port)
            self.settings_and_the_tab(br)
            for density, width, flush in (("comfortable", 901, True), ("comfortable", 1400, True), ("comfortable", 900, False),
                                          ("compact", 901, False), ("compact", 1400, False)):
                with self.subTest(density=density, width=width):
                    br.js(f"document.documentElement.dataset.density = '{density}'")
                    br.width(width)
                    time.sleep(0.4)
                    band = br.js(EDGES + "(document.querySelector('#gantt-page').getBoundingClientRect())")
                    plan = br.js(EDGES + "(document.querySelector('[data-gp-plan]').getBoundingClientRect())")
                    if flush:
                        self.assertEqual(plan, band, "flush with the band")
                    else:
                        self.assertEqual(plan[0] - band[0], band[1] - plan[1], "the sides are even")
                        self.assertGreaterEqual(plan[0], band[0], "never wider than the band")
                    self.assertEqual(br.js("getComputedStyle(document.querySelector('[data-gp-plan]')).marginLeft.charAt(0) === '-'"), flush, f"negative side margin only when flush: {plan} {band}")

    def test_cards_keeps_the_plan_inside_the_frame(self):
        """The rule is Classic's (rules.css): on the Cards page (no theme), .gp-plan has no negative side margin at 1400 or 900, comfortable."""
        with chrome() as cdp:
            br = Browser(self, cdp, self.rig.httpd.server_port)
            self.settings_and_the_tab(br)
            br.js("document.documentElement.dataset.density = 'comfortable'")
            for width in (1400, 900):
                with self.subTest(width=width):
                    br.width(width)
                    time.sleep(0.4)
                    self.assertEqual(br.js("document.getElementById('theme')"), None, "no theme: Cards")
                    self.assertEqual(br.js("(m => [m.marginLeft, m.marginRight])(getComputedStyle(document.querySelector('[data-gp-plan]')))"), ["0px", "0px"], "Cards: no negative side margin")

    def test_an_empty_chart_keeps_the_table_and_chart_buttons(self):
        with chrome() as cdp:
            br = Browser(self, cdp, self.rig.httpd.server_port)
            self.settings_and_the_tab(br)
            br.until("document.querySelector('#gantt-page').dataset.gpShown === 'chart'", "the chart is the layout")
            self.assertEqual(br.text("[data-g-none]"), "No lines to show.")
            for layout in ("table", "chart"):
                self.assertEqual(br.js(f"document.querySelectorAll('[data-gantt] [data-gp-layout={layout}]').length"), 1, f"the {layout} button is in the empty chart's toolbar")
            br.click("[data-gp-layout=table]")
            br.until("document.querySelector('#gantt-page').dataset.gpShown === 'table'", "table switches the layout")


del E2E
if __name__ == "__main__":
    unittest.main()
