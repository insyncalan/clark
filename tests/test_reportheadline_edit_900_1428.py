"""Row 1428: the Report headline's Edit view at 900 px keeps the health pill beside the Headline and reason boxes (Classic, light and dark),
as the approved mock-up's .erow does, instead of stacking them. Checked at 1400 and 900. Fictional data only.

Run: python3 dev/run_tests.py test_reportheadline_edit_900_1428
"""
import json

from _demo import USER
from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import chrome

from clark import page, theme
import _testpage as testpage
from _real_server import real_server

SIZES = ((1400, "light"), (1400, "dark"), (900, "light"), (900, "dark"))


class EditAt900(Base):
    def setUp(self):
        super().setUp()
        self.s.close()      # the Classic page: the test page with the Classic theme layered
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css), seam=self.seam)
        self.addCleanup(self.s.close)
        body = {"v": 1, "health": "at_risk", "headline": "Fictional plan holds", "sentence": "Fictional reason."}
        with self.store.step("dashboard", USER) as st:
            self.on = st.create("report_sections", {"project": "ABC", "type": "reportheadline", "title": "Fictional on", "sort_order": 990, "body": json.dumps(body)})
            self.off = st.create("report_sections", {"project": "ABC", "type": "reportheadline", "title": "Fictional off", "sort_order": 991,
                                                     "body": json.dumps(dict(body, pill=False))})

    def edit_page(self, cdp, width, theme_name, ref):
        p = self.visit(cdp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.js(f"document.documentElement.dataset.theme = {json.dumps(theme_name)}")
        p.edit()
        p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .tpl-rh-edit-text')", "the Edit view drew")
        return p

    def box(self, p, ref, rest):
        return p.js(f"""(function(){{ var e = document.querySelector('[data-id="{ref}"] {rest}'); if (!e) return null; var r = e.getBoundingClientRect();
          return {{x: r.left, y: r.top, w: r.width, right: r.right}}; }})()""")

    def test_edit_pill_stays_beside_the_text_at_900(self):
        for width, theme_name in SIZES:
            with self.subTest(width=width, theme=theme_name), chrome() as cdp:
                p = self.edit_page(cdp, width, theme_name, self.on)
                pill, text = self.box(p, self.on, ".tpl-rh-edit-pill"), self.box(p, self.on, ".tpl-rh-edit-text")
                self.assertLess(pill["right"], text["x"], f"the pill is left of the text column: {pill} {text}")
                self.assertAlmostEqual(pill["y"], text["y"], delta=2, msg="and on the same row")
                gap = p.js(f"getComputedStyle(document.querySelector('[data-id=\"{self.on}\"] .tpl-rh-edit')).columnGap")
                self.assertEqual(gap, "12px", "mock-up .erow gap 12px")

    def test_edit_text_column_is_wider_than_217px_and_no_sideways_scroll(self):
        for width, theme_name in SIZES:
            with self.subTest(width=width, theme=theme_name), chrome() as cdp:
                p = self.edit_page(cdp, width, theme_name, self.on)
                self.assertGreater(self.box(p, self.on, ".tpl-rh-edit-text")["w"], 217)
                self.assertGreater(self.box(p, self.on, "textarea[aria-label=Headline]")["w"], 217)
                self.assertFalse(p.js("document.documentElement.scrollWidth > window.innerWidth"), "no sideways scroll")

    def test_edit_text_runs_the_full_row_when_the_pill_is_hidden(self):
        for width, theme_name in SIZES:
            with self.subTest(width=width, theme=theme_name), chrome() as cdp:
                p = self.edit_page(cdp, width, theme_name, self.off)
                row, text = self.box(p, self.off, ".tpl-rh-edit"), self.box(p, self.off, ".tpl-rh-edit-text")
                self.assertIsNone(self.box(p, self.off, ".tpl-rh-edit-pill"), "no pill menu while the pill is hidden")
                self.assertAlmostEqual(text["x"], row["x"], delta=1)
                self.assertAlmostEqual(text["right"], row["right"], delta=1, msg="the text runs to the right edge of the row")
