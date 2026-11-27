"""Row 1299: the Projects overview in a real browser at 1400 and 900 px, Classic only: the AP15 intro line.
Run: python3 dev/run_tests.py test_settings_overview_1299
Chrome is required: these tests fail, never skip, without it."""
import unittest

from test_server import chrome
from test_projects_overview_ui_1299 import Service, ROWS, TWO, Base, Rig, theme, page, testpage, calm, address

WIDTHS = (1400, 900)


class Intro(Base):
    def setUp(self):
        css = theme.css("prototype-2.0")
        self.rig = Rig(self, saved=self.saved, page_html=lambda: page.layer_theme(testpage.html(), css))
        self.rig.httpd.projects = lambda archived=False: TWO
        self.rig.httpd.projects_overview = Service(ROWS)

    def open_settings(self, p, w, mode="light", slug="projects"):
        p.width(w)
        calm(p, mode)
        p.js(f"location.hash = '{address(slug)}'")
        p.until("!!document.querySelector('.set-nav .set-chip[aria-current]') && !!document.querySelector('.set-cards').children.length", "Settings drew")

    def test_intro_line_without_tick_rows_sentence(self):
        """AP15: the intro line is exactly the ruled sentence at 1400 and 900 (equality, so an appended sentence fails), and no "Tick rows" text is on the page."""
        want = "Every project at a glance. Click a value to open that setting for the project. Grey is the default, amber is an override or something to fix."
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w)
                p.until("!!document.querySelector('#projects-overview .ov-table')", "the overview drew")
                self.assertEqual(p.js("document.querySelector('#projects-overview > p.muted').textContent.trim()"), want)
                self.assertNotIn("Tick rows", p.js("document.querySelector('#projects-overview').textContent"))



if __name__ == "__main__":
    unittest.main()
