"""Row 1197: on the Gantt page the plan (the toolbar and the chart or the table) is as wide as the page band, as the Dashboard's tiles are (row 1152).

Run: python3 dev/run_tests.py test_gantt_plan_width_1197
The real page against the real server (the rig of test_gantt_e2e), Comfortable spacing, 1400 and 900 px, chart and table, View and Edit.
"""
import time
import unittest

import _paths  # noqa: F401
from test_gantt_e2e import Browser, E2E
from test_server import chrome

EDGES = "(r => [Math.round(r.left), Math.round(r.right)])"


class PlanWidth(E2E):
    test_the_gantt_from_settings_to_the_published_file = None      # the e2e's own flow is not run again here

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
                                br.click(f"[data-gp-mode={want}]")      # the pill's button names the mode it goes to
                            br.until(f"document.querySelector('#gantt-page').dataset.mode === '{want}'", want)
                            band = br.js(EDGES + "(document.querySelector('#gantt-page').getBoundingClientRect())")
                            plan = br.js(EDGES + "(document.querySelector('[data-gp-plan]').getBoundingClientRect())")
                            self.assertEqual(plan, band, "the plan's edges are the page band's edges")


del E2E
if __name__ == "__main__":
    unittest.main()
