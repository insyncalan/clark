"""Row 1299 AP12: the project tabs with no project, one project and on Backups, in a real browser at 1400 and 900 px. Run: python3 dev/run_tests.py test_settings_tabs_empty_1299

What is asserted (Classic): with no project there is no tab bar, the five per-project pages are not in the menu (and an address that names one opens the first page that is),
and an "Add project" link shows and opens the Projects page; with one project there is one tab, its own, marked; Backups has no tabs (with several projects too: test_settings_tabs_1299b), and the
menu keeps all five per-project pages once there is a project. Chrome is required: these tests fail, never skip, without it.
"""
import unittest

from test_server import chrome
from test_settings_tabs_1299 import Rigged, LIVE, TABS, WIDTHS

PROJECT_PAGES = ("reports", "brand", "people", "claude", "data")
MENU = "[...document.querySelectorAll('.set-nav .set-chip')].map(c => c.textContent.trim())"
LINK = "document.querySelector('.set-add-project')"


class Empty(Rigged):
    def test_no_project_one_project_and_backups(self):
        for w in WIDTHS:
            self.listed = []      # the case with no project
            with self.subTest(case="no project", width=w), chrome() as cdp:
                p = self.page(cdp, hash_="#settings")
                p.width(w)
                p.until("!!document.querySelector('.set-nav .set-chip[aria-current]')", "Settings drew")
                p.until(f"!!{LINK}", "the Add project link shows")
                self.assertEqual(p.js(f"{LINK}.textContent"), "Add project")
                self.assertFalse(p.js("!!document.querySelector('.set-tabs')"), "no tab bar")
                menu = p.js(MENU)
                for name in ("Reports and pages", "Brand and publishing", "People", "ask clark", "Data"):
                    self.assertNotIn(name, menu, f"{name} is hidden with no project")
                for name in ("Profile", "Projects overview", "Backups"):
                    self.assertIn(name, menu)
                p.js("location.hash = '#settings&s=people'")      # an address that names a hidden page opens the first page that is shown
                p.until("!!document.querySelector('.set-nav .set-chip[aria-current]') && !!document.querySelector('.set-cards').children.length", "Settings drew")
                self.assertFalse(p.js("[...document.querySelectorAll('.set-chip[aria-current]')].some(c => c.textContent.trim() === 'People')"), "People is not opened")
                p.js(f"{LINK}.click()")
                p.until("document.querySelector('.set-cards').getAttribute('data-page') === 'projects'", "the link opened the Projects page")
            self.listed = LIVE[:1]      # the case with one project: its one tab on each of the five pages, no Add project link
            with self.subTest(case="one project", width=w), chrome() as cdp:
                p = self.page(cdp)
                for slug in PROJECT_PAGES:
                    self.open_settings(p, w, slug=slug)
                    p.until(f"{TABS}.length === 1", f"{slug} has its one tab")
                    self.assertEqual(p.js(f"{TABS}.map(b => [b.textContent, b.getAttribute('aria-current')])"), [[LIVE[0]["name"], "page"]], slug)
                    self.assertFalse(p.js(f"!!{LINK}"), f"{slug}: a project exists, no Add project link")
                for name in ("Reports and pages", "Brand and publishing", "People", "ask clark", "Data"):
                    self.assertIn(name, p.js(MENU), f"{name} is in the menu with one project")
                self.open_settings(p, w, slug="backups")      # the Backups case: no tabs
                p.until("document.querySelector('.set-cards').getAttribute('data-page') === 'backups'", "Backups drew")
                self.assertFalse(p.js("!!document.querySelector('.set-tabs')"), "Backups has no tabs with one project")
            self.listed = []
            with self.subTest(case="backups, no project", width=w), chrome() as cdp:
                p = self.page(cdp, hash_="#settings&s=backups")
                p.width(w)
                p.until("document.querySelector('.set-cards') && document.querySelector('.set-cards').getAttribute('data-page') === 'backups'", "Backups drew")
                self.assertFalse(p.js("!!document.querySelector('.set-tabs')"), "Backups has no tabs with no project")


if __name__ == "__main__":
    unittest.main()
