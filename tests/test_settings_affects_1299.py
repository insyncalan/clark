"""Row 1299 AP9: the "Affects:" line on every Settings page, in a real browser at 1400 and 900 px. Run: python3 dev/run_tests.py test_settings_affects_1299

What is asserted (Classic): a Project settings page says "Affects: <project code>" (the code of the chosen tab, not the top bar's project), an All projects page (Projects overview and
Backups) says "Affects: All projects", a You page says "Affects: You", a Help and about page says nothing; the line is the first thing in the page and is drawn once; with
the Cards look no page has it. Chrome is required: these tests fail, never skip, without it.
"""
import unittest

from test_server import chrome
from test_settings_tabs_1299 import Rigged, LIVE, TABS, WIDTHS

WANT = {"profile": "Affects: You", "appearance": "Affects: You", "projects": "Affects: All projects", "backups": "Affects: All projects",
        "reports": "Affects: PUB", "brand": "Affects: PUB", "people": "Affects: PUB", "claude": "Affects: PUB", "data": "Affects: PUB", "version": None, "logs": None}
LINE = "[...document.querySelectorAll('.set-affects')].map(e => e.textContent.trim())"


class Affects(Rigged):
    def test_affects_label_on_each_page(self):
        for w in WIDTHS:
            with chrome() as cdp:
                p = self.page(cdp)
                for slug, want in WANT.items():
                    with self.subTest(width=w, page=slug):
                        self.open_settings(p, w, slug=slug)
                        p.until(f"document.querySelector('.set-cards').getAttribute('data-page') === {slug!r}", f"{slug} drew")
                        self.assertEqual(p.js(LINE), [want] if want else [])
                        if want:
                            self.assertEqual(p.js("document.querySelector('.set-cards').firstElementChild.className.includes('set-affects')"), True, "the first thing on the page")
                            self.assertTrue(p.js("(() => { const r = document.querySelector('.set-affects').getBoundingClientRect(); return r.width > 0 && r.right <= window.innerWidth; })()"), "inside the window")

    def test_a_project_page_names_the_chosen_tab_not_the_top_bar(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400, slug="reports")
            p.until(f"{TABS}.length === {len(LIVE)}", "the tabs drew")
            p.js(f"{TABS}[1].click()")
            p.until(f"document.querySelector('.set-affects').textContent.trim() === 'Affects: {LIVE[1]['code']}'", "the line follows the tab")


if __name__ == "__main__":
    unittest.main()
