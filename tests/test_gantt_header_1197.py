"""Row 1197: a measuring page test for the Gantt page's header and toolbar, Classic, 1400 and 900 px.

Run: python3 dev/run_tests.py test_gantt_header_1197
Measures the real page against the real server (the rig of test_gantt_e2e): the Gantt tab is the last tab and the open one;
the table and chart buttons are two equal icon buttons side by side, left of the scale switches;
the one View/Edit control is the pill above the toolbar (Classic has no text button);
the zoom buttons sit left of the filter (Show), then Today, then full screen, all on one row.
Not measured here (not built on main): the gap between header and toolbar, icon sizes. Look in Chrome: not checked.
"""
import time

import _paths  # noqa: F401
from clark import page
from test_publish_route import EMPTY_BRANDING
from test_gantt_e2e import Browser
import test_gantt_e2e as _test_gantt_e2e
from test_server import chrome

BOX = "(e => { const r = document.querySelector(e).getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right), Math.round(r.top), Math.round(r.bottom)]; })"


class HeaderAndToolbar(_test_gantt_e2e.E2E):
    test_the_gantt_from_settings_to_the_published_file = None      # the e2e's own flow is not run again here

    def setUp(self):
        super().setUp()
        self.rig.httpd.page_html = lambda: page.page_html(EMPTY_BRANDING, theme="prototype-2.0")

    def box(self, br, sel):
        return br.js(BOX + f"({sel!r})")

    def test_the_gantt_tab_is_last_and_open_and_the_toolbar_reads_in_order_at_both_widths(self):
        with chrome() as cdp:
            br = Browser(self, cdp, self.rig.httpd.server_port)
            self.settings_and_the_tab(br)
            br.click(".modes [data-mode=edit]")      # Classic: the pill is the one View/Edit control (no text button in the toolbar)
            br.until("document.querySelector('#gantt-page').dataset.mode === 'edit'", "Edit")
            br.click("[data-gp-first]")
            br.until("document.querySelector('[data-g-row]')", "the first line is drawn")
            for kind, n in (("task", 2), ("milestone", 3)):      # three lines, so the chart draws its whole toolbar
                br.click("[data-g-add]" if n == 2 else "[data-g-add='GNT-002']")
                br.click(f"[data-g-addtype={kind}]")
                br.until(f"document.querySelectorAll('[data-g-row]').length === {n}", "the line is drawn")
            br.until("document.querySelector('[data-g-scale]')", "the chart toolbar")
            for width in (1400, 900):
                br.width(width)
                time.sleep(0.4)
                with self.subTest(width=width):
                    tabs = br.js("[].map.call(document.querySelectorAll('.tab[data-view]'), t => [t.dataset.view, t.getAttribute('aria-selected')])")
                    self.assertEqual(tabs[-1], ["gantt", "true"], f"the Gantt tab is last and the open one: {tabs}")
                    self.assertEqual([t for t in tabs if t[1] == "true"], [tabs[-1]], "only the Gantt tab is open")
                    tab = self.box(br, ".tab[data-view=gantt]")
                    self.assertGreater(tab[3] - tab[2], 0, "the tab has a height")
                    self.assertLessEqual(tab[1], width, "the tab is inside the window")
                    bar = self.box(br, "[data-gantt] .gt-bar")
                    self.assertEqual(br.js("document.querySelectorAll('[data-gp-mode]').length"), 0, "Classic has no text View/Edit button in the toolbar")
                    view, edit = self.box(br, ".modes [data-mode=view]"), self.box(br, ".modes [data-mode=edit]")
                    self.assertEqual(view[2], edit[2], "the pill's two buttons are on one line")
                    self.assertLessEqual(min(view[1], edit[1]), max(view[0], edit[0]) + 1, "side by side")
                    self.assertLessEqual(max(view[3], edit[3]), bar[2] + 1, "the pill sits above the toolbar")
                    tbl, cht = self.box(br, "[data-gp-layout=table]"), self.box(br, "[data-gp-layout=chart]")
                    self.assertEqual([tbl[1] - tbl[0], tbl[3] - tbl[2]], [cht[1] - cht[0], cht[3] - cht[2]], "the two layout buttons are the same size")
                    self.assertEqual([tbl[1] - tbl[0], tbl[3] - tbl[2]], [36, 34], "36 wide, 34 high as this PR draws them (main: 36 by 32)")
                    self.assertEqual(tbl[2], cht[2], "on one line")
                    self.assertLessEqual(tbl[1], cht[0] + 8, "side by side")
                    self.assertLess(min(tbl[0], cht[0]), self.box(br, "[data-g-scale]")[0], "left of the scale switches")
                    xs = [self.box(br, s)[0] for s in ("[data-g-zout]", "[data-g-fit]", "[data-g-zin]", "[data-g-show]", "[data-g-today-btn]", "[data-g-expand]")]
                    self.assertEqual(xs, sorted(xs), f"zoom out, fit, zoom in, Show, Today, full screen run left to right: {xs}")
                    self.assertEqual(len(set(xs)), 6, "no two sit on the same spot")
                    self.assertLessEqual(self.box(br, "[data-g-zin]")[1], self.box(br, "[data-g-show]")[0] + 1, "zoom ends where the filter begins")
                    for s in ("[data-g-zout]", "[data-g-show]", "[data-g-today-btn]", "[data-g-expand]"):
                        b = self.box(br, s)
                        self.assertTrue(bar[0] <= b[0] and b[1] <= bar[1] and bar[2] <= b[2] and b[3] <= bar[3], f"{s} is inside the toolbar at {width}")
                        self.assertEqual(b[2] <= self.box(br, "[data-g-fit]")[3] and b[3] >= self.box(br, "[data-g-fit]")[2], True, f"{s} shares the zoom's row")
